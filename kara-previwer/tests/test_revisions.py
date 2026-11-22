import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from kara_previwer.proposals import check_fonts, decorate, revise, save_package
from kara_previwer.store import Session


class RevisionTest(unittest.TestCase):
    def test_delta_uses_submitted_direction_and_values(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session.create(Path(directory), "song")
            clip = {"id": "verse", "fallback": "old.webm"}
            option = {
                "parameters": [
                    {"name": "ink", "kind": "color"},
                    {"name": "rate", "kind": "float", "low": 0, "high": 2},
                ],
                "clip": clip,
                "template": "stars",
                "hook": "original",
                "config": "stars",
                "values": {"ink": "FF0000", "rate": 1},
            }
            session.publish(0, {**option, "template": "quiet", "directions": [option]})
            token = str(uuid.uuid4())
            session.submit(
                {
                    "action": "feedback",
                    "version": 1,
                    "base": 1,
                    "token": token,
                    "direction": 1,
                    "values": {"ink": "FFEEDD", "rate": 1},
                }
            )
            edit = {"values": {"rate": 0.5}, "focus": ["rate"]}
            with patch("kara_previwer.proposals.compiled", return_value="updated"):
                result = revise(session, 1, token, edit)
                self.assertEqual(result, revise(session, 1, token, edit))
            self.assertEqual(result["template"], "stars")
            self.assertEqual(result["values"], {"rate": 0.5, "ink": "FFEEDD"})
            self.assertNotIn("fallback", result["clip"])
            self.assertEqual(session.state()["version"], 2)

    def test_font_removed_after_publish(self):
        p = {
            "parameters": [{"name": "font", "kind": "text"}],
            "values": {"font": "A"},
            "fonts": {"font": ["A", "B"]},
        }
        faces = {"A": {"fullname": "A Regular"}, "B": {"fullname": "B Regular"}}
        with patch("kara_previwer.proposals.resolve_font", side_effect=faces.get):
            decorate(p)
            del faces["A"]
            with self.assertRaisesRegex(ValueError, "候选：B"):
                check_fonts(p, p["values"])
            decorate(p, require_selected=False)
            self.assertEqual(p["fonts"]["font"], ["B"])
            check_fonts(p, {"font": "B"})
        with self.assertRaisesRegex(ValueError, "模板源"):
            save_package(None, {}, {})

    def test_push_and_poll_deliver_same_token(self):
        from kara_previwer.notify import bind, forward

        with tempfile.TemporaryDirectory() as directory:
            session = Session.create(Path(directory), "song")
            option = {
                "parameters": [],
                "values": {},
                "template": "quiet",
                "hook": "quiet",
                "clip": {},
            }
            session.publish(0, option)
            with (
                patch.dict("os.environ", {"CODEX_THREAD_ID": str(uuid.uuid4())}),
                patch("shutil.which", return_value="mock-queue"),
            ):
                bind(session)
            token = str(uuid.uuid4())
            session.submit(
                {"token": token, "version": 1, "action": "feedback", "values": {}}
            )
            with patch("kara_previwer.notify.subprocess.run") as queue:
                queue.return_value.returncode = 0
                forward(session)
                forward(session)
                forward(session)
                self.assertEqual(queue.call_count, 1)
                self.assertIn(token, queue.call_args.args[0][5])
            (event,) = session.events(1)
            self.assertEqual(event["token"], token)
            patch_data = {"summary": "细调", "focus": []}
            first = revise(session, 1, token, patch_data)
            self.assertEqual(revise(session, 1, event["token"], patch_data), first)
            self.assertEqual(Session(session.root).state()["version"], 2)
