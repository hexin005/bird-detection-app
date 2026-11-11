import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.detector import NAMES
from backend.knowledge import KNOWLEDGE_SPECIES
from backend.main import create_app
from backend.store import Store


def local_ts(hour, minute=30):
    """构造指定本地时刻的 unix 时间戳,验证 24 桶按本地时间聚合。"""
    return time.mktime(time.strptime(f'2026-01-15 {hour:02d}:{minute:02d}:00', '%Y-%m-%d %H:%M:%S'))


class KnowledgeApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'),
                                 'tester', 'test-password', 'test-secret', worker_enabled=False)
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.client.__enter__()
        token = self.client.post('/api/login', json={'username': 'tester', 'password': 'test-password'}).json()['token']
        self.headers = {'Authorization': 'Bearer ' + token}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def seed_alarms(self):
        """八哥 5 条(8:30 三条 / 14:30 两条)、树麻雀 3 条(20:30)、知识外鸟种 2 条。"""
        store = self.app.state.store
        h8, h14, h20 = local_ts(8), local_ts(14), local_ts(20)
        for i in range(3):
            store.alarm(f'task-a{i}', '八哥', 2, .9 - i * .05, f'a{i}.jpg', i * 10.0, i, 0, h8)
        for i in range(2):
            store.alarm(f'task-b{i}', '八哥', 1, .8, f'b{i}.jpg', i * 10.0, i, 0, h14)
        for i in range(3):
            store.alarm(f'task-c{i}', '树麻雀', 3, .7, f'c{i}.jpg', i * 10.0, i, 0, h20)
        for i in range(2):
            store.alarm(f'task-d{i}', '老数据', 1, .5, None, 0, i, 0, h8)
        return h8, h14, h20

    def item(self, name):
        data = self.client.get('/api/knowledge', headers=self.headers).json()
        return next(i for i in data['items'] if i['name'] == name)

    def test_seeds_13_species_with_complete_fields(self):
        data = self.client.get('/api/knowledge', headers=self.headers)
        self.assertEqual(data.status_code, 200)
        items = data.json()['items']
        self.assertEqual(len(items), 13)
        self.assertEqual({i['name'] for i in items}, set(NAMES.values()))
        for item in items:
            for field in ('en', 'scientific_name', 'family', 'domestic_protection', 'iucn_status',
                          'level', 'desc', 'harm', 'traits', 'voice', 'diet', 'ecology', 'hours', 'advice'):
                self.assertTrue(item[field], f"{item['name']} 缺少 {field}")
            self.assertEqual(len(item['records']['hour_buckets']), 24)
        self.assertEqual([i['level'] for i in items], ['high'] * 7 + ['mid'] * 4 + ['low'] * 2)

    def test_requires_auth(self):
        self.assertEqual(self.client.get('/api/knowledge').status_code, 401)
        self.assertEqual(self.client.get('/api/knowledge/八哥').status_code, 401)

    def test_zero_alarm_species_records_are_empty(self):
        records = self.item('八哥')['records']
        self.assertEqual(records['total'], 0)
        self.assertEqual(records['pending'], 0)
        self.assertIsNone(records['last_seen'])
        self.assertIsNone(records['cover'])
        self.assertIsNone(records['best_confidence'])
        self.assertEqual(records['videos'], 0)
        self.assertEqual(records['hour_buckets'], [0] * 24)

    def test_species_isolation_and_hour_buckets(self):
        h8, h14, h20 = self.seed_alarms()
        myna = self.item('八哥')
        sparrow = self.item('树麻雀')
        self.assertEqual(myna['records']['total'], 5)
        self.assertEqual(sparrow['records']['total'], 3)
        # 知识表外的告警物种不进入知识列表
        names = [i['name'] for i in self.client.get('/api/knowledge', headers=self.headers).json()['items']]
        self.assertNotIn('老数据', names)
        # 24 桶只统计本物种:八哥 8/14 时,树麻雀 20 时,互不混入
        self.assertEqual(myna['records']['hour_buckets'][8], 3)
        self.assertEqual(myna['records']['hour_buckets'][14], 2)
        self.assertEqual(myna['records']['hour_buckets'][20], 0)
        self.assertEqual(sparrow['records']['hour_buckets'][20], 3)
        self.assertEqual(sparrow['records']['hour_buckets'][8], 0)

    def test_detail_matches_list_and_library_group(self):
        self.seed_alarms()
        detail = self.client.get('/api/knowledge/八哥', headers=self.headers).json()
        self.assertEqual(detail['records'], self.item('八哥')['records'])
        # 与 /api/library 的告警分组同源同值(口径一致性回归)
        groups = {g['species']: g for g in self.client.get('/api/library', headers=self.headers).json()['alarm_groups']}
        self.assertEqual(detail['records']['total'], groups['八哥']['total'])
        self.assertEqual(detail['records']['cover'], groups['八哥']['cover'])

    def test_unknown_species_404(self):
        self.assertEqual(self.client.get('/api/knowledge/不存在', headers=self.headers).status_code, 404)

    def test_upsert_realigns_manual_edits(self):
        # 库内手改会在下次 Store 初始化时被种子覆盖(代码即权威版本)
        with self.app.state.store.tx() as db:
            db.execute("UPDATE species_knowledge SET diet='旧文案' WHERE name='八哥'")
        store = Store(self.settings)
        try:
            value = store.rows("SELECT diet FROM species_knowledge WHERE name='八哥'")[0]['diet']
        finally:
            store.close()
        self.assertEqual(value, KNOWLEDGE_SPECIES[0]['diet'])

    def test_reopen_persists_without_duplicate_seed(self):
        self.client.__exit__(None, None, None)
        store = Store(self.settings)
        try:
            count = store.rows('SELECT COUNT(*) n FROM species_knowledge')[0]['n']
        finally:
            store.close()
        self.assertEqual(count, 13)
