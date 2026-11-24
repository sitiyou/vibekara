"""Rebuild a whole-song Hook from a saved review snapshot."""

import argparse
from pathlib import Path

from _common import print_json

from kara_previwer.delivery import rebuild


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--python")
    args = parser.parse_args()
    print_json(rebuild(args.snapshot, args.output, args.python))


if __name__ == "__main__":
    main()
