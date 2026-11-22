"""Basic external recipe. Copy beside song_input.py for a standalone build."""

from kara_templater import Document, KaraokeEffects, KaraokeRows, Style, Track, prepare_tracks


def build(song, values):
    styles = tuple(
        Style(name=name, fontname="sans-serif", fontsize=size)
        for role in ("default", "top")
        for name, size in ((role, 100), (role + "-furigana", 45))
    )
    document = Document.create(width=1920, height=1080, styles=styles)
    effects = (KaraokeEffects(),)
    tracks = (
        Track(id="lead", source=lambda line: line.style != "top", effects=effects),
        Track(id="harmony", source=lambda line: line.style == "top",
              layout=KaraokeRows(anchor="top"), effects=effects),
    )
    return prepare_tracks(document, inputs=song.sources, tracks=tracks, bpm=song.bpm)


def register(registry):
    registry.add(id="basic", title="Basic karaoke", semantic=True, build=build)


if __name__ == "__main__":
    from pathlib import Path

    from song_input import load_song

    build(load_song(), {}).export_hook(Path(__file__).with_name("lyrics.hook"), fps=60)
