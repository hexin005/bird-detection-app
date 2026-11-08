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
        return cls(data, Path(os.getenv('BIRD_MODEL_PATH', values['model_path'])),
                   Path(os.getenv('BIRD_VIDEO_PATH', values['video_path'])),
                   values['username'], values['password'], values['secret'],
                   device=os.getenv('BIRD_DEVICE', 'cpu'),
                   smtp_host=values.get('smtp_host', ''),
                   smtp_port=int(values.get('smtp_port', 465)),
                   smtp_user=values.get('smtp_user', ''),
                   smtp_pass=values.get('smtp_pass', ''),
                   smtp_from=values.get('smtp_from', ''),
                   email_demo=values.get('email_demo', True))
