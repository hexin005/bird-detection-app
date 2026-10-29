"""Opt-in tests with the actual local YOLO weights, not fake detections.

Run with BIRD_INTEGRATION=1 and BIRD_TEST_VIDEO pointing to a short known-bird clip.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path

from backend.config import Settings
from backend.detector import VideoMonitor
from backend.store import Store


@unittest.skipUnless(os.getenv('BIRD_INTEGRATION') == '1', 'enable BIRD_INTEGRATION for actual YOLO inference')
class InferenceTests(unittest.TestCase):
    def test_real_video_detection_snapshot_and_control(self):
        base = Settings.load()
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(Path(tmp), base.model_path, Path(os.environ['BIRD_TEST_VIDEO']), 'test', 'test-password', 'secret')
            store = Store(settings)
            monitor = VideoMonitor(settings, store)
            try:
                monitor.start()
                deadline = time.monotonic() + 60
                while monitor.thread.is_alive() and time.monotonic() < deadline:
                    time.sleep(.1)
                self.assertEqual(monitor.snapshot()['status'], 'ended', monitor.snapshot())
                alarms = store.snapshot()['alarms']
                self.assertGreater(len(alarms), 0)
                self.assertTrue((settings.data_dir / 'captures' / alarms[0]['snapshot']).is_file())
                frame = monitor.snapshot()['frame']
                self.assertIsNotNone(monitor.get_frame(frame['key']))
                self.assertEqual(frame['count'], len(frame['detections']))
                store.start_command('actual-video-command', alarms[0]['id'], 3, 1)
                store.tick(10); store.tick(13)
                self.assertEqual(store.snapshot()['alarms'][0]['status'], 'handled')
                # Reuse the loaded real model against a generated empty test clip.
                import cv2
                import numpy as np
                empty = Path(tmp) / 'empty.avi'
                writer = cv2.VideoWriter(str(empty), cv2.VideoWriter_fourcc(*'MJPG'), 10, (320, 240))
                self.assertTrue(writer.isOpened())
                for _ in range(10):
                    writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
                writer.release()
                settings.video_path = empty
                prior = len(store.snapshot()['alarms'])
                monitor.start(); monitor.thread.join(20)
                self.assertEqual(monitor.snapshot()['status'], 'ended')
                self.assertEqual(monitor.snapshot()['frame']['count'], 0)
                self.assertEqual(len(store.snapshot()['alarms']), prior)
            finally:
                monitor.close(); store.close()
