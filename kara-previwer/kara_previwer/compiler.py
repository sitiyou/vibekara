"""Trusted local adapter. Run with the interpreter containing the producer's packages."""

import hashlib
import json
import shutil
import sys
import traceback
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from functools import lru_cache
from inspect import signature
from pathlib import Path


@lru_cache(maxsize=8)
def load_recipe(script, name):
    from kara_previwer.templates import load_templates

    return load_templates([script]).get(name)


@lru_cache(maxsize=4)
def load_song(krc, midi, offset_ms, colors, wavetone, track_style=()):
    from namioto.karaoke.song_input import build_song

    from kara_previwer.timing import template_song

    timing = build_song(Path(krc).read_text(), Path(midi).read_bytes(), wavetone=wavetone)
    return template_song(timing, offset_ms=offset_ms, colors=dict(colors), track_style=dict(track_style))


@lru_cache(maxsize=4)
def load_timing_directory(directory):
    from kara_previwer.timing import load_timing_directory as read_timing_directory

    return read_timing_directory(directory)


@lru_cache(maxsize=4)
def load_project_song(path, offset_ms, harmony_tracks):
    from kara_previwer.timing import load_project_song as read_project_song

    return read_project_song(path, offset_ms=offset_ms, harmony_tracks=harmony_tracks)


DEFAULT_OFFSET_MS = -100


def timing_key(job):
    if "project" in job:
        return (job["project"], job.get("offset_ms", DEFAULT_OFFSET_MS), job.get("harmony_tracks", ""))
    if "song_input" in job:
        return (job["song_input"],)
    return (
        job["krc"],
        job["midi"],
        job.get("offset_ms", DEFAULT_OFFSET_MS),
        tuple(sorted((int(k), v) for k, v in job.get("colors", {}).items())),
        job.get("wavetone", False),
        tuple(sorted((int(k), v) for k, v in job.get("track_style", {}).items())),
    )


# One immutable whole-song scene per scene worker. Keep the editing worker free for
# first paints, descriptions, and new designs while this scene is being built.
_scene_key = None
_scene = None


def build_scene(recipe, song, values, composition):
    if composition is None:
        return recipe.build(song, values)
    return recipe.build(song, values, composition=composition)


def compiler_stamp(package_file):
    root = Path(package_file).parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.suffix in {".py", ".so", ".pyd", ".dll"} or path.name in {
            "_kara_wgsl", "_kara_wgsl.exe",
        }:
            digest.update(path.relative_to(root).as_posix().encode())
            with path.open("rb") as stream:
                digest.update(hashlib.file_digest(stream, "sha256").digest())
    return digest.hexdigest()


def describe_components(job):
    import kara_templater

    height = job["composition_height"]
    if not hasattr(kara_templater, "component_catalog"):
        return {
            "component_schema": {
                name: asdict(component)
                for name, component in kara_templater.effect_components(script_height=height).items()
            },
        }
    directory = job.get("component_preview_directory")
    catalog = kara_templater.component_catalog(script_height=height, preview_directory=directory)
    previews = {}
    copied = {}
    output = Path(job["component_preview_output"])
    for kind, card_id in catalog["preferred_cards"].items():
        card = catalog["cards"][card_id]
        media = {}
        for field, source_field in (("poster", "poster"), ("src", "video")):
            name = card.get(source_field)
            if not name:
                continue
            if name not in copied:
                resource = kara_templater.component_preview_resource(name, preview_directory=directory)
                if not resource.is_file():
                    continue
                filename = str(len(copied)) + Path(name).suffix
                with resource.open("rb") as source, (output / filename).open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                copied[name] = filename
            media[field] = copied[name]
        if "src" in media and "start_at" in card:
            media["startAt"] = card["start_at"]
        if media:
            previews[kind] = media
    return {
        "component_schema": catalog["components"],
        "component_previews": previews,
        "compiler_stamp": compiler_stamp(kara_templater.__file__),
    }


def shared_scene(job, recipe, song, values, timing):
    global _scene_key, _scene
    key = (
        job["script"],
        job["template"],
        job.get("compiler_stamp"),
        timing,
        tuple(sorted(values.items())),
        json.dumps(job.get("composition"), sort_keys=True),
    )
    if key != _scene_key:
        if job.get("cached_only"):
            return None
        built = build_scene(recipe, song, values, job.get("composition")).prepare_hook()
        _scene_key, _scene = key, built
    return _scene


def material_fields(scene, fields, values):
    from kara_templater import Color

    inputs = scene.material_inputs()
    names = []
    for field in fields:
        default = inputs.get(field.name)
        value = values[field.name]
        color = field.kind == "color" and isinstance(default, Color) and default == Color.hex("#" + value)
        scalar = field.kind in ("int", "float") and type(default) in (int, float) and default == value
        if color or scalar:
            names.append(field.name)
    return sorted(names)


def inspect_lyrics(scene, interval):
    from kara_templater import KaraokeEffects, KaraokeRows, Layout

    plans = getattr(scene, "plans", None)
    if plans is None:
        return {"tracks": None, "details": {}}
    details = {}
    settings = {track.id: track for track in getattr(scene, "track_settings", ())}
    attrs = ("fontname", "fontsize", "bold", "italic", "spacing", "outline", "shadow", "scale_x", "scale_y")

    def rgb(color):
        return f"{color.red:02X}{color.green:02X}{color.blue:02X}"

    def style_values(track, glyph):
        if not glyph or not glyph.source_style:
            return {}
        styles = {style.name: style for style in getattr(track, "styles", ())}
        style = styles.get(glyph.source_style) or scene.document.styles.get(glyph.source_style)
        return {name: getattr(style, name) for name in attrs} if style else {}

    ordered = sorted(plans, key=lambda plan: plan.placement.display.start)
    for plan in ordered:
        if plan.placement.display.start >= interval[1] or plan.placement.display.end <= interval[0]:
            continue
        projections = plan.line.layout
        timings = (
            span.start for unit in plan.source.lyrics.units for segment in unit.segments
            if (span := segment.timing).start < interval[1] and span.end > interval[0]
        )
        audible = min(timings, default=None)
        entry = details.setdefault(plan.track_id, {"start": None, "ruby": False, "properties": {}})
        if audible is not None:
            start = max(interval[0], audible)
            entry["start"] = start if entry["start"] is None else min(entry["start"], start)
        props = entry["properties"]
        if "typography.body" not in props:
            glyph = next((g for g in projections.body.characters if g.object.text.strip()), None)
            props["typography.body"] = style_values(settings.get(plan.track_id), glyph)
        props.setdefault("glyph-blur.body", {"blur": 0})
        props.setdefault("offset-shadow.body", {"x": 0, "y": 0})
        if projections.ruby and not entry["ruby"]:
            entry["ruby"] = True
            glyph = next((g for reading in projections.ruby for g in reading.layout.characters), None)
            props["typography.ruby"] = style_values(settings.get(plan.track_id), glyph)
            props["glyph-blur.ruby"] = {"blur": 0}
            props["offset-shadow.ruby"] = {"x": 0, "y": 0}

    for track_id, entry in details.items():
        track = settings.get(track_id)
        if track is None:
            continue
        props = entry["properties"]
        layout = track.layout or KaraokeRows()
        if type(layout) in (KaraokeRows, Layout):
            alignment = ("center" if layout.rows == 1 else "alternating") if isinstance(layout, KaraokeRows) else layout.alignment
            props["layout.track"] = {
                "rows": layout.rows, "vertical": track.vertical, "right_to_left": track.right_to_left,
                **({"alignment": alignment} if isinstance(alignment, str) else {}),
            }
            if isinstance(layout, KaraokeRows):
                props["karaoke-rows.track"] = {"vertical": track.vertical, "right_to_left": track.right_to_left}
        props["ruby-layout.track"] = {"ruby_gap": track.ruby_gap, "ruby_alignment": track.ruby_alignment}
        recipe = next((effect for effect in track.effects if isinstance(effect, KaraokeEffects)), None)
        if recipe:
            props["lyric-colors.track"] = {
                name: rgb(color) for name in ("before_fill", "after_fill", "before_outline", "after_outline")
                if (color := getattr(recipe, name)) is not None
            } | {"dual_outline": recipe.dual_outline}
            rim = recipe.secondary_outline
            props["outline.track"] = {"width": rim.width if rim else 0}
            if rim:
                props["outline.track"]["color"] = rgb(rim.color)
    return {"tracks": sorted(details), "details": details}


def run(job):
    recipe = load_recipe(job["script"], job["template"])
    if not recipe.semantic or "hook" not in recipe.formats:
        raise ValueError("review requires a recipe registered with semantic=True and Hook support")
    values = recipe.resolve(job.get("values", {}))
    if job.get("describe"):
        schema = {
            "parameters": [asdict(field) for field in recipe.parameters],
            "values": values,
            "material_fields_allowed": recipe.validate is None and any(
                field.kind in ("color", "int", "float") for field in recipe.parameters
            ),
        }
        if job.get("describe_composition"):
            parameter = signature(recipe.build).parameters.get("composition")
            if parameter is None or parameter.kind not in (parameter.KEYWORD_ONLY, parameter.POSITIONAL_OR_KEYWORD):
                raise ValueError("组合模板的构建函数需要显式 composition 参数")
            schema.update(describe_components(job))
        return schema
    timing = timing_key(job)
    if "project" in job:
        song = load_project_song(*timing)
    elif "song_input" in job:
        song = load_timing_directory(job["song_input"])
    else:
        song = load_song(*timing)
    if job.get("warm"):
        return {}
    if job.get("inspect_tracks"):
        interval = job["start"], job["start"] + job["duration"]
        scene = build_scene(recipe, replace(song, preview_interval=interval), values, job["composition"])
        return inspect_lyrics(scene, interval)
    if job.get("shared_scene"):
        scene = shared_scene(job, recipe, song, values, timing)
        if scene is None:
            return {"miss": True}
        if job.get("prepare_scene"):
            return {}
        if job.get("material_fields"):
            return {"material_fields": material_fields(scene, recipe.parameters, values)}
    else:
        if "duration" in job:
            song = replace(
                song, preview_interval=(job["start"], job["start"] + job["duration"])
            )
        scene = build_scene(recipe, song, values, job.get("composition"))
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
        if name.partition(".")[0] in {"kara_previwer", "kara_templater", "namioto"}:
            filename = getattr(module, "__file__", None)
            if filename:
                path = Path(filename)
                if path not in watched:
                    watched[path] = module_stamp(path)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    watched = {Path(__file__): module_stamp(Path(__file__))}
    for line in sys.stdin:
        if any(module_stamp(path) != stamp for path, stamp in watched.items()):
            print(json.dumps({"restart": True}), flush=True)
            break
        try:
            with redirect_stdout(sys.stderr):
                result = {"result": run(json.loads(line))}
        except Exception:  # noqa: BLE001 - report template errors across the subprocess boundary
            result = {"error": traceback.format_exc()}
        track_producer_modules(watched)
        print(json.dumps(result), flush=True)
