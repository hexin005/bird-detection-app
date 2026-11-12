import json
import os
import tempfile
import unittest
from pathlib import Path

from backend.config import Settings


class ConfigMergeTests(unittest.TestCase):
    """local.json 升级合并:缺失的可选字段自动补进文件,已填值不被覆盖,env 优先级不变。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_env = os.environ.get('BIRD_DATA_DIR')
        os.environ['BIRD_DATA_DIR'] = self.tmp.name

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop('BIRD_DATA_DIR', None)
        else:
            os.environ['BIRD_DATA_DIR'] = self._old_env
        self.tmp.cleanup()

    def _write(self, payload):
        (Path(self.tmp.name) / 'local.json').write_text(json.dumps(payload), encoding='utf-8')

    def _read(self):
        return json.loads((Path(self.tmp.name) / 'local.json').read_text(encoding='utf-8'))

    def test_missing_optional_keys_are_merged_back(self):
        self._write({'username': 'u', 'password': 'p', 'secret': 's', 'model_path': 'm', 'video_path': 'v'})
        settings = Settings.load()
        data = self._read()
        self.assertEqual(data['deepseek_key'], '')
        self.assertEqual(data['deepseek_base_url'], 'https://api.deepseek.com')
        self.assertEqual(data['deepseek_model'], 'deepseek-chat')
        self.assertEqual(data['username'], 'u')  # 已有键原样保留
        self.assertEqual(settings.deepseek_key, '')

    def test_filled_values_are_not_overwritten(self):
        self._write({'username': 'u', 'password': 'p', 'secret': 's', 'model_path': 'm', 'video_path': 'v',
                     'deepseek_key': 'sk-existing', 'deepseek_model': 'deepseek-reasoner'})
        settings = Settings.load()
        data = self._read()
        self.assertEqual(data['deepseek_key'], 'sk-existing')
        self.assertEqual(settings.deepseek_key, 'sk-existing')
        self.assertEqual(settings.deepseek_model, 'deepseek-reasoner')

    def test_env_key_beats_file_value(self):
        self._write({'username': 'u', 'password': 'p', 'secret': 's', 'model_path': 'm', 'video_path': 'v',
                     'deepseek_key': 'sk-file'})
        old = os.environ.get('BIRD_DEEPSEEK_KEY')
        os.environ['BIRD_DEEPSEEK_KEY'] = 'sk-env'
        try:
            settings = Settings.load()
        finally:
            if old is None:
                os.environ.pop('BIRD_DEEPSEEK_KEY', None)
            else:
                os.environ['BIRD_DEEPSEEK_KEY'] = old
        self.assertEqual(settings.deepseek_key, 'sk-env')
