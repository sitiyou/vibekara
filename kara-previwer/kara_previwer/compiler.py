"""Trusted local adapter. Run with the interpreter containing the producer's packages."""

import json
import sys
import traceback
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=8)
def load_recipe(script, name):
    from namioto.karaoke.templates import load_templates

    return load_templates([script]).get(name)


@lru_cache(maxsize=4)
def load_song(krc, midi, offset_ms, colors, wavetone, track_style=()):
    from namioto.karaoke.export_settings import ExportSettings
    from namioto.subtitle import build_song

    return build_song(
        Path(krc).read_text(),
        Path(midi).read_bytes(),
        semantic=True,
        settings=ExportSettings(offset_ms=offset_ms, channel_colors=dict(colors), track_style=dict(track_style)),
        wavetone=wavetone,
    )


@lru_cache(maxsize=4)
def load_timing_directory(directory):
    from namioto.karaoke.song_input import load_song_input

    return load_song_input(directory)


@lru_cache(maxsize=4)
def load_project_song(path, offset_ms, harmony_tracks):
    from namioto.karaoke.song_input import load_project_input

    return load_project_input(path, offset_ms=offset_ms, harmony_tracks=harmony_tracks)


def timing_key(job):
    if "project" in job:
        return (job["project"], job.get("offset_ms", 0), job.get("harmony_tracks", ""))
    if "song_input" in job:
        return (job["song_input"],)
    return (
        job["krc"],
        job["midi"],
        job.get("offset_ms", 0),
        tuple(sorted((int(k), v) for k, v in job.get("colors", {}).items())),
        job.get("wavetone", False),
        tuple(sorted((int(k), v) for k, v in job.get("track_style", {}).items())),
    )


# One immutable whole-song scene per scene worker. Keep the editing worker free for
# first paints, descriptions, and new designs while this scene is being built.
_scene_key = None
_scene = None


def shared_scene(job, recipe, song, values, timing):
    global _scene_key, _scene
    key = (
        job["script"],
        job["template"],
        timing,
        tuple(sorted(values.items())),
    )
    if key != _scene_key:
        if job.get("cached_only"):
            return None
        built = recipe.build(song, values).prepare_hook()
        _scene_key, _scene = key, built
    return _scene


def run(job):
    recipe = load_recipe(job["script"], job["template"])
    if recipe.id == "default" or not recipe.semantic:
        raise ValueError(
            "review requires an external recipe registered with semantic=True"
        )
    values = recipe.resolve(job.get("values", {}))
    if job.get("describe"):
        return {
            "parameters": [asdict(field) for field in recipe.parameters],
            "values": values,
            "palette": {
                f.name: str(f.default).lstrip("#")
                for f in recipe.parameters
                if f.name in recipe.palette_parameters
            },
        }
    timing = timing_key(job)
    if "project" in job:
        song = load_project_song(*timing)
    elif "song_input" in job:
        song = load_timing_directory(job["song_input"])
    else:
        song = load_song(*timing)
    if job.get("warm"):
        return {}
    if job.get("shared_scene"):
        scene = shared_scene(job, recipe, song, values, timing)
        if scene is None:
            return {"miss": True}
        if job.get("prepare_scene"):
            return {}
    else:
        if "duration" in job:
            song = replace(
                song, preview_interval=(job["start"], job["start"] + job["duration"])
            )
        scene = recipe.build(song, values)
    export = scene.export_resources if job.get("resources_output") else scene.export
    export(
        job["output"],
        fps=job["fps"],
        start=job.get("start", 0),
        duration=job.get("duration"),
    )
    return {"values": values}


def module_stamp(path):
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    return info.st_mtime_ns, info.st_size, info.st_ino


def track_producer_modules(watched):
    for name, module in sys.modules.copy().items():
        if name.partition(".")[0] in {"kara_templater", "namioto"}:
            filename = getattr(module, "__file__", None)
            if filename:
                path = Path(filename)
                if path not in watched:
                    watched[path] = module_stamp(path)


if __name__ == "__main__":
    watched = {Path(__file__): module_stamp(Path(__file__))}
    for line in sys.stdin:
        if any(module_stamp(path) != stamp for path, stamp in watched.items()):
            print(json.dumps({"restart": True}), flush=True)
            break
        try:
            with redirect_stdout(sys.stderr):
                result = {"result": run(json.loads(line))}
        except Exception:  # noqa: BLE001 - report user template errors at the subprocess boundary
            result = {"error": traceback.format_exc()}
        track_producer_modules(watched)
        print(json.dumps(result), flush=True)
