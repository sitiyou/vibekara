"""Loopback-only review API, replayable event stream and immutable assets."""

import base64
import binascii
import hashlib
import json
import math
import mimetypes
import re
import struct
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Lock, Thread
from typing import cast
from urllib.parse import parse_qs, urlsplit

from .bundle import (
    compile_job,
    compiled,
    editing_clip,
    local_config,
    native_preview,
    resource_path,
    segment_clip,
    validate_values,
)
from .preferences import Preferences
from .proposals import check_fonts, decorate, reuse, save_package, selected
from .store import Conflict, Session


def preview_window(session, proposal, values, frame, *, whole=False, presented=None):
    clip = editing_clip(proposal, values)
    window = segment_clip(clip, frame)
    if "segment_frames" in clip and "segment_frames" not in proposal["clip"]:
        if whole:
            return clip
        if presented and "config" in proposal:
            path = resource_path(proposal, values)
            if presented == path and (session.root / path).is_dir():
                return clip
    return window


def snapshot(session, data, width, height):
    prefix = "data:image/png;base64,"
    if not isinstance(data, str) or not data.startswith(prefix):
        raise ValueError("PNG capture required")
    raw = base64.b64decode(data[len(prefix) :], validate=True)
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("invalid PNG")
    if len(raw) < 24 or struct.unpack(">II", raw[16:24]) != (width, height):
        raise ValueError("PNG dimensions differ from the capture")
    target = session.root / "assets" / (hashlib.sha256(raw).hexdigest() + ".png")
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as f:
            f.write(raw)
        Path(f.name).replace(target)
    return "assets/" + target.name


class ReviewServer(ThreadingHTTPServer):
    def __init__(self, root: Path, port: int, executor: ThreadPoolExecutor):
        super().__init__(("127.0.0.1", port), Handler)
        self.root = root
        self.executor = executor
        self.warm_lock = Lock()
        self.warmed: set[str] = set()


class Handler(BaseHTTPRequestHandler):
    def respond(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def dispatch(self):
        server = cast(ReviewServer, self.server)
        host = self.headers.get("Host", "")
        if host not in (
            f"127.0.0.1:{server.server_port}",
            f"localhost:{server.server_port}",
        ):
            return self.respond({"error": "local host required"}, 403)
        url = urlsplit(self.path)
        match = re.fullmatch(r"/s/([a-f0-9]{32})/(.*)", url.path)
        if not match:
            return self.respond({"error": "unknown session URL"}, 404)
        session = Session(server.root / match[1])
        if not session.db.exists():
            raise FileNotFoundError
        route = match[2]
        if self.command == "POST":
            if (
                self.headers.get("Origin", "http://" + host) != "http://" + host
                or self.headers.get_content_type() != "application/json"
            ):
                return self.respond({"error": "same-origin JSON required"}, 403)
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 64 * 1024**2:
                return self.respond({"error": "invalid request size"}, 413)
            data = json.loads(self.rfile.read(size))
            if route == "preferences":
                return self.respond(Preferences().save(data["text"], data["digest"]))
            if route == "collection" and data["action"] in {"remove", "rename"}:
                return self.respond(Preferences().manage(**data))
            state = session.state()
            version = data["version"]
            if type(version) != int or not 1 <= version <= len(state["revisions"]):
                raise ValueError("unknown version")
            proposal = selected(
                state["revisions"][version - 1], data.get("direction", 0)
            )
            if route == "reuse":
                package = Preferences().lookup(data["key"])
                return self.respond(reuse(session, proposal, package, data["base"]))
            values = data["values"]
            if not isinstance(values, dict):
                raise ValueError("invalid parameter snapshot")
            validate_values(proposal, values)
            if (
                any(
                    f["name"].lower() in {"font", "fontname", "font_family"}
                    for f in proposal["parameters"]
                )
                and "fonts" not in proposal
            ):
                decorate(proposal, require_selected=False)
            check_fonts(proposal, values)
            # Agent only receives values actually rendered by this revision.
            clip = editing_clip(proposal, values)
            window = preview_window(
                session, proposal, values, data.get("frame", clip.get("entry_frame", 0)),
                whole=route == "render" and data.get("whole") is True,
                presented=data.get("hook"),
            )
            segment = {**proposal, "clip": window}
            initial = segment_clip(clip, clip.get("entry_frame", 0))
            if values == proposal.get("values", {}) and window == initial:
                hook = proposal["hook"]
            elif "config" in proposal:
                hook = compiled(
                    session,
                    segment,
                    values,
                    prefetch=route == "render" and data.get("prefetch") is True,
                )
            else:
                raise ValueError("fixed candidate")
            if route == "collection":
                if data["hook"] != hook:
                    raise Conflict("preview is still compiling")
                return self.respond(
                    Preferences().manage(
                        data["action"],
                        data["digest"],
                        data.get("key", ""),
                        data["name"],
                        data.get("description", ""),
                        save_package(session, proposal, values),
                    )
                )
            if route == "native":
                return self.respond(
                    {
                        "video": native_preview(
                            session,
                            segment,
                            hook,
                            values,
                            prefetch=data.get("prefetch") is True,
                        )
                    }
                )
            if route == "render":
                return self.respond({"hook": hook})
            if route == "submit":
                if data["hook"] != hook:
                    raise Conflict("selected parameters have not been presented")
                if {"kind", "id"} & data.keys():
                    raise ValueError("reserved event fields")
                for frame in data.get("frames", []):
                    revision = frame["version"]
                    if type(revision) != int or not 1 <= revision <= len(
                        state["revisions"]
                    ):
                        raise ValueError("unknown capture revision")
                    design = selected(
                        state["revisions"][revision - 1], frame.get("direction", 0)
                    )
                    clip = editing_clip(design, frame["values"])
                    validate_values(design, frame["values"])
                    if (frame["fps"], frame["start"], frame["clip"]) != (
                        clip["fps"],
                        clip["start"],
                        clip["id"],
                    ):
                        raise ValueError("capture clock differs from its clip")
                    if type(frame["frame"]) != int or not 0 <= frame[
                        "frame"
                    ] < math.ceil(clip["duration"] * clip["fps"]):
                        raise ValueError("capture frame outside clip")
                    if not math.isclose(
                        frame["time"], clip["start"] + frame["frame"] / clip["fps"]
                    ):
                        raise ValueError(
                            "capture timestamp differs from its frame number"
                        )
                    if "segment_frames" in clip:
                        capture_window = preview_window(
                            session, design, frame["values"], frame["frame"], presented=frame["hook"]
                        )
                        expected = compiled(
                            session, {**design, "clip": capture_window}, frame["values"]
                        )
                        if frame["hook"] != expected:
                            raise Conflict("capture differs from rendered segment")
                    for mark in frame["marks"]:
                        if mark["type"] not in ("box", "point"):
                            raise ValueError("unknown annotation marker")
                        coordinates = (
                            ("x", "y", "endX", "endY")
                            if mark["type"] == "box"
                            else ("x", "y")
                        )
                        if any(not 0 <= mark[axis] <= 1 for axis in coordinates):
                            raise ValueError("marker outside frame")
                    for field in ("image", "annotated"):
                        frame[field] = snapshot(
                            session, frame[field], frame["width"], frame["height"]
                        )
                return self.respond({"event": session.submit(data)})
            raise FileNotFoundError
        if route == "state":
            state = session.state()
            if state["revisions"]:
                p = state["revisions"][-1]
                if "config" in p:
                    with server.warm_lock:
                        if p["config"] not in server.warmed:
                            server.warmed.add(p["config"])
                            server.executor.submit(
                                compile_job, local_config(session, p), warm=True
                            )
            for revision in state["revisions"]:
                for option in [revision, *revision.get("directions", [])]:
                    decorate(option, require_selected=False)
            return self.respond(state)
        if route == "preferences":
            return self.respond(Preferences().read())
        if route == "history":
            return self.respond(
                [
                    event
                    for event in session.events(0)
                    if event["kind"] in ("feedback", "accept")
                ]
            )
        if route == "events":
            after = int(
                self.headers.get("Last-Event-ID")
                or parse_qs(url.query).get("after", ["0"])[0]
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            for _ in range(100):
                for event in session.events(after):
                    after = event["id"]
                    self.wfile.write(
                        f"id: {after}\ndata: {json.dumps(event)}\n\n".encode()
                    )
                self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
                time.sleep(0.5)
            return
        if re.fullmatch(
            r"assets/[a-f0-9]{64}(?:\.(?:png|jpeg|jpg|webp|ogg|wav|m4a|mp3|mp4|webm)|/(?:scene.frag|textures.json|KARA(?:MASK|DATA).bin))",
            route,
        ):
            path = session.root / route
        elif not route or re.fullmatch(r"ui/[\w.-]+", route):
            path = Path(__file__).with_name("web") / (route or "index.html")
        else:
            raise FileNotFoundError
        with path.open("rb") as f:
            length = path.stat().st_size
            header = self.headers.get("Range")
            start, end = 0, length - 1
            if header:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
                if not match or not any(match.groups()):
                    return self.respond({"error": "invalid byte range"}, 416)
                if match[1]:
                    start = int(match[1])
                    end = min(end, int(match[2])) if match[2] else end
                else:
                    start = max(0, length - int(match[2]))
                if start > end:
                    return self.respond({"error": "unsatisfiable byte range"}, 416)
            self.send_response(206 if header else 200)
            self.send_header(
                "Content-Type",
                mimetypes.guess_type(path)[0] or "application/octet-stream",
            )
            self.send_header("Accept-Ranges", "bytes")
            if header:
                self.send_header("Content-Range", f"bytes {start}-{end}/{length}")
            remaining = end - start + 1
            self.send_header("Content-Length", str(remaining))
            self.end_headers()
            f.seek(start)
            while remaining:
                chunk = f.read(min(remaining, 256 * 1024))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def handle_request(self):
        try:
            self.dispatch()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except FileNotFoundError:
            self.respond({"error": "file not found"}, 404)
        except Conflict as error:
            self.respond({"error": str(error)}, 409)
        except (ValueError, TypeError, KeyError, binascii.Error) as error:
            self.respond({"error": str(error)}, 400)

        except OSError as error:
            self.respond({"error": str(error)}, 500)
        except subprocess.CalledProcessError as error:
            self.respond({"error": str(error.stderr)[-1000:]}, 422)

    do_GET = do_POST = handle_request


def serve(root, port):
    with (
        ThreadPoolExecutor(max_workers=1) as executor,
        ReviewServer(root, port, executor) as server,
    ):
        from .notify import watch

        stop = Event()
        notifications = Thread(target=watch, args=(root, stop), daemon=True)
        notifications.start()
        try:
            server.serve_forever()
        finally:
            stop.set()
            notifications.join(timeout=21)
