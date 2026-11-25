"""Extract the two textures and MAIN pass emitted by kara-templater."""

import json
import math
import re
import struct
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
    parameters = {}
    header = next(lines, "")
    while header.startswith("//!PARAM kara_input_"):
        symbol = header.removeprefix("//!PARAM ")
        if not re.fullmatch(r"kara_input_[a-f0-9]{24}_[0-2]", symbol):
            raise ValueError("invalid material uniform")
        expect("//!TYPE DYNAMIC float")
        value = float(next(lines, ""))
        if not math.isfinite(value):
            raise ValueError("invalid material uniform value")
        parameters[symbol] = {"kind": "float", "uniforms": [symbol], "default": [value]}
        expect("")
        header = next(lines, "")
    if header != "//!PARAM PTS":
        raise ValueError("unsupported hook: expected //!PARAM PTS")
    for line in (
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
    if "PTS * item(0)" not in shader:
        raise ValueError("expected a kara-templater hook clock")
    rate, first, count = struct.unpack_from("=3f", raw)
    sizes["clock"] = [int(rate), int(first), int(count)]
    if parameters:
        sizes["parameters"] = parameters
    (directory / "scene.frag").write_text(shader)
    (directory / "textures.json").write_text(json.dumps(sizes))


def repack(directory: Path, destination: Path, values=None):
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
        for name, slot in sizes.get("parameters", {}).items():
            parts = slot["default"]
            if values is not None and name in values:
                value = values[name]
                if slot["kind"] == "float":
                    parts = [float(value)]
                elif slot["kind"] == "color":
                    parts = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            for symbol, part in zip(slot["uniforms"], parts, strict=True):
                if not re.fullmatch(r"kara_input_[a-f0-9]{24}_[0-2]", symbol) or not math.isfinite(part):
                    raise ValueError("invalid material uniform")
                out.write(f"//!PARAM {symbol}\n//!TYPE DYNAMIC float\n{part:.9g}\n\n")
        out.write(
            "//!PARAM PTS\n//!TYPE DYNAMIC float\n//!MINIMUM -1\n//!MAXIMUM 10000000\n-1\n\n"
        )
        out.write("//!HOOK MAIN\n//!BIND HOOKED\n//!BIND KARAMASK\n//!BIND KARADATA\n")
        out.write((directory / "scene.frag").read_text())
