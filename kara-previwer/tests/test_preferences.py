import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kara_previwer.preferences import Preferences
from kara_previwer.store import Conflict


class PreferencesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.prefs = Preferences(Path(tmp.name))
        self.script = Path(tmp.name) / "source.py"
        self.script.write_text("# template")
        self.package = self.script, {"template": "test", "values": {"size": 100}}

    def test_unicode_limit_repair_and_concurrent_writes(self):
        prefs = self.prefs
        digest = prefs.read()["digest"]
        text = "字歌🎵" * 409 + "日本"
        self.assertEqual(len(text.encode()), 4096)
        valid = prefs.save(text, digest)
        with self.assertRaisesRegex(ValueError, "exceeds 4096 by 1"):
            prefs.save(text + "!", valid["digest"])
        with self.assertRaises(Conflict):
            prefs.save("stale", digest)
        self.assertEqual(prefs.read(), valid)
        prefs.file.write_text(text + "!")
        invalid = prefs.read()
        self.assertIn("4097", invalid["error"])
        self.assertEqual(prefs.save(text, invalid["digest"]), valid)

    def test_library_versioning_and_atomic_failure(self):
        prefs = self.prefs
        new = prefs.manage(
            "add", prefs.read()["digest"], name="明朝", package=self.package
        )
        (entry,) = new["templates"]
        changed = prefs.manage(
            "update", new["digest"], entry["id"], "明朝", "", self.package
        )
        (latest,) = changed["templates"]
        self.assertEqual(latest["id"], entry["id"])
        self.assertNotEqual(latest["generation"], entry["generation"])
        self.assertNotEqual(changed["digest"], new["digest"])
        with (
            patch("kara_previwer.preferences.atomic", side_effect=OSError("disk full")),
            self.assertRaises(OSError),
        ):
            prefs.manage(
                "update", changed["digest"], entry["id"], "新名", "", self.package
            )
        self.assertEqual(prefs.read(), changed)
        with self.assertRaises(ValueError):
            prefs.save(changed["text"] + changed["text"], changed["digest"])
        renamed = prefs.manage("rename", changed["digest"], entry["id"], "新名")
        self.assertEqual(renamed["templates"][0]["name"], "新名")
        removed = prefs.manage("remove", renamed["digest"], entry["id"])
        self.assertEqual(removed["templates"], [])

    def test_full_index_and_failed_commit_preserve_active_package(self):
        prefs = self.prefs
        new = prefs.manage(
            "add", prefs.read()["digest"], name="明朝", package=self.package
        )
        text = "a" * (4095 - new["size"]) + "\n" + new["text"]
        full = prefs.save(text, new["digest"])
        with self.assertRaisesRegex(ValueError, "exceeds 4096"):
            prefs.manage("add", full["digest"], name="星空", package=self.package)
        self.assertEqual(prefs.read(), full)
        (entry,) = full["templates"]
        stored, _ = prefs.package(entry["id"], entry["generation"])
        self.assertEqual(
            (stored / "template.py").read_bytes(), self.script.read_bytes()
        )
