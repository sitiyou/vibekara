import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from kara_previwer.bundle import store_song_input
from kara_previwer.delivery import accepted_build, rebuild, snapshot
from kara_previwer.store import Session


class DeliveryTest(unittest.TestCase):
    def test_rebuild_uses_the_accepted_project_and_export_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = Session.create(root / "state", "project review")
            assets = session.root / "assets"
            assets.mkdir()
            (assets / "song.nto").write_text('{"fixture":"saved project"}')
            (assets / "template.py").write_text("# recipe")
            configs = session.root / "configs"
            configs.mkdir()
            (configs / "build").write_text(json.dumps({
                "script": "assets/template.py", "python": "recipe-python", "project": "assets/song.nto",
                "offset_ms": -125, "harmony_tracks": "1",
            }))
            session.publish(0, {"config": "build"})
            token = str(uuid.uuid4())
            session.submit({"action": "accept", "token": token, "version": 1, "values": {}})
            approved = root / "approved"
            proposal, item = accepted_build(session)
            snapshot(session, proposal, item, 30, approved)

            def compile_fixture(config, *, values, fps, output):
                self.assertEqual(Path(config["project"]), approved / "song.nto")
                self.assertEqual(Path(config["project"]).read_text(), '{"fixture":"saved project"}')
                self.assertEqual((config["offset_ms"], config["harmony_tracks"], fps), (-125, "1", 30))
                Path(output).write_text("rebuilt")
                return {"values": values}

            with patch("kara_previwer.delivery.compile_job", side_effect=compile_fixture):
                rebuild(approved, root / "out.hook")

    def test_previous_recipe_imports_can_read_a_saved_project(self):
        try:
            from kara_previwer.compiler import load_project_song, load_recipe
            from kara_previwer.timing import TemplateSong
            from namioto import project
        except ImportError:
            self.skipTest("requires the Namioto and kara-templater rendering environment")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = root / "song.nto"
            project.save(project.Project(
                audio="missing.wav",
                lyrics=project.Lyrics(text="京[きょう]\n---\n@1{あ}"),
                notes=(project.Note(1.0001, 0.6, 60, 0), project.Note(2, 0.5, 62, 0), project.Note(3, 1, 64, 1)),
            ), saved)
            script = root / "template.py"
            script.write_text(
                "from namioto.karaoke.song import TemplateSong\n"
                "from namioto.karaoke.templates import Registry\n"
                "def build(song: TemplateSong, values): return song\n"
                "def register(registry: Registry):\n"
                "    registry.add(id='saved', title='Saved', build=build, semantic=True)\n",
                encoding="utf-8",
            )
            recipe = load_recipe(str(script), "saved")
            song = recipe.build(load_project_song(str(saved), -100, "1"), {})
            self.assertIsInstance(song, TemplateSong)
            self.assertEqual(song.tracks, {"line-1": 0, "line-2": 1})
            self.assertEqual([(line.chapter, line.style) for line in song.sources], [("0", "default"), ("1", "top")])
            first, second = song.sources[0].lyrics.units[0].segments
            self.assertAlmostEqual(first.timing.start, 0.9001)
            self.assertAlmostEqual(second.timing.start, 1.9)
            self.assertIsNotNone(first.ruby)

    def test_snapshot_keeps_timing_and_can_retry_a_failed_hook_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = Session.create(root / "state", "review")
            assets = session.root / "assets"
            assets.mkdir()
            source = root / "timing"
            source.mkdir()
            (source / "lyrics.krc").write_text("あ", encoding="utf-8")
            (source / "vocal.mid").write_bytes(b"MIDI fixture")
            timing = source / "song.json"
            first_settings = '{"wavetone":true,"offset_ms":-100,"track_style":{},"colors":{}}'
            timing.write_text(first_settings)
            stored = store_song_input(source, assets)
            self.assertEqual(store_song_input(source, assets), stored)
            timing.write_text(first_settings.replace("-100", "0"))
            self.assertNotEqual(store_song_input(source, assets), stored)
            (assets / "template.py").write_text("# recipe")
            configs = session.root / "configs"
            configs.mkdir()
            (configs / "build").write_text(json.dumps({
                "script": "assets/template.py", "python": "recipe-python", "song_input": stored,
            }))
            session.publish(0, {"config": "build"})
            token = str(uuid.uuid4())
            session.submit({"action": "accept", "token": token, "version": 1, "values": {}})
            proposal, item = accepted_build(session)
            approved = root / "approved"
            hook = root / "lyrics.hook"

            receipt = snapshot(session, proposal, item, 30, approved)
            self.assertEqual(receipt["token"], token)
            self.assertEqual(snapshot(session, proposal, item, 30, approved), receipt)
            self.assertFalse(hook.exists())
            self.assertEqual((approved / "song/song.json").read_text(), first_settings)
            with self.assertRaisesRegex(ValueError, "different build"):
                snapshot(session, proposal, item, 60, approved)

            hook.write_text("existing")
            with (
                patch("kara_previwer.delivery.compile_job", side_effect=ValueError("compile failed")),
                self.assertRaisesRegex(ValueError, "compile failed"),
            ):
                rebuild(approved, hook)
            self.assertEqual(hook.read_text(), "existing")

            def compile_fixture(config, *, values, fps, output):
                self.assertEqual(config["python"], "new-environment")
                self.assertEqual(Path(config["song_input"]), approved / "song")
                self.assertEqual((values, fps), ({}, 30))
                Path(output).write_text("rebuilt")
                return {"values": values}

            with patch("kara_previwer.delivery.compile_job", side_effect=compile_fixture):
                rebuild(approved, hook, "new-environment")
            self.assertEqual(hook.read_text(), "rebuilt")
