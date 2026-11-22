"""Portable, accepted whole-song build inputs."""

import json
import shutil
import tempfile
from pathlib import Path

from .bundle import compile_job, local_config
from .proposals import check_fonts


def snapshot(session, proposal, item, fps, destination):
    config = local_config(session, proposal)
    check_fonts(proposal, item["values"])
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
        for key, name in (
            ("script", "recipe/template.py"),
            ("midi", "song.mid"),
            ("krc", "song.krc"),
        ):
            (root / name).parent.mkdir(exist_ok=True)
            shutil.copyfile(config[key], root / name)
            manifest["config"][key] = name
        for name in config.get("resources", []):
            dest = root / "recipe" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(config["script"]).parent / name, dest)
        (root / "accepted.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2)
        )
        if destination.exists():
            for file in root.rglob("*"):
                if (
                    file.is_file()
                    and file.read_bytes()
                    != (destination / file.relative_to(root)).read_bytes()
                ):
                    raise ValueError("snapshot destination contains a different build")
        else:
            root.rename(destination)


def rebuild(root, output, python=None):
    m = json.loads((root / "accepted.json").read_text())
    check_fonts(m, m["values"])
    config = m["config"].copy()
    for key in ("script", "midi", "krc"):
        config[key] = str((root / config[key]).resolve())
    if python:
        config["python"] = python
    return compile_job(config, values=m["values"], fps=m["fps"], output=str(output))
