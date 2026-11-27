"""Import a saved Namioto project into a Python karaoke template."""

import sys
from dataclasses import replace
from pathlib import Path

from kara_templater import Document, Style

# The integration runs directly from the checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "kara-previwer"))

from kara_previwer.timing import load_project_song


def load_nto(
    path: str | Path,
    *,
    width: int = 1920,
    height: int = 1080,
    styles: tuple[Style, ...] = (),
    offset_ms: int = -100,
    harmony_tracks: str = "",
) -> Document:
    """Load timed lyrics, ruby, chapters, vocal tracks and BPM from a saved project.

    The source actor holds the MIDI channel as text. Style names are `default`
    and `top`, with optional `-furigana` companion styles. `harmony_tracks`
    selects comma-separated channels for the `top` label.
    """
    song = load_project_song(path, offset_ms=offset_ms, harmony_tracks=harmony_tracks)
    return Document.create(
        width=width,
        height=height,
        styles=styles or tuple(Style(name=name, fontname="sans-serif") for name in ("default", "top")),
        lyric_sources=tuple(replace(source, actor=str(song.tracks[source.id])) for source in song.sources),
        bpm=song.bpm,
    )
