"""Persisted video jobs and species indexes; media files are never duplicated per species."""
import hashlib
import secrets
import threading
import time
from pathlib import Path

from .store import Conflict


class VideoLibrary:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.root = settings.data_dir / 'videos'
        self.root.mkdir(exist_ok=True)
        self.jobs = settings.data_dir / 'jobs'
        self.jobs.mkdir(parents=True, exist_ok=True)
        self.previous_result_jobs = settings.data_dir / 'videos' / 'result'
        self.legacy_jobs = settings.data_dir / 'video' / 'result'
        self.upload_lock = threading.Lock()
        self.pending_uploads = set()

    def begin_upload(self, path):
        with self.upload_lock:
            self.pending_uploads.add(path.resolve())

    def end_upload(self, path):
        with self.upload_lock:
            self.pending_uploads.discard(path.resolve())

    def job_dir(self, task_id):
        for root in (self.jobs, self.previous_result_jobs, self.legacy_jobs):
            folder = root / task_id
            if folder.exists():
                return folder
        return self.jobs / task_id

    def already_processed(self, video):
        rows = self.store.rows("""SELECT t.id FROM tasks t JOIN videos v ON v.id=t.video_id
            WHERE t.status='ended' AND t.result_ready=1
              AND (v.id=? OR (v.sha256 IS NOT NULL AND v.sha256=?)) LIMIT 1""",
            (video['id'], video.get('sha256')))
        if rows:
            raise Conflict('该视频已经识别并归档，请在记录中查看结果，无需重复识别')

    @staticmethod
    def file_sha256(path):
        digest = hashlib.sha256()
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    def register(self, path, name, reuse_local_source=False):
        with self.upload_lock:
            return self._register(path, name, reuse_local_source)

    def _register(self, path, name, reuse_local_source):
        import cv2
        cap = cv2.VideoCapture(str(path))
        try:
            fps, frames = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
            ok, frame = cap.read()
            if not ok or frame is None or not 1 <= fps <= 120 or frames < 1:
                raise Conflict('无法读取视频，请选择有效的 MP4、MOV、AVI 或 WebM 文件')
            sha = self.file_sha256(path)
            existing = self.store.rows('SELECT * FROM videos WHERE sha256=? OR path=? ORDER BY at DESC LIMIT 1',
                (sha, str(path.resolve())))
            if existing and Path(existing[0]['path']).is_file():
                return existing[0]
            source_path = path.resolve()
            if reuse_local_source and path.parent.resolve() == self.root.resolve():
                candidates = sorted(self.root.iterdir(), key=lambda item: item.name != name)
                for candidate in candidates:
                    if candidate.resolve() == source_path or candidate.resolve() in self.pending_uploads or not candidate.is_file():
                        continue
                    if candidate.stat().st_size == path.stat().st_size and self.file_sha256(candidate) == sha:
                        source_path = candidate.resolve()
                        break
            video_id = 'V' + secrets.token_hex(8)
            with self.store.tx() as db:
                db.execute('INSERT INTO videos (id,name,path,duration,fps,at,sha256) VALUES (?,?,?,?,?,?,?)',
                    (video_id, name[:160], str(source_path), frames / fps, fps, time.time(), sha))
            return self.video(video_id)
        finally:
            cap.release()

    def video(self, video_id):
        rows = self.store.rows('SELECT * FROM videos WHERE id=?', (video_id,))
        if not rows:
            raise Conflict('视频不存在，请重新选择')
        return rows[0]

    def attach(self, task_id, video):
        with self.store.tx() as db:
            db.execute('UPDATE tasks SET video_id=?,duration=? WHERE id=?', (video['id'], video['duration'], task_id))

    def progress(self, task_id, value, ready=False):
        with self.store.tx() as db:
            db.execute('UPDATE tasks SET progress=?,result_ready=? WHERE id=?', (value, int(ready), task_id))

    def samples(self, task_id, detections, timestamp, frame_id):
        grouped = {}
        for item in detections:
            values = grouped.setdefault(item['species'], [0, 0.0])
            values[0] += 1
            values[1] = max(values[1], item['confidence'])
        with self.store.tx() as db:
            db.executemany('INSERT INTO samples VALUES (?,?,?,?,?,?)',
                [(task_id, species, timestamp, values[0], values[1], frame_id) for species, values in grouped.items()])

    def list(self, species=None, offset=0):
        condition = 'WHERE EXISTS (SELECT 1 FROM samples s WHERE s.task_id=t.id AND s.species=?)' if species else ''
        args = (species, offset) if species else (offset,)
        rows = self.store.rows(f'''SELECT t.*,v.name FROM tasks t JOIN videos v ON v.id=t.video_id
            {condition} ORDER BY t.at DESC LIMIT 30 OFFSET ?''', args)
        for row in rows:
            row['species'] = self.store.rows('SELECT species,MIN(video_time) first_seen,MAX(video_time) last_seen,MAX(count) peak_count FROM samples WHERE task_id=? GROUP BY species', (row['id'],))
        return rows

    def summary(self):
        """记录页统计(一检一记口径):只统计已归档任务(result_ready=1,进行中/失败不计);
        鸟只数 = 各任务各物种的峰值(同帧最多同时出现数)合计,与记录卡「N 种 · M 只」同源,不跨帧累加。"""
        archived = 'WHERE t.result_ready=1'
        tasks_total = self.store.rows(f'SELECT COUNT(*) n FROM tasks t JOIN videos v ON v.id=t.video_id {archived}')[0]['n']
        birds_sql = '''SELECT COALESCE(SUM(peak),0) n FROM (
            SELECT s.task_id, s.species, MAX(s.count) peak FROM samples s
            JOIN tasks t ON t.id=s.task_id {cond} GROUP BY s.task_id, s.species)'''
        birds_total = self.store.rows(birds_sql.format(cond=archived))[0]['n']
        midnight = time.mktime(time.localtime(time.time())[:3] + (0, 0, 0, 0, 0, -1))
        today_tasks = self.store.rows(f'SELECT COUNT(*) n FROM tasks t JOIN videos v ON v.id=t.video_id {archived} AND t.at>=?', (midnight,))[0]['n']
        today_birds = self.store.rows(birds_sql.format(cond=archived + ' AND t.at>=?'), (midnight,))[0]['n']
        return {'tasks_total': tasks_total, 'birds_total': birds_total, 'today_tasks': today_tasks, 'today_birds': today_birds}

    def detail(self, task_id):
        rows = self.store.rows('SELECT t.*,v.name FROM tasks t JOIN videos v ON v.id=t.video_id WHERE t.id=?', (task_id,))
        if not rows:
            raise Conflict('该任务没有视频档案（旧版本记录仅保留抓拍）')
        row = rows[0]
        samples = self.store.rows('SELECT * FROM samples WHERE task_id=? ORDER BY video_time', (task_id,))
        intervals = {}
        for sample in samples:
            spans = intervals.setdefault(sample['species'], [])
            if spans and sample['video_time'] - spans[-1]['end'] <= 1.5:
                spans[-1]['end'] = sample['video_time']
                spans[-1]['peak_count'] = max(spans[-1]['peak_count'], sample['count'])
            else:
                spans.append({'start': sample['video_time'], 'end': sample['video_time'], 'peak_count': sample['count']})
        row['intervals'] = [{'species': species, **span} for species, spans in intervals.items() for span in spans]
        row['species'] = self.store.rows('SELECT species,MIN(video_time) first_seen,MAX(video_time) last_seen,MAX(count) peak_count FROM samples WHERE task_id=? GROUP BY species', (task_id,))
        row['alarms'] = self.store.rows('SELECT * FROM alarms WHERE task_id=? ORDER BY video_time', (task_id,))
        row['stream_ready'] = (self.job_dir(task_id) / 'index.m3u8').exists()
        return row

    def species(self):
        return self.store.rows('''SELECT species,COUNT(DISTINCT task_id) videos,MAX(count) peak_count,
            MIN(video_time) first_seen FROM samples GROUP BY species ORDER BY videos DESC,species''')

    def alarm_groups(self):
        """按鸟类聚合告警，并附上一张代表性抓拍作为分类封面。

        封面优先取该鸟类置信度最高的告警抓拍，供前端分类下拉框展示。
        """
        return self.store.rows(
            """SELECT species,
                      COUNT(*) total,
                      SUM(status='new') pending,
                      (SELECT snapshot FROM alarms a2
                        WHERE a2.species = a1.species AND a2.snapshot IS NOT NULL
                        ORDER BY a2.confidence DESC LIMIT 1) cover,
                      (SELECT confidence FROM alarms a3
                        WHERE a3.species = a1.species
                        ORDER BY a3.confidence DESC LIMIT 1) best_confidence
                 FROM alarms a1
                GROUP BY species
                ORDER BY pending DESC, total DESC""")

