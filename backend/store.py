import json
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager

from .security import digest, hash_password, verify_password


class Conflict(Exception):
    pass


class Store:
    def __init__(self, settings):
        self.lock = threading.RLock()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(settings.data_dir / 'orchard.sqlite3', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          PRAGMA journal_mode=WAL;
          PRAGMA foreign_keys=ON;
          CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT);
          CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, user_id INTEGER, expires REAL);
          CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, value TEXT);
          CREATE TABLE IF NOT EXISTS alarms (
            id TEXT PRIMARY KEY, task_id TEXT, site TEXT, species TEXT, count INTEGER,
            confidence REAL, at REAL, last_seen REAL, hits INTEGER, status TEXT,
            snapshot TEXT, video_time REAL, frame_id INTEGER);
          CREATE TABLE IF NOT EXISTS commands (
            id TEXT PRIMARY KEY, request_id TEXT UNIQUE, alarm_id TEXT REFERENCES alarms(id),
            user_id INTEGER, duration INTEGER, scenario TEXT, status TEXT,
            at REAL, started_at REAL, ended_at REAL, message TEXT);
          CREATE UNIQUE INDEX IF NOT EXISTS one_active_command ON commands((1))
            WHERE status IN ('pending','running');
          CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, ref_id TEXT, at REAL, message TEXT);
          CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, status TEXT, at REAL, ended_at REAL, message TEXT);
          CREATE TABLE IF NOT EXISTS videos (id TEXT PRIMARY KEY, name TEXT, path TEXT, duration REAL, fps REAL, at REAL);
          CREATE TABLE IF NOT EXISTS samples (task_id TEXT, species TEXT, video_time REAL, count INTEGER, confidence REAL, frame_id INTEGER);
          CREATE INDEX IF NOT EXISTS sample_lookup ON samples(task_id,species,video_time);
        ''')
        columns = {r[1] for r in self.db.execute('PRAGMA table_info(tasks)')}
        for name, kind in [('video_id','TEXT'),('duration','REAL DEFAULT 0'),('progress','REAL DEFAULT 0'),('result_ready','INTEGER DEFAULT 0')]:
            if name not in columns:
                self.db.execute(f'ALTER TABLE tasks ADD COLUMN {name} {kind}')
        if 'last_video_time' not in {r[1] for r in self.db.execute('PRAGMA table_info(alarms)')}:
            self.db.execute('ALTER TABLE alarms ADD COLUMN last_video_time REAL')
        self.db.commit()
        with self.tx() as db:
            if not db.execute('SELECT 1 FROM users').fetchone():
                db.execute('INSERT INTO users VALUES (1,?,?)', (settings.username, hash_password(settings.password)))
            defaults = {'scenario': 'normal', 'confidence': settings.confidence,
                        'consecutive': settings.consecutive, 'cooldown': settings.cooldown}
            db.execute('INSERT OR IGNORE INTO settings VALUES (1,?)', (json.dumps(defaults),))
        self.recover()

    @contextmanager
    def tx(self):
        with self.lock:
            try:
                self.db.execute('BEGIN IMMEDIATE')
                yield self.db
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def rows(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def event(self, db, kind, ref_id, message):
        db.execute('INSERT INTO events(kind,ref_id,at,message) VALUES (?,?,?,?)',
                   (kind, ref_id, time.time(), message))

    def recover(self):
        with self.tx() as db:
            for c in db.execute("SELECT * FROM commands WHERE status IN ('pending','running')").fetchall():
                self._finish(db, c, 'unknown', '服务中断，执行结果未知；不会自动重放')
            db.execute("UPDATE tasks SET status='interrupted',ended_at=?,message='服务重启，需手动重新开始' WHERE status IN ('starting','running','stopping')", (time.time(),))

    def login(self, username, password):
        users = self.rows('SELECT * FROM users WHERE username=?', (username,))
        if not users or not verify_password(password, users[0]['password']):
            return None
        token = secrets.token_urlsafe(32)
        with self.tx() as db:
            db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES (?,?,?)', (digest(token), users[0]['id'], time.time() + 86400))
        return token

    def session(self, session_id):
        rows = self.rows('SELECT user_id FROM sessions WHERE id=? AND expires>?', (session_id, time.time()))
        return rows[0]['user_id'] if rows else None

    def logout(self, session_id):
        with self.tx() as db:
            db.execute('DELETE FROM sessions WHERE id=?', (session_id,))

    def config(self):
        return json.loads(self.rows('SELECT value FROM settings WHERE id=1')[0]['value'])

    def configure(self, changes):
        with self.tx() as db:
            if db.execute("SELECT 1 FROM commands WHERE status IN ('pending','running')").fetchone():
                raise Conflict('执行期间不能切换演示参数')
            config = json.loads(db.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])
            config.update(changes)
            db.execute('UPDATE settings SET value=? WHERE id=1', (json.dumps(config),))
        return config

    def alarm(self, task_id, species, count, confidence, snapshot, video_time, frame_id, cooldown, now=None, video_clock=False):
        now = now if now is not None else time.time()
        with self.tx() as db:
            old = db.execute('SELECT * FROM alarms WHERE task_id=? AND species=? ORDER BY last_seen DESC LIMIT 1', (task_id, species)).fetchone()
            age = (video_time - (old['last_video_time'] if old['last_video_time'] is not None else old['video_time'])) if old and video_clock else (now - old['last_seen'] if old else cooldown)
            if old and 0 <= age < cooldown:
                # Preserve the original evidence/count; hits tracks repeated detections, not individual birds.
                db.execute('UPDATE alarms SET last_seen=?,last_video_time=?,hits=hits+1 WHERE id=?', (now, video_time, old['id']))
                return old['id'], False
            aid = 'A' + secrets.token_hex(5)
            db.execute('INSERT INTO alarms(id,task_id,site,species,count,confidence,at,last_seen,hits,status,snapshot,video_time,frame_id,last_video_time) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (aid, task_id, '东区 · CAM 01', species, count, confidence, now, now, 1, 'new', snapshot, video_time, frame_id, video_time))
            self.event(db, 'detection', aid, f'检测到{species}，画面中 {count} 只')
            return aid, True

    def ignore(self, alarm_id):
        with self.tx() as db:
            result = db.execute("UPDATE alarms SET status='ignored' WHERE id=? AND status='new'", (alarm_id,))
            if result.rowcount != 1:
                raise Conflict('告警已被处理或不存在，请刷新')
            self.event(db, 'ignored', alarm_id, '人工忽略本次告警')

    def start_command(self, request_id, alarm_id, duration, user_id):
        if duration not in (3, 5, 8):
            raise Conflict('执行时长必须为 3、5 或 8 秒')
        with self.tx() as db:
            old = db.execute('SELECT * FROM commands WHERE request_id=?', (request_id,)).fetchone()
            if old:
                if (old['alarm_id'], old['duration'], old['user_id']) != (alarm_id, duration, user_id):
                    raise Conflict('重复请求的内容不一致')
                return dict(old)
            config = json.loads(db.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])
            if config['scenario'] == 'offline':
                raise Conflict('模拟设备离线，未下发指令')
            if db.execute("SELECT 1 FROM commands WHERE status IN ('pending','running')").fetchone():
                raise Conflict('已有执行中的指令，请等待或停止')
            if alarm_id:
                a = db.execute('SELECT * FROM alarms WHERE id=?', (alarm_id,)).fetchone()
                if not a or a['status'] != 'new':
                    raise Conflict('关联告警已被处理或不存在')
                db.execute("UPDATE alarms SET status='processing' WHERE id=?", (alarm_id,))
            cid = 'C' + secrets.token_hex(5)
            db.execute('INSERT INTO commands VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (cid, request_id, alarm_id, user_id, duration, config['scenario'], 'pending', time.time(), None, None, '等待模拟设备接收'))
            self.event(db, 'command', cid, '人工确认，指令已入队（模拟设备）')
            return dict(db.execute('SELECT * FROM commands WHERE id=?', (cid,)).fetchone())

    def _finish(self, db, command, status, message):
        db.execute('UPDATE commands SET status=?,ended_at=?,message=? WHERE id=?', (status, time.time(), message, command['id']))
        if command['alarm_id']:
            db.execute('UPDATE alarms SET status=? WHERE id=?', ('handled' if status == 'completed' else 'new', command['alarm_id']))
        self.event(db, status, command['id'], message)

    def stop_command(self, cid):
        with self.tx() as db:
            c = db.execute('SELECT * FROM commands WHERE id=?', (cid,)).fetchone()
            if not c:
                raise Conflict('指令不存在')
            if c['status'] in ('pending', 'running'):
                self._finish(db, c, 'cancelled', '模拟执行器已确认停止')
        return self.rows('SELECT * FROM commands WHERE id=?', (cid,))[0]

    def tick(self, now=None):
        now = now if now is not None else time.time()
        with self.tx() as db:
            for c in db.execute("SELECT * FROM commands WHERE status IN ('pending','running')").fetchall():
                if c['status'] == 'pending':
                    db.execute("UPDATE commands SET status='running',started_at=?,message='模拟设备已接收，正在执行' WHERE id=?", (now, c['id']))
                    self.event(db, 'running', c['id'], '模拟设备开始执行')
                elif now - c['started_at'] >= c['duration']:
                    timeout = c['scenario'] == 'timeout'
                    self._finish(db, c, 'failed' if timeout else 'completed',
                                 '执行超时，未收到模拟完成回执' if timeout else '模拟完成回执已收到；不代表实际驱鸟效果')

    def task(self, task_id, status, message=''):
        with self.tx() as db:
            db.execute('INSERT OR IGNORE INTO tasks(id,status,at,ended_at,message) VALUES (?,?,?,?,?)', (task_id, status, time.time(), None, message))
            db.execute('UPDATE tasks SET status=?,message=?,ended_at=? WHERE id=?',
                       (status, message, None if status in ('starting', 'running', 'stopping') else time.time(), task_id))

    def snapshot(self):
        with self.lock:
            alarms = self.rows('SELECT * FROM alarms ORDER BY at DESC LIMIT 100')
            commands = self.rows('SELECT * FROM commands ORDER BY at DESC LIMIT 100')
            events = self.rows('SELECT * FROM events ORDER BY id DESC LIMIT 100')
            counts = self.rows("SELECT COUNT(*) total,SUM(status='new') pending FROM alarms")[0]
            counts['completed'] = self.rows("SELECT COUNT(*) n FROM commands WHERE status='completed'")[0]['n']
            counts['pending'] = counts['pending'] or 0
            return {'alarms': alarms, 'commands': commands, 'events': events, 'counts': counts, 'settings': self.config()}

    def close(self):
        with self.lock:
            self.db.close()
