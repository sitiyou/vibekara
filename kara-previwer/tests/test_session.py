"""The CLI and HTTP handler share these transaction and asset boundaries."""

import base64
import json
import tempfile
import unittest
import uuid
import wave
from array import array
from pathlib import Path

from kara_previwer.bundle import prepare
from kara_previwer.hook import repack
from kara_previwer.store import Conflict, Session


class ReviewTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.session = Session.create(self.root, "Song")

    def test_retry_reconnect_and_return_to_earlier_design(self):
        first = {"values": {"size": 100}}
        self.session.publish(0, first)
        item = {
            "token": str(uuid.uuid4()),
            "action": "feedback",
            "version": 1,
            "values": {"size": 95},
        }
        receipt = self.session.submit(item)
        self.assertEqual(self.session.submit(item), receipt)
        with self.assertRaises(Conflict):
            self.session.submit(dict(item, values={}))
        resumed = Session(self.session.root)
        self.assertEqual(resumed.pending(), [item])
        self.assertEqual(resumed.claim(item["token"]), resumed.claim(item["token"]))
        self.assertTrue(resumed.state()["working"])
        revision = resumed.publish(1, {"values": item["values"]}, item["token"])
        self.assertEqual(
            resumed.publish(1, {"values": item["values"]}, item["token"]), revision
        )
        self.assertEqual(resumed.pending(), [])
        with self.assertRaises(Conflict):
            resumed.publish(1, first)
        adopted = dict(item, action="accept", token=str(uuid.uuid4()), base=2)
        resumed.submit(adopted)
        self.assertEqual(resumed.state()["saved"], adopted)
        with self.assertRaises(Conflict):
            resumed.publish(2, first)

    def test_standalone_bundle_clock_and_lossless_native_roundtrip(self):
        parts = self.root / "scene"
        parts.mkdir()
        (parts / "KARAMASK.bin").write_bytes(bytes([255]))
        (parts / "KARADATA.bin").write_bytes(array("f", (30, 900, 270, 1)).tobytes())
        (parts / "textures.json").write_text(
            json.dumps({"KARAMASK": [1, 1], "KARADATA": [1, 1], "clock": [30, 900, 270]})
        )
        (parts / "scene.frag").write_text(
            "vec4 hook(){int index=int(floor(PTS * item(0) + 0.001)) - refAt(1);"
            "if(index>=refAt(2))return vec4(0);return HOOKED_tex(HOOKED_pos);}"
        )
        repack(parts, self.root / "scene.hook")
        clip = {
            "id": "v",
            "start": 30,
            "duration": 9,
            "fps": 30,
            "width": 1,
            "height": 1,
            "audio": "clip.wav",
            "background": "cover.png",
        }
        with wave.open(str(self.root / "clip.wav"), "wb") as sound:
            sound.setparams((1, 1, 8000, 0, "NONE", ""))
            sound.writeframes(bytes(9 * 8000))
        (self.root / "cover.png").write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            )
        )
        manifest = self.root / "proposal.json"
        spec = {"template": "verse", "hook": "scene.hook", "clip": clip}
        manifest.write_text(json.dumps(spec))
        p = prepare(self.session, manifest)
        result = self.session.root / p["hook"]
        for path in parts.iterdir():
            self.assertEqual(path.read_bytes(), (result / path.name).read_bytes())
        spec["clip"]["start"] = 0
        manifest.write_text(json.dumps(spec))
        with self.assertRaisesRegex(ValueError, "clock"):
            prepare(self.session, manifest)
        spec["template"] = "default"
        manifest.write_text(json.dumps(spec))
        with self.assertRaisesRegex(ValueError, "external"):
            prepare(self.session, manifest)
