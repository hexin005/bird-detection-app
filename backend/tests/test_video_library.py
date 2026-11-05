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
            db.execute('INSERT INTO videos VALUES (?,?,?,?,?,?)',('video-1','多鸟录像','source.mp4',20,30,1))
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
        self.assertEqual(list((Path(self.tmp.name)/'videos').iterdir()),[])

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
        self.assertEqual(self.client.get('/api/library/task-media',headers=self.headers).json()['name'],'测试.avi')
        original=self.client.get(url+'source?ticket='+ticket+'&download=true')
        self.assertEqual(original.status_code,200)
        self.assertEqual(original.content,source.read_bytes())
