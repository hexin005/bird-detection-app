import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.detector import AlarmGate
from backend.main import create_app
from backend.store import Conflict, Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'), 'tester', 'test-password', 'test-secret', worker_enabled=False)
        self.store = Store(self.settings)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def alarm(self, now=None):
        return self.store.alarm('task-1', '八哥', 2, .9, 'test.jpg', 1.5, 30, 20, now)[0]

    def test_complete_links_alarm_and_persists(self):
        aid = self.alarm()
        c = self.store.start_command('request-001', aid, 3, 1)
        self.assertEqual(c['status'], 'pending')
        self.store.tick(100)
        self.store.tick(102)
        self.assertEqual(self.store.snapshot()['commands'][0]['status'], 'running')
        self.store.tick(103)
        self.assertEqual(self.store.snapshot()['alarms'][0]['status'], 'handled')
        self.store.close()
        self.store = Store(self.settings)
        self.assertEqual(self.store.snapshot()['commands'][0]['status'], 'completed')

    def test_idempotency_and_concurrent_requests(self):
        aid = self.alarm()
        def start(_):
            return self.store.start_command('same-request', aid, 3, 1)['id']
        with ThreadPoolExecutor(4) as pool:
            ids = list(pool.map(start, range(8)))
        self.assertEqual(len(set(ids)), 1)
        with self.assertRaises(Conflict):
            self.store.start_command('same-request', aid, 5, 1)
        with self.assertRaises(Conflict):
            self.store.start_command('other-request', None, 3, 1)

    def test_offline_does_not_queue_or_replay(self):
        self.store.configure({'scenario': 'offline'})
        with self.assertRaises(Conflict):
            self.store.start_command('request-001', None, 3, 1)
        self.store.configure({'scenario': 'normal'})
        self.store.tick()
        self.assertEqual(self.store.snapshot()['commands'], [])

    def test_timeout_and_stop_restore_alarm(self):
        aid = self.alarm()
        self.store.configure({'scenario': 'timeout'})
        self.store.start_command('timeout-001', aid, 3, 1)
        self.store.tick(10); self.store.tick(13)
        self.assertEqual(self.store.snapshot()['commands'][0]['status'], 'failed')
        self.assertEqual(self.store.snapshot()['alarms'][0]['status'], 'new')
        c = self.store.start_command('stop-request', aid, 3, 1)
        self.store.stop_command(c['id']); self.store.tick(999)
        self.assertEqual(self.store.snapshot()['commands'][0]['status'], 'cancelled')
        self.assertEqual(self.store.snapshot()['alarms'][0]['status'], 'new')

    def test_restart_is_unknown_and_never_success(self):
        aid = self.alarm()
        self.store.start_command('request-001', aid, 3, 1)
        self.store.tick()
        self.store.recover()
        self.store.tick(time.time()+100)
        self.assertEqual(self.store.snapshot()['commands'][0]['status'], 'unknown')
        self.assertEqual(self.store.snapshot()['alarms'][0]['status'], 'new')

    def test_alarm_merge_preserves_original_evidence(self):
        first = self.alarm(100)
        second, created = self.store.alarm('task-1', '八哥', 5, .99, 'later.jpg', 2, 40, 20, 110)
        self.assertEqual(first, second); self.assertFalse(created)
        row = self.store.snapshot()['alarms'][0]
        self.assertEqual((row['count'], row['snapshot'], row['hits']), (2, 'test.jpg', 2))
        self.assertNotEqual(first, self.alarm(135))

    def test_ignore_and_config_validation_during_execution(self):
        aid = self.alarm()
        self.store.ignore(aid)
        with self.assertRaises(Conflict):
            self.store.start_command('request-001', aid, 3, 1)
        self.store.start_command('request-002', None, 3, 1)
        with self.assertRaises(Conflict):
            self.store.configure({'scenario': 'offline'})

    def test_continuous_detection_resets_after_absence(self):
        gate = AlarmGate()
        detections = [{'species':'八哥'}, {'species':'八哥'}]
        self.assertEqual(gate.update(detections, 2), {})
        self.assertEqual(len(gate.update(detections, 2)['八哥']), 2)
        self.assertEqual(gate.update([], 2), {})
        self.assertEqual(gate.update(detections, 2), {})


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'), 'tester', 'test-password', 'test-secret', worker_enabled=False)
        self.app = create_app(settings)
        self.client = TestClient(self.app).__enter__()
        result = self.client.post('/api/login', json={'username':'tester', 'password':'test-password'})
        self.token = result.json()['token']
        self.headers = {'Authorization': 'Bearer ' + self.token}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def test_auth_media_and_logout(self):
        self.assertEqual(self.client.get('/api/state').status_code, 401)
        self.assertEqual(self.client.post('/api/login', json={'username':'tester','password':'bad'}).status_code, 401)
        ticket = self.client.get('/api/state', headers=self.headers).json()['media_ticket']
        self.assertEqual(self.client.get('/api/frame/x.jpg').status_code, 401)
        self.assertEqual(self.client.get('/api/frame/x.jpg?ticket='+ticket).status_code, 404)
        self.client.post('/api/logout', headers=self.headers)
        self.assertEqual(self.client.get('/api/state', headers=self.headers).status_code, 401)
        self.assertEqual(self.client.get('/api/frame/x.jpg?ticket='+ticket).status_code, 401)

    def test_missing_source_and_invalid_inputs(self):
        self.assertEqual(self.client.post('/api/monitor/start', headers=self.headers).status_code, 409)
        self.assertEqual(self.client.post('/api/commands', json={'duration':100, 'request_id':'abcdefgh'}, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.get('/api/history?kind=users', headers=self.headers).status_code, 422)
        self.assertEqual(self.client.put('/api/settings', json={'scenario':'normal','confidence':5,'consecutive':2,'cooldown':20}, headers=self.headers).status_code, 422)

    def test_websocket_auth_and_state(self):
        with self.client.websocket_connect('/api/ws') as ws:
            ws.send_json({'token':self.token})
            data = ws.receive_json()
            self.assertEqual(data['counts']['pending'], 0)
            self.assertTrue(data['simulated_device'])

    def test_api_command_lifecycle_and_history(self):
        aid, _ = self.app.state.store.alarm('T1','树麻雀',2,.9,'a.jpg',1,20,20)
        payload = {'request_id':'request-001','duration':3,'alarm_id':aid}
        c = self.client.post('/api/commands', json=payload, headers=self.headers).json()
        self.app.state.store.tick(100)
        self.assertEqual(self.client.get('/api/state', headers=self.headers).json()['alarms'][0]['status'], 'processing')
        self.client.post('/api/commands/'+c['id']+'/stop', headers=self.headers)
        state = self.client.get('/api/state', headers=self.headers).json()
        self.assertEqual(state['alarms'][0]['status'], 'new')
        self.assertEqual(state['commands'][0]['status'], 'cancelled')
        cursor = state['events'][0]['id']
        older = self.client.get('/api/history?kind=events&before='+str(cursor), headers=self.headers).json()['items']
        self.assertTrue(all(e['id'] < cursor for e in older))


if __name__ == '__main__':
    unittest.main()
