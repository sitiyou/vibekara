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


# One immutable whole-song scene per scene worker. Keep the editing worker free for
# first paints, descriptions, and new designs while this scene is being built.
_scene_key = None
_scene = None


def shared_scene(job, recipe, song, values):
    global _scene_key, _scene
    key = (
        job["script"],
        job["template"],
        job["krc"],
        job["midi"],
        job.get("offset_ms", 0),
        job.get("wavetone", False),
        tuple(sorted(job.get("track_style", {}).items())),
        tuple(sorted(job.get("colors", {}).items())),
        tuple(sorted(values.items())),
    )
    if key != _scene_key:
        if job.get("cached_only"):
            return None
        built = recipe.build(song, values)
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
    colors = tuple(sorted((int(k), v) for k, v in job.get("colors", {}).items()))
    song = load_song(
        job["krc"],
        job["midi"],
        job.get("offset_ms", 0),
        colors,
        job.get("wavetone", False),
        tuple(sorted((int(k), v) for k, v in job.get("track_style", {}).items())),
    )
    if job.get("warm"):
        return {}
    if job.get("shared_scene"):
        scene = shared_scene(job, recipe, song, values)
        if scene is None:
            return {"miss": True}
    else:
        if "duration" in job:
            song = replace(
                song, preview_interval=(job["start"], job["start"] + job["duration"])
            )
        scene = recipe.build(song, values)
    scene.export_hook(
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
