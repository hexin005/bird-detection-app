import asyncio
import contextlib
import threading
import time
import secrets
from urllib.parse import unquote
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, Settings
from .video_pipeline import VideoPipeline
from .security import check_media, digest, media_ticket
from .store import Conflict, Store


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class Command(BaseModel):
    request_id: str = Field(min_length=8, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    alarm_id: Optional[str] = None
    duration: Literal[3, 5, 8] = 3


class Preferences(BaseModel):
    scenario: Literal['normal', 'offline', 'timeout']
    confidence: float = Field(ge=.1, le=.95)
    consecutive: int = Field(ge=1, le=10)
    cooldown: float = Field(ge=1, le=300)


class StartVideo(BaseModel):
    video_id: Optional[str] = None


def create_app(settings=None):
    settings = settings or Settings.load()
    store = Store(settings)
    monitor = VideoPipeline(settings, store)
    shutdown = threading.Event()

    def worker():
        while not shutdown.wait(.1):
            store.tick()

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
    app.state.store, app.state.monitor = store, monitor
    app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5178', 'http://localhost:5178'],
                       allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Authorization', 'Content-Type', 'X-Filename'])

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
                'media_ticket': media_ticket(sid, settings.secret), 'simulated_device': True}

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
        try:
            with target.open('wb') as output:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 500 * 1024 * 1024:
                        raise HTTPException(413, '视频不能超过 500 MB')
                    output.write(chunk)
            video = await run_in_threadpool(monitor.library.register, target, name)
            return {key: value for key, value in video.items() if key != 'path'}
        except BaseException:
            target.unlink(missing_ok=True)
            raise

    @app.get('/api/videos')
    def videos(user=Depends(auth)):
        return {'items': store.rows('SELECT id,name,duration,fps,at FROM videos ORDER BY at DESC LIMIT 30')}

    @app.get('/api/library')
    def library(species: Optional[str] = None, offset: int = Query(0, ge=0), user=Depends(auth)):
        return {'items': monitor.library.list(species, offset), 'species': monitor.library.species(), 'alarm_groups': monitor.library.alarm_groups()}

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
        folder = (monitor.library.jobs / task_id).resolve()
        path = (folder / name).resolve()
        if folder.parent != monitor.library.jobs.resolve() or path.parent != folder or not path.is_file():
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
        return store.start_command(body.request_id, body.alarm_id, body.duration, user[1])

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
        response = await call_next(request)
        path = request.url.path
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
        app.mount('/scene', StaticFiles(directory=scene_build, html=True), name='scene')

    build = ROOT / 'mobile/dist/build/h5'
    if build.exists():
        app.mount('/', StaticFiles(directory=build, html=True), name='mobile')
    return app
