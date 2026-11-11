import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.store import Store
from backend.video_library import VideoLibrary


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.settings=Settings(Path(self.tmp.name),Path('missing.pt'),Path('missing.mp4'),'test','password','secret',worker_enabled=False)
        self.store=Store(self.settings)
        self.lib=VideoLibrary(self.settings,self.store)
        with self.store.tx() as db:
            db.execute('INSERT INTO videos (id,name,path,duration,fps,at) VALUES (?,?,?,?,?,?)',('video-1','多鸟录像','source.mp4',20,30,1))
        self.store.task('task-1','running')
        self.lib.attach('task-1',self.lib.video('video-1'))

    def tearDown(self):
        self.store.close();self.tmp.cleanup()

    def test_two_species_reference_one_video_with_separate_intervals(self):
        self.lib.samples('task-1',[{'species':'八哥','confidence':.9},{'species':'八哥','confidence':.8},{'species':'树麻雀','confidence':.95}],1,30)
        self.lib.samples('task-1',[{'species':'八哥','confidence':.9}],1.5,45)
        self.lib.samples('task-1',[{'species':'八哥','confidence':.9}],10,300)
        self.assertEqual(len(self.lib.species()),2)
        for species in ['八哥','树麻雀']:
            self.assertEqual(self.lib.list(species)[0]['id'],'task-1')
        self.assertEqual(len(self.lib.list()),1)
        spans=self.lib.detail('task-1')['intervals']
        self.assertEqual(len(spans),3)
        self.assertEqual(spans[0],{'species':'八哥','start':1,'end':1.5,'peak_count':2})
        self.assertEqual(self.lib.list('不存在'),[])

    def test_no_bird_task_is_retained_and_pending_groups_use_all_records(self):
        self.lib.progress('task-1',100,True);self.store.task('task-1','ended')
        self.assertEqual(self.lib.list()[0]['species'],[])
        self.assertEqual(self.lib.list()[0]['result_ready'],1)
        for i in range(105):
            self.store.alarm('t'+str(i),'八哥',1,.9,'a.jpg',0,0,20)
        self.assertEqual(self.lib.alarm_groups()[0]['pending'],105)

    def test_alarm_merge_uses_video_time_when_processing_faster_than_playback(self):
        first,_=self.store.alarm('task-1','八哥',1,.9,'a.jpg',1,30,20,now=100,video_clock=True)
        same,created=self.store.alarm('task-1','八哥',1,.9,'b.jpg',2,60,20,now=100.1,video_clock=True)
        self.assertEqual(first,same);self.assertFalse(created)
        later,created=self.store.alarm('task-1','八哥',1,.9,'c.jpg',30,900,20,now=100.2,video_clock=True)
        self.assertNotEqual(first,later);self.assertTrue(created)

    def test_summary_counts_only_archived_tasks_with_peak_bird_sums(self):
        # 未归档(running):不计入场次,也不计鸟数
        self.lib.samples('task-1',[{'species':'八哥','confidence':.9},{'species':'八哥','confidence':.8}],1,30)
        self.lib.samples('task-1',[{'species':'八哥','confidence':.9}],1.5,45)
        before=self.lib.summary()
        self.assertEqual(before['tasks_total'],0);self.assertEqual(before['birds_total'],0)
        # 归档后:1 场;鸟数=峰值 2(同帧最多同时 2 只,不跨帧累加为 3)
        self.lib.progress('task-1',100,True);self.store.task('task-1','ended')
        row=self.lib.summary()
        self.assertEqual(row['tasks_total'],1);self.assertEqual(row['birds_total'],2)
        self.assertEqual(row['today_tasks'],1);self.assertEqual(row['today_birds'],2)
        # 第二场多物种:树麻雀峰值 1 + 珠颈斑鸠峰值 3,合计 6
        with self.store.tx() as db:
            db.execute('INSERT INTO videos (id,name,path,duration,fps,at) VALUES (?,?,?,?,?,?)',('video-2','第二段','b.mp4',15,25,2))
        self.store.task('task-2','running');self.lib.attach('task-2',self.lib.video('video-2'))
        self.lib.samples('task-2',[{'species':'树麻雀','confidence':.8},{'species':'珠颈斑鸠','confidence':.7},{'species':'珠颈斑鸠','confidence':.8},{'species':'珠颈斑鸠','confidence':.8}],1,25)
        self.lib.progress('task-2',100,True);self.store.task('task-2','ended')
        row=self.lib.summary()
        self.assertEqual(row['tasks_total'],2);self.assertEqual(row['birds_total'],6)

    def test_build_task_summary_peaks_bbox_and_empty_task(self):
        # 场景复现快照:物种×峰值 + 每物种首条告警 bbox(解析为列表);无检出/不存在 → None
        from backend.video_pipeline import build_task_summary
        self.lib.samples('task-1',[{'species':'八哥','confidence':.9},{'species':'八哥','confidence':.8},{'species':'树麻雀','confidence':.95}],1,30)
        self.store.alarm('task-1','八哥',2,.9,'a.jpg',1,30,20,bbox=[10,20,60,80])
        summary=build_task_summary(self.store,'task-1','ended')
        self.assertEqual(summary['status'],'ended');self.assertEqual(summary['total'],3)
        self.assertEqual(summary['name'],'多鸟录像');self.assertEqual(summary['duration'],20)
        by={s['species']:s for s in summary['species']}
        self.assertEqual(by['八哥']['peak'],2);self.assertEqual(by['树麻雀']['peak'],1)
        self.assertEqual(by['八哥']['bbox'],[10,20,60,80]);self.assertIsNone(by['树麻雀']['bbox'])
        self.assertIsNone(build_task_summary(self.store,'missing','ended'))
        # 无检出任务:不需要场景复现
        with self.store.tx() as db:
            db.execute("INSERT INTO videos (id,name,path,duration,fps,at) VALUES ('v-empty','空','e.mp4',5,25,3)")
        self.store.task('task-empty','ended');self.lib.attach('task-empty',self.lib.video('v-empty'))
        self.assertIsNone(build_task_summary(self.store,'task-empty','ended'))

    def test_pipeline_snapshot_carries_last_task_field(self):
        # 快照带 last_task 字段(默认 None;由 VideoPipeline 在任务 ended/stopped 时写入)
        from backend.video_pipeline import build_task_summary
        self.lib.samples('task-1',[{'species':'八哥','confidence':.9}],1,30)
        self.store.alarm('task-1','八哥',1,.9,'a.jpg',1,30,20,bbox=[10,20,60,80])
        summary=build_task_summary(self.store,'task-1','ended')
        self.assertEqual(summary['total'],1)
        self.assertEqual(summary['species'][0]['bbox'],[10,20,60,80])


class VideoApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        settings=Settings(Path(self.tmp.name),Path('missing.pt'),Path('missing.mp4'),'test','password','secret',worker_enabled=False)
        self.app=create_app(settings);self.client=TestClient(self.app).__enter__()
        token=self.client.post('/api/login',json={'username':'test','password':'password'}).json()['token']
        self.headers={'Authorization':'Bearer '+token,'X-Filename':'sample.mp4'}

    def tearDown(self):
        self.client.__exit__(None,None,None);self.tmp.cleanup()

    def test_upload_rejects_unauthorized_invalid_and_bad_video_without_orphan(self):
        self.assertEqual(self.client.post('/api/videos',content=b'x').status_code,401)
        self.assertEqual(self.client.post('/api/videos',content=b'x',headers={**self.headers,'X-Filename':'test.exe'}).status_code,415)
        self.assertEqual(self.client.post('/api/videos',content=b'invalid',headers=self.headers).status_code,409)
        video_root = Path(self.tmp.name) / 'videos'
        self.assertEqual([path for path in video_root.iterdir() if path.is_file()], [])
        self.assertFalse((video_root / 'result').exists())

    def test_same_video_content_is_registered_once_and_completed_analysis_is_rejected(self):
        import cv2
        import numpy as np
        from backend.store import Conflict
        source = Path(self.tmp.name) / 'repeat.avi'
        writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 64))
        for _ in range(3): writer.write(np.zeros((64, 64, 3), dtype=np.uint8))
        writer.release()
        library = self.app.state.monitor.library
        first = library.register(source, 'first.avi')
        copy = Path(self.tmp.name) / 'same-content.avi'
        copy.write_bytes(source.read_bytes())
        second = library.register(copy, 'again.avi')
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(self.app.state.store.rows('SELECT id FROM videos')), 1)
        self.app.state.store.task('finished', 'ended')
        library.attach('finished', first)
        library.progress('finished', 100, True)
        with self.assertRaisesRegex(Conflict, '已经识别'):
            library.already_processed(second)
        self.assertEqual(library.jobs, Path(self.tmp.name) / 'jobs')
        self.assertTrue(library.jobs.is_dir())

    def test_upload_reuses_identical_file_already_in_video_directory(self):
        import cv2
        import numpy as np
        library = self.app.state.monitor.library
        original = library.root / 'in-library.avi'
        writer = cv2.VideoWriter(str(original), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 64))
        for _ in range(3):
            writer.write(np.zeros((64, 64, 3), dtype=np.uint8))
        writer.release()
        payload = original.read_bytes()
        headers = {**self.headers, 'X-Filename': original.name}
        first = self.client.post('/api/videos', content=payload, headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(library.video(first.json()['id'])['path'], str(original.resolve()))
        second = self.client.post('/api/videos', content=payload, headers=headers)
        self.assertEqual(second.json()['id'], first.json()['id'])
        self.assertEqual([file for file in library.root.iterdir() if file.is_file()], [original])

    def test_concurrent_identical_uploads_keep_one_source_file(self):
        import cv2
        import numpy as np
        from concurrent.futures import ThreadPoolExecutor
        source = Path(self.tmp.name) / 'concurrent.avi'
        writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 64))
        for _ in range(3):
            writer.write(np.zeros((64, 64, 3), dtype=np.uint8))
        writer.release()
        payload = source.read_bytes()
        headers = {**self.headers, 'X-Filename': source.name}
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.client.post('/api/videos', content=payload, headers=headers), range(2)))
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(responses[0].json()['id'], responses[1].json()['id'])
        self.assertEqual(len([file for file in self.app.state.monitor.library.root.iterdir() if file.is_file()]), 1)

    def test_previous_result_paths_remain_readable(self):
        library = self.app.state.monitor.library
        ticket = self.client.get('/api/state', headers=self.headers).json()['media_ticket']
        for index, root in enumerate((library.previous_result_jobs, library.legacy_jobs)):
            task_id = f'old-task-{index}'
            folder = root / task_id
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'result.mp4').write_bytes(b'previous result')
            self.assertEqual(library.job_dir(task_id), folder)
            response = self.client.get(f'/api/media/{task_id}/result.mp4?ticket={ticket}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b'previous result')
        self.assertEqual(library.job_dir('new-task'), library.jobs / 'new-task')

    def test_state_snapshot_includes_last_task_field(self):
        data = self.client.get('/api/state', headers=self.headers).json()
        self.assertIn('last_task', data)
        self.assertIsNone(data['last_task'])

    def test_custom_species_photo_is_listed_and_served_with_media_ticket(self):
        import cv2
        import numpy as np
        self.assertNotIn('八哥', self.client.get('/api/library', headers=self.headers).json()['guide_images'])
        folder = Path(self.tmp.name) / 'species'
        self.assertEqual(len([path for path in folder.iterdir() if path.is_dir()]), 13)
        image = cv2.imencode('.jpg', np.zeros((16, 16, 3), dtype=np.uint8))[1].tobytes()
        photo_path = folder / '八哥' / '我的八哥照片.jpg'
        photo_path.write_bytes(image)
        self.assertIn('八哥', self.client.get('/api/library', headers=self.headers).json()['guide_images'])
        self.assertEqual(self.client.get('/api/species-images/八哥').status_code, 401)
        ticket = self.client.get('/api/state', headers=self.headers).json()['media_ticket']
        photo = self.client.get('/api/species-images/八哥?ticket=' + ticket)
        self.assertEqual(photo.status_code, 200)
        self.assertEqual(photo.headers['content-type'], 'image/jpeg')
        self.assertEqual(photo.content, image)
        self.assertEqual(self.client.get('/api/species-images/未知鸟?ticket=' + ticket).status_code, 404)
        photo_path.unlink()
        self.assertNotIn('八哥', self.client.get('/api/library', headers=self.headers).json()['guide_images'])
        (folder / '八哥.jpg').write_bytes(image)
        self.assertIn('八哥', self.client.get('/api/library', headers=self.headers).json()['guide_images'])

    def test_upload_library_and_scoped_media_range(self):
        import cv2
        import numpy as np
        source=Path(self.tmp.name)/'fixture.avi'
        writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'MJPG'),10,(64,64))
        for _ in range(10):writer.write(np.zeros((64,64,3),dtype=np.uint8))
        writer.release()
        response=self.client.post('/api/videos',content=source.read_bytes(),headers={**self.headers,'X-Filename':'%E6%B5%8B%E8%AF%95.avi'})
        self.assertEqual(response.status_code,200,response.text)
        row=response.json();self.assertNotIn('path',row);self.assertEqual(row['name'],'测试.avi')
        library=self.app.state.monitor.library
        self.app.state.store.task('task-media','ended');library.attach('task-media',library.video(row['id']))
        folder=library.jobs/'task-media';folder.mkdir();(folder/'result.mp4').write_bytes(b'0123456789')
        (folder/'index.m3u8').write_text('#EXTM3U\nseg00000.ts\n',encoding='utf8')
        (folder/'encoder.log').write_text('private')
        ticket=self.client.get('/api/state',headers=self.headers).json()['media_ticket']
        url='/api/media/task-media/'
        self.assertEqual(self.client.get(url+'result.mp4').status_code,401)
        part=self.client.get(url+'result.mp4?ticket='+ticket,headers={'Range':'bytes=2-5'})
        self.assertEqual(part.status_code,206);self.assertEqual(part.content,b'2345')
        playlist=self.client.get(url+'index.m3u8?ticket='+ticket)
        self.assertIn('seg00000.ts?ticket=',playlist.text)
        self.assertEqual(self.client.get(url+'encoder.log?ticket='+ticket).status_code,404)
        self.assertEqual(self.client.get('/api/library?species=不存在',headers=self.headers).json()['items'],[])
        self.assertEqual(self.client.get('/api/library/summary').status_code,401)
        # summary 路由必须先于 /{task_id} 声明:返回统计字段而非 detail 的 409/404
        summary=self.client.get('/api/library/summary',headers=self.headers).json()
        self.assertEqual(summary['tasks_total'],0)
        self.assertEqual(self.client.get('/api/library/task-media',headers=self.headers).json()['name'],'测试.avi')
        original=self.client.get(url+'source?ticket='+ticket+'&download=true')
        self.assertEqual(original.status_code,200)
        self.assertEqual(original.content,source.read_bytes())
