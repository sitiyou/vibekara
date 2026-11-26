"""Basic Hook recipe for direct builds and interactive review."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from kara_templater import (
    Document,
    KaraokeEffects,
    KaraokeRows,
    Scene,
    Style,
    Track,
    build_lyric_scene,
)

if TYPE_CHECKING:
    from kara_previwer.templates import Registry
    from kara_previwer.timing import TemplateSong


def build(document: Document, *, preview_interval: tuple[float, float] | None = None) -> Scene:
    styles = tuple(
        Style(name=name, fontname="sans-serif", fontsize=size)
        for role in ("default", "top")
        for name, size in ((role, 100), (role + "-furigana", 45))
    )
    effects = (KaraokeEffects(),)
    tracks = (
        Track(id="lead", source=lambda line: line.style != "top", styles=styles, effects=effects),
        Track(
            id="harmony",
            source=lambda line: line.style == "top",
            layout=KaraokeRows(anchor="top"),
            styles=styles,
            effects=effects,
        ),
    )
    return build_lyric_scene(document, tracks=tracks, preview_interval=preview_interval)


def _build_review(song: TemplateSong, _values: Mapping[str, object]) -> Scene:
    document = Document.create(
        width=1920, height=1080, lyric_sources=song.sources, bpm=song.bpm,
    )
    return build(document, preview_interval=song.preview_interval)


def register(registry: Registry) -> None:
    registry.add(id="basic", title="Basic karaoke", formats=("hook",), semantic=True, build=_build_review)
