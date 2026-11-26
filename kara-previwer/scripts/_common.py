"""Shared paths and output for scripts running the local review backend."""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kara_previwer.paths import vibekara_home


def review_parser(
    description: str | None, *, session: bool = False, port: bool = False
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("KARA_REVIEW_ROOT") or vibekara_home() / "review").expanduser(),
    )
    if port:
        parser.add_argument("--port", type=int, default=18673)
    if session:
        parser.add_argument("session")
    return parser


def frame_rate(value: str) -> int:
    fps = int(value)
    if not 1 <= fps <= 240:
        raise argparse.ArgumentTypeError("frame rate must be 1 through 240")
    return fps


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False))
