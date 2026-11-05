import os
import contextlib
import shutil
import subprocess
import time
from pathlib import Path

from .detector import AlarmGate, NAMES, VideoMonitor
from .store import Conflict
from .video_library import VideoLibrary


def encoder_path():
    return os.getenv('BIRD_FFMPEG') or shutil.which('ffmpeg') or ''


class VideoPipeline(VideoMonitor):
    def __init__(self, settings, store):
        super().__init__(settings, store)
        self.library = VideoLibrary(settings, store)
        self.selected = None

    def start(self, video_id=None):
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise Conflict('已有分析任务，请等待完成或停止')
            if not encoder_path():
                raise Conflict('服务器缺少 FFmpeg，无法生成可播放视频')
            if video_id:
                self.selected = self.library.video(video_id)
            else:
                if not self.settings.video_path.is_file():
                    raise Conflict('请先上传视频，或配置默认演示视频')
                self.selected = self.library.register(self.settings.video_path, '演示录像 · ' + self.settings.video_path.name)
            # Preserve legacy path checks without changing Settings for later default runs.
            original = self.settings.video_path
            try:
                self.settings.video_path = Path(self.selected['path'])
                result = super().start()
            finally:
                self.settings.video_path = original
            return result

    def snapshot(self):
        result = super().snapshot()
        if self.selected:
            result['source'] = self.selected['name']
        task_id = result.get('task_id')
        if task_id:
            rows = self.store.rows('SELECT progress,result_ready,duration,video_id FROM tasks WHERE id=?', (task_id,))
            if rows:
                result.update(rows[0])
            result['stream_ready'] = (self.library.jobs / task_id / 'index.m3u8').exists()
        return result

    def run(self):
        cap, process, log = None, None, None
        task_id = self.current['task_id']
        output = self.library.jobs / task_id
        output.mkdir(exist_ok=True)
        status, message = 'ended', '视频分析完成，结果已归档'
        try:
            video = dict(self.selected)
            self.library.attach(task_id, video)
            config_dir = self.settings.data_dir / 'yolo'
            config_dir.mkdir(exist_ok=True)
            os.environ['YOLO_CONFIG_DIR'] = str(config_dir)
            import cv2
            from ultralytics import YOLO
            if self.model is None:
                self.model = YOLO(str(self.settings.model_path))
            if self.stop_event.is_set():
                self.set_status('stopped', '已取消分析，尚未生成视频')
                return
            cap = cv2.VideoCapture(video['path'])
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError('无法解码视频')
            height, width = frame.shape[:2]
            scale = min(1, 960 / width)
            width, height = int(width * scale) // 2 * 2, int(height * scale) // 2 * 2
            fps = video['fps']
            # Preserve playback FPS while sampling inference; boxes are held only until the next sample.
            stride = max(1, round(fps / max(2, self.settings.sample_fps)))
            log = (output / 'encoder.log').open('wb')
            args = [encoder_path(), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                    '-s', f'{width}x{height}', '-r', str(fps), '-i', 'pipe:0', '-an', '-c:v', 'libx264',
                    '-preset', 'ultrafast', '-crf', '24', '-pix_fmt', 'yuv420p', '-g', str(max(1, round(fps * 2))),
                    '-sc_threshold', '0', '-f', 'hls', '-hls_time', '2', '-hls_list_size', '0',
                    '-hls_flags', 'independent_segments+temp_file', '-hls_segment_filename', str(output / 'seg%05d.ts'), str(output / 'index.m3u8')]
            process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.set_status('running', '正在分析并生成视频，可在缓冲后播放')
            gate, detections, frame_no = AlarmGate(), [], 0
            rule_signature = None
            while ok and not self.stop_event.is_set():
                timestamp = frame_no / fps
                frame = cv2.resize(frame, (width, height))
                sampled = frame_no % stride == 0
                started = time.monotonic()
                config = self.store.config()
                signature = (config['confidence'], config['consecutive'])
                if signature != rule_signature:
                    gate = AlarmGate()
                    rule_signature = signature
                if sampled:
                    prediction = self.model.predict(frame, conf=config['confidence'], imgsz=640,
                                                     device=self.settings.device, verbose=False)[0]
                    detections = []
                    for box in prediction.boxes:
                        name = self.model.names[int(box.cls[0])]
                        detections.append({'species': NAMES.get(name, name), 'class_name': name,
                            'confidence': round(float(box.conf[0]), 4), 'bbox': [int(v) for v in box.xyxy[0].tolist()]})
                annotated = frame.copy()
                for detection in detections:
                    x1,y1,x2,y2 = detection['bbox']
                    cv2.rectangle(annotated, (x1,y1), (x2,y2), (81,205,160), 2)
                    cv2.putText(annotated, f"{detection['class_name']} {detection['confidence']:.0%}", (x1,max(20,y1-7)),
                                cv2.FONT_HERSHEY_SIMPLEX, .5, (81,205,160), 1)
                process.stdin.write(annotated.tobytes())
                if sampled:
                    _, jpeg = cv2.imencode('.jpg', annotated)
                    key = f'{task_id}-{frame_no}'
                    with self.lock:
                        self.frames[key] = jpeg.tobytes()
                        while len(self.frames) > 20:
                            self.frames.popitem(last=False)
                        self.current['frame'] = {'key': key, 'frame_id': frame_no, 'video_time': timestamp,
                            'duration': video['duration'], 'at': time.time(), 'detections': detections,
                            'count': len(detections), 'inference_ms': round((time.monotonic()-started)*1000)}
                    self.library.samples(task_id, detections, timestamp, frame_no)
                    candidates = gate.update(detections, config['consecutive'])
                    if candidates:
                        capture = f'{key}.jpg'
                        path = self.settings.data_dir / 'captures' / capture
                        path.write_bytes(jpeg.tobytes())
                        created = False
                        for species, values in candidates.items():
                            _, new = self.store.alarm(task_id, species, len(values), max(d['confidence'] for d in values),
                                capture, timestamp, frame_no, config['cooldown'], video_clock=True)
                            created = created or new
                        if not created:
                            path.unlink(missing_ok=True)
                    self.library.progress(task_id, min(99, timestamp / video['duration'] * 100))
                frame_no += 1
                ok, frame = cap.read()
            if self.stop_event.is_set():
                status, message = 'stopped', '已停止分析，已处理部分保留为视频档案'
            process.stdin.close()
            if process.wait(timeout=60) != 0 and frame_no:
                raise RuntimeError('视频编码失败，请检查 encoder.log')
            if frame_no:
                result = output / 'result.mp4'
                # Stream-copy video segments; preserve source audio if available.
                args = [encoder_path(), '-hide_banner', '-loglevel', 'error', '-y', '-i', str(output/'index.m3u8'),
                    '-i', video['path'], '-map', '0:v:0', '-map', '1:a:0?', '-c:v', 'copy', '-c:a', 'aac',
                    '-shortest', '-movflags', '+faststart', str(result)]
                completed = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=log, timeout=120,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if completed.returncode or not result.is_file():
                    raise RuntimeError('结果视频合成失败；已生成片段仍可回看')
                self.library.progress(task_id, 100 if status == 'ended' else min(99, frame_no/fps/video['duration']*100), True)
            self.set_status(status, message)
        except Exception as exc:
            self.set_status('error', f'视频处理失败：{str(exc)[:200]}')
        finally:
            if cap:
                cap.release()
            if process and process.poll() is None:
                if process.stdin and not process.stdin.closed:
                    with contextlib.suppress(OSError):
                        process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
            if log:
                log.close()
