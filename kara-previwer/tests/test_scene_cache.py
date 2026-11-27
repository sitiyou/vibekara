import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock, patch

from kara_previwer import compiler


class SceneCacheTest(unittest.TestCase):
    def test_inspect_tracks_uses_all_lyrics_in_the_clip_and_excludes_other_tracks(self):
        @dataclass
        class Song:
            preview_interval: tuple[int, int] | None = None

        def plan(track_id, start, end):
            return SimpleNamespace(
                track_id=track_id, placement=SimpleNamespace(display=SimpleNamespace(start=start, end=end)),
                line=SimpleNamespace(layout=SimpleNamespace(body=SimpleNamespace(characters=[]), ruby=[])),
                source=SimpleNamespace(lyrics=SimpleNamespace(units=[SimpleNamespace(segments=[
                    SimpleNamespace(timing=SimpleNamespace(start=start + 0.5, end=end)),
                ])])),
            )

        recipe = Mock(id="external", semantic=True, formats=("hook",))
        recipe.resolve.side_effect = lambda values: values
        recipe.build.return_value.track_settings = ()
        recipe.build.return_value.plans = (
            plan("lead", 3, 9), plan("lead", 5, 12), plan("harmony", 11, 15),
        )
        job = {
            "script": "template", "template": "external", "project": "song.nto",
            "inspect_tracks": True, "start": 5, "duration": 6,
            "composition": {"version": 1, "groups": []}, "values": {},
        }
        with (
            patch.object(compiler, "load_recipe", return_value=recipe),
            patch.object(compiler, "load_project_song", return_value=Song()),
        ):
            info = compiler.run(job)
            self.assertEqual(info["tracks"], ["lead"])
            self.assertEqual(info["details"]["lead"]["start"], 5)
            recipe.build.assert_called_once_with(Song((5, 11)), {}, composition=job["composition"])
            all_tracks = compiler.run(dict(job, duration=8))
            self.assertEqual(all_tracks["tracks"], ["harmony", "lead"])
            self.assertEqual(all_tracks["details"]["harmony"]["start"], 11.5)

    def test_compiler_reuses_full_scene_across_windows_and_invalidates_inputs(self):
        recipe = Mock(id="external", semantic=True, formats=("hook",))
        recipe.resolve.side_effect = lambda values: values
        job = {
            "script": "template",
            "template": "external",
            "krc": "lyrics",
            "midi": "notes",
            "values": {"size": 100},
            "fps": 30,
            "output": "out",
            "start": 8,
            "duration": 8,
            "shared_scene": True,
        }
        with (
            patch.object(compiler, "load_recipe", return_value=recipe),
            patch.object(compiler, "load_song", return_value="whole song"),
            patch.object(compiler, "_scene_key", None),
            patch.object(compiler, "_scene", None),
        ):
            self.assertEqual(compiler.run(dict(job, cached_only=True)), {"miss": True})
            self.assertEqual(compiler.run(dict(job, prepare_scene=True)), {})
            recipe.build.return_value.prepare_hook.return_value.export.assert_not_called()
            compiler.run(job)
            compiler.run(dict(job, start=24, cached_only=True))
            recipe.build.assert_called_once_with("whole song", {"size": 100})
            recipe.build.return_value.prepare_hook.assert_called_once_with()
            self.assertEqual(recipe.build.return_value.prepare_hook.return_value.export.call_count, 2)
            for changed in [
                {"script": "v2"},
                {"krc": "v2"},
                {"midi": "v2"},
                {"offset_ms": 0},
                {"colors": {"0": "red"}},
                {"values": {"size": 110}},
            ]:
                self.assertEqual(
                    compiler.run(dict(job, **changed, cached_only=True)), {"miss": True}
                )
