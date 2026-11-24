"""Read local preferences or save them against the last read digest."""

import argparse
from pathlib import Path

from _common import print_json

from kara_previwer.preferences import Preferences


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", type=Path)
    parser.add_argument("--digest")
    args = parser.parse_args()
    prefs = Preferences()
    result = (
        prefs.save(args.write.read_bytes().decode("utf-8"), args.digest)
        if args.write
        else prefs.read()
    )
    if result.get("error"):
        result.pop("text", None)
        result["path"] = str(prefs.file)
    print_json(result)


if __name__ == "__main__":
    main()
