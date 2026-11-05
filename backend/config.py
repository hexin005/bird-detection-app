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
                   device=os.getenv('BIRD_DEVICE', 'cpu'))
