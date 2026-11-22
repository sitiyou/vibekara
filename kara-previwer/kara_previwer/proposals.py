"""Declarative review directions and revisions based on a submitted snapshot."""

import json
import re
import subprocess
from pathlib import Path

from .bundle import compiled, prepare, segment_clip, validate_values

CATALOG = {
    "directions": "manifest paths in alternatives, same clip and clock",
    "presets": "title, description, values",
    "focus": "parameter names emphasized this round",
    "groups": "mapping from display title to parameter names",
    "fonts": "mapping from parameter name to ordered fontconfig family or full names",
    "sample": "actual lyric excerpt used to preview fonts",
    "favorite": "saved template ID from review preferences; supply target clip and song compiler inputs",
    "parameters": ["choice", "color", "bool", "int", "float", "text"],
}


def resolve_font(name):
    result = subprocess.check_output(
        [
            "fc-match",
            "--format",
            "%{family}\n%{fullname}\n%{postscriptname}\n%{style}\n%{index}",
            "--",
            name.replace("-", r"\-"),
        ],
        text=True,
    )
    if not result.strip():
        return None
    family, full, ps, style, index = result.splitlines()
    if name.casefold() in {
        part.strip().casefold() for part in re.split("[,\n]", f"{family}\n{full}\n{ps}")
    }:
        return {
            "family": family,
            "fullname": full,
            "postscript": ps,
            "style": style,
            "index": index,
        }
    return None


def check_fonts(proposal, values):
    for field, options in proposal.get("fonts", {}).items():
        face = resolve_font(values[field])
        expected = proposal.get("faces", {}).get(values[field])
        if values[field] not in options or not face or (expected and expected != face):
            available = [name for name in options if resolve_font(name)]
            raise ValueError(
                f"字体不可用，请重新选择 {field}（{values[field]}）。候选：{', '.join(available) or '请安装所需字体'}"
            )


def refresh_fonts(p):
    """Resolve current choices without discarding the published face identity."""
    fields = {f["name"] for f in p.get("parameters", [])}
    for field, options in p.get("fonts", {}).items():
        if field not in fields or not isinstance(options, list):
            raise ValueError("invalid fonts field")
        faces = p.setdefault("faces", {})
        available = []
        for name in options:
            face = resolve_font(name)
            if face and face == faces.setdefault(name, face):
                available.append(name)
        p["fonts"][field] = available


def decorate(p, *, require_selected=True):
    names = {f["name"] for f in p["parameters"]}
    for f in p["parameters"]:
        if f["name"].lower() in {"font", "fontname", "font_family"}:
            fonts = p.setdefault("fonts", {})
            fonts.setdefault(
                f["name"],
                list(
                    dict.fromkeys(
                        [
                            p["values"][f["name"]],
                            "Noto Serif CJK JP",
                            "Noto Sans CJK JP",
                        ]
                    )
                ),
            )
    refresh_fonts(p)
    if require_selected:
        check_fonts(p, p["values"])
    for group in [p.get("focus", []), *p.get("groups", {}).values()]:
        if not isinstance(group, list) or not set(group) <= names:
            raise ValueError("unknown focus or group field")
    return p


def media_clock(clip):
    return {k: v for k, v in clip.items() if k != "fallback"}


def directions(session, manifest, inherited):
    primary = prepare(session, manifest, inherited)
    if "config" in primary and not primary.get("sample"):
        from .bundle import local_config

        krc = Path(local_config(session, primary)["krc"]).read_text()
        primary["sample"] = next(
            (
                re.sub(r"\[[^]]*\]", "", line)
                for line in krc.splitlines()
                if line.strip()
            ),
            "",
        )
    decorate(primary)
    alternatives = primary.pop("alternatives", [])
    primary["directions"] = []
    for path in alternatives:
        option = decorate(prepare(session, manifest.parent / path))
        option.setdefault("sample", primary.get("sample", ""))
        if media_clock(option["clip"]) != media_clock(primary["clip"]):
            raise ValueError("directions must share media and clip timing")
        primary["directions"].append(option)
    return primary


def selected(revision, index=0):
    if type(index) != int or not 0 <= index <= len(revision.get("directions", [])):
        raise ValueError("unknown direction")
    if index:
        return dict(revision["directions"][index - 1], version=revision["version"])
    return revision


def revise(session, base, token, patch, directory=Path(".")):
    event = next(
        (
            e
            for e in session.events(0)
            if e.get("token") == token and e["kind"] == "feedback"
        ),
        None,
    )
    if not event or event.get("base", event["version"]) != base:
        raise ValueError("feedback base differs from revision")
    revision = session.state()["revisions"][event["version"] - 1]
    option = selected(revision, event.get("direction", 0))
    if set(patch) - {
        "values",
        "focus",
        "groups",
        "summary",
        "presets",
        "alternatives",
        "manifest",
    }:
        raise ValueError("unknown revision field")
    patch = dict(patch)
    alternatives = patch.pop("alternatives", [])
    if "manifest" in patch:
        new = directions(session, directory / patch.pop("manifest"), {})
        if media_clock(new["clip"]) != media_clock(option["clip"]):
            raise ValueError("replacement template must share the reviewed clip")
        option = new
    values = dict(option["values"])
    dropped = []
    for name, value in event["values"].items():
        candidate = {**values, name: value}
        try:
            validate_values(option, candidate)
            check_fonts(option, candidate)
            values = candidate
        except ValueError:
            dropped.append(name)
    values.update(patch.get("values", {}))
    validate_values(option, values)
    result = {k: v for k, v in option.items() if k not in {"directions", "version"}}
    result.update(patch, values=values)
    if values != option["values"]:
        result["clip"] = media_clock(option["clip"])
    result["not_inherited"] = dropped
    if alternatives:
        result["directions"] = []
        for path in alternatives:
            candidate = directions(session, directory / path, {})
            if media_clock(candidate["clip"]) != media_clock(option["clip"]):
                raise ValueError("directions must share the reviewed clip")
            result["directions"].append(candidate)
    decorate(result)
    for preset in result.get("presets", []):
        validate_values(result, {**values, **preset["values"]})
    if "config" in option:
        clip = option["clip"]
        entry = (
            segment_clip(clip, clip.get("entry_frame", 0))
            if "segment_frames" in clip
            else clip
        )
        result["hook"] = compiled(session, {**option, "clip": entry}, values)
    return session.publish(base, result, token)


def save_package(session, option, values):
    from .bundle import local_config

    if not option.get("config"):
        raise ValueError("收藏需要能重建的模板源，当前只有编译好的 hook")
    cfg = local_config(session, option)
    return Path(cfg["script"]), {
        "template": option["template"],
        "version": option["version"],
        "values": values,
        "fonts": option.get("fonts", {}),
        "faces": option.get("faces", {}),
        "dependencies": list(
            dict.fromkeys(["namioto", "kara-templater", *cfg.get("dependencies", [])])
        ),
        "resources": cfg.get("resources", []),
    }


def reuse(session, option, package, base):
    from tempfile import TemporaryDirectory

    from .bundle import local_config

    if not option.get("config"):
        raise ValueError("目标歌曲需要 KRC 与 MIDI 编译源")
    directory, meta = package
    cfg = local_config(session, option)
    cfg["script"] = str(directory / "template.py")
    cfg["dependencies"] = meta.get("dependencies", [])
    cfg["resources"] = {
        name: str(directory / name) for name in meta.get("resources", [])
    }
    clip = media_clock(option["clip"])
    for key in ("background", "audio", "fallback"):
        if key in clip:
            clip[key] = str(session.root / clip[key])
    manifest = {
        "template": meta["template"],
        "clip": clip,
        "values": meta["values"],
        "fonts": meta["fonts"],
        "faces": meta.get("faces", {}),
        "compiler": cfg,
        "summary": "从我的模板开始",
        "sample": option.get("sample", ""),
    }
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "manifest.json"
        path.write_text(json.dumps(manifest))
        return session.publish(base, directions(session, path, {}))
