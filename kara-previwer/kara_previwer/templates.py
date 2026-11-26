# SPDX-License-Identifier: AGPL-3.0-only
"""Registration and typed parameters for explicitly loaded review recipes."""

import math
import runpy
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

from kara_templater import Color, Scene
from namioto.params import Field

from . import timing
from .timing import TemplateSong


def parameter_value(field: Field, value):
    if field.kind == "color":
        Color.hex("#" + str(value).lstrip("#"))
        return str(value).lstrip("#")
    if field.kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise ValueError("expected true or false")
    if field.kind in ("int", "float"):
        if isinstance(value, bool):
            raise ValueError("expected a number")
        number = float(value)
        if not math.isfinite(number) or not field.low <= number <= field.high:
            raise ValueError(f"expected {field.low:g}..{field.high:g}")
        if field.kind == "int" and not number.is_integer():
            raise ValueError("expected an integer")
        return int(number) if field.kind == "int" else number
    if field.kind == "choice" and value not in field.choices:
        raise ValueError(f"expected one of {field.choices}")
    if field.kind not in ("text", "choice"):
        raise ValueError(f"unknown parameter kind {field.kind!r}")
    if not isinstance(value, str):
        raise TypeError("expected text")
    return value


@dataclass(frozen=True)
class Template:
    id: str
    title: str
    formats: tuple[str, ...]
    parameters: tuple[Field, ...]
    build: Callable[[TemplateSong, dict], Scene]
    validate: Callable[[dict], None] | None = None
    semantic: bool = False
    palette_parameters: tuple[str, ...] = ()

    def resolve(self, overrides: Mapping) -> dict:
        result = {}
        unknown = set(overrides).difference(field.name for field in self.parameters)
        if unknown:
            raise ValueError(f"{self.id}: unknown parameters {sorted(unknown)}")
        for field in self.parameters:
            value = overrides.get(field.name, field.default)
            try:
                result[field.name] = parameter_value(field, value)
            except (TypeError, ValueError) as error:
                raise ValueError(f"{self.id}.{field.name}: {error}") from error
        if self.validate is not None:
            try:
                self.validate(result)
            except ValueError as error:
                raise ValueError(f"{self.id}: {error}") from error
        return result


class Registry:
    def __init__(self):
        self.templates: dict[str, Template] = {}
        self.origins: dict[str, str] = {}
        self.source = "built-in"

    def add(
        self, *, id, title, build, formats=("ass", "hook"), parameters=(), validate=None,
        semantic=False, palette_parameters=(),
    ):
        if not id or id in self.templates:
            raise ValueError(f"duplicate or empty template {id!r}: {self.origins.get(id)} and {self.source}")
        fields = tuple(parameters)
        if len({f.name for f in fields}) != len(fields) or not callable(build):
            raise ValueError(f"{id}: invalid parameters or builder")
        if not formats or set(formats) - {"ass", "hook"}:
            raise ValueError(f"{id}: invalid formats")
        palette = tuple(palette_parameters)
        if any(name not in {f.name for f in fields if f.kind == "color"} for name in palette):
            raise ValueError(f"{id}: palette parameters must name colour fields")
        if len({str(f.default).lstrip("#").upper() for f in fields if f.name in palette}) != len(palette):
            raise ValueError(f"{id}: palette parameters require distinct default colours")
        template = Template(id, title, tuple(formats), fields, build, validate, semantic, palette)
        template.resolve({})
        self.templates[id] = template
        self.origins[id] = self.source

    def get(self, id):
        if id not in self.templates:
            raise ValueError(f"unknown template {id!r}; load its Python script")
        return self.templates[id]


def load_templates(scripts: Iterable[str | Path] = ()) -> Registry:
    registry = Registry()
    # Old copied review recipes still import these two types from Namioto.
    for name, module in (
        ("namioto.karaoke.song", timing),
        ("namioto.karaoke.templates", sys.modules[__name__]),
    ):
        if find_spec(name) is None:
            sys.modules[name] = module
    for path in map(Path, scripts):
        if path.suffix.lower() != ".py":
            raise ValueError(f"{path}: expected a Python template file (.py)")
        registry.source = str(path)
        try:
            namespace = runpy.run_path(str(path))
            register = namespace.get("register")
            if not callable(register):
                raise TypeError("expected register(registry)")
            register(registry)
        except Exception as error:
            raise ValueError(f"{path}: {error}") from error
    return registry
