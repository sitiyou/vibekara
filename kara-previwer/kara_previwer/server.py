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
from functools import lru_cache
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
from .composition import normalize, structural_composition
from .preferences import Preferences
from .proposals import check_fonts, decorate, reuse, save_package, selected
from .store import Conflict, Session


@lru_cache(maxsize=64)
def composition_details(root, version, direction):
    session = Session(root)
    revisions = session.state()["revisions"]
    if not 1 <= version <= len(revisions):
        raise ValueError("unknown version")
    proposal = selected(revisions[version - 1], direction)
    declared = proposal.get("composition_tracks", {})
    if not declared:
        return {"tracks": {}}
    clip = proposal["clip"]
    result = compile_job(
        local_config(session, proposal), worker="metadata", inspect_tracks=True,
        start=clip["start"], duration=clip["duration"], values=proposal["values"],
        composition=structural_composition(proposal, proposal["composition"]),
    )
    present = result["tracks"]
    details = result.get("details", {})
    return {"tracks": {
        key: {"label": label, **details.get(key, {})}
        for key, label in declared.items() if present is not None and key in present
    }}


@lru_cache(maxsize=32)
def candidate_card(root, version, direction):
    session = Session(root)
    revisions = session.state()["revisions"]
    if not 1 <= version <= len(revisions):
        raise ValueError("unknown version")
    proposal = selected(revisions[version - 1], direction)
    clip = proposal["clip"]
    window = segment_clip(clip, clip.get("entry_frame", 0))
    entry = clip.get("entry_frame", 0) / clip["fps"]
    offset = max(window.get("media_offset", 0), entry - 0.5)
    end = window.get("media_offset", 0) + window["duration"]
    offset = max(window.get("media_offset", 0), min(offset, end - 2))
    offset = round(offset * clip["fps"]) / clip["fps"]
    short = {
        **window, "start": clip["start"] + offset, "media_offset": offset,
        "duration": min(3, end - offset),
    }
    video = native_preview(session, {**proposal, "clip": short}, proposal["hook"], proposal["values"], thumbnail=True)
    poster = (session.root / video).with_suffix(".jpg")
    if not poster.is_file():
        sample = max(0, min(entry - offset, short["duration"] - 1 / clip["fps"]))
        with tempfile.TemporaryDirectory(dir=poster.parent) as folder:
            still = Path(folder) / "poster.jpg"
            subprocess.run(
                ["ffmpeg", "-v", "error", "-nostdin", "-ss", str(sample), "-i", str(session.root / video),
                 "-frames:v", "1", str(still)],
                check=False, capture_output=True,
            )
            if still.is_file():
                still.replace(poster)
    return {"video": video, "poster": "assets/" + poster.name} if poster.is_file() else {"video": video}


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


@lru_cache(maxsize=1)
def legacy_effect_previews():
    return json.loads(Path(__file__).with_name("legacy-effect-previews.json").read_text(encoding="utf-8"))


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
            if "composition" in proposal:
                published = proposal["composition"]
                edited = normalize(proposal, data.get("composition", published))
                proposal = {**proposal, "composition": edited, "published_composition": published}
                if route == "draft":
                    return self.respond(session.save_draft(
                        version, data.get("direction", 0), data["revision"], values, edited,
                    ))
                if route in ("submit", "collection") and "composition" not in data:
                    raise Conflict("需要提交当前预览的组件组合")
            elif "composition" in data:
                raise ValueError("当前方案没有可编辑的组件")
            # Agent only receives values actually rendered by this revision.
            clip = editing_clip(proposal, values)
            window = preview_window(
                session, proposal, values, data.get("frame", clip.get("entry_frame", 0)),
                whole=route == "render" and data.get("whole") is True,
                presented=data.get("hook"),
            )
            segment = {**proposal, "clip": window}
            initial = segment_clip(clip, clip.get("entry_frame", 0))
            unchanged_composition = structural_composition(proposal, proposal.get("composition")) == (
                structural_composition(proposal, proposal.get("published_composition"))
            )
            if values == proposal.get("values", {}) and unchanged_composition and window == initial:
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
                if "composition" in proposal:
                    raise ValueError("组合将随本次评审保存")
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
                return self.respond({"video": native_preview(session, segment, hook, values)})
            if route == "render":
                return self.respond({"hook": hook})
            if route == "submit":
                if data["hook"] != hook:
                    raise Conflict("selected parameters have not been presented")
                if {"kind", "id"} & data.keys():
                    raise ValueError("reserved event fields")
                if "composition" in proposal:
                    data["composition"] = proposal["composition"]
                elif data["action"] == "continue":
                    raise ValueError("当前方案没有可继续的组件组合")
                for frame in data.get("frames", []):
                    revision = frame["version"]
                    if type(revision) != int or not 1 <= revision <= len(
                        state["revisions"]
                    ):
                        raise ValueError("unknown capture revision")
                    design = selected(
                        state["revisions"][revision - 1], frame.get("direction", 0)
                    )
                    if "composition" in design:
                        design = {**design, "published_composition": design["composition"],
                                  "composition": normalize(design, frame.get("composition"))}
                        frame["composition"] = design["composition"]
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
                    if "composition" in design or "segment_frames" in clip:
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
        if route in {"composition-tracks", "composition-details", "candidate-card"}:
            query = parse_qs(url.query)
            version = int(query.get("version", ["0"])[0])
            direction = int(query.get("direction", ["0"])[0])
            if route == "candidate-card":
                return self.respond(candidate_card(session.root, version, direction))
            details = composition_details(session.root, version, direction)
            if route == "composition-tracks":
                return self.respond({key: track["label"] for key, track in details["tracks"].items()})
            return self.respond(details)
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
                    if "component_schema" in option and "component_previews" not in option:
                        option["component_previews"] = legacy_effect_previews()
            return self.respond(state)
        if route == "preferences":
            return self.respond(Preferences().read())
        if route == "history":
            return self.respond(
                [
                    event
                    for event in session.events(0)
                    if event["kind"] in ("feedback", "continue", "accept")
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
        elif re.fullmatch(r"effect-previews/[a-z][a-z0-9-]*\.(?:jpg|mp4)", route):
            path = Path(__file__).parent / route
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
