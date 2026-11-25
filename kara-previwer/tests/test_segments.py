import unittest

from kara_previwer.bundle import editing_clip, resource_path, segment_clip


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

    def test_whole_preview_and_saved_captures_use_the_same_geometry_and_clock(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace

        from kara_previwer.server import preview_window

        proposal = {"clip": {"start": 14, "duration": 17.21, "fps": 30, "edit_segment_frames": 60},
                    "values": {"size": 50}, "config": "recipe"}
        values = {"size": 55}
        with tempfile.TemporaryDirectory() as temporary:
            session = SimpleNamespace(root=Path(temporary))
            key = resource_path(proposal, values)
            self.assertEqual(preview_window(session, proposal, values, 90, presented=key)["start"], 16)
            (session.root / key).mkdir(parents=True)
            for options in ({"whole": True}, {"presented": key}):
                result = preview_window(session, proposal, values, 90, **options)
                self.assertEqual((result["start"], result["duration"]), (14, 17.21))
            self.assertEqual(preview_window(session, proposal, {"size": 56}, 90, presented=key)["start"], 16)

    def test_live_shader_inputs_share_the_asset_and_keep_whole_song_seekable(self):
        clip = {"start": 14, "duration": 17.21, "fps": 30, "edit_segment_frames": 60}
        start = {"tint": "FF0000", "size": 50}
        proposal = {"clip": clip, "values": start, "config": "recipe", "material_fields": ["tint"]}
        appearance = {**start, "tint": "00FF00"}
        geometry = {**appearance, "size": 55}
        self.assertEqual(resource_path(proposal, appearance), resource_path(proposal, start))
        self.assertNotEqual(resource_path(proposal, geometry), resource_path(proposal, start))
        self.assertEqual(editing_clip(proposal, appearance), clip)
        self.assertEqual(editing_clip(proposal, geometry)["segment_frames"], 60)
