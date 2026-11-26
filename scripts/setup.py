"""Install vibekara's shared Python environment and link its skills."""

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kara-previwer"))

from kara_previwer.paths import vibekara_home


def install(uv: str, namioto: Path, templater: Path, *, build_templater: bool) -> Path:
    venv = vibekara_home() / ".venv"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        project = tomllib.loads((namioto / "pyproject.toml").read_text(encoding="utf-8")).get("project", {})
        subprocess.run(
            [uv, "venv", "--no-project", "--python", project["requires-python"], venv],
            check=True,
        )

    command = [
        uv, "pip", "install", "--python", python,
        "--reinstall-package", "kara-templater", f"{namioto}[cpu]",
    ]
    if build_templater:
        command.append(templater)
    else:
        project = tomllib.loads((templater / "pyproject.toml").read_text(encoding="utf-8")).get("project", {})
        command.extend(("--only-binary", "kara-templater", f"kara-templater=={project['version']}"))
    subprocess.run(command, check=True)
    subprocess.run([uv, "pip", "check", "--python", python], check=True)
    return python


def link_skill(source: Path, target: Path) -> None:
    if os.name == "nt":
        subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                (
                    "New-Item -ErrorAction Stop -ItemType Junction "
                    "-Path $env:VIBEKARA_LINK_PATH -Target $env:VIBEKARA_LINK_SOURCE | Out-Null"
                ),
            ],
            env={**os.environ, "VIBEKARA_LINK_PATH": str(target), "VIBEKARA_LINK_SOURCE": str(source)},
            check=True,
        )
    else:
        target.symlink_to(source, target_is_directory=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skills-dir", type=Path,
        default=Path(os.environ.get("AGENT_SKILLS_DIR") or Path.home() / ".agents/skills"),
        help="Agent skill directory (defaults to AGENT_SKILLS_DIR or ~/.agents/skills)",
    )
    parser.add_argument("--build-kara-templater", action="store_true", help="Build kara-templater from its submodule")
    args = parser.parse_args()
    uv = shutil.which("uv")
    if uv is None:
        parser.exit(1, "Install uv and make it available on PATH, then run setup again.\n")

    try:
        subprocess.run(
            ["git", "submodule", "update", "--init", "--checkout", "--", "deps/namioto", "deps/kara-templater"],
            cwd=ROOT, check=True,
        )
        namioto = ROOT / "deps/namioto"
        templater = ROOT / "deps/kara-templater"
        skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
        skills += [
            namioto / "skills/namioto-nicokara/SKILL.md",
            templater / "skills/kara-templater/SKILL.md",
        ]
        destination = args.skills_dir.expanduser().resolve()
        links = []
        for skill in skills:
            if not skill.is_file():
                raise ValueError(f"Missing skill at {skill}")
            source = skill.parent
            target = destination / source.name
            if os.path.lexists(target):
                if target.is_dir() and target.samefile(source):
                    continue
                raise ValueError(f"Skill already exists at {target}. Choose another --skills-dir or move it first.")
            links.append((source, target))

        python = install(uv, namioto, templater, build_templater=args.build_kara_templater)
        destination.mkdir(parents=True, exist_ok=True)
        for source, target in links:
            link_skill(source, target)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Setup failed: {error}\n")
    print(f"vibekara data directory: {vibekara_home()}")
    print(f"Skills installed in {destination}")
    print(f"Use {python} for rendering and for compiler.python in review proposals.")


if __name__ == "__main__":
    main()
