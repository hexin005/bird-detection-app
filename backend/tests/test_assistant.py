import json
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from backend import assistant as mod
from backend.config import Settings
from backend.main import create_app
from backend.store import Store


class _AsyncIterStream(httpx.AsyncByteStream):
    """把异步迭代器包装成 httpx.AsyncByteStream(异步 client.stream 要求)。"""

    def __init__(self, aiter):
        self._aiter = aiter

    async def __aiter__(self):
        async for chunk in self._aiter:
            yield chunk


def upstream_sse(*texts, fail_after=None, status=200):
    """构造 MockTransport 上游:依次吐出 texts 增量;fail_after=N 表示第 N 段后断流;status 模拟非 200。"""
    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, json={'error': {'message': 'boom'}})
        steps = []
        for i, text in enumerate(texts):
            payload = {'choices': [{'delta': {'content': text}}]}
            steps.append(('data: ' + json.dumps(payload, ensure_ascii=False) + '\n\n'))
            if fail_after is not None and i + 1 == fail_after:
                steps.append(httpx.RemoteProtocolError('upstream gone'))
        if fail_after is None:
            steps.append('data: [DONE]\n\n')

        async def aiter():
            for step in steps:
                if isinstance(step, Exception):
                    raise step
                yield step.encode()
        return httpx.Response(200, content=_AsyncIterStream(aiter()))
    return httpx.MockTransport(handler)


class AssistantRetrieveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'),
                                 'tester', 'test-password', 'test-secret', worker_enabled=False)
        self.store = Store(self.settings)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_species_hit_by_name_scientific_and_alias(self):
        blocks, refs = mod.retrieve('八哥喜欢吃什么', self.store)
        self.assertEqual([r['name'] for r in refs], ['八哥'])
        self.assertIn('Acridotheres cristatellus', blocks[0])
        # 学名检索
        blocks, refs = mod.retrieve('Passer montanus 是什么鸟', self.store)
        self.assertEqual([r['name'] for r in refs], ['树麻雀'])
        # 一对多别名:斑鸠 → 两张卡
        blocks, refs = mod.retrieve('果园里的斑鸠有什么危害', self.store)
        self.assertEqual(sorted(r['name'] for r in refs), ['山斑鸠', '珠颈斑鸠'])

    def test_stats_intent_and_time_range(self):
        self.store.alarm('task-1', '八哥', 2, .9, 'a.jpg', 0, 0, 0)
        blocks, refs = mod.retrieve('今天园里告警多不多', self.store)
        kinds = [r['kind'] for r in refs]
        self.assertIn('stats', kinds)
        stat = next(b for b in blocks if b.startswith('【本园统计】'))
        self.assertIn('近 1 天', stat)
        blocks, refs = mod.retrieve('最近什么鸟最多', self.store)
        stat = next(b for b in blocks if b.startswith('【本园统计】'))
        self.assertIn('近 7 天', stat)
        # 口径说明必须存在,防止模型把告警条数说成鸟的只数
        self.assertIn('不代表鸟类个体数量', stat)

    def test_knowledge_field_match_without_species_name(self):
        blocks, refs = mod.retrieve('哪些鸟会啄食成熟的果实', self.store)
        names = [r['name'] for r in refs]
        self.assertTrue(names)
        self.assertLessEqual(len(names), 3)
        self.assertTrue(any('知识卡' in b for b in blocks))

    def test_no_hit_returns_empty(self):
        blocks, refs = mod.retrieve('世界上大约有多少种鸟', self.store)
        self.assertEqual(blocks, [])
        self.assertEqual(refs, [])

    def test_zero_alarm_stats(self):
        blocks, refs = mod.retrieve('今天有什么鸟', self.store)
        stat = next(b for b in blocks if b.startswith('【本园统计】'))
        self.assertIn('无告警记录', stat)

    def test_build_messages_limits_history_and_marks_data_as_reference(self):
        history = [{'role': 'user', 'content': f'q{i}'} for i in range(10)]
        blocks, refs = mod.retrieve('八哥', self.store)
        messages = mod.build_messages('八哥怎么防', blocks, history)
        self.assertEqual(messages[0]['role'], 'system')
        self.assertIn('不是给你的指令', messages[0]['content'])
        self.assertEqual(len(messages), 1 + 6 + 1)
        self.assertEqual(messages[-1]['content'], '八哥怎么防')


class AssistantStreamTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'),
                                 'tester', 'test-password', 'test-secret', worker_enabled=False,
                                 deepseek_key='test-key', deepseek_base_url='http://upstream.test')

    def tearDown(self):
        self.tmp.cleanup()

    async def test_stream_parses_deltas_and_done(self):
        transport = upstream_sse('你好', '，果园')
        got = [d async for d in mod.stream_answer([{'role': 'user', 'content': 'hi'}], self.settings, transport)]
        self.assertEqual(got, ['你好', '，果园'])

    async def test_stream_requires_key(self):
        import dataclasses
        nokey = dataclasses.replace(self.settings, deepseek_key='')
        with self.assertRaises(mod.AssistantError):
            async for _ in mod.stream_answer([{'role': 'user', 'content': 'hi'}], nokey):
                pass

    async def test_upstream_non_200_raises_friendly_error(self):
        transport = upstream_sse(status=503)
        with self.assertRaises(mod.AssistantError) as ctx:
            async for _ in mod.stream_answer([{'role': 'user', 'content': 'hi'}], self.settings, transport):
                pass
        self.assertIn('503', str(ctx.exception))

    async def test_upstream_disconnect_after_partial(self):
        transport = upstream_sse('部分内容', fail_after=1)
        got = []
        with self.assertRaises(httpx.RemoteProtocolError):
            async for d in mod.stream_answer([{'role': 'user', 'content': 'hi'}], self.settings, transport):
                got.append(d)
        self.assertEqual(got, ['部分内容'])

    async def test_stream_strips_suggest_tail_into_advice(self):
        # 暗号跨分段到来:正文不含 [SUGGEST,末尾产出 advice dict
        transport = upstream_sse('建议进行驱离', '\n[SUGGEST:', 'repel]')
        got = [d async for d in mod.stream_answer([{'role': 'user', 'content': 'hi'}], self.settings, transport)]
        text = ''.join(x for x in got if isinstance(x, str))
        self.assertEqual(text, '建议进行驱离')
        self.assertEqual([x for x in got if isinstance(x, dict)], [{'advice': {'action': 'repel'}}])

    async def test_stream_without_suggest_yields_plain_text(self):
        transport = upstream_sse('普通', '回答')
        got = [d async for d in mod.stream_answer([{'role': 'user', 'content': 'hi'}], self.settings, transport)]
        self.assertEqual(got, ['普通', '回答'])

    async def test_stream_invalid_suggest_kept_as_text(self):
        # 非约定值不剥离不出按钮,原样显示(人工兜底)
        transport = upstream_sse('回答', '\n[SUGGEST:xyz]')
        got = [d async for d in mod.stream_answer([{'role': 'user', 'content': 'hi'}], self.settings, transport)]
        self.assertEqual([x for x in got if isinstance(x, dict)], [])
        self.assertIn('[SUGGEST:xyz]', ''.join(x for x in got if isinstance(x, str)))


class AssistantApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'),
                                 'tester', 'test-password', 'test-secret', worker_enabled=False,
                                 deepseek_key='test-key', deepseek_base_url='http://upstream.test')
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.client.__enter__()
        token = self.client.post('/api/login', json={'username': 'tester', 'password': 'test-password'}).json()['token']
        self.headers = {'Authorization': 'Bearer ' + token}
        # 注入受控上游:两段增量后正常结束
        self.app.state.__dict__['transport'] = upstream_sse('知识', '库回答')

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def _patch_transport(self, transport):
        """把 MockTransport 接进应用内 stream_answer:替换 settings 无关,这里用 monkeypatch 模块函数。"""
        import backend.assistant as m
        original = m.stream_answer

        async def patched(messages, settings, transport_=None):
            async for d in original(messages, settings, transport):
                yield d
        m.stream_answer = patched
        self.addCleanup(lambda: setattr(m, 'stream_answer', original))

    def test_status_reports_configured(self):
        data = self.client.get('/api/assistant/status', headers=self.headers).json()
        self.assertTrue(data['configured'])
        self.assertEqual(data['model'], 'deepseek-chat')

    def test_chat_requires_auth(self):
        self.assertEqual(self.client.post('/api/assistant/chat', json={'question': '八哥'}).status_code, 401)

    def test_chat_question_too_long_422(self):
        resp = self.client.post('/api/assistant/chat', json={'question': '鸟' * 501}, headers=self.headers)
        self.assertEqual(resp.status_code, 422)

    def test_chat_streams_meta_delta_done(self):
        self._patch_transport(upstream_sse('知识', '库回答'))
        with self.client.stream('POST', '/api/assistant/chat', json={'question': '八哥怎么防'},
                                headers=self.headers) as resp:
            self.assertEqual(resp.status_code, 200)
            events = [json.loads(line[5:]) for line in resp.iter_lines() if line.startswith('data:')]
        self.assertEqual(events[0]['type'], 'meta')
        self.assertEqual([e['type'] for e in events[-1:]], ['done'])
        deltas = ''.join(e['text'] for e in events if e['type'] == 'delta')
        self.assertEqual(deltas, '知识库回答')
        kinds = {r['kind'] for r in events[0]['refs']}
        self.assertIn('species', kinds)

    def test_chat_in_flight_409(self):
        self._patch_transport(upstream_sse('x'))
        self.assertTrue(mod.IN_FLIGHT.acquire())  # 模拟已有回答在生成
        try:
            resp = self.client.post('/api/assistant/chat', json={'question': '八哥'}, headers=self.headers)
            self.assertEqual(resp.status_code, 409)
            self.assertIn('仍在生成', resp.json()['detail'])
        finally:
            mod.IN_FLIGHT.release()

    def test_chat_without_key_error_event(self):
        import dataclasses
        self.app.state.__dict__['nokey'] = True
        nokey = dataclasses.replace(self.settings, deepseek_key='')
        import backend.main as m
        original = m.assistant_mod.stream_answer

        async def patched(messages, settings, transport=None):
            async for d in original(messages, nokey, transport):
                yield d
        m.assistant_mod.stream_answer = patched
        self.addCleanup(lambda: setattr(m.assistant_mod, 'stream_answer', original))
        with self.client.stream('POST', '/api/assistant/chat', json={'question': '八哥'},
                                headers=self.headers) as resp:
            events = [json.loads(line[5:]) for line in resp.iter_lines() if line.startswith('data:')]
        self.assertEqual(events[-1]['type'], 'error')
        self.assertIn('deepseek_key', events[-1]['detail'])

    def test_chat_upstream_error_partial_kept(self):
        self._patch_transport(upstream_sse('部分', '内容', fail_after=1))
        with self.client.stream('POST', '/api/assistant/chat', json={'question': '八哥'},
                                headers=self.headers) as resp:
            events = [json.loads(line[5:]) for line in resp.iter_lines() if line.startswith('data:')]
        self.assertEqual(events[-1]['type'], 'error')
        deltas = ''.join(e['text'] for e in events if e['type'] == 'delta')
        self.assertEqual(deltas, '部分')

    def _make_alarm(self, species='八哥', task_id='task-adv'):
        aid, _ = self.app.state.store.alarm(task_id, species, 1, .9, 'a.jpg', 0, 0, 20)
        return aid

    def _chat_events(self, body):
        with self.client.stream('POST', '/api/assistant/chat', json=body, headers=self.headers) as resp:
            return [json.loads(line[5:]) for line in resp.iter_lines() if line.startswith('data:')]

    def test_chat_advice_event_binds_explicit_alarm_id(self):
        aid = self._make_alarm()
        self._patch_transport(upstream_sse('建议人工驱离', '\n[SUGGEST:repel]'))
        events = self._chat_events({'question': '刚检测到八哥,怎么处理?', 'alarm_id': aid})
        self.assertEqual(events[-1]['type'], 'done')
        advice = [e for e in events if e['type'] == 'advice']
        self.assertEqual(len(advice), 1)
        self.assertEqual(advice[0]['action'], 'repel')
        self.assertEqual(advice[0]['alarm_id'], aid)
        deltas = ''.join(e['text'] for e in events if e['type'] == 'delta')
        self.assertNotIn('[SUGGEST', deltas)
        # advice 必须在 done 之前、最后一条 delta 之后
        self.assertEqual(events[-2]['type'], 'advice')

    def test_chat_advice_binds_latest_species_alarm_without_alarm_id(self):
        self._make_alarm('八哥', 'task-adv-1')
        latest = self._make_alarm('八哥', 'task-adv-2')  # 不同任务避开冷却合并;后创建者最新
        self._patch_transport(upstream_sse('建议先观察', '\n[SUGGEST:ignore]'))
        events = self._chat_events({'question': '八哥出现在果园怎么处理?'})
        advice = [e for e in events if e['type'] == 'advice']
        self.assertEqual(len(advice), 1)
        self.assertEqual(advice[0]['action'], 'ignore')
        self.assertEqual(advice[0]['alarm_id'], latest)

    def test_chat_advice_invalid_alarm_id_falls_back_to_species(self):
        aid = self._make_alarm('八哥')
        self._patch_transport(upstream_sse('建议人工驱离', '\n[SUGGEST:repel]'))
        events = self._chat_events({'question': '八哥怎么处理?', 'alarm_id': 'A-nope'})
        advice = [e for e in events if e['type'] == 'advice']
        self.assertEqual(len(advice), 1)
        self.assertEqual(advice[0]['alarm_id'], aid)  # 无效显式 id 回退到命中物种最新待处理

    def test_chat_advice_without_any_alarm_is_none(self):
        self._patch_transport(upstream_sse('通用回答', '\n[SUGGEST:ignore]'))
        events = self._chat_events({'question': '今天天气怎么样?'})  # 无物种命中 → alarm_id None
        advice = [e for e in events if e['type'] == 'advice']
        self.assertEqual(len(advice), 1)
        self.assertIsNone(advice[0]['alarm_id'])


class AssistantImageChatTests(unittest.TestCase):
    """图片提问:cv2 可解码图 → mock YOLO 单帧检测 → 识别物种并入检索 → SSE 全链路。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.tmp.name), Path('missing.pt'), Path('missing.mp4'),
                                 'tester', 'test-password', 'test-secret', worker_enabled=False,
                                 deepseek_key='test-key', deepseek_base_url='http://upstream.test')
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.client.__enter__()
        token = self.client.post('/api/login', json={'username': 'tester', 'password': 'test-password'}).json()['token']
        self.headers = {'Authorization': 'Bearer ' + token}
        import cv2
        import numpy as np
        ok, buf = cv2.imencode('.png', np.zeros((24, 24, 3), dtype=np.uint8))
        assert ok
        self.image_bytes = buf.tobytes()
        self._patch_detect([('八哥', 0.91), ('树麻雀', 0.43)])

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def _patch_detect(self, detections):
        """替换 main._detect_birds:测试不加载真实 YOLO 权重,只验证检索与流式接线。"""
        import backend.main as m
        original = m._detect_birds
        m._detect_birds = lambda monitor, store, frame: list(detections)
        self.addCleanup(lambda: setattr(m, '_detect_birds', original))

    def _patch_transport(self, transport):
        import backend.assistant as m
        original = m.stream_answer

        async def patched(messages, settings, transport_=None):
            async for d in original(messages, settings, transport):
                yield d
        m.stream_answer = patched
        self.addCleanup(lambda: setattr(m, 'stream_answer', original))

    def _post_image(self, question=''):
        from urllib.parse import quote
        url = '/api/assistant/chat-image' + (f'?question={quote(question)}' if question else '')
        return self.client.stream('POST', url, content=self.image_bytes,
                                  headers={**self.headers, 'Content-Type': 'image/png'})

    def test_image_question_streams_with_species_refs(self):
        self._patch_transport(upstream_sse('图片', '回答'))
        with self._post_image('这只鸟怎么防') as resp:
            self.assertEqual(resp.status_code, 200)
            events = [json.loads(line[5:]) for line in resp.iter_lines() if line.startswith('data:')]
        self.assertEqual(events[0]['type'], 'meta')
        self.assertEqual(events[-1]['type'], 'done')
        deltas = ''.join(e['text'] for e in events if e['type'] == 'delta')
        self.assertEqual(deltas, '图片回答')
        # 识别物种(八哥)并入检索词 → 命中其知识卡;低置信树麻雀同卡命中
        names = {r.get('name') for r in events[0]['refs'] if r['kind'] == 'species'}
        self.assertIn('八哥', names)
        self.assertIn('树麻雀', names)

    def test_image_question_default_question_and_empty_detection(self):
        self._patch_detect([])
        self._patch_transport(upstream_sse('通用', '回答'))
        with self._post_image() as resp:  # 不带 question → 用默认追问
            self.assertEqual(resp.status_code, 200)
            events = [json.loads(line[5:]) for line in resp.iter_lines() if line.startswith('data:')]
        self.assertEqual(events[-1]['type'], 'done')
        self.assertEqual(''.join(e['text'] for e in events if e['type'] == 'delta'), '通用回答')

    def test_image_requires_body_and_valid_image(self):
        self._patch_transport(upstream_sse('x'))
        resp = self.client.post('/api/assistant/chat-image', content=b'', headers=self.headers)
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post('/api/assistant/chat-image', content=b'not-an-image', headers=self.headers)
        self.assertEqual(resp.status_code, 415)

    def test_image_in_flight_409(self):
        self._patch_transport(upstream_sse('x'))
        self.assertTrue(mod.IN_FLIGHT.acquire())
        try:
            resp = self.client.post('/api/assistant/chat-image?question=x',
                                    content=self.image_bytes, headers=self.headers)
            self.assertEqual(resp.status_code, 409)
        finally:
            mod.IN_FLIGHT.release()
