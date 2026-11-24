"""Publish a design patch in response to a feedback event."""

import json
from pathlib import Path

from _common import print_json, review_parser

from kara_previwer.proposals import revise
from kara_previwer.store import Session


def main() -> None:
    parser = review_parser(__doc__, session=True)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--base", required=True, type=int)
    parser.add_argument("--feedback", required=True)
    args = parser.parse_args()
    session = Session(args.root / args.session)
    patch = json.loads(args.manifest.read_text(encoding="utf-8"))
    print_json(revise(session, args.base, args.feedback, patch, args.manifest.parent))


if __name__ == "__main__":
    main()
