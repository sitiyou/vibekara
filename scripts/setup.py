"""Install vibekara's shared Python environment and link its skills."""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kara-previwer"))

from kara_previwer.paths import vibekara_home


def gpu_vendors() -> set[str]:
    if os.name == "nt":
        devices = subprocess.check_output(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                (
                    "Get-CimInstance Win32_VideoController -ErrorAction Stop | "
                    "Select-Object -ExpandProperty PNPDeviceID"
                ),
            ],
            text=True, timeout=20,
        )
        return set(re.findall(r"ven_([0-9a-f]{4})", devices.lower()))
    if not sys.platform.startswith("linux"):
        return set()

    vendors = set()
    for device in Path("/sys/bus/pci/devices").glob("*"):
        try:
            device_class = (device / "class").read_text(encoding="ascii").strip()
            if device_class.startswith(("0x03", "0x12")):
                vendor = (device / "vendor").read_text(encoding="ascii").strip().removeprefix("0x")
                if device_class.startswith("0x03") or vendor == "10de":
                    vendors.add(vendor)
        except FileNotFoundError:
            continue
    return vendors


def namioto_backend() -> str:
    vendors = gpu_vendors()
    if "10de" in vendors or any(Path("/dev").glob("nvidia[0-9]*")):
        return "cuda"
    # Ignore PCI display-only adapters from BMCs and virtual machines.
    if vendors - {"102b", "1234", "1414", "15ad", "1a03", "1b36"}:
        return "webgpu"
    if any(Path("/dev/dri").glob("renderD*")):
        return "webgpu"
    return "cpu"


def namioto_wheel_url(version: str) -> str:
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ValueError("Namioto release wheels require an x86-64 machine.")
    if sys.platform == "win32":
        wheel_platform = "win_amd64"
    elif sys.platform.startswith("linux"):
        wheel_platform = "manylinux_2_28_x86_64"
    else:
        raise ValueError("Namioto release wheels are available for Linux and Windows.")

    filename = f"namioto-{version}-cp314-cp314-{wheel_platform}.whl"
    return f"https://github.com/sitiyou/namioto/releases/download/v{version}/{filename}"


def install(uv: str, namioto: Path, templater: Path, *, backend: str, build_templater: bool) -> Path:
    project = tomllib.loads((namioto / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    wheel = namioto_wheel_url(project["version"])
    venv = vibekara_home() / ".venv"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        subprocess.run(
            [uv, "venv", "--no-project", "--python", project["requires-python"], venv],
            check=True,
        )

    command = [
        uv, "pip", "install", "--python", python,
        "--reinstall-package", "kara-templater",
        "--reinstall-package", "namioto", f"namioto[{backend}] @ {wheel}",
    ]
    if build_templater:
        command.append(templater)
    else:
        project = tomllib.loads((templater / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        command.extend(("--only-binary", ":all:", f"kara-templater=={project['version']}"))

    runtimes = {
        "cpu": {"onnxruntime"},
        "cuda": {"onnxruntime-gpu"},
        "webgpu": {"onnxruntime", "onnxruntime-ep-webgpu"},
    }
    gpu_packages = subprocess.check_output([uv, "pip", "list", "--python", python, "--format", "json"])
    installed = {package["name"]: package["version"] for package in json.loads(gpu_packages)}
    known_runtimes = set.union(*runtimes.values())
    stale = installed.keys() & (known_runtimes - runtimes[backend])
    if stale:
        command.extend(("--reinstall-package", "onnxruntime-gpu" if backend == "cuda" else "onnxruntime"))
        subprocess.run([*command, "--dry-run"], check=True)
    try:
        if stale:
            subprocess.run([uv, "pip", "uninstall", "--python", python, *sorted(stale)], check=True)
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        if stale:
            previous = sorted(installed.keys() & known_runtimes)
            replacement = runtimes[backend] - installed.keys()
            if replacement:
                subprocess.run([uv, "pip", "uninstall", "--python", python, *sorted(replacement)], check=False)
            subprocess.run(
                [
                    uv, "pip", "install", "--python", python, "--offline", "--no-deps", "--reinstall",
                    *(f"{name}=={installed[name]}" for name in previous),
                ],
                check=False,
            )
        raise
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

        backend = namioto_backend()
        print(f"Namioto analysis backend: {backend}", flush=True)
        python = install(uv, namioto, templater, backend=backend, build_templater=args.build_kara_templater)
        destination.mkdir(parents=True, exist_ok=True)
        for source, target in links:
            link_skill(source, target)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Setup failed: {error}\n")
    print(f"vibekara data directory: {vibekara_home()}")
    print(f"Skills installed in {destination}")
    print(f"Use {python} for rendering and for compiler.python in review proposals.")


if __name__ == "__main__":
    main()
