import unittest

from kara_previwer.bundle import segment_clip


class SegmentTest(unittest.TestCase):
    def test_frame_clock_and_partial_tail(self):
        clip = {"start": 14, "duration": 17.21, "fps": 30, "segment_frames": 240}
        for frame, offset, count in [
            (0, 0, 240),
            (239, 0, 240),
            (240, 8, 240),
            (516, 16, 37),
        ]:
            segment = segment_clip(clip, frame)
            self.assertEqual(segment["media_offset"], offset)
            self.assertEqual(segment["start"], 14 + offset)
            self.assertAlmostEqual(segment["duration"] * 30, count)
        for invalid in [-1, 517, 2.5, True]:
            with self.assertRaises(ValueError):
                segment_clip(clip, invalid)
