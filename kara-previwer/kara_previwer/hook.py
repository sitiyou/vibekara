"""Extract the two textures and MAIN pass emitted by kara-templater."""

import json
import re
from pathlib import Path


def unpack(source: Path, directory: Path):
    lines = iter(source.read_text(encoding="ascii").splitlines())

    def expect(line):
        if next(lines, None) != line:
            raise ValueError(f"unsupported hook: expected {line}")

    sizes = {}
    for name, fmt, filtering, stride in (
        ("KARAMASK", "r8", "LINEAR", 1),
        ("KARADATA", "rgba32f", "NEAREST", 16),
    ):
        expect(f"//!TEXTURE {name}")
        dimensions = re.fullmatch(r"//!SIZE (\d+) (\d+)", next(lines, ""))
        if not dimensions:
            raise ValueError(f"{name}: invalid dimensions")
        width, height = map(int, dimensions.groups())
        expect(f"//!FORMAT {fmt}")
        expect(f"//!FILTER {filtering}")
        raw = bytes.fromhex(next(lines, ""))
        if min(width, height) < 1 or len(raw) != width * height * stride:
            raise ValueError(f"{name}: invalid texture size")
        (directory / f"{name}.bin").write_bytes(raw)
        sizes[name] = [width, height]
        # Sections in the exporter are separated by blank lines.
        expect("")
    for line in (
        "//!PARAM PTS",
        "//!TYPE DYNAMIC float",
        "//!MINIMUM -1",
        "//!MAXIMUM 10000000",
        "-1",
        "",
        "//!HOOK MAIN",
        "//!BIND HOOKED",
        "//!BIND KARAMASK",
        "//!BIND KARADATA",
    ):
        expect(line)
    shader = "\n".join(lines)
    if "vec4 hook()" not in shader or "//!" in shader:
        raise ValueError("expected a single MAIN pass")
    (directory / "scene.frag").write_text(shader)
    (directory / "textures.json").write_text(json.dumps(sizes))


def repack(directory: Path, destination: Path):
    """Reconstruct a supported native hook from its lossless browser resources."""
    sizes = json.loads((directory / "textures.json").read_text())
    with destination.open("w", encoding="ascii") as out:
        for name, fmt, filtering in (
            ("KARAMASK", "r8", "LINEAR"),
            ("KARADATA", "rgba32f", "NEAREST"),
        ):
            width, height = sizes[name]
            out.write(
                f"//!TEXTURE {name}\n//!SIZE {width} {height}\n//!FORMAT {fmt}\n//!FILTER {filtering}\n"
            )
            out.write((directory / (name + ".bin")).read_bytes().hex() + "\n\n")
        out.write(
            "//!PARAM PTS\n//!TYPE DYNAMIC float\n//!MINIMUM -1\n//!MAXIMUM 10000000\n-1\n\n"
        )
        out.write("//!HOOK MAIN\n//!BIND HOOKED\n//!BIND KARAMASK\n//!BIND KARADATA\n")
        out.write((directory / "scene.frag").read_text())
