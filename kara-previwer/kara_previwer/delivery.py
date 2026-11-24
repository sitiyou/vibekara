"""Portable, accepted whole-song build inputs."""

import json
import shutil
import tempfile
from pathlib import Path

from .bundle import compile_job, local_config, resolve_config
from .proposals import check_fonts, selected


def accepted_build(session):
    state = session.state()
    item = next((event for event in session.pending() if event["token"] == state["accepted"]), None)
    if item is None:
        raise ValueError("review has no accepted revision")
    proposal = selected(state["revisions"][item["version"] - 1], item.get("direction", 0))
    if "config" not in proposal:
        raise ValueError("this precompiled review has no whole-song compiler")
    return proposal, item


def snapshot(session, proposal, item, fps, destination):
    config = local_config(session, proposal)
    manifest = {
        "session": session.root.name,
        "token": item["token"],
        "version": item["version"],
        "direction": item.get("direction", 0),
        "values": item["values"],
        "fps": fps,
        "fonts": proposal.get("fonts", {}),
        "faces": proposal.get("faces", {}),
        "config": config.copy(),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        root = Path(staging) / "snapshot"
        root.mkdir()
        files = [("script", "recipe/template.py")]
        if "project" in config:
            files.append(("project", "song.nto"))
        elif "song_input" in config:
            shutil.copytree(config["song_input"], root / "song")
            manifest["config"]["song_input"] = "song"
        else:
            files.extend((("midi", "song.mid"), ("krc", "song.krc")))
        for key, name in files:
            (root / name).parent.mkdir(exist_ok=True)
            shutil.copyfile(config[key], root / name)
            manifest["config"][key] = name
        for name in config.get("resources", []):
            dest = root / "recipe" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(config["script"]).parent / name, dest)
        (root / "accepted.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not destination.exists():
            try:
                root.rename(destination)
            except OSError:
                if not destination.exists():
                    raise
        if root.exists():
            for file in root.rglob("*"):
                if file.is_file():
                    existing = destination / file.relative_to(root)
                    if not existing.is_file() or existing.read_bytes() != file.read_bytes():
                        raise ValueError("snapshot destination contains a different build")
    return {key: manifest[key] for key in ("session", "token", "version", "direction", "fps")}


def build_hook(config, source, values, fps: int, output: Path):
    """Publish the complete Hook and preserve the previous file on build failure."""
    check_fonts(source, values)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        staged = Path(tmp).resolve() / output.name
        result = compile_job(config, values=values, fps=fps, output=str(staged))
        staged.replace(output)
    return result


def rebuild(root: Path, output: Path, python: str | None = None):
    manifest = json.loads((root / "accepted.json").read_text(encoding="utf-8"))
    config = resolve_config(root.resolve(), manifest["config"])
    if python:
        config["python"] = python
    return build_hook(config, manifest, manifest["values"], manifest["fps"], output)
