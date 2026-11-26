# SPDX-License-Identifier: AGPL-3.0-only
"""Delivery settings stored beside matched KRC and MIDI in older reviews."""

import json
from pathlib import Path

_CHANNELS = {str(channel) for channel in range(16)}


def _channel_map(value: object, field: str) -> dict[int, str]:
    if not isinstance(value, dict):
        raise TypeError(f"song.json: {field} must be an object")
    channels = {}
    for key, label in value.items():
        if not isinstance(key, str) or key not in _CHANNELS:
            raise ValueError(f"song.json: {field} must use MIDI channels 0..15")
        if not isinstance(label, str):
            raise TypeError(f"song.json: {field} values must be strings")
        channels[int(key)] = label
    return channels


def read_song_settings(directory: str | Path) -> tuple[bool, int, dict[int, str], dict[int, str]]:
    """Read the MIDI convention, offset, vocal roles and colours from song.json."""
    data: object = json.loads((Path(directory) / "song.json").read_text(encoding="utf-8"))
    fields = {"wavetone", "offset_ms", "track_style", "colors"}
    if not isinstance(data, dict) or data.keys() != fields:
        raise ValueError("song.json must contain wavetone, offset_ms, track_style and colors")
    wavetone = data["wavetone"]
    offset_ms = data["offset_ms"]
    if type(wavetone) is not bool or type(offset_ms) is not int:
        raise ValueError("song.json: wavetone must be boolean and offset_ms must be an integer")
    return wavetone, offset_ms, _channel_map(data["track_style"], "track_style"), _channel_map(data["colors"], "colors")
