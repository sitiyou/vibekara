import unittest
from unittest.mock import Mock, patch

from kara_previwer import compiler


class SceneCacheTest(unittest.TestCase):
    def test_compiler_reuses_full_scene_across_windows_and_invalidates_inputs(self):
        recipe = Mock(id="external", semantic=True)
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
                {"offset_ms": -100},
                {"colors": {"0": "red"}},
                {"values": {"size": 110}},
            ]:
                self.assertEqual(
                    compiler.run(dict(job, **changed, cached_only=True)), {"miss": True}
                )
