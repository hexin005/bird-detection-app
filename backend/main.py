import asyncio
import contextlib
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
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, Settings
from .detector import NAMES
from .emailer import MailSendError, send_code_mail
from .video_pipeline import VideoPipeline
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

    def snapshot(sid):
        return {**store.snapshot(), 'monitor': monitor.snapshot(), 'server_time': time.time(),
                'media_ticket': media_ticket(sid, settings.secret), 'simulated_device': True,
                'last_task': getattr(monitor, 'last_task', None)}

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
        """果园数据分析聚合(口径见 store.stats)。共享果园数据,不区分账号。"""
        return store.stats({'today': 1, '7d': 7, '30d': 30}[scope])

    @app.get('/api/state')
    def state(user=Depends(auth)):
        return snapshot(user[0])

    @app.get('/api/history')
    def history(kind: Literal['alarms', 'commands', 'events'], offset: int = Query(0, ge=0), before: Optional[int] = None, user=Depends(auth)):
        order = 'id' if kind == 'events' else 'at'
        if kind == 'events' and before is not None:
            return {'items': store.rows('SELECT * FROM events WHERE id<? ORDER BY id DESC LIMIT 100', (before,))}
        return {'items': store.rows(f'SELECT * FROM {kind} ORDER BY {order} DESC LIMIT 100 OFFSET ?', (offset,))}

    @app.get('/api/detail/{kind}/{record_id}')
    def detail(kind: Literal['alarms', 'commands'], record_id: str, user=Depends(auth)):
        rows = store.rows(f'SELECT * FROM {kind} WHERE id=?', (record_id,))
        if not rows:
            raise HTTPException(404, '记录不存在')
        return rows[0]

    @app.post('/api/monitor/start')
    def start(body: Optional[StartVideo] = None, user=Depends(auth)):
        return monitor.start(body.video_id if body else None)

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
            video = await run_in_threadpool(monitor.library.register, target, name, True)
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
        return {'items': store.rows('SELECT id,name,duration,fps,at FROM videos ORDER BY at DESC LIMIT 30')}

    @app.get('/api/library')
    def library(species: Optional[str] = None, offset: int = Query(0, ge=0), user=Depends(auth)):
        return {'items': monitor.library.list(species, offset), 'species': monitor.library.species(),
                'alarm_groups': monitor.library.alarm_groups(),
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
        return monitor.library.summary()

    @app.get('/api/library/{task_id}')
    def video_detail(task_id: str, user=Depends(auth)):
        return monitor.library.detail(task_id)

    @app.get('/api/alarm-list')
    def alarm_list(species: Optional[str] = None, pending: bool = False, before: Optional[float] = None, user=Depends(auth)):
        clauses, values = [], []
        if species:
            clauses.append('species=?'); values.append(species)
        if pending:
            clauses.append("status='new'")
        if before is not None:
            clauses.append('at<?'); values.append(before)
        condition = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        return {'items': store.rows('SELECT * FROM alarms' + condition + ' ORDER BY at DESC LIMIT 100', tuple(values))}

    @app.get('/api/media/{task_id}/{name}', dependencies=[Depends(media_auth)])
    def video_media(task_id: str, name: str, ticket: str, download: bool = False):
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
        return monitor.stop()

    @app.put('/api/settings')
    def configure(body: Preferences, user=Depends(auth)):
        return store.configure(body.model_dump())

    @app.post('/api/alarms/{alarm_id}/ignore')
    def ignore(alarm_id: str, user=Depends(auth)):
        store.ignore(alarm_id)
        return {'ok': True}

    @app.post('/api/commands')
    def command(body: Command, user=Depends(auth)):
        return store.start_command(body.request_id, body.alarm_id, body.duration, user[1], body.mode, body.automatic)

    @app.post('/api/commands/{command_id}/stop')
    def stop_command(command_id: str, user=Depends(auth)):
        return store.stop_command(command_id)

    @app.get('/api/frame/{key}.jpg', dependencies=[Depends(media_auth)])
    def frame(key: str):
        data = monitor.get_frame(key)
        if not data:
            raise HTTPException(404, '该帧已过期，等待新画面')
        return Response(data, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})

    @app.get('/api/captures/{name}', dependencies=[Depends(media_auth)])
    def capture(name: str):
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
