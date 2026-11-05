"""Persisted video jobs and species indexes; media files are never duplicated per species."""
import secrets
import time

from .store import Conflict


class VideoLibrary:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.root = settings.data_dir / 'videos'
        self.root.mkdir(exist_ok=True)
        self.jobs = settings.data_dir / 'jobs'
        self.jobs.mkdir(exist_ok=True)

    def register(self, path, name):
        import cv2
        cap = cv2.VideoCapture(str(path))
        try:
            fps, frames = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
            ok, frame = cap.read()
            if not ok or frame is None or not 1 <= fps <= 120 or frames < 1:
                raise Conflict('无法读取视频，请选择有效的 MP4、MOV、AVI 或 WebM 文件')
            video_id = 'V' + secrets.token_hex(8)
            with self.store.tx() as db:
                db.execute('INSERT INTO videos VALUES (?,?,?,?,?,?)', (video_id, name[:160], str(path.resolve()), frames / fps, fps, time.time()))
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
        row['alarms'] = self.store.rows('SELECT * FROM alarms WHERE task_id=? ORDER BY video_time', (task_id,))
        row['stream_ready'] = (self.jobs / task_id / 'index.m3u8').exists()
        return row

    def species(self):
        return self.store.rows('''SELECT species,COUNT(DISTINCT task_id) videos,MAX(count) peak_count,
            MIN(video_time) first_seen FROM samples GROUP BY species ORDER BY videos DESC,species''')

    def alarm_groups(self):
        return self.store.rows("SELECT species,COUNT(*) total,SUM(status='new') pending FROM alarms GROUP BY species ORDER BY pending DESC,total DESC")
