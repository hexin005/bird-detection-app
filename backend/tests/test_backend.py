import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.detector import AlarmGate
from backend.main import create_app
from backend.security import digest
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

    def test_command_records_selected_mode_and_automatic_source(self):
        c = self.store.start_command('automatic-001', None, 3, 1, 'infrared', True)
        self.assertEqual(c['mode'], 'infrared')
        self.assertEqual(c['automatic'], 1)
        event = self.store.rows("SELECT * FROM events WHERE ref_id=?", (c['id'],))[0]
        self.assertIn('自动策略触发', event['message'])
        with self.assertRaises(Conflict):
            self.store.start_command('automatic-001', None, 3, 1, 'acoustic', True)

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

    def test_app_start_recovers_orphaned_monitor_and_stop_clears_stale_state(self):
        self.store.task('old-monitor', 'starting')
        self.store.close()
        app = create_app(self.settings)
        self.assertEqual(app.state.monitor.snapshot()['status'], 'interrupted')
        self.assertEqual(app.state.store.rows('SELECT status FROM tasks WHERE id=?', ('old-monitor',))[0]['status'], 'interrupted')
        app.state.store.task('orphan-monitor', 'starting')
        app.state.monitor.current.update(task_id='orphan-monitor', status='starting')
        class ActiveThread:
            def is_alive(self):
                return True
        app.state.monitor.thread = ActiveThread()
        self.assertEqual(app.state.monitor.stop()['status'], 'stopping')
        self.assertTrue(app.state.monitor.stop_event.is_set())
        app.state.monitor.thread = None
        self.assertEqual(app.state.monitor.stop()['status'], 'stopped')
        self.assertEqual(app.state.store.rows('SELECT status FROM tasks WHERE id=?', ('orphan-monitor',))[0]['status'], 'stopped')
        app.state.store.close()
        self.store = Store(self.settings)

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

    def test_username_endpoint_preserves_email_login_and_reports_duplicate(self):
        changed = self.client.put('/api/me/username', json={'username': '果园_One'}, headers=self.headers)
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(self.client.get('/api/me', headers=self.headers).json()['username'], '果园_One')
        self.assertEqual(self.client.post('/api/login', json={'username': '果园_one', 'password': 'test-password'}).status_code, 200)
        self.assertEqual(self.client.put('/api/me/username', json={'username': 'bad name'}, headers=self.headers).status_code, 422)
        self.app.state.store.create_user('another@example.com', 'password123')
        self.app.state.store.set_username(2, 'Second_1')
        duplicate = self.client.put('/api/me/username', json={'username': 'second_1'}, headers=self.headers)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()['detail'], '当前名称重复')

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

    def test_api_accepts_automatic_infrared_command(self):
        response = self.client.post('/api/commands', json={
            'request_id': 'automatic-001', 'duration': 3, 'mode': 'infrared', 'automatic': True,
        }, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mode'], 'infrared')
        self.assertEqual(response.json()['automatic'], 1)


def tiny_png(width=8, height=8):
    ok, buffer = cv2.imencode('.png', np.zeros((height, width, 3), dtype=np.uint8))
    assert ok
    return buffer.tobytes()


class UserStoreTests(unittest.TestCase):
    """users 迁移(全新库 / 旧库重开)与账号存储方法。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'), 'tester', 'test-password', 'test-secret', worker_enabled=False)
        self.store = Store(self.settings)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_fresh_db_seeds_and_reopen_migrates_again(self):
        columns = {r['name'] for r in self.store.rows('PRAGMA table_info(users)')}
        self.assertTrue({'email', 'display_name', 'avatar_path'} <= columns)
        seed = self.store.rows('SELECT * FROM users WHERE id=1')[0]
        self.assertEqual(seed['username'], 'tester')
        self.assertIsNone(seed['email'])
        self.store.close()
        self.store = Store(self.settings)  # 旧库重复迁移不得报错
        self.assertEqual(self.store.rows('SELECT COUNT(*) c FROM users')[0]['c'], 1)

    def test_username_is_independent_of_email_and_unique(self):
        first = self.store.create_user('Zhou123@Example.COM', 'password123')
        self.assertEqual(first['email'], 'zhou123@example.com')
        self.assertTrue(first['username'].startswith('user_'))
        self.assertNotIn('zhou123', first['username'])
        with self.assertRaises(Conflict):
            self.store.create_user('zhou123@example.com', 'password123')
        second = self.store.create_user('wang@other.com', 'password123')
        self.assertNotEqual(first['username'], second['username'])
        self.assertEqual(self.store.set_username(first['id'], '果园_Ab2'), '果园_Ab2')
        self.assertIsNotNone(self.store.login('果园_ab2', 'password123'))
        self.assertIsNotNone(self.store.login('zhou123@example.com', 'password123'))
        with self.assertRaisesRegex(Conflict, '当前名称重复'):
            self.store.set_username(second['id'], '果园_aB2')
        for invalid in ('a', 'x' * 21, 'has space', 'bad@name', 'emoji😀'):
            with self.assertRaises(ValueError):
                self.store.set_username(first['id'], invalid)

    def test_theme_isolated_per_user(self):
        self.store.set_user_theme(1, 'pixel')
        self.assertEqual(self.store.get_profile(1)['theme'], 'pixel')
        other = self.store.create_user('other@x.com', 'password123')
        self.assertEqual(other['theme'], 'b1bit')

    def test_set_password_revokes_sessions(self):
        token = self.store.login('tester', 'test-password')
        self.store.set_password(1, 'x$y')
        self.assertIsNone(self.store.session(digest(token)))


class AuthApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'), 'tester', 'test-password', 'test-secret', worker_enabled=False)
        self.app = create_app(settings)
        self.client = TestClient(self.app).__enter__()
        result = self.client.post('/api/login', json={'username': 'tester', 'password': 'test-password'})
        self.token = result.json()['token']
        self.headers = {'Authorization': 'Bearer ' + self.token}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def _clear_rate(self):
        verification = self.app.state.verification
        verification.codes.clear()
        verification.sent_log.clear()

    def _send(self, email, purpose):
        return self.client.post('/api/auth/send-code', json={'email': email, 'purpose': purpose})

    def test_register_with_demo_code_and_email_login(self):
        response = self._send('New@Example.com', 'register')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['demo'])
        self.assertRegex(body['demo_code'], r'^\d{6}$')
        wrong = self.client.post('/api/auth/register', json={'email': 'new@example.com', 'code': '000000', 'password': 'password123'})
        self.assertEqual(wrong.status_code, 400)
        ok = self.client.post('/api/auth/register', json={'email': 'new@example.com', 'code': body['demo_code'], 'password': 'password123'})
        self.assertEqual(ok.status_code, 200)
        token = ok.json()['token']
        me = self.client.get('/api/me', headers={'Authorization': 'Bearer ' + token}).json()
        self.assertEqual(me['email'], 'new@example.com')
        self.assertEqual(me['display_name'], '果园用户')
        self.assertEqual(me['theme'], 'b1bit')
        via_email = self.client.post('/api/login', json={'username': 'new@example.com', 'password': 'password123'})
        self.assertEqual(via_email.status_code, 200)
        duplicate = self.client.post('/api/auth/register', json={'email': 'NEW@example.com', 'code': '123456', 'password': 'password123'})
        self.assertEqual(duplicate.status_code, 409)

    def test_code_lifecycle_purpose_attempts_and_rate_limit(self):
        # 用途隔离:注册码不能用于重置
        sent = self._send('life@x.com', 'register').json()
        misuse = self.client.post('/api/auth/reset', json={'email': 'life@x.com', 'code': sent['demo_code'], 'password': 'password123'})
        self.assertEqual(misuse.status_code, 400)
        # 5 次错误后作废,正确码也失效
        for _ in range(5):
            self.assertEqual(self.client.post('/api/auth/register', json={'email': 'life@x.com', 'code': '000000', 'password': 'password123'}).status_code, 400)
        self.assertEqual(self.client.post('/api/auth/register', json={'email': 'life@x.com', 'code': sent['demo_code'], 'password': 'password123'}).status_code, 400)
        # 同邮箱 60s 频控
        self.assertEqual(self._send('rate@x.com', 'register').status_code, 200)
        self.assertEqual(self._send('rate@x.com', 'register').status_code, 429)
        # 全来源 10 条/分钟
        self._clear_rate()
        for index in range(10):
            self.assertEqual(self._send(f'g{index}@x.com', 'register').status_code, 200)
        self.assertEqual(self._send('overflow@x.com', 'register').status_code, 429)

    def test_reset_revokes_token_ticket_and_websocket(self):
        registered = self._send('victim@x.com', 'register').json()
        self.client.post('/api/auth/register', json={'email': 'victim@x.com', 'code': registered['demo_code'], 'password': 'password123'})
        old_token = self.client.post('/api/login', json={'username': 'victim@x.com', 'password': 'password123'}).json()['token']
        old_headers = {'Authorization': 'Bearer ' + old_token}
        ticket = self.client.get('/api/state', headers=old_headers).json()['media_ticket']
        self._clear_rate()
        reset_code = self._send('victim@x.com', 'reset').json()['demo_code']
        self.assertEqual(self.client.post('/api/auth/reset', json={'email': 'victim@x.com', 'code': reset_code, 'password': 'newpassword9'}).status_code, 200)
        self.assertEqual(self.client.get('/api/state', headers=old_headers).status_code, 401)
        self.assertEqual(self.client.get('/api/avatars/none.jpg?ticket=' + ticket).status_code, 401)
        with self.client.websocket_connect('/api/ws') as ws:
            ws.send_json({'token': old_token})
            with self.assertRaises(WebSocketDisconnect):
                ws.receive_json()
        self.assertEqual(self.client.post('/api/login', json={'username': 'victim@x.com', 'password': 'newpassword9'}).status_code, 200)

    def test_change_password_validates_old_and_revokes(self):
        self.assertEqual(self.client.post('/api/password/change', json={'old_password': 'bad', 'new_password': 'newpassword9'}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/password/change', json={'old_password': 'test-password', 'new_password': 'newpassword9'}, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/api/state', headers=self.headers).status_code, 401)
        self.assertEqual(self.client.post('/api/login', json={'username': 'tester', 'password': 'newpassword9'}).status_code, 200)

    def test_send_code_validation_and_reset_unknown_email(self):
        self.assertEqual(self._send('not-an-email', 'register').status_code, 422)
        self.assertEqual(self._send('ghost@x.com', 'reset').status_code, 404)
        self.assertEqual(self._send('ghost@x.com', 'register').status_code, 200)  # 注册允许新邮箱

    def test_theme_preferences_isolated(self):
        self.assertEqual(self.client.put('/api/me/preferences', json={'theme': 'tower'}, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/api/me', headers=self.headers).json()['theme'], 'tower')
        self.assertEqual(self.client.put('/api/me/preferences', json={'theme': 'dark'}, headers=self.headers).status_code, 422)
        registered = self._send('second@x.com', 'register').json()
        second = self.client.post('/api/auth/register', json={'email': 'second@x.com', 'code': registered['demo_code'], 'password': 'password123'}).json()
        me_second = self.client.get('/api/me', headers={'Authorization': 'Bearer ' + second['token']}).json()
        self.assertEqual(me_second['theme'], 'b1bit')

    def test_display_name_update(self):
        response = self.client.put('/api/me', json={'display_name': '果园老周'}, headers=self.headers)
        self.assertEqual(response.json()['display_name'], '果园老周')
        self.assertEqual(self.client.get('/api/me', headers=self.headers).json()['display_name'], '果园老周')


class SmtpFailTests(unittest.TestCase):
    """配置了 SMTP 但发送失败 → 502,绝不回退 demo_code。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'), 'tester', 'test-password', 'test-secret',
                            worker_enabled=False, smtp_host='127.0.0.1', smtp_port=1, email_demo=False)
        self.app = create_app(settings)
        self.client = TestClient(self.app).__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def test_send_code_fails_closed(self):
        response = self.client.post('/api/auth/send-code', json={'email': 'a@b.com', 'purpose': 'register'})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('demo_code', response.json())


class AvatarApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'), 'tester', 'test-password', 'test-secret', worker_enabled=False)
        self.app = create_app(settings)
        self.client = TestClient(self.app).__enter__()
        token = self.client.post('/api/login', json={'username': 'tester', 'password': 'test-password'}).json()['token']
        self.headers = {'Authorization': 'Bearer ' + token}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def _upload(self, data):
        return self.client.post('/api/avatar', content=data, headers={**self.headers, 'Content-Type': 'application/octet-stream'})

    def test_upload_serve_replace_and_unauthorized(self):
        first = self._upload(tiny_png())
        self.assertEqual(first.status_code, 200)
        me = self.client.get('/api/me', headers=self.headers).json()
        self.assertTrue(me['avatar'].startswith('/api/avatars/'))
        self.assertEqual(self.client.get(me['avatar']).status_code, 401)  # 无票据 401
        ticket = self.client.get('/api/state', headers=self.headers).json()['media_ticket']
        served = self.client.get(me['avatar'] + '?ticket=' + ticket)
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served.headers['content-type'], 'image/jpeg')
        second = self._upload(tiny_png(6, 6))
        self.assertEqual(second.status_code, 200)
        avatars_dir = Path(self.tmp.name) / 'avatars'
        files = [p for p in avatars_dir.iterdir() if p.suffix == '.jpg']
        self.assertEqual(len(files), 1)  # 旧头像已被清理
        self.assertEqual(self.client.get('/api/me', headers=self.headers).json()['avatar'], second.json()['avatar'])

    def test_fake_oversize_and_huge_pixels_rejected(self):
        self.assertEqual(self._upload(b'not-an-image').status_code, 415)
        self.assertEqual(self._upload(b'\x00' * (2 * 1024 * 1024 + 1)).status_code, 413)
        ok, buffer = cv2.imencode('.png', np.zeros((5000, 5000, 3), dtype=np.uint8))
        self.assertTrue(ok)
        self.assertEqual(self._upload(buffer.tobytes()).status_code, 413)  # 体积小但像素超大
        self.assertEqual(self._upload(b'').status_code, 400)

    def test_failed_upload_keeps_previous_avatar(self):
        self._upload(tiny_png())
        before = self.client.get('/api/me', headers=self.headers).json()['avatar']
        self.assertEqual(self._upload(b'junk').status_code, 415)
        self.assertEqual(self.client.get('/api/me', headers=self.headers).json()['avatar'], before)


class StatsApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'), 'tester', 'test-password', 'test-secret', worker_enabled=False)
        self.app = create_app(settings)
        self.store = self.app.state.store
        self.client = TestClient(self.app).__enter__()
        token = self.client.post('/api/login', json={'username': 'tester', 'password': 'test-password'}).json()['token']
        self.headers = {'Authorization': 'Bearer ' + token}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def test_empty_stats_shape(self):
        data = self.client.get('/api/stats?range=7d', headers=self.headers).json()
        self.assertEqual(len(data['trend']), 7)
        self.assertEqual(data['trend'], [0] * 7)
        self.assertEqual(len(data['hourly']), 24)
        self.assertEqual(data['breakdown'], {'new': 0, 'processing': 0, 'handled': 0, 'ignored': 0})
        self.assertEqual(data['exec']['total'], 0)
        self.assertIsNone(data['exec']['avg_start_seconds'])
        self.assertIsNone(data['exec']['avg_done_seconds'])
        self.assertIsNone(data['exec']['dual_share'])

    def test_stats_counts_range_and_averages(self):
        # cooldown=0:三条告警各自独立创建(默认 20 秒内同鸟种会触发合并语义)
        self.store.alarm('T1', '珠颈斑鸠', 2, .9, 'a.jpg', 1, 20, 0)
        self.store.alarm('T1', '珠颈斑鸠', 1, .8, 'b.jpg', 2, 21, 0)
        self.store.alarm('T1', '八哥', 1, .7, 'c.jpg', 3, 22, 0)
        self.store.alarm('T1', '老数据', 1, .5, 'old.jpg', 4, 23, 0, now=1000000000)  # 范围外不计
        command = self.store.start_command('stats-001', None, 3, 1)
        self.store.tick(time.time() + 1)
        self.store.tick(time.time() + 5)
        today = self.client.get('/api/stats?range=today', headers=self.headers).json()
        self.assertEqual(today['trend'], [3])
        self.assertEqual(today['breakdown']['new'], 3)
        self.assertEqual(today['species'][0]['species'], '珠颈斑鸠')
        self.assertEqual(today['species'][0]['count'], 2)
        self.assertEqual(today['exec']['completed'], 1)
        self.assertIsNotNone(today['exec']['avg_start_seconds'])
        self.assertIsNotNone(today['exec']['avg_done_seconds'])
        self.assertEqual(today['exec']['dual_share'], 1.0)
        week = self.client.get('/api/stats?range=7d', headers=self.headers).json()
        self.assertEqual(len(week['trend']), 7)
        self.assertEqual(week['trend'][6], 3)
        month = self.client.get('/api/stats?range=30d', headers=self.headers).json()
        self.assertEqual(len(month['trend']), 30)
        self.assertEqual(self.client.get('/api/stats?range=1h', headers=self.headers).status_code, 422)


class AutomationTests(unittest.TestCase):
    """自动哨兵:响应规则触发/冷却/burst、离线与互斥跳过、定时巡逻窗口。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'), 'tester', 'test-password', 'test-secret', worker_enabled=False)
        self.store = Store(self.settings)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def rule(self, **kw):
        params = dict(name='规则一', trigger='alarm_any', mode='acoustic', duration=3, cooldown_minutes=10)
        params.update(kw)
        return self.store.create_rule(1, **params)

    def alarm(self, task='t1', species='八哥', now=None):
        return self.store.alarm(task, species, 1, .9, f'{task}.jpg', 1, 1, 20, now)[0]

    @staticmethod
    def ts_for_minute(minute):
        """取本机未来某个本地时刻的时间戳,用于确定性的巡逻窗口测试。"""
        local = time.localtime()
        base = time.mktime((local.tm_year, local.tm_mon, local.tm_mday, minute // 60, minute % 60, 0, 0, 0, -1))
        if base <= time.time():
            base += 86400
        return base

    def test_rule_crud_and_ownership(self):
        r = self.rule()
        self.assertEqual(len(self.store.rules(1)), 1)
        self.assertEqual(self.store.rules(2), [])
        with self.assertRaises(Conflict):
            self.store.update_rule(2, r['id'], {'enabled': False})
        with self.assertRaises(Conflict):
            self.store.delete_rule(2, r['id'])
        self.store.update_rule(1, r['id'], {'enabled': False, 'duration': 5})
        row = self.store.rules(1)[0]
        self.assertEqual((row['enabled'], row['duration']), (0, 5))
        self.store.delete_rule(1, r['id'])
        self.assertEqual(self.store.rules(1), [])

    def test_alarm_any_rule_fires_with_cooldown(self):
        self.rule()
        self.alarm('t1', now=1000)
        cmds = self.store.snapshot()['commands']
        self.assertEqual(len(cmds), 1)
        self.assertEqual((cmds[0]['automatic'], cmds[0]['user_id'], cmds[0]['mode']), (1, 1, 'acoustic'))
        self.assertEqual(self.store.snapshot()['alarms'][0]['status'], 'processing')
        events = self.store.rows("SELECT * FROM events WHERE kind='automation'")
        self.assertTrue(any('自动响应' in e['message'] and '规则一' in e['message'] for e in events))
        self.store.tick(1000)
        self.store.tick(1004)
        # 冷却期内(600s)的第二报静默跳过
        self.alarm('t2', '喜鹊', now=1100)
        self.assertEqual(len(self.store.snapshot()['commands']), 1)
        # 冷却过后再次触发
        self.alarm('t3', '乌鸦', now=1700)
        self.assertEqual(len(self.store.snapshot()['commands']), 2)

    def test_burst_rule_requires_three_recent_alarms(self):
        self.rule(name='爆发规则', trigger='alarm_burst', mode='both', duration=5)
        for i in range(2):
            self.alarm(f't{i}', f'鸟{i}', now=100 + i)
        self.assertEqual(self.store.snapshot()['commands'], [])
        self.alarm('t2', '鸟2', now=102)
        cmds = self.store.snapshot()['commands']
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0]['mode'], 'both')

    def test_automation_respects_offline_and_busy(self):
        self.rule(cooldown_minutes=1)
        self.store.configure({'scenario': 'offline'})
        self.alarm('t1', now=1000)
        self.assertEqual(self.store.snapshot()['commands'], [])
        events = self.store.rows("SELECT * FROM events WHERE kind='automation'")
        self.assertTrue(any('未触发' in e['message'] and '离线' in e['message'] for e in events))
        # 冷却被跳过占用:紧接着的第二报不刷跳过事件
        self.alarm('t2', '喜鹊', now=1001)
        self.assertEqual(len(self.store.rows("SELECT * FROM events WHERE kind='automation'")), len(events))
        # 在线但指令通道被人工指令占用 → 记跳过;完成后冷却过了再触发成功
        self.store.configure({'scenario': 'normal'})
        manual = self.store.start_command('manual-001', None, 3, 1)
        self.store.tick(2100)
        self.alarm('t3', '乌鸦', now=2100)
        self.assertEqual(len(self.store.snapshot()['commands']), 1)  # 只有 manual
        self.assertTrue(any('未触发' in e['message'] and '执行中' in e['message']
                            for e in self.store.rows("SELECT * FROM events WHERE kind='automation'")))
        self.store.tick(2104)
        self.alarm('t4', '珠颈斑鸠', now=2300)
        self.assertEqual(len(self.store.snapshot()['commands']), 2)

    def test_patrol_window_and_interval(self):
        self.store.set_patrol(1, {'enabled': True, 'start_minute': 600, 'end_minute': 700,
                                  'interval_minutes': 5, 'mode': 'both', 'duration': 3})
        t_in, t_out = self.ts_for_minute(620), self.ts_for_minute(700)  # 700=窗口终点,不含
        self.store.automation_tick(t_out)
        self.assertEqual(self.store.snapshot()['commands'], [])
        self.store.automation_tick(t_in)
        cmds = self.store.snapshot()['commands']
        self.assertEqual(len(cmds), 1)
        self.assertEqual((cmds[0]['automatic'], cmds[0]['mode'], cmds[0]['user_id']), (1, 'both', 1))
        # 间隔 5 分钟内不重复触发;完成上一条后,超过间隔触发第二次
        self.store.automation_tick(t_in + 60)
        self.assertEqual(len(self.store.snapshot()['commands']), 1)
        self.store.tick(t_in + 2)
        self.store.tick(t_in + 6)
        self.store.automation_tick(t_in + 301)
        self.assertEqual(len(self.store.snapshot()['commands']), 2)

    def test_patrol_skips_when_channel_busy(self):
        self.rule(cooldown_minutes=1)
        self.store.set_patrol(1, {'enabled': True, 'start_minute': 0, 'end_minute': 1440, 'interval_minutes': 5})
        now = time.time()
        self.alarm('t1', now=now)  # 规则先占通道
        self.store.automation_tick(now + .5)  # 巡逻到点但通道被占 → 跳过事件
        self.assertEqual(len(self.store.snapshot()['commands']), 1)
        events = self.store.rows("SELECT * FROM events WHERE kind='automation'")
        self.assertTrue(any('定时巡逻未触发' in e['message'] for e in events))

    def test_patrol_api_defaults_and_validation(self):
        self.assertEqual(self.store.patrol(9)['enabled'], 0)
        with self.assertRaises(Conflict):
            self.store.set_patrol(1, {'start_minute': 700, 'end_minute': 600})
        p = self.store.set_patrol(1, {'enabled': True, 'mode': 'infrared'})
        self.assertEqual((p['enabled'], p['mode'], p['interval_minutes']), (1, 'infrared', 120))


if __name__ == '__main__':
    unittest.main()
