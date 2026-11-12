import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Settings:
    data_dir: Path
    model_path: Path
    video_path: Path
    username: str
    password: str
    secret: str
    device: str = 'cpu'
    confidence: float = .35
    consecutive: int = 2
    cooldown: float = 20
    sample_fps: float = 2
    worker_enabled: bool = True
    # AI 助手(DeepSeek,OpenAI 兼容):key 只存本机 .runtime/local.json 或环境变量,不入库不入 git
    deepseek_key: str = ''
    deepseek_base_url: str = 'https://api.deepseek.com'
    deepseek_model: str = 'deepseek-chat'
    # 邮件/验证码:smtp_* 配置齐全则真发;email_demo 显式开启时走演示模式(服务端日志打印验证码)。
    # 真发失败一律报错,绝不降级回演示码,避免"SMTP 配置意外丢失"被解释成可公开重置密码。
    smtp_host: str = ''
    smtp_port: int = 465
    smtp_user: str = ''
    smtp_pass: str = ''
    smtp_from: str = ''
    email_demo: bool = True

    @classmethod
    def load(cls):
        data = Path(os.getenv('BIRD_DATA_DIR', str(ROOT / '.runtime'))).resolve()
        data.mkdir(parents=True, exist_ok=True)
        config = data / 'local.json'
        if not config.exists():
            config.write_text(json.dumps({
                'username': 'orchard', 'password': secrets.token_urlsafe(12),
                'secret': secrets.token_hex(32),
                'model_path': str(ROOT / 'assets/best.pt'),
                'video_path': str(ROOT / 'assets/demo-bird.mp4'),
            }, ensure_ascii=False, indent=2), encoding='utf-8')
        values = json.loads(config.read_text(encoding='utf-8'))
        # 升级合并:新版本新增的可选字段缺省补进旧 local.json(不覆盖已填值),
        # 让升级后的用户能直接看到新配置项,与数据库迁移"幂等补列"同一思路。
        optional_defaults = {'deepseek_key': '', 'deepseek_base_url': 'https://api.deepseek.com',
                             'deepseek_model': 'deepseek-chat'}
        if any(key not in values for key in optional_defaults):
            for key, default in optional_defaults.items():
                values.setdefault(key, default)
            config.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')
        return cls(data, Path(os.getenv('BIRD_MODEL_PATH', values['model_path'])),
                   Path(os.getenv('BIRD_VIDEO_PATH', values['video_path'])),
                   values['username'], values['password'], values['secret'],
                   device=os.getenv('BIRD_DEVICE', 'cpu'),
                   deepseek_key=os.getenv('BIRD_DEEPSEEK_KEY', values.get('deepseek_key', '')),
                   deepseek_base_url=values.get('deepseek_base_url', 'https://api.deepseek.com'),
                   deepseek_model=values.get('deepseek_model', 'deepseek-chat'),
                   smtp_host=values.get('smtp_host', ''),
                   smtp_port=int(values.get('smtp_port', 465)),
                   smtp_user=values.get('smtp_user', ''),
                   smtp_pass=values.get('smtp_pass', ''),
                   smtp_from=values.get('smtp_from', ''),
                   email_demo=values.get('email_demo', True))
