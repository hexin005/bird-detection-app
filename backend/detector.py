"""Frame inference follows the existing web detector's YOLO predict + box extraction.

Only model labels are translated; conservation/harm claims from the old bird library
are not imported. A captured frame and its predictions are always published together.
"""
import os
import secrets
import threading
import time
from collections import OrderedDict

from .store import Conflict

NAMES = {
    'Chestnut Munia': '栗腹文鸟', 'Collared Kingfisher': '白领翡翠',
    'Crested Myna': '八哥', 'Eurasian Tree Sparrow': '树麻雀',
    'Garden Sunbird': '花蜜鸟', 'Sooty-headed Bulbul': '白喉红臀鹎',
    'Large-billed Crow': '大嘴乌鸦', 'Black-collared Starling': '黑领椋鸟',
    'Red-billed Blue Magpie': '红嘴蓝鹊', 'Red-billed Starling': '丝光椋鸟',
    'Oriental Magpie': '东方喜鹊', 'Oriental Turtle Dove': '山斑鸠', 'Spotted Dove': '珠颈斑鸠',
}


class AlarmGate:
    def __init__(self):
        self.streak = {}

    def update(self, detections, required):
        grouped = {}
        for detection in detections:
            grouped.setdefault(detection['species'], []).append(detection)
        self.streak = {species: self.streak.get(species, 0) + 1 for species in grouped}
        return {species: values for species, values in grouped.items() if self.streak[species] >= required}


class VideoMonitor:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.model = None
        self.frames = OrderedDict()
        self.current = {'status': 'idle', 'task_id': None, 'message': '选择开始监测，读取配置的录像', 'frame': None}
        latest = store.rows('SELECT * FROM tasks ORDER BY at DESC LIMIT 1')
        if latest:
            self.current.update(status=latest[0]['status'], task_id=latest[0]['id'], message=latest[0]['message'])
        (settings.data_dir / 'captures').mkdir(exist_ok=True)

    def snapshot(self):
        with self.lock:
            return {**self.current, 'source': self.settings.video_path.name, 'model': self.settings.model_path.name,
                    'device': self.settings.device, 'sample_fps': self.settings.sample_fps,
                    'source_ready': self.settings.video_path.is_file(), 'model_ready': self.settings.model_path.is_file()}

    def set_status(self, status, message=''):
        with self.lock:
            self.current.update(status=status, message=message)
            self.store.task(self.current['task_id'], status, message)

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise Conflict('检测任务已在运行或正在停止')
            if not self.settings.model_path.is_file() or not self.settings.video_path.is_file():
                raise Conflict('模型或视频不存在，请检查服务器 local.json 配置')
            self.current = {'task_id': 'T' + secrets.token_hex(5), 'status': 'starting', 'message': '正在加载模型和录像', 'frame': None}
            self.frames.clear()
            self.stop_event.clear()
            self.store.task(self.current['task_id'], 'starting')
            self.thread = threading.Thread(target=self.run, daemon=True, name='bird-inference')
            self.thread.start()
        return self.snapshot()

    def stop(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                self.stop_event.set()
                self.set_status('stopping', '等待当前帧结束')
            elif self.current['status'] in ('starting', 'running', 'stopping'):
                self.set_status('stopped', '检测进程已中断，任务已停止')
        return self.snapshot()

    def get_frame(self, frame_key):
        with self.lock:
            return self.frames.get(frame_key)

    def run(self):
        cap = None
        try:
            config_dir = self.settings.data_dir / 'yolo'
            config_dir.mkdir(exist_ok=True)
            os.environ['YOLO_CONFIG_DIR'] = str(config_dir)
            import cv2
            from ultralytics import YOLO
            if self.model is None:
                self.model = YOLO(str(self.settings.model_path))
            cap = cv2.VideoCapture(str(self.settings.video_path))
            if not cap.isOpened():
                raise RuntimeError('无法打开录像')
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            stride = max(1, round(fps / self.settings.sample_fps))
            gate = AlarmGate()
            frame_no = 0
            self.set_status('running', '真实模型推理 · 预录视频')
            while not self.stop_event.is_set():
                started = time.monotonic()
                ok, frame = cap.read()
                if not ok:
                    self.set_status('ended', '录像已结束，可重新开始监测')
                    return
                frame_no += 1
                config = self.store.config()
                result = self.model.predict(frame, conf=config['confidence'], imgsz=640,
                                            device=self.settings.device, verbose=False)[0]
                detections = []
                annotated = frame.copy()
                for box in result.boxes:
                    name = self.model.names[int(box.cls[0])]
                    confidence = round(float(box.conf[0]), 4)
                    x1, y1, x2, y2 = [int(x) for x in box.xyxy[0].tolist()]
                    detections.append({'species': NAMES.get(name, name), 'class_name': name,
                                       'confidence': confidence, 'bbox': [x1, y1, x2, y2]})
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (81, 205, 160), 3)
                    cv2.putText(annotated, f'{name} {confidence:.0%}', (x1, max(22, y1 - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, .65, (81, 205, 160), 2)
                if annotated.shape[1] > 960:
                    annotated = cv2.resize(annotated, (960, round(annotated.shape[0] * 960 / annotated.shape[1])))
                encoded_ok, jpeg = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if not encoded_ok:
                    raise RuntimeError('画面编码失败')
                if self.stop_event.is_set():
                    break
                now = time.time()
                key = f'{self.current["task_id"]}-{frame_no}'
                metadata = {'key': key, 'frame_id': frame_no, 'video_time': (frame_no - 1) / fps,
                            'duration': total / fps, 'at': now, 'detections': detections,
                            'count': len(detections), 'inference_ms': round((time.monotonic() - started) * 1000)}
                with self.lock:
                    self.frames[key] = jpeg.tobytes()
                    while len(self.frames) > 20:
                        self.frames.popitem(last=False)
                    self.current['frame'] = metadata
                candidates = gate.update(detections, config['consecutive'])
                if candidates:
                    capture = f'{key}.jpg'
                    path = self.settings.data_dir / 'captures' / capture
                    path.write_bytes(jpeg.tobytes())
                    created = False
                    for species, values in candidates.items():
                        # bbox 取自本帧该物种的第一个框，与抓拍图同帧成对保存
                        first_bbox = values[0].get('bbox') if values else None
                        _, is_new = self.store.alarm(self.current['task_id'], species, len(values),
                            max(d['confidence'] for d in values), capture, metadata['video_time'], frame_no, config['cooldown'],
                            bbox=first_bbox)
                        created = created or is_new
                    if not created:
                        path.unlink(missing_ok=True)
                for _ in range(stride - 1):
                    if not cap.grab():
                        break
                    frame_no += 1
                self.stop_event.wait(max(0, 1 / self.settings.sample_fps - (time.monotonic() - started)))
            self.set_status('stopped', '监测已停止，画面为最后一次检测')
        except Exception as exc:
            self.set_status('error', f'检测失败：{str(exc)[:250]}')
        finally:
            if cap is not None:
                cap.release()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=30)
