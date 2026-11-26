"""One shared source template for comparing editable lyric directions."""

from collections.abc import Mapping

from kara_previwer.templates import Registry
from kara_previwer.timing import TemplateSong
from kara_templater import (
    Box,
    ComponentSelection,
    Document,
    KaraokeEffects,
    Layout,
    LyricScene,
    LyricSource,
    PaintControl,
    Style,
    Track,
    build_lyric_scene,
    compose_track,
)

HEIGHT = 720
WIDTH = 1280


def _lead(source: LyricSource) -> bool:
    return source.style != "harmony"


def _harmony(source: LyricSource) -> bool:
    return source.style == "harmony"


def build(song: TemplateSong, _values: Mapping[str, object], *, composition: dict | None = None) -> LyricScene:
    """Lay out the original timed lyrics with the reviewed composition."""
    body = Style(name="default", fontname="Noto Sans CJK JP", fontsize=49, outline=2.2, shadow=0)
    reading = Style(name="default-furigana", fontname=body.fontname, fontsize=24, outline=1.2, shadow=0)
    voices = tuple(
        Style(name=name, fontname=body.fontname, fontsize=body.fontsize, outline=body.outline, shadow=0)
        for name in sorted({source.style for source in song.sources} - {"default"})
    )
    styles = (body, reading, *voices)
    document = Document.create(width=WIDTH, height=HEIGHT, styles=styles)
    groups = (composition or {"groups": []})["groups"]
    tracks = []
    for track_id, source, region in (
        ("lead", _lead, Box(70, 487, 1140, 165)),
        ("harmony", _harmony, Box(100, 380, 1080, 92)),
    ):
        track = Track(
            id=track_id, source=source, region=region, styles=styles,
            layout=Layout(rows=2, alignment="center" if track_id == "lead" else "right"),
            preview=0.55, effects=(KaraokeEffects(entry="none", exit="none", highlight="none"),),
        )
        selections = tuple(
            ComponentSelection(
                id=node["id"], component=node["component"], target=node["target"],
                values=node["values"], bindings=node["bindings"],
                controls={
                    name: PaintControl(
                        bounds=(bounds[0], bounds[1]) if (bounds := options["bounds"]) else None,
                        step=options["step"], label=options["label"],
                        group=options["group"], order=options["order"],
                    )
                    for name, options in node["controls"].items()
                },
            )
            for group in groups if group["track"] == track_id
            for node in group["components"]
        )
        tracks.append(compose_track(track, selections, script_height=HEIGHT))
    return build_lyric_scene(
        document, tracks=tuple(tracks), inputs=song.sources, bpm=song.bpm,
        preview_interval=song.preview_interval,
    )


def register(registry: Registry) -> None:
    registry.add(id="editable-lyrics", title="Editable lyric effects", build=build, formats=("hook",), semantic=True)
