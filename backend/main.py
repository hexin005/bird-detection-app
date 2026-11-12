import asyncio
import contextlib
import json
import os
import re
import threading
import time
import secrets
from urllib.parse import unquote
from contextlib import asynccontextmanager
from typing import Literal, Optional

import cv2
import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import assistant as assistant_mod
from .config import ROOT, Settings
from .detector import NAMES
from .emailer import MailSendError, send_code_mail
from .video_pipeline import VideoPipeline, build_task_summary
from .security import check_media, digest, hash_password, media_ticket, verify_password
from .store import Conflict, Store, normalize_email
from .verification import RateLimited, VerificationService


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=200)


class Command(BaseModel):
    request_id: str = Field(min_length=8, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    alarm_id: Optional[str] = None
    duration: Literal[3, 5, 8] = 3
    mode: Literal['acoustic', 'infrared', 'both'] = 'both'
    automatic: bool = False


class AssistantHistory(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=2000)


class AssistantAsk(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    history: list[AssistantHistory] = Field(default_factory=list)


class Preferences(BaseModel):
    scenario: Literal['normal', 'offline', 'timeout']
    confidence: float = Field(ge=.1, le=.95)
    consecutive: int = Field(ge=1, le=10)
    cooldown: float = Field(ge=1, le=300)


class StartVideo(BaseModel):
    video_id: Optional[str] = None


class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    trigger: Literal['alarm_any', 'alarm_burst']
    mode: Literal['acoustic', 'infrared', 'both']
    duration: Literal[3, 5, 8]
    cooldown_minutes: int = Field(default=10, ge=1, le=720)


class RulePatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    trigger: Optional[Literal['alarm_any', 'alarm_burst']] = None
    mode: Optional[Literal['acoustic', 'infrared', 'both']] = None
    duration: Optional[Literal[3, 5, 8]] = None
    cooldown_minutes: Optional[int] = Field(default=None, ge=1, le=720)
    enabled: Optional[bool] = None


class PatrolIn(BaseModel):
    enabled: Optional[bool] = None
    start_minute: Optional[int] = Field(default=None, ge=0, le=1439)
    end_minute: Optional[int] = Field(default=None, ge=1, le=1440)
    interval_minutes: Optional[int] = Field(default=None, ge=5, le=720)
    mode: Optional[Literal['acoustic', 'infrared', 'both']] = None
    duration: Optional[Literal[3, 5, 8]] = None


EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
THEME_IDS = ('b1bit', 'tower', 'signal', 'pixel')
AVATAR_MAX_BYTES = 2 * 1024 * 1024
AVATAR_MAX_PIXELS = 4096


def parse_email(value):
    email = normalize_email(value)
    if not EMAIL_PATTERN.match(email) or len(email) > 254:
        raise HTTPException(422, '邮箱格式不正确')
    return email


class SendCode(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    purpose: Literal['register', 'reset']


class RegisterPayload(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=6, pattern=r'^\d{6}$')
    password: str = Field(min_length=8, max_length=200)


class ResetPayload(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=6, pattern=r'^\d{6}$')
    password: str = Field(min_length=8, max_length=200)


class ChangePassword(BaseModel):
    old_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class DisplayName(BaseModel):
    display_name: str = Field(min_length=1, max_length=32)


class UsernameChange(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class ThemePref(BaseModel):
    theme: Literal['b1bit', 'tower', 'signal', 'pixel']


def _reencode_avatar(data):
    """头像真实校验与重编码:cv2 解码拒绝伪装/空文件,限像素尺寸,统一转 JPG。

    已知限制:cv2 不处理 EXIF 方向;主流手机浏览器上传时已自动转正。
    """
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(415, '仅支持 JPG / PNG / WebP 图片')
    height, width = image.shape[:2]
    if max(height, width) > AVATAR_MAX_PIXELS:
        raise HTTPException(413, '图片像素过大，请缩小后再上传')
    ok, buffer = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise HTTPException(500, '头像处理失败，请重试')
    return buffer.tobytes()


def _detect_birds(monitor, store, frame):
    """单帧 YOLO 推理:返回 [(物种中文名, 置信度)] 去重后按置信度降序,最多 3 个。

    模型懒加载与检测线程共用同一实例(重复加载会双倍占内存);加载在 monitor.lock 内,
    推理同锁执行——检测线程仅在状态更新时短暂取锁,不会造成长阻塞。
    识别结果只作检索候选,物种鉴定语义由【图片识别】块声明。
    """
    with monitor.lock:
        if monitor.model is None:
            config_dir = monitor.settings.data_dir / 'yolo'
            config_dir.mkdir(exist_ok=True)
            os.environ['YOLO_CONFIG_DIR'] = str(config_dir)
            from ultralytics import YOLO
            monitor.model = YOLO(str(monitor.settings.model_path))
        conf_threshold = store.config()['confidence']
        result = monitor.model.predict(frame, conf=conf_threshold, imgsz=640,
                                       device=monitor.settings.device, verbose=False)[0]
    found = {}
    for box in result.boxes:
        label = monitor.model.names[int(box.cls[0])]
        species = NAMES.get(label, label)
        conf = float(box.conf[0])
        if species not in found or conf > found[species]:
            found[species] = conf
    return sorted(found.items(), key=lambda kv: -kv[1])[:3]


def create_app(settings=None):
    settings = settings or Settings.load()
    store = Store(settings)
    store.recover()
    monitor = VideoPipeline(settings, store)
    species_dir = settings.data_dir / 'species'
    species_dir.mkdir(parents=True, exist_ok=True)
    species_names = frozenset(NAMES.values())
    image_types = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}
    for species_name in species_names:
        (species_dir / species_name).mkdir(exist_ok=True)

    def species_image(name: str):
        if name not in species_names:
            return None
        folder = species_dir / name
        if folder.is_dir() and folder.resolve().parent == species_dir.resolve():
            for path in sorted(folder.iterdir()):
                if path.suffix.lower() in image_types and path.is_file() and path.resolve().parent == folder.resolve():
                    return path
        for suffix in image_types:
            path = species_dir / (name + suffix)
            if path.is_file() and path.resolve().parent == species_dir.resolve():
                return path
        return None

    verification = VerificationService()
    shutdown = threading.Event()

    def worker():
        while not shutdown.wait(.1):
            store.tick()
            store.automation_tick()

    @asynccontextmanager
    async def lifespan(app):
        thread = threading.Thread(target=worker, daemon=True, name='simulated-executor')
        if settings.worker_enabled:
            thread.start()
        yield
        shutdown.set()
        if thread.is_alive():
            thread.join()
        monitor.close()
        store.recover()
        store.close()

    app = FastAPI(title='青禾果园守护 MVP', lifespan=lifespan)
    app.state.store, app.state.monitor, app.state.verification = store, monitor, verification
    app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5178', 'http://localhost:5178'],
                       allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Authorization', 'Content-Type', 'X-Filename'])

    @app.exception_handler(Conflict)
    async def conflict(_, exc):
        return JSONResponse(status_code=409, content={'detail': str(exc)})

    def auth(authorization: str = Header(default='')):
        if not authorization.startswith('Bearer '):
            raise HTTPException(401, '请先登录')
        sid = digest(authorization[7:])
        user = store.session(sid)
        if not user:
            raise HTTPException(401, '登录已过期，请重新登录')
        return sid, user

    def media_auth(ticket: str = Query(default='')):
        sid = check_media(ticket, settings.secret)
        if not sid or not store.session(sid):
            raise HTTPException(401, '画面授权已过期')
        return sid

    def uid_of_sid(sid):
        rows = store.rows('SELECT user_id FROM sessions WHERE id=?', (sid,))
        return rows[0]['user_id'] if rows else None

    def last_task_of(uid):
        """最近一次已归档任务(按账号),重建与快照同构的汇总;替代仅存内存的 monitor.last_task。"""
        if uid is None:
            return None
        rows = store.rows("SELECT id,status FROM tasks WHERE user_id=? AND status IN ('ended','stopped') AND result_ready=1 ORDER BY ended_at DESC LIMIT 1", (uid,))
        return build_task_summary(store, rows[0]['id'], rows[0]['status']) if rows else None

    def snapshot(sid):
        uid = uid_of_sid(sid)
        return {**store.snapshot(uid), 'monitor': monitor.snapshot(uid), 'server_time': time.time(),
                'media_ticket': media_ticket(sid, settings.secret), 'simulated_device': True,
                'last_task': last_task_of(uid)}

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'version': '0.2.0'}

    @app.post('/api/login')
    def login(body: Login):
        token = store.login(body.username, body.password)
        if not token:
            raise HTTPException(401, '账号或密码错误')
        return {'token': token, 'username': body.username}

    @app.post('/api/logout')
    def logout(user=Depends(auth)):
        store.logout(user[0])
        return {'ok': True}

    # ---- 账号体系:注册 / 找回 / 资料 / 头像 / 主题 ----
    # 产品边界:同一个演示果园的多个账号,果园数据(告警/指令/视频)共享,
    # 个人资料、主题偏好独立;统计分析覆盖整个果园。

    @app.post('/api/auth/send-code')
    def auth_send_code(body: SendCode):
        email = parse_email(body.email)
        if body.purpose == 'reset':
            if not store.rows('SELECT id FROM users WHERE email=?', (email,)):
                raise HTTPException(404, '该邮箱未绑定任何账号')
        try:
            code = verification.issue(email, body.purpose)
        except RateLimited as exc:
            raise HTTPException(429, str(exc))
        try:
            demo = send_code_mail(settings, email, code, body.purpose)
        except MailSendError as exc:
            raise HTTPException(502, str(exc))
        return {'sent': True, 'demo': demo, **({'demo_code': code} if demo else {})}

    @app.post('/api/auth/register')
    def auth_register(body: RegisterPayload):
        email = parse_email(body.email)
        if store.rows('SELECT 1 FROM users WHERE email=?', (email,)):
            raise HTTPException(409, '该邮箱已注册，请直接登录')
        if not verification.verify(email, 'register', body.code):
            raise HTTPException(400, '验证码错误或已过期')
        try:
            user = store.create_user(email, body.password)
        except Conflict as exc:
            raise HTTPException(409, str(exc))  # 并发注册兜底(唯一索引)
        token = store.login(email, body.password)
        return {'token': token, 'username': user['username'], 'display_name': user['display_name']}

    @app.post('/api/auth/reset')
    def auth_reset(body: ResetPayload):
        email = parse_email(body.email)
        if not verification.verify(email, 'reset', body.code):
            raise HTTPException(400, '验证码错误或已过期')
        rows = store.rows('SELECT id FROM users WHERE email=?', (email,))
        if not rows:
            raise HTTPException(404, '该邮箱未绑定任何账号')
        store.set_password(rows[0]['id'], hash_password(body.password))
        return {'ok': True}

    @app.post('/api/password/change')
    def change_password(body: ChangePassword, user=Depends(auth)):
        rows = store.rows('SELECT password FROM users WHERE id=?', (user[1],))
        if not rows or not verify_password(body.old_password, rows[0]['password']):
            raise HTTPException(400, '当前密码不正确')
        # 同事务改密并吊销该用户全部会话(含当前),前端收到后跳转登录页
        store.set_password(user[1], hash_password(body.new_password))
        return {'ok': True, 'relogin': True}

    @app.get('/api/me')
    def me(user=Depends(auth)):
        profile = store.get_profile(user[1])
        if not profile:
            raise HTTPException(401, '登录已过期，请重新登录')
        avatar = profile['avatar_path']
        return {'username': profile['username'],
                'display_name': profile['display_name'] or profile['username'],
                'email': profile['email'],
                'avatar': ('/api/avatars/' + avatar) if avatar else None,
                'theme': profile['theme'] or 'b1bit'}

    @app.put('/api/me')
    def update_me(body: DisplayName, user=Depends(auth)):
        name = body.display_name.strip()
        store.update_profile(user[1], display_name=name)
        return {'ok': True, 'display_name': name}

    @app.put('/api/me/username')
    def update_username(body: UsernameChange, user=Depends(auth)):
        try:
            name = store.set_username(user[1], body.username)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return {'ok': True, 'username': name}

    @app.put('/api/me/preferences')
    def update_my_preferences(body: ThemePref, user=Depends(auth)):
        store.set_user_theme(user[1], body.theme)
        return {'ok': True, 'theme': body.theme}

    # ---- 自动哨兵:响应规则 / 定时巡逻 ----

    @app.get('/api/automation/rules')
    def automation_rules(user=Depends(auth)):
        return {'items': store.rules(user[1])}

    @app.post('/api/automation/rules')
    def create_automation_rule(body: RuleIn, user=Depends(auth)):
        return store.create_rule(user[1], body.name.strip(), body.trigger, body.mode, body.duration, body.cooldown_minutes)

    @app.put('/api/automation/rules/{rule_id}')
    def update_automation_rule(rule_id: int, body: RulePatch, user=Depends(auth)):
        changes = {k: v for k, v in body.model_dump().items() if v is not None}
        return store.update_rule(user[1], rule_id, changes)

    @app.delete('/api/automation/rules/{rule_id}')
    def delete_automation_rule(rule_id: int, user=Depends(auth)):
        store.delete_rule(user[1], rule_id)
        return {'ok': True}

    @app.get('/api/automation/patrol')
    def automation_patrol(user=Depends(auth)):
        return store.patrol(user[1])

    @app.put('/api/automation/patrol')
    def update_automation_patrol(body: PatrolIn, user=Depends(auth)):
        changes = {k: v for k, v in body.model_dump().items() if v is not None}
        return store.set_patrol(user[1], changes)

    @app.post('/api/avatar')
    async def upload_avatar(request: Request, user=Depends(auth)):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > AVATAR_MAX_BYTES:
                raise HTTPException(413, '头像不能超过 2 MB')
        if not data:
            raise HTTPException(400, '请选择图片文件')
        payload = await run_in_threadpool(_reencode_avatar, bytes(data))
        avatars_dir = settings.data_dir / 'avatars'
        avatars_dir.mkdir(parents=True, exist_ok=True)
        name = f"{user[1]}-{int(time.time())}.jpg"
        target = avatars_dir / name
        staging = avatars_dir / (name + '.part')
        staging.write_bytes(payload)
        staging.replace(target)  # 原子替换,失败不留半截文件
        previous = store.rows('SELECT avatar_path FROM users WHERE id=?', (user[1],))[0]['avatar_path']
        store.update_profile(user[1], avatar_path=name)
        if previous and previous != name:  # 同秒重传时新旧同名,不能误删新文件
            old_path = (avatars_dir / previous).resolve()
            if old_path.parent == avatars_dir.resolve():
                old_path.unlink(missing_ok=True)
        return {'ok': True, 'avatar': '/api/avatars/' + name}

    @app.get('/api/avatars/{name}', dependencies=[Depends(media_auth)])
    def avatar_file(name: str):
        folder = (settings.data_dir / 'avatars').resolve()
        path = (folder / name).resolve()
        if path.parent != folder or not path.is_file():
            raise HTTPException(404, '头像不存在')
        return FileResponse(path, media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=300'})

    @app.get('/api/stats')
    def statistics(scope: Literal['today', '7d', '30d'] = Query('7d', alias='range'), user=Depends(auth)):
        """果园数据分析聚合(口径见 store.stats);按账号作用域,只统计本人数据。"""
        return store.stats({'today': 1, '7d': 7, '30d': 30}[scope], user[1])

    @app.get('/api/state')
    def state(user=Depends(auth)):
        return snapshot(user[0])

    @app.get('/api/history')
    def history(kind: Literal['alarms', 'commands', 'events'], offset: int = Query(0, ge=0), before: Optional[int] = None, user=Depends(auth)):
        order = 'id' if kind == 'events' else 'at'
        scope = 'AND user_id=?'
        if kind == 'events' and before is not None:
            return {'items': store.rows(f'SELECT * FROM events WHERE id<? {scope} ORDER BY id DESC LIMIT 100', (before, user[1]))}
        return {'items': store.rows(f'SELECT * FROM {kind} WHERE 1=1 {scope} ORDER BY {order} DESC LIMIT 100 OFFSET ?', (user[1], offset))}

    @app.get('/api/detail/{kind}/{record_id}')
    def detail(kind: Literal['alarms', 'commands'], record_id: str, user=Depends(auth)):
        rows = store.rows(f'SELECT * FROM {kind} WHERE id=?', (record_id,))
        if not rows or (rows[0]['user_id'] is not None and rows[0]['user_id'] != user[1]):
            raise HTTPException(404, '记录不存在')
        return rows[0]

    @app.post('/api/monitor/start')
    def start(body: Optional[StartVideo] = None, user=Depends(auth)):
        return monitor.start(body.video_id if body else None, user[1])

    @app.post('/api/videos')
    async def upload(request: Request, x_filename: str = Header(default='video.mp4'), user=Depends(auth)):
        name = unquote(x_filename).replace('\\', '/').split('/')[-1][:160]
        suffix = name.rsplit('.', 1)[-1].lower()
        if suffix not in ('mp4', 'mov', 'avi', 'webm', 'mkv'):
            raise HTTPException(415, '请选择 MP4、MOV、AVI、MKV 或 WebM 视频')
        target = monitor.library.root / (secrets.token_hex(16) + '.' + suffix)
        size = 0
        monitor.library.begin_upload(target)
        try:
            with target.open('wb') as output:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 500 * 1024 * 1024:
                        raise HTTPException(413, '视频不能超过 500 MB')
                    output.write(chunk)
            video = await run_in_threadpool(monitor.library.register, target, name, True, user[1])
            if video['path'] != str(target.resolve()):
                target.unlink(missing_ok=True)
            return {key: value for key, value in video.items() if key != 'path'}
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        finally:
            monitor.library.end_upload(target)

    @app.get('/api/videos')
    def videos(user=Depends(auth)):
        return {'items': store.rows('SELECT id,name,duration,fps,at FROM videos WHERE user_id=? ORDER BY at DESC LIMIT 30', (user[1],))}

    @app.get('/api/library')
    def library(species: Optional[str] = None, offset: int = Query(0, ge=0), user=Depends(auth)):
        return {'items': monitor.library.list(species, offset, user[1]), 'species': monitor.library.species(user[1]),
                'alarm_groups': monitor.library.alarm_groups(user[1]),
                'guide_images': [name for name in species_names if species_image(name)]}

    @app.get('/api/species-images/{name}', dependencies=[Depends(media_auth)])
    def guide_image(name: str):
        path = species_image(name)
        if path is None:
            raise HTTPException(404, '图鉴图片不存在')
        return FileResponse(path, media_type=image_types[path.suffix.lower()], headers={'Cache-Control': 'no-store'})

    # 注意:必须先于 /api/library/{task_id} 声明,否则 'summary' 会被路径参数捕获
    @app.get('/api/library/summary')
    def library_summary(user=Depends(auth)):
        """记录页统计:今日/累计的检测场次与发现鸟数(口径=已归档任务,鸟数=各场峰值合计)。"""
        return monitor.library.summary(user[1])

    @app.get('/api/library/{task_id}')
    def video_detail(task_id: str, user=Depends(auth)):
        row = monitor.library.detail(task_id)
        if row.get('user_id') is not None and row['user_id'] != user[1]:
            raise HTTPException(404, '记录不存在')
        return row

    def knowledge_items(user_id=None):
        """知识行 + 本园记录:聚合直接复用 /api/library 同源数据(alarm_groups/species),
        列表与详情共用本函数,统计口径必然一致;统计按账号作用域,知识卡本体全局共享。"""
        hours = store.knowledge_hours(user_id)
        alarm_map = {r['species']: r for r in monitor.library.alarm_groups(user_id)}
        sample_map = {r['species']: r for r in monitor.library.species(user_id)}
        last_seen_rows = (store.rows('SELECT species, MAX(at) last_seen FROM alarms WHERE user_id=? GROUP BY species', (user_id,))
                          if user_id is not None else
                          store.rows('SELECT species, MAX(at) last_seen FROM alarms GROUP BY species'))
        last_seen = {r['species']: r['last_seen'] for r in last_seen_rows}
        items = []
        for row in store.knowledge_rows():
            a, s = alarm_map.get(row['name'], {}), sample_map.get(row['name'], {})
            items.append({**row, 'records': {
                'total': a.get('total', 0), 'pending': a.get('pending', 0) or 0,
                'last_seen': last_seen.get(row['name']),
                'cover': a.get('cover'), 'best_confidence': a.get('best_confidence'),
                'videos': s.get('videos', 0), 'peak_count': s.get('peak_count', 0),
                'first_seen': s.get('first_seen'),
                'hour_buckets': hours.get(row['name'], [0] * 24),
            }})
        return items

    @app.get('/api/knowledge')
    def knowledge_list(user=Depends(auth)):
        return {'items': knowledge_items(user[1]),
                'guide_images': [name for name in species_names if species_image(name)]}

    @app.get('/api/knowledge/{name}')
    def knowledge_detail(name: str, user=Depends(auth)):
        for item in knowledge_items(user[1]):
            if item['name'] == name:
                return item
        raise HTTPException(404, '知识卡不存在')

    @app.get('/api/assistant/status')
    def assistant_status(user=Depends(auth)):
        """前端打开聊天即查;configured=False 时前端展示配置引导并禁用发送。"""
        return {'configured': bool(settings.deepseek_key), 'model': settings.deepseek_model}

    def _assistant_stream(messages, refs):
        """SSE 流式响应(文本/图片提问共用):meta(参考资料) → delta* → done;AI 只读,不触达设备接口。"""
        def sse(obj) -> str:
            return 'data: ' + json.dumps(obj, ensure_ascii=False) + '\n\n'

        async def events():
            sent_delta = False
            try:
                yield sse({'type': 'meta', 'refs': refs})
                try:
                    async for delta in assistant_mod.stream_answer(messages, settings):
                        sent_delta = True
                        yield sse({'type': 'delta', 'text': delta})
                    yield sse({'type': 'done'})
                except assistant_mod.AssistantError as exc:
                    yield sse({'type': 'error', 'detail': str(exc)})
                except Exception:
                    note = '回答已中断' + ('（已生成的部分保留）' if sent_delta else '')
                    yield sse({'type': 'error', 'detail': note})
            finally:
                assistant_mod.IN_FLIGHT.release()

        return StreamingResponse(events(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

    @app.post('/api/assistant/chat')
    async def assistant_chat(body: AssistantAsk, user=Depends(auth)):
        """SSE 流式问答:meta(参考资料) → delta* → done;AI 只读,不触达设备接口。"""
        if not assistant_mod.IN_FLIGHT.acquire():
            raise HTTPException(409, '上一条回答仍在生成，请稍候')
        blocks, refs = assistant_mod.retrieve(body.question, store, user[1])
        messages = assistant_mod.build_messages(body.question, blocks,
                                                [item.model_dump() for item in body.history])
        return _assistant_stream(messages, refs)

    @app.post('/api/assistant/chat-image')
    async def assistant_chat_image(request: Request, question: str = '', user=Depends(auth)):
        """图片提问:YOLO 识别图中鸟类 → 识别结果并入检索词取知识卡 → 同一 SSE 流程作答。

        图片走请求体原始字节(与头像上传同款约定,免 multipart 依赖),question 走 query。
        识别结果是检索候选而非鉴定结论:由【图片识别】块与系统提示词双重声明,不写死结论。
        """
        data = await request.body()
        if not data:
            raise HTTPException(400, '未收到图片')
        if len(data) > 8 * 1024 * 1024:
            raise HTTPException(413, '图片不能超过 8 MB')
        frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(415, '仅支持 JPG / PNG / WebP 图片')
        detections = await run_in_threadpool(_detect_birds, monitor, store, frame)
        q = (question or '').strip() or '这是什么鸟？该怎么处理？'
        if not assistant_mod.IN_FLIGHT.acquire():
            raise HTTPException(409, '上一条回答仍在生成，请稍候')
        names = ' '.join(name for name, _ in detections)
        # 识别物种并入检索词:命中知识卡走既有一对多别名/名称匹配,统计意图词不受影响
        blocks, refs = assistant_mod.retrieve((q + ' ' + names).strip(), store, user[1])
        if detections:
            detail = '、'.join(f'{name}(置信度{int(conf * 100)}%)' for name, conf in detections)
            blocks.insert(0, '【图片识别】用户上传的图片经 YOLO 检出: ' + detail +
                             '。识别结果是检索候选而非鉴定结论,回答时须向用户说明这一点。')
        return _assistant_stream(assistant_mod.build_messages(q, blocks, []), refs)

    @app.get('/api/alarm-list')
    def alarm_list(species: Optional[str] = None, pending: bool = False, before: Optional[float] = None, user=Depends(auth)):
        clauses, values = ['user_id=?'], [user[1]]
        if species:
            clauses.append('species=?'); values.append(species)
        if pending:
            clauses.append("status='new'")
        if before is not None:
            clauses.append('at<?'); values.append(before)
        condition = ' WHERE ' + ' AND '.join(clauses)
        return {'items': store.rows('SELECT * FROM alarms' + condition + ' ORDER BY at DESC LIMIT 100', tuple(values))}

    @app.get('/api/media/{task_id}/{name}')
    def video_media(task_id: str, name: str, ticket: str, download: bool = False, sid: str = Depends(media_auth)):
        uid = uid_of_sid(sid)
        owner_rows = store.rows('SELECT user_id FROM tasks WHERE id=?', (task_id,))
        # 媒体归属:任务 owner 与票据账号不一致 → 404;无任务行的历史归档目录保持可读(老版本兼容)
        if owner_rows and owner_rows[0]['user_id'] is not None and uid is not None and owner_rows[0]['user_id'] != uid:
            raise HTTPException(404, '视频不存在或无权访问')
        if name == 'source':
            import mimetypes
            from pathlib import Path
            rows = store.rows('SELECT v.path,v.name FROM tasks t JOIN videos v ON v.id=t.video_id WHERE t.id=?', (task_id,))
            if not rows or not Path(rows[0]['path']).is_file():
                raise HTTPException(404, '原视频已不存在')
            return FileResponse(rows[0]['path'], media_type=mimetypes.guess_type(rows[0]['path'])[0] or 'application/octet-stream',
                                filename=rows[0]['name'] if download else None, headers={'Cache-Control':'private, max-age=0'})
        folder = monitor.library.job_dir(task_id).resolve()
        path = (folder / name).resolve()
        if folder.parent not in (monitor.library.jobs.resolve(), monitor.library.previous_result_jobs.resolve(), monitor.library.legacy_jobs.resolve()) or path.parent != folder or not path.is_file():
            raise HTTPException(404, '视频仍在生成或文件不存在')
        if name == 'index.m3u8':
            # Only segment requests receive a scoped media ticket, never an API session token.
            text = path.read_text(encoding='utf-8')
            lines = [line if not line or line.startswith('#') else line + '?ticket=' + ticket for line in text.splitlines()]
            return Response('\n'.join(lines)+'\n', media_type='application/vnd.apple.mpegurl', headers={'Cache-Control':'no-store'})
        if name == 'result.mp4' or (name.startswith('seg') and name.endswith('.ts')):
            return FileResponse(path, media_type='video/mp4' if name.endswith('.mp4') else 'video/mp2t',
                                filename='orchard-'+task_id+'.mp4' if download and name == 'result.mp4' else None,
                                headers={'Cache-Control':'private, max-age=0'})
        raise HTTPException(404)

    @app.post('/api/monitor/stop')
    def stop(user=Depends(auth)):
        # 仅任务归属者(或设备空闲时)可停止检测
        if monitor.owner is not None and user[1] != monitor.owner:
            raise HTTPException(403, '设备被其他账号占用，无法停止')
        return monitor.stop()

    @app.put('/api/settings')
    def configure(body: Preferences, user=Depends(auth)):
        admin = store.rows('SELECT is_device_admin FROM users WHERE id=?', (user[1],))
        if not admin or not admin[0]['is_device_admin']:
            raise HTTPException(403, '仅设备管理员可修改设备参数')
        return store.configure(body.model_dump())

    @app.post('/api/alarms/{alarm_id}/ignore')
    def ignore(alarm_id: str, user=Depends(auth)):
        store.ignore(alarm_id, user[1])
        return {'ok': True}

    @app.post('/api/commands')
    def command(body: Command, user=Depends(auth)):
        return store.start_command(body.request_id, body.alarm_id, body.duration, user[1], body.mode, body.automatic)

    @app.post('/api/commands/{command_id}/stop')
    def stop_command(command_id: str, user=Depends(auth)):
        return store.stop_command(command_id, user[1])

    @app.get('/api/frame/{key}.jpg')
    def frame(key: str, sid: str = Depends(media_auth)):
        uid = uid_of_sid(sid)
        task_id = key.rsplit('-', 1)[0]
        owner_rows = store.rows('SELECT user_id FROM tasks WHERE id=?', (task_id,))
        if not owner_rows or (owner_rows[0]['user_id'] is not None and uid is not None and owner_rows[0]['user_id'] != uid):
            raise HTTPException(404, '该帧已过期，等待新画面')
        data = monitor.get_frame(key)
        if not data:
            raise HTTPException(404, '该帧已过期，等待新画面')
        return Response(data, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})

    @app.get('/api/captures/{name}')
    def capture(name: str, sid: str = Depends(media_auth)):
        uid = uid_of_sid(sid)
        task_id = name.rsplit('-', 1)[0]
        owner_rows = store.rows('SELECT user_id FROM tasks WHERE id=?', (task_id,))
        if not owner_rows or (owner_rows[0]['user_id'] is not None and uid is not None and owner_rows[0]['user_id'] != uid):
            raise HTTPException(404)
        path = (settings.data_dir / 'captures' / name).resolve()
        if path.parent != (settings.data_dir / 'captures').resolve() or not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})

    @app.websocket('/api/ws')
    async def websocket(ws: WebSocket):
        await ws.accept()
        try:
            message = await asyncio.wait_for(ws.receive_json(), timeout=5)
            sid = digest(str(message.get('token', '')))
            if not store.session(sid):
                await ws.close(code=4401)
                return
            while store.session(sid):
                await ws.send_json(snapshot(sid))
                await asyncio.sleep(.6)
            await ws.close(code=4401)
        except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError, ValueError):
            with contextlib.suppress(RuntimeError):
                await ws.close()

    # 本机演示场景：开发期间反复重建产物，必须禁用浏览器缓存，
    # 否则改了样式但浏览器仍用旧的 index.html / css，看起来像是修复没生效。
    @app.middleware('http')
    async def no_cache_for_static(request: Request, call_next):
        # Starlette StaticFiles 遇到 Windows 非法字符（如 '**'、未编码中文等）
        # 会在 os.stat 时抛 OSError [WinError 123] 导致 500，而不是优雅 404。
        # 这里提前拦截这类非法路径，返回 404。
        path = request.url.path
        try:
            response = await call_next(request)
        except OSError:
            return JSONResponse({'detail': 'Not Found'}, status_code=404)
        if (
            path.startswith('/assets/')
            or path.startswith('/scene')
            or path == '/'
            or path.endswith('.html')
        ):
            response.headers['Cache-Control'] = 'no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    # 3D 场景必须挂在 '/' 之前，否则 StaticFiles(html=True) 会先截获请求。
    scene_build = ROOT / 'scene/dist'
    if scene_build.exists():
        # 手输地址常漏末尾斜杠，/scene 会 404 到 mobile 的 StaticFiles 上。
        # 这里显式重定向到 /scene/，避免"链接打不开"。
        @app.get('/scene', include_in_schema=False)
        async def redirect_scene():
            return RedirectResponse(url='/scene/', status_code=307)

        app.mount('/scene', StaticFiles(directory=scene_build, html=True), name='scene')

    build = ROOT / 'mobile/dist/build/h5'
    if build.exists():
        app.mount('/', StaticFiles(directory=build, html=True), name='mobile')
    return app
