import os
import tempfile
import time
import threading
import unittest
from pathlib import Path
from backend.config import Settings
from backend.store import Store
from backend.video_pipeline import VideoPipeline


@unittest.skipUnless(os.getenv('BIRD_INTEGRATION')=='1','enable real model/FFmpeg integration')
class PipelineTests(unittest.TestCase):
    def test_real_encoding_full_frame_rate_archive_and_restart(self):
        import cv2
        base=Settings.load()
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(os.environ['BIRD_TEST_VIDEO'])
            settings=Settings(Path(tmp),base.model_path,source,'test','password','secret')
            store=Store(settings);pipeline=VideoPipeline(settings,store)
            try:
                pipeline.start();pipeline.thread.join(90)
                self.assertEqual(pipeline.snapshot()['status'],'ended',pipeline.snapshot())
                task=pipeline.snapshot()['task_id']
                folder=pipeline.library.jobs/task
                self.assertTrue((folder/'index.m3u8').exists())
                self.assertTrue((folder/'result.mp4').exists())
                original=cv2.VideoCapture(str(source));result=cv2.VideoCapture(str(folder/'result.mp4'))
                try:
                    self.assertAlmostEqual(original.get(cv2.CAP_PROP_FPS),result.get(cv2.CAP_PROP_FPS),delta=.1)
                    self.assertAlmostEqual(original.get(cv2.CAP_PROP_FRAME_COUNT),result.get(cv2.CAP_PROP_FRAME_COUNT),delta=1)
                    self.assertTrue(result.read()[0])
                finally:original.release();result.release()
                detail=pipeline.library.detail(task)
                self.assertEqual(pipeline.snapshot()['video_id'],detail['video_id'])
                self.assertTrue(detail['result_ready']);self.assertGreater(len(detail['intervals']),0)
                self.assertEqual(store.snapshot()['alarms'][0]['task_id'],task)
                # Stopping during preparation must be a cancellation, not an encoder error.
                attached, release = threading.Event(), threading.Event()
                original_attach = pipeline.library.attach
                def paused_attach(task_id, video):
                    original_attach(task_id,video);attached.set();release.wait(10)
                pipeline.library.attach=paused_attach
                pipeline.start()
                self.assertTrue(attached.wait(10))
                pipeline.stop();release.set();pipeline.thread.join(30)
                self.assertEqual(pipeline.snapshot()['status'],'stopped',pipeline.snapshot())
                pipeline.close();store.close();store=Store(settings)
                library=VideoPipeline(settings,store).library
                self.assertTrue(library.detail(task)['result_ready'])
                self.assertGreater(len(library.species()),0)
            finally:
                pipeline.close();store.close()
