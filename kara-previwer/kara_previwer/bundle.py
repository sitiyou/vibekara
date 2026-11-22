"""Publish immutable assets. All paths here are supplied by the local Agent CLI."""

import atexit
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from threading import Lock

from .hook import unpack


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_media(path, role, clip):
    supported = {
        "background": {".jpg", ".jpeg", ".png", ".webp"},
        "audio": {".m4a", ".ogg", ".mp3", ".wav", ".webm", ".mp4"},
        "fallback": {".webm", ".mp4"},
    }
    if path.suffix.lower() not in supported[role]:
        raise ValueError(f"unsupported {role} file type")
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode:
        raise ValueError(f"unreadable {role}: {probe.stderr.strip()}")
    metadata = json.loads(probe.stdout)
    stream_type = "audio" if role == "audio" else "video"
    stream = next(
        (s for s in metadata["streams"] if s["codec_type"] == stream_type), None
    )
    if not stream:
        raise ValueError(f"{role} has no {stream_type} stream")
    if (
        role != "audio"
        and stream["width"] * clip["height"] != stream["height"] * clip["width"]
    ):
        raise ValueError(f"{role} and preview must have the same aspect ratio")
    if role != "background":
        duration = float(metadata["format"].get("duration", 0))
        if (
            not math.isfinite(duration)
            or abs(duration - clip["duration"]) > 1 / clip["fps"]
        ):
            raise ValueError(f"{role} must be trimmed to the declared clip duration")


def segment_clip(clip, frame):
    """Resolve a whole-media frame to a frame-aligned compiler window."""
    count = math.ceil(clip["duration"] * clip["fps"])
    if type(frame) is not int or not 0 <= frame < count:
        raise ValueError("frame outside timeline")
    width = clip.get("segment_frames")
    if width is None:
        return clip
    if type(width) is not int or width < 1:
        raise ValueError("segment_frames must be a positive integer")
    first = frame // width * width
    return {
        **clip,
        "start": clip["start"] + first / clip["fps"],
        "duration": min(width, count - first) / clip["fps"],
        "media_offset": first / clip["fps"],
    }


def prepare(session, manifest, inherited=None):
    proposal = json.loads(manifest.read_text())
    if "favorite" in proposal:
        from .preferences import Preferences

        prefs = Preferences()
        directory, meta = prefs.lookup(proposal.pop("favorite"))
        compiler = proposal["compiler"]
        compiler["script"] = str(directory / "template.py")
        compiler["resources"] = {
            name: str(directory / name) for name in meta.get("resources", [])
        }
        compiler["dependencies"] = meta.get("dependencies", [])
        proposal.update(
            template=meta["template"],
            fonts=meta.get("fonts", {}),
            faces=meta.get("faces", {}),
            values={**meta["values"], **proposal.get("values", {})},
        )
    if not proposal.get("template") or proposal["template"] == "default":
        raise ValueError("review requires an external template")
    if "config" in proposal or "palette" in proposal:
        raise ValueError("config and palette are generated from the selected template")
    if "compiler" not in proposal and proposal.get("parameters"):
        raise ValueError("editable parameters require a compiler")
    fields = proposal.setdefault("parameters", [])
    proposal.setdefault("values", {f["name"]: f["default"] for f in fields})
    names = [f["name"] for f in fields]
    if len(set(names)) != len(names):
        raise ValueError("duplicate parameter")
    clip = proposal["clip"]
    fps = clip["fps"]
    if type(fps) != int or not 1 <= fps <= 240:
        raise ValueError("invalid frame rate")
    if (
        not all(math.isfinite(clip[k]) for k in ("start", "duration"))
        or clip["start"] < 0
        or clip["duration"] <= 0
    ):
        raise ValueError("invalid clip interval")
    if not all(
        type(clip.get(k)) == int and 0 < clip[k] <= 8192 for k in ("width", "height")
    ) or not clip.get("id"):
        raise ValueError("clip needs a name and valid preview dimensions")
    if abs(clip["start"] * fps - round(clip["start"] * fps)) > 1e-7:
        raise ValueError("clip start must be frame aligned")
    entry = clip.get("entry_frame", 0)
    window = segment_clip(clip, entry)
    if "segment_frames" in clip and ("compiler" not in proposal or "fallback" in clip):
        raise ValueError("segmented review requires compiler-generated previews")
    directory = session.root / "assets"
    directory.mkdir(exist_ok=True)

    def store_file(value, *, hook=False):
        path = (manifest.parent / value).resolve(strict=True)
        key = digest(path)
        target = directory / (key if hook else key + path.suffix.lower())
        if not target.exists():
            with tempfile.TemporaryDirectory(dir=directory) as tmp:
                staging = Path(tmp) / "asset"
                if hook:
                    staging.mkdir()
                    unpack(path, staging)
                else:
                    shutil.copyfile(path, staging)
                try:
                    os.rename(staging, target)
                except OSError:
                    if not target.exists():
                        raise
        return "assets/" + target.name

    for key in ("audio", "background", "fallback"):
        if key == "fallback" and key not in clip:
            continue
        clip[key] = store_file(clip[key])
        check_media(session.root / clip[key], key, clip)
        if key == "audio" and clip.get("motion"):
            check_media(session.root / clip[key], "fallback", clip)
    if "compiler" in proposal:
        config = proposal.pop("compiler")
        config["template"] = proposal["template"]
        config["python"] = str((manifest.parent / config["python"]).absolute())
        for name in ("script", "krc", "midi"):
            config[name] = store_file(config[name])
        resources = config.pop("resources", {})
        if resources:
            stored = {}
            for name, value in resources.items():
                path = Path(name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or path == Path(".")
                    or path.parts[0] in {"template.py", "template.json"}
                ):
                    raise ValueError("invalid recipe resource path")
                stored[name] = store_file(value)
            key = hashlib.sha256(
                json.dumps([config["script"], stored], sort_keys=True).encode()
            ).hexdigest()
            target = directory / key
            if not target.exists():
                with tempfile.TemporaryDirectory(dir=directory) as tmp:
                    tree = Path(tmp) / "recipe"
                    tree.mkdir()
                    shutil.copyfile(
                        session.root / config["script"], tree / "template.py"
                    )
                    for name, value in stored.items():
                        destination = tree / name
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(session.root / value, destination)
                    try:
                        tree.rename(target)
                    except OSError:
                        if not target.is_dir():
                            raise
            config.update(script=f"assets/{key}/template.py", resources=list(stored))
        configs = session.root / "configs"
        configs.mkdir(exist_ok=True)
        content = json.dumps(config, sort_keys=True)
        key = hashlib.sha256(content.encode()).hexdigest()
        with tempfile.NamedTemporaryFile(dir=configs, mode="w", delete=False) as f:
            f.write(content)
        os.replace(f.name, configs / key)
        proposal["config"] = key
        local = {**config, "script": str(session.root / config["script"])}
        schema = compile_job(local, describe=True)
        choices = {k: v for k, v in (inherited or {}).items() if k in schema["values"]}
        choices.update(proposal.get("values", {}))
        proposal.update(
            compile_job(local, describe=True, values=choices) if choices else schema
        )
        proposal["hook"] = compiled(
            session, {**proposal, "clip": window}, proposal["values"]
        )
    else:
        proposal["hook"] = store_file(proposal["hook"], hook=True)
    for preset in proposal.get("presets", []):
        validate_values(proposal, {**proposal.get("values", {}), **preset["values"]})
    shader = (session.root / proposal["hook"] / "scene.frag").read_text()
    clock = re.search(r"PTS \* float\((\d+)\).*?\) - (\d+)", shader)
    length = re.search(r"index>=(\d+)", shader)
    if not clock or (int(clock[1]), int(clock[2])) != (
        fps,
        round(window["start"] * fps),
    ):
        raise ValueError("hook clock differs from the clip start or frame rate")
    if not length or int(length[1]) < math.ceil(window["duration"] * fps - 1e-8):
        raise ValueError("hook ends before the clip")
    return proposal


_workers = {}
_worker_lock = Lock()
_scene_locks = {"preview": Lock(), "native": Lock()}
_ready_scenes = {}


@atexit.register
def stop_workers():
    for process in _workers.values():
        process.terminate()


def compile_job(config, **options):
    interpreter = config["python"]
    lane = options.get("shared_scene")
    key = (interpreter, lane)
    lock = _scene_locks[lane] if lane else _worker_lock
    scene_key = (
        json.dumps([config, options["values"]], sort_keys=True) if lane else None
    )
    # A warm scene may be exporting another short interval. Wait for that export
    # instead of rebuilding the song prefix. A new design can paint independently.
    if options.get("cached_only") and _ready_scenes.get(key) != scene_key:
        return {"miss": True}
    lock.acquire()
    try:
        while True:
            process = _workers.get(key)
            if process is None or process.poll() is not None:
                _ready_scenes.pop(key, None)
                if options.get("cached_only"):
                    return {"miss": True}
                process = subprocess.Popen(
                    [interpreter, "-u", str(Path(__file__).with_name("compiler.py"))],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                )
                _workers[key] = process
            process.stdin.write(json.dumps({**config, **options}) + "\n")
            process.stdin.flush()
            line = process.stdout.readline()
            if not line:
                raise ValueError("template compiler stopped")
            message = json.loads(line)
            if not message.get("restart"):
                break
            process.wait()
        if "error" in message:
            raise ValueError(message["error"][-2000:])
        if lane and not message["result"].get("miss"):
            _ready_scenes[key] = scene_key
        return message["result"]
    finally:
        lock.release()


def validate_values(proposal, values):
    fields = {f["name"]: f for f in proposal.get("parameters", [])}
    if set(values) != set(fields):
        raise ValueError("incomplete or unknown parameters")
    for name, value in values.items():
        field = fields[name]
        match field["kind"]:
            case "color":
                valid = isinstance(value, str) and re.fullmatch("[0-9a-fA-F]{6}", value)
            case "float" | "int":
                types = (int,) if field["kind"] == "int" else (int, float)
                valid = type(value) in types and field["low"] <= value <= field["high"]
            case "bool":
                valid = type(value) is bool
            case "choice":
                valid = value in field["choices"]
            case "text":
                valid = isinstance(value, str)
            case _:
                valid = False
        if not valid:
            raise ValueError(f"invalid value for {name}")


def local_config(session, proposal):
    config = json.loads((session.root / "configs" / proposal["config"]).read_text())
    for name in ("script", "krc", "midi"):
        config[name] = str(session.root / config[name])
    return config


def _export_window(config, clip, values, output, *, prefetch, lane):
    job = {
        "values": values,
        "fps": clip["fps"],
        "start": clip["start"],
        "duration": clip["duration"],
        "output": str(output),
    }
    if "segment_frames" in clip:
        result = compile_job(config, **job, shared_scene=lane, cached_only=not prefetch)
        if not result.get("miss"):
            return
    compile_job(config, **job)


def compiled(session, proposal, values, *, full=None, prefetch=False):
    """Resolve relative immutable source paths only in the trusted service."""
    config = local_config(session, proposal)
    clip = proposal["clip"]
    options = {"values": values, "fps": clip["fps"]}
    if full:
        return compile_job(config, **options, output=str(full))
    options["values"] = {**values, **proposal.get("palette", {})}
    key = hashlib.sha256(
        json.dumps(
            [proposal["config"], options, clip["start"], clip["duration"]],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    target = session.root / "assets" / key
    if not target.exists():
        with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
            hook = Path(tmp) / "preview.hook"
            _export_window(
                config, clip, options["values"], hook, prefetch=prefetch, lane="preview"
            )
            staging = Path(tmp) / "parts"
            staging.mkdir()
            unpack(hook, staging)
            try:
                os.rename(staging, target)
            except OSError:
                if not target.exists():
                    raise
    return "assets/" + key


def native_preview(session, proposal, hook, values, *, prefetch=False):
    import subprocess

    from .hook import repack

    clip = proposal["clip"]
    if clip.get("fallback") and values == proposal.get("values", {}):
        return clip["fallback"]
    key = hashlib.sha256(
        json.dumps(["song-clock", hook, values, clip], sort_keys=True).encode()
    ).hexdigest()
    target = session.root / "assets" / (key + ".webm")
    if not target.exists():
        with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
            directory = Path(tmp)
            source = directory / "scene.hook"
            if any(
                values[name] != default
                for name, default in proposal.get("palette", {}).items()
            ):
                _export_window(
                    local_config(session, proposal),
                    clip,
                    values,
                    source,
                    prefetch=prefetch,
                    lane="native",
                )
            else:
                repack(session.root / hook, source)
            fps = clip["fps"]
            if clip.get("motion"):
                inputs = [
                    "-ss",
                    str(clip.get("media_offset", 0)),
                    "-i",
                    str(session.root / clip["audio"]),
                ]
                frames = f"fps={fps},format=gbrp"
            else:
                inputs = [
                    "-framerate",
                    str(fps),
                    "-i",
                    str(session.root / clip["background"]),
                ]
                frames = "format=gbrp,loop=-1:1:0"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-init_hw_device",
                    "vulkan=vk:0",
                    "-filter_hw_device",
                    "vk",
                    *inputs,
                    "-an",
                    "-vf",
                    f"{frames},setpts=N+{round(clip['start'] * fps)},libplacebo=w={clip['width']}:h={clip['height']}:custom_shader_path=scene.hook:format=yuv420p,setpts=PTS-STARTPTS",
                    "-frames:v",
                    str(math.ceil(clip["fps"] * clip["duration"] - 1e-8)),
                    "-c:v",
                    "libvpx-vp9",
                    "-deadline",
                    "realtime",
                    "-cpu-used",
                    "6",
                    "-crf",
                    "18",
                    "-b:v",
                    "0",
                    "preview.webm",
                ],
                cwd=directory,
                check=True,
                capture_output=True,
            )
            os.replace(directory / "preview.webm", target)
    return "assets/" + target.name
