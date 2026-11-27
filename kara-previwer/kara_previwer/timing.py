# SPDX-License-Identifier: AGPL-3.0-only
"""Convert Namioto's validated lyric timing into kara-templater sources."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from kara_templater import (
    BLACK,
    WHITE,
    DocumentLyrics,
    DocumentText,
    Lifetime,
    LyricMapping,
    LyricSegment,
    LyricSource,
    LyricUnit,
    RubyText,
    TextAppearance,
    TextRun,
    TimedTextSpan,
)
from namioto.document import OVERLAP_SLACK
from namioto.karaoke.song_input import TimedLyrics, build_song, load_project_input

from .song_settings import read_song_settings


@dataclass(frozen=True)
class Segment:
    start_ms: float
    end_ms: float
    ruby: str = ""


@dataclass(frozen=True)
class TextUnit:
    text: str
    segments: tuple[Segment, ...] = ()
    ruby_continuation: bool = False

    def __post_init__(self):
        segments = list(self.segments)
        for index, (previous, current) in enumerate(zip(self.segments, self.segments[1:], strict=False)):
            if previous.end_ms <= current.start_ms:
                continue
            if current.start_ms < max(previous.start_ms, previous.end_ms - OVERLAP_SLACK * 1000):
                raise ValueError(f"overlapping segments in {self.text!r}")
            # Namioto may round starts and durations independently when it saves a project.
            # Keep the next attack and trim the previous release to the shared boundary.
            segments[index] = replace(previous, end_ms=current.start_ms)
        object.__setattr__(self, "segments", tuple(segments))


@dataclass(frozen=True)
class _DisplayLine:
    units: tuple[TextUnit, ...]
    segment_colours: tuple[tuple[int, ...], ...]
    first: float
    last: float


def _convert(line, spans, offset_ms, index):
    if len(spans) != len(line.sounds):
        return None
    units, colours, segment_colours, channels = [], [], [], []
    first, last = None, 0
    explicit = []
    for container_index, container in enumerate(line.containers):
        owned = [sound for sound in line.sounds if sound.container == container_index]
        cursor = 0
        for sound in owned:
            if container.key[0] == "top":
                for atom in range(cursor, sound.first_atom):
                    units.append(TextUnit(container.atoms[atom]))
                    channels.append(container.channels[atom])
                    colour = container.color_channels[atom]
                    colours.append(container.channels[atom] if colour is None else colour)
                    segment_colours.append(())
            span = spans[sound.index]
            segment = None
            if span is not None and span[0] is not None and span[1] is not None:
                start, end = (float(value) * 1000 + offset_ms for value in span)
                if end < start:
                    raise ValueError(f"lyric line {index + 1}: reversed interval {start}..{end}")
                if end > 0 or offset_ms >= 0:
                    segment = Segment(max(0, start), max(0, end), sound.reading if sound.rubied else "")
                    explicit.append(segment)
                    if segment.end_ms > segment.start_ms:
                        first = segment.start_ms if first is None else min(first, segment.start_ms)
                        last = max(last, segment.end_ms)
            if sound.rubied and segment is None:
                anchor = next(
                    (
                        max(0, timing[0] * 1000 + offset_ms)
                        for timing in spans[sound.index :]
                        if timing and timing[0] is not None
                    ),
                    0,
                )
                if sound is not owned[0] and units[-1].segments:
                    anchor = units[-1].segments[-1].end_ms
                segment = Segment(anchor, anchor, sound.reading)
            colour = sound.channel if sound.color_channel is None else sound.color_channel
            if sound.rubied and sound is not owned[0]:
                unit = units[-1]
                segments = unit.segments + ((segment,) if segment is not None else ())
                try:
                    units[-1] = replace(unit, segments=segments)
                except ValueError as error:
                    raise ValueError(f"lyric line {index + 1}: {error}") from error
                segment_colours[-1] += (colour,)
            else:
                units.append(
                    TextUnit(
                        sound.base if sound.rubied else sound.reading,
                        (segment,) if segment else (),
                        ruby_continuation=container.key[0] == "part" and container.key[2] > 0,
                    )
                )
                channels.append(sound.channel)
                colours.append(colour)
                segment_colours.append((colour,) if segment else ())
            cursor = sound.last_atom + 1
        if container.key[0] == "top":
            for atom in range(cursor, len(container.atoms)):
                units.append(TextUnit(container.atoms[atom]))
                channels.append(container.channels[atom])
                colour = container.color_channels[atom]
                colours.append(container.channels[atom] if colour is None else colour)
                segment_colours.append(())
    if first is None:
        timed = [
            segment
            for unit in units
            for segment in unit.segments
            if segment is not None and segment.end_ms > segment.start_ms
        ]
        if not timed and not explicit:
            return None
        if timed:
            first = min(segment.start_ms for segment in timed)
            last = max(segment.end_ms for segment in timed)
        else:
            first = min(segment.start_ms for segment in explicit)
            last = max(segment.end_ms for segment in explicit)
    preceding = []
    previous = None
    for unit, colour in zip(units, colours, strict=True):
        preceding.append(previous)
        if unit.segments:
            previous = (colour, unit.segments[-1].end_ms)
    following = None
    for position in range(len(units) - 1, -1, -1):
        unit, colour = units[position], colours[position]
        if unit.segments:
            following = (colour, unit.segments[0].start_ms)
            continue
        previous = preceding[position]
        if following is not None and (previous is None or (previous[0] != colour and colour == following[0])):
            anchor = following[1]
        else:
            anchor = previous[1] if previous is not None else first
        units[position] = replace(unit, segments=(Segment(anchor, anchor),))
        segment_colours[position] = (colour,)
    entries = [
        (i, j, channel, segment)
        for i, (unit, channel) in enumerate(zip(units, channels, strict=True))
        for j, segment in enumerate(unit.segments)
    ]
    durations = [segment.end_ms - segment.start_ms for _, _, _, segment in entries]
    for position, (i, _, channel, segment) in enumerate(entries):
        if durations[position] or not units[i].text.strip() or (offset_ms < 0 and segment.end_ms == 0):
            continue
        for direction in (-1, 1):
            for donor in range(position + direction, len(entries) if direction == 1 else -1, direction):
                if entries[donor][2] != channel:
                    break
                if durations[donor] >= 160:
                    durations[donor] -= 80
                    durations[position] = 80
                    break
            if durations[position]:
                break
        if not durations[position]:
            durations[position] = 10
    adjusted = [list(unit.segments) for unit in units]
    shift, previous_channel = 0, None
    for (i, j, channel, segment), duration in zip(entries, durations, strict=True):
        if channel != previous_channel:
            shift = 0
        previous_channel = channel
        start = max(0, segment.start_ms + shift)
        adjusted[i][j] = replace(segment, start_ms=start, end_ms=start + duration)
        shift += duration - (segment.end_ms - segment.start_ms)
    units = [replace(unit, segments=tuple(segments)) for unit, segments in zip(units, adjusted, strict=True)]
    return _DisplayLine(tuple(units), tuple(segment_colours), first, last)



@dataclass(frozen=True)
class TemplateSong:
    """Timed lyrics and track information passed to review and export templates."""

    sources: tuple[LyricSource, ...]
    bpm: float
    tracks: Mapping[str, int]
    channels: Mapping[str, tuple[tuple[int, ...], ...]]
    channel_colors: Mapping[int, str]
    preview_interval: tuple[float, float] | None = None


def template_song(
    timing: TimedLyrics,
    *,
    offset_ms: int = 0,
    track_style: Mapping[int, str] | None = None,
    colors: Mapping[int, str] | None = None,
) -> TemplateSong:
    if type(offset_ms) is not int or not -2147483647 <= offset_ms <= 2147483647:
        raise ValueError("offset_ms must be an integer between -2147483647 and 2147483647")
    roles = track_style or {}
    for role in roles.values():
        if role not in ("default", "top"):
            raise ValueError(f"unknown track style {role!r}")
    palette = {}
    for channel, color in (timing.channel_colors if colors is None else colors).items():
        if type(channel) is not int or not 0 <= channel < 16:
            raise ValueError("a colour channel must be between 0 and 15")
        if not isinstance(color, str):
            raise TypeError("channel colours must be six-digit RGB colours")
        rgb = color.lstrip("#").upper()
        if len(rgb) != 6 or any(char not in "0123456789ABCDEF" for char in rgb):
            raise ValueError("channel colours must be six-digit RGB colours")
        palette[channel] = rgb

    sources, source_tracks, source_channels = [], {}, {}
    for index, (line, spans) in enumerate(zip(timing.lines, timing.spans, strict=True)):
        row = _convert(line, spans, offset_ms, index)
        if row is None:
            continue
        family = roles.get(line.track, "default")
        identity = f"line-{index + 1}"
        appearance = TextAppearance(family, WHITE, WHITE, BLACK, BLACK, frozenset())
        runs, units = [], []
        offset = 0
        for unit in row.units:
            end = offset + len(unit.text)
            runs.append(TextRun(unit.text, offset, end, appearance))
            segments = []
            for segment in unit.segments:
                reading = None
                if segment.ruby:
                    length = len(segment.ruby)
                    run = TextRun(segment.ruby, 0, length, appearance)
                    reading = RubyText(
                        DocumentText(None, (), (run,), (), (), ()),
                        (LyricMapping(0, length, 0, length),),
                        "join" if unit.ruby_continuation or segments else "spill",
                    )
                clock = TimedTextSpan(offset, end, segment.start_ms / 1000, segment.end_ms / 1000, "k")
                segments.append(LyricSegment(clock, offset, end, reading))
            units.append(LyricUnit(offset, end, tuple(segments)))
            offset = end
        body = DocumentText(None, (), tuple(runs), (), (), ())
        lyrics = DocumentLyrics(body, body, (LyricMapping(0, offset, 0, offset),), tuple(units))
        sources.append(
            LyricSource.from_lyrics(
                identity,
                lyrics,
                style=family,
                actor=str(line.chapter),
                chapter=str(line.chapter),
                display=Lifetime(row.first / 1000, max(row.first + 1, row.last) / 1000),
            )
        )
        source_tracks[identity] = line.track
        source_channels[identity] = row.segment_colours
    return TemplateSong(tuple(sources), timing.bpm, source_tracks, source_channels, palette)


DEFAULT_OFFSET_MS = -100


def load_project_song(
    path: str | Path, *, offset_ms: int = DEFAULT_OFFSET_MS, harmony_tracks: str = ""
) -> TemplateSong:
    roles = {}
    for entry in harmony_tracks.split(","):
        track = entry.strip()
        if track:
            if not track.isdecimal() or not 0 <= int(track) < 16:
                raise ValueError("harmony_tracks must contain MIDI channel numbers 0..15")
            roles[int(track)] = "top"
    return template_song(load_project_input(path), offset_ms=offset_ms, track_style=roles)


def load_timing_directory(directory: str | Path) -> TemplateSong:
    """Read an existing review's matched KRC/MIDI and delivery settings."""
    root = Path(directory)
    wavetone, offset_ms, roles, colors = read_song_settings(root)
    timing = build_song(
        (root / "lyrics.krc").read_text(encoding="utf-8"),
        (root / "vocal.mid").read_bytes(),
        wavetone=wavetone,
    )
    return template_song(timing, offset_ms=offset_ms, track_style=roles, colors=colors)
