import json
import re
import secrets
import unicodedata
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import date, timedelta

from .security import digest, hash_password, verify_password


class Conflict(Exception):
    pass


def normalize_email(email):
    """邮箱入库统一:去除首尾空白并转小写。"""
    return email.strip().lower()


def display_username(email):
    """注册用户名生成:邮箱前缀清洗为 [a-z0-9_],冲突时追加 _2/_3…。"""
    base = re.sub(r'[^a-z0-9_]', '', normalize_email(email).split('@')[0])[:32] or 'user'
    return base


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
            snapshot TEXT, video_time REAL, frame_id INTEGER, bbox TEXT);
          CREATE TABLE IF NOT EXISTS commands (
            id TEXT PRIMARY KEY, request_id TEXT UNIQUE, alarm_id TEXT REFERENCES alarms(id),
            user_id INTEGER, duration INTEGER, scenario TEXT, status TEXT,
            at REAL, started_at REAL, ended_at REAL, message TEXT, mode TEXT, automatic INTEGER DEFAULT 0);
          CREATE UNIQUE INDEX IF NOT EXISTS one_active_command ON commands((1))
            WHERE status IN ('pending','running');
          CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, ref_id TEXT, at REAL, message TEXT);
          CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, status TEXT, at REAL, ended_at REAL, message TEXT);
          CREATE TABLE IF NOT EXISTS videos (id TEXT PRIMARY KEY, name TEXT, path TEXT, duration REAL, fps REAL, at REAL);
          CREATE TABLE IF NOT EXISTS samples (task_id TEXT, species TEXT, video_time REAL, count INTEGER, confidence REAL, frame_id INTEGER);
          CREATE INDEX IF NOT EXISTS sample_lookup ON samples(task_id,species,video_time);
        ''')
        if 'sha256' not in {r[1] for r in self.db.execute('PRAGMA table_info(videos)')}:
            self.db.execute('ALTER TABLE videos ADD COLUMN sha256 TEXT')
        self.db.execute('CREATE INDEX IF NOT EXISTS video_sha256 ON videos(sha256)')
        columns = {r[1] for r in self.db.execute('PRAGMA table_info(tasks)')}
        for name, kind in [('video_id','TEXT'),('duration','REAL DEFAULT 0'),('progress','REAL DEFAULT 0'),('result_ready','INTEGER DEFAULT 0')]:
            if name not in columns:
                self.db.execute(f'ALTER TABLE tasks ADD COLUMN {name} {kind}')
        if 'last_video_time' not in {r[1] for r in self.db.execute('PRAGMA table_info(alarms)')}:
            self.db.execute('ALTER TABLE alarms ADD COLUMN last_video_time REAL')
        if 'bbox' not in {r[1] for r in self.db.execute('PRAGMA table_info(alarms)')}:
            self.db.execute('ALTER TABLE alarms ADD COLUMN bbox TEXT')
        if 'mode' not in {r[1] for r in self.db.execute('PRAGMA table_info(commands)')}:
            self.db.execute("ALTER TABLE commands ADD COLUMN mode TEXT DEFAULT 'both'")
        if 'automatic' not in {r[1] for r in self.db.execute('PRAGMA table_info(commands)')}:
            self.db.execute('ALTER TABLE commands ADD COLUMN automatic INTEGER DEFAULT 0')
        # 账号体系扩展:users 加列(旧库走 ALTER,种子账号 email/display_name 保持为空)
        user_columns = {r[1] for r in self.db.execute('PRAGMA table_info(users)')}
        for name, kind in [('email', 'TEXT'), ('display_name', 'TEXT'), ('avatar_path', 'TEXT')]:
            if name not in user_columns:
                self.db.execute(f'ALTER TABLE users ADD COLUMN {name} {kind}')
        self.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        self.db.execute('''CREATE TABLE IF NOT EXISTS user_preferences (
          user_id INTEGER PRIMARY KEY REFERENCES users(id),
          theme TEXT NOT NULL DEFAULT 'b1bit')''')
        # 自动哨兵:响应规则(每用户多条) + 定时巡逻(每用户一条)
        self.db.execute('''CREATE TABLE IF NOT EXISTS automation_rules (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL REFERENCES users(id),
          name TEXT NOT NULL,
          trigger TEXT NOT NULL,
          mode TEXT NOT NULL,
          duration INTEGER NOT NULL,
          cooldown_minutes INTEGER NOT NULL DEFAULT 10,
          enabled INTEGER NOT NULL DEFAULT 1,
          last_fired_at REAL,
          created_at REAL NOT NULL)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS patrol_schedules (
          user_id INTEGER PRIMARY KEY REFERENCES users(id),
          enabled INTEGER NOT NULL DEFAULT 0,
          start_minute INTEGER NOT NULL DEFAULT 360,
          end_minute INTEGER NOT NULL DEFAULT 1140,
          interval_minutes INTEGER NOT NULL DEFAULT 120,
          mode TEXT NOT NULL DEFAULT 'acoustic',
          duration INTEGER NOT NULL DEFAULT 3,
          last_fired_at REAL)''')
        self.db.commit()
        with self.tx() as db:
            if not db.execute('SELECT 1 FROM users').fetchone():
                # 显式列名:users 已迁移扩展列,按位置插入会失配
                db.execute('INSERT INTO users (id, username, password) VALUES (1, ?, ?)',
                           (settings.username, hash_password(settings.password)))
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

    def login(self, identifier, password):
        """identifier 支持用户名或邮箱(邮箱统一小写匹配)。"""
        ident = identifier.strip()
        email = normalize_email(ident) if '@' in ident else '\x00not-an-email'
        users = self.rows('SELECT * FROM users WHERE username=? COLLATE NOCASE OR email=?', (ident, email))
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

    # ---- 账号体系:注册 / 资料 / 主题 / 密码 ----

    def create_user(self, email, password):
        """注册新账号;邮箱唯一由唯一索引+前置检查双重保证,用户名自动派生。"""
        email = normalize_email(email)
        with self.tx() as db:
            if db.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
                raise Conflict('该邮箱已注册，请直接登录')
            username = 'user_' + secrets.token_hex(5)
            while db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
                username = 'user_' + secrets.token_hex(5)
            db.execute('INSERT INTO users (username, password, email, display_name) VALUES (?,?,?,?)',
                       (username, hash_password(password), email, '果园用户'))
            user_id = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()[0]
        return self.get_profile(user_id)

    def set_username(self, user_id, username):
        name = unicodedata.normalize('NFKC', username.strip())
        if not 2 <= len(name) <= 20 or not re.fullmatch(r'[A-Za-z0-9_\u4e00-\u9fff]+', name):
            raise ValueError('用户名须为 2–20 个汉字、字母、数字或下划线')
        with self.tx() as db:
            others = db.execute('SELECT username FROM users WHERE id<>?', (user_id,)).fetchall()
            if any(unicodedata.normalize('NFKC', row[0]).casefold() == name.casefold() for row in others):
                raise Conflict('当前名称重复')
            db.execute('UPDATE users SET username=? WHERE id=?', (name, user_id))
        return name

    def get_profile(self, user_id):
        rows = self.rows('''SELECT u.id, u.username, u.email, u.display_name, u.avatar_path,
                            COALESCE(p.theme, 'b1bit') AS theme
                            FROM users u LEFT JOIN user_preferences p ON p.user_id = u.id WHERE u.id=?''', (user_id,))
        return rows[0] if rows else None

    def update_profile(self, user_id, display_name=None, avatar_path=None):
        changes, values = [], []
        if display_name is not None:
            changes.append('display_name=?'); values.append(display_name)
        if avatar_path is not None:
            changes.append('avatar_path=?'); values.append(avatar_path)
        if not changes:
            return
        with self.tx() as db:
            db.execute(f'UPDATE users SET {", ".join(changes)} WHERE id=?', (*values, user_id))

    def set_user_theme(self, user_id, theme):
        with self.tx() as db:
            db.execute('''INSERT INTO user_preferences (user_id, theme) VALUES (?,?)
                          ON CONFLICT(user_id) DO UPDATE SET theme=excluded.theme''', (user_id, theme))

    def set_password(self, user_id, hashed):
        """改密/重置密码:同一事务内吊销该用户全部会话,旧 token/媒体票据/WS 即刻失效。"""
        with self.tx() as db:
            db.execute('UPDATE users SET password=? WHERE id=?', (hashed, user_id))
            db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))

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

    def alarm(self, task_id, species, count, confidence, snapshot, video_time, frame_id, cooldown, now=None, video_clock=False, bbox=None):
        now = now if now is not None else time.time()
        with self.tx() as db:
            old = db.execute('SELECT * FROM alarms WHERE task_id=? AND species=? ORDER BY last_seen DESC LIMIT 1', (task_id, species)).fetchone()
            age = (video_time - (old['last_video_time'] if old['last_video_time'] is not None else old['video_time'])) if old and video_clock else (now - old['last_seen'] if old else cooldown)
            if old and 0 <= age < cooldown:
                # Preserve the original evidence/count; hits tracks repeated detections, not individual birds.
                db.execute('UPDATE alarms SET last_seen=?,last_video_time=?,hits=hits+1 WHERE id=?', (now, video_time, old['id']))
                return old['id'], False
            aid = 'A' + secrets.token_hex(5)
            # bbox 记录的是"本条告警抓拍帧"里的检测框，保证 snapshot 图与框始终成对
            bbox_json = json.dumps(bbox) if bbox else None
            db.execute('INSERT INTO alarms(id,task_id,site,species,count,confidence,at,last_seen,hits,status,snapshot,video_time,frame_id,last_video_time,bbox) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (aid, task_id, '东区 · CAM 01', species, count, confidence, now, now, 1, 'new', snapshot, video_time, frame_id, video_time, bbox_json))
            self.event(db, 'detection', aid, f'检测到{species}，画面中 {count} 只')
            rule = self._match_rules(db, now)
            if rule:
                self._fire_automation(db, rule, aid, now, '自动响应')
            return aid, True

    def ignore(self, alarm_id):
        with self.tx() as db:
            result = db.execute("UPDATE alarms SET status='ignored' WHERE id=? AND status='new'", (alarm_id,))
            if result.rowcount != 1:
                raise Conflict('告警已被处理或不存在，请刷新')
            self.event(db, 'ignored', alarm_id, '人工忽略本次告警')

    def start_command(self, request_id, alarm_id, duration, user_id, mode='both', automatic=False):
        if duration not in (3, 5, 8):
            raise Conflict('执行时长必须为 3、5 或 8 秒')
        if mode not in ('acoustic', 'infrared', 'both'):
            raise Conflict('驱离方式必须是 acoustic、infrared 或 both')
        with self.tx() as db:
            return self._insert_command(db, request_id, alarm_id, duration, user_id, mode, automatic)

    def _insert_command(self, db, request_id, alarm_id, duration, user_id, mode='both', automatic=False):
        """在调用方事务内落一条指令(去重/离线/互斥检查);人工与自动触发共用,保证同一套边界。"""
        old = db.execute('SELECT * FROM commands WHERE request_id=?', (request_id,)).fetchone()
        if old:
            if (old['alarm_id'], old['duration'], old['user_id'], old['mode'], bool(old['automatic'])) != (alarm_id, duration, user_id, mode, bool(automatic)):
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
        db.execute('INSERT INTO commands(id,request_id,alarm_id,user_id,duration,scenario,status,at,started_at,ended_at,message,mode,automatic) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (cid, request_id, alarm_id, user_id, duration, config['scenario'], 'pending', time.time(), None, None, '等待模拟设备接收', mode, int(bool(automatic))))
        source = '自动策略触发' if automatic else '人工确认'
        self.event(db, 'command', cid, f'{source}，指令已入队（模拟设备）')
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

    # ---- 自动哨兵:响应规则 + 定时巡逻 ----

    MODE_CN = {'acoustic': '声波', 'infrared': '红外', 'both': '双模'}
    RULE_FIELDS = ('name', 'trigger', 'mode', 'duration', 'cooldown_minutes', 'enabled')

    def rules(self, user_id):
        return self.rows('SELECT * FROM automation_rules WHERE user_id=? ORDER BY id', (user_id,))

    def create_rule(self, user_id, name, trigger, mode, duration, cooldown_minutes):
        if trigger not in ('alarm_any', 'alarm_burst'):
            raise Conflict('触发条件无效')
        if mode not in self.MODE_CN:
            raise Conflict('驱离方式无效')
        if duration not in (3, 5, 8):
            raise Conflict('执行时长必须为 3、5 或 8 秒')
        with self.tx() as db:
            cur = db.execute('INSERT INTO automation_rules(user_id,name,trigger,mode,duration,cooldown_minutes,enabled,last_fired_at,created_at) VALUES (?,?,?,?,?,?,1,NULL,?)',
                             (user_id, name, trigger, mode, duration, cooldown_minutes, time.time()))
            return dict(db.execute('SELECT * FROM automation_rules WHERE id=?', (cur.lastrowid,)).fetchone())

    def update_rule(self, user_id, rule_id, changes):
        sets = [k for k in self.RULE_FIELDS if k in changes]
        if sets:
            with self.tx() as db:
                cur = db.execute(f'UPDATE automation_rules SET {", ".join(k + "=?" for k in sets)} WHERE id=? AND user_id=?',
                                 (*[changes[k] for k in sets], rule_id, user_id))
                if cur.rowcount != 1:
                    raise Conflict('规则不存在或无权修改')
        rows = self.rows('SELECT * FROM automation_rules WHERE id=? AND user_id=?', (rule_id, user_id))
        if not rows:
            raise Conflict('规则不存在或无权修改')
        return rows[0]

    def delete_rule(self, user_id, rule_id):
        with self.tx() as db:
            cur = db.execute('DELETE FROM automation_rules WHERE id=? AND user_id=?', (rule_id, user_id))
            if cur.rowcount != 1:
                raise Conflict('规则不存在或无权删除')

    def patrol(self, user_id):
        rows = self.rows('SELECT * FROM patrol_schedules WHERE user_id=?', (user_id,))
        if rows:
            return rows[0]
        return {'user_id': user_id, 'enabled': 0, 'start_minute': 360, 'end_minute': 1140,
                'interval_minutes': 120, 'mode': 'acoustic', 'duration': 3, 'last_fired_at': None}

    def set_patrol(self, user_id, changes):
        merged = {k: v for k, v in self.patrol(user_id).items() if k != 'user_id'}
        merged.update(changes)
        if merged['start_minute'] >= merged['end_minute']:
            raise Conflict('巡逻时段无效，需开始早于结束')
        if merged['mode'] not in self.MODE_CN:
            raise Conflict('驱离方式无效')
        if merged['duration'] not in (3, 5, 8):
            raise Conflict('执行时长必须为 3、5 或 8 秒')
        with self.tx() as db:
            db.execute('''INSERT INTO patrol_schedules(user_id,enabled,start_minute,end_minute,interval_minutes,mode,duration,last_fired_at)
                          VALUES (?,?,?,?,?,?,?,?)
                          ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled,
                            start_minute=excluded.start_minute,end_minute=excluded.end_minute,
                            interval_minutes=excluded.interval_minutes,mode=excluded.mode,duration=excluded.duration''',
                       (user_id, int(bool(merged['enabled'])), merged['start_minute'], merged['end_minute'],
                        merged['interval_minutes'], merged['mode'], merged['duration'], merged['last_fired_at']))
        return self.patrol(user_id)

    def _match_rules(self, db, now):
        """挑选当前该触发的首条启用规则;burst 需 10 分钟内 ≥3 报,冷却期内静默跳过。"""
        burst = None
        for rule in db.execute('SELECT * FROM automation_rules WHERE enabled=1 ORDER BY id').fetchall():
            if rule['trigger'] == 'alarm_burst':
                if burst is None:
                    burst = db.execute('SELECT COUNT(*) n FROM alarms WHERE at>=?', (now - 600,)).fetchone()[0]
                if burst < 3:
                    continue
            if rule['last_fired_at'] is not None and now - rule['last_fired_at'] < rule['cooldown_minutes'] * 60:
                continue
            return rule
        return None

    def _fire_automation(self, db, rule, alarm_id, now, source):
        """在当前事务内触发规则;离线/互斥冲突记跳过事件,并同样占用冷却窗口防止事件刷屏。"""
        request_id = f'rule-{rule["id"]}-{alarm_id or int(now)}'
        try:
            c = self._insert_command(db, request_id, alarm_id, rule['duration'], rule['user_id'], rule['mode'], True)
        except Conflict as exc:
            db.execute('UPDATE automation_rules SET last_fired_at=? WHERE id=?', (now, rule['id']))
            self.event(db, 'automation', f'rule-{rule["id"]}', f'{source}未触发：规则「{rule["name"]}」，{exc}')
            return None
        db.execute('UPDATE automation_rules SET last_fired_at=? WHERE id=?', (now, rule['id']))
        self.event(db, 'automation', c['id'], f'{source}：规则「{rule["name"]}」→ {self.MODE_CN[rule["mode"]]} {rule["duration"]} 秒')
        return c

    def automation_tick(self, now=None):
        """worker 循环调用:巡逻窗口内按间隔自动触发;与响应规则共用单指令互斥边界。"""
        now = now if now is not None else time.time()
        if not self.rows('SELECT 1 FROM patrol_schedules WHERE enabled=1 LIMIT 1'):
            return
        local = time.localtime(now)
        cur = local.tm_hour * 60 + local.tm_min
        with self.tx() as db:
            for p in db.execute('SELECT * FROM patrol_schedules WHERE enabled=1').fetchall():
                if not (p['start_minute'] <= cur < p['end_minute']):
                    continue
                if p['last_fired_at'] is not None and now - p['last_fired_at'] < p['interval_minutes'] * 60:
                    continue
                request_id = f'patrol-{p["user_id"]}-{int(now)}'
                try:
                    c = self._insert_command(db, request_id, None, p['duration'], p['user_id'], p['mode'], True)
                    self.event(db, 'automation', c['id'], f'定时巡逻：{self.MODE_CN[p["mode"]]} {p["duration"]} 秒')
                except Conflict as exc:
                    self.event(db, 'automation', f'patrol-{p["user_id"]}', f'定时巡逻未触发：{exc}')
                db.execute('UPDATE patrol_schedules SET last_fired_at=? WHERE user_id=?', (now, p['user_id']))

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

    def stats(self, days):
        """果园数据分析聚合(所有账号共享果园数据,口径见接口文档):

        - 范围:服务器本地时区自然日,含今天,共 days 个日桶;
        - trend = 按天告警事件数(口径=检测告警,非逐帧识别次数),缺失日期补 0;
        - species = 按告警条数 TOP5,不累计鸟只数;
        - task_trend / bird_trend / bird_species = 已归档视频任务及每场各物种峰值之和;
        - hourly = 范围内所有天按小时聚合 24 桶;
        - breakdown = 范围内告警状态分布;
        - exec = 范围内指令统计,平均启动响应=started_at-at、平均完成耗时=ended_at-at
          (仅 status='completed'),无记录时为 null;双模占比分母=范围内已完成指令。
        """
        now = time.time()
        local = time.localtime(now)
        dates = [(date(local.tm_year, local.tm_mon, local.tm_mday) - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
        start_date = dates[0]
        start = time.mktime(time.strptime(start_date, '%Y-%m-%d'))
        date_index = {day: i for i, day in enumerate(dates)}
        trend = [0] * days
        for row in self.rows("SELECT date(at, 'unixepoch', 'localtime') day, COUNT(*) n FROM alarms WHERE at>=? GROUP BY day", (start,)):
            if row['day'] in date_index:
                trend[date_index[row['day']]] = row['n']
        species = self.rows('SELECT species, COUNT(*) count FROM alarms WHERE at>=? GROUP BY species ORDER BY count DESC, species LIMIT 5', (start,))
        task_trend = [0] * days
        bird_trend = [0] * days
        archived = '''FROM tasks t JOIN videos v ON v.id=t.video_id
            WHERE t.result_ready=1 AND t.at>=?'''
        for row in self.rows(f"SELECT date(t.at, 'unixepoch', 'localtime') day, COUNT(*) n {archived} GROUP BY day", (start,)):
            if row['day'] in date_index:
                task_trend[date_index[row['day']]] = row['n']
        peaks = '''FROM (SELECT s.task_id,s.species,MAX(s.count) peak FROM samples s
            JOIN tasks t ON t.id=s.task_id JOIN videos v ON v.id=t.video_id
            WHERE t.result_ready=1 AND t.at>=? GROUP BY s.task_id,s.species) p
            JOIN tasks t ON t.id=p.task_id'''
        for row in self.rows(f"SELECT date(t.at, 'unixepoch', 'localtime') day, SUM(p.peak) n {peaks} GROUP BY day", (start,)):
            if row['day'] in date_index:
                bird_trend[date_index[row['day']]] = row['n']
        bird_species = self.rows(f'SELECT p.species, SUM(p.peak) count {peaks} GROUP BY p.species ORDER BY count DESC,p.species LIMIT 5', (start,))
        hourly = [0] * 24
        for row in self.rows("SELECT CAST(strftime('%H', at, 'unixepoch', 'localtime') AS INTEGER) h, COUNT(*) n FROM alarms WHERE at>=? GROUP BY h", (start,)):
            if 0 <= row['h'] < 24:
                hourly[row['h']] = row['n']
        breakdown = {'new': 0, 'processing': 0, 'handled': 0, 'ignored': 0}
        for row in self.rows('SELECT status, COUNT(*) n FROM alarms WHERE at>=? GROUP BY status', (start,)):
            if row['status'] in breakdown:
                breakdown[row['status']] = row['n']
        commands = self.rows('SELECT status, COUNT(*) n FROM commands WHERE at>=? GROUP BY status', (start,))
        counts = {r['status']: r['n'] for r in commands}
        total = sum(counts.values())
        completed = counts.get('completed', 0)
        failed = counts.get('failed', 0)
        def avg(sql, args=()):
            rows = self.rows(sql, args)
            return round(rows[0]['avg'], 2) if rows and rows[0]['avg'] is not None else None
        avg_start = avg('SELECT AVG(started_at-at) avg FROM commands WHERE at>=? AND started_at IS NOT NULL', (start,))
        avg_done = avg("SELECT AVG(ended_at-at) avg FROM commands WHERE at>=? AND status='completed' AND ended_at IS NOT NULL", (start,))
        dual = self.rows("SELECT COUNT(*) n FROM commands WHERE at>=? AND status='completed' AND mode='both'", (start,))[0]['n']
        return {'range_days': days, 'dates': dates, 'trend': trend, 'species': species, 'hourly': hourly,
                'task_trend': task_trend, 'bird_trend': bird_trend, 'bird_species': bird_species,
                'breakdown': breakdown,
                'exec': {'total': total, 'completed': completed, 'failed': failed,
                         'avg_start_seconds': avg_start, 'avg_done_seconds': avg_done,
                         'dual_share': round(dual / completed, 2) if completed else None}}

    def close(self):
        with self.lock:
            self.db.close()
