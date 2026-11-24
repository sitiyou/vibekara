"""Connect an existing review session to the current Codex thread."""

import os

from _common import print_json, review_parser

from kara_previwer.notify import bind
from kara_previwer.store import Session


def main() -> None:
    parser = review_parser(__doc__, session=True)
    args = parser.parse_args()
    if not os.environ.get("CODEX_THREAD_ID"):
        parser.error("run this script from the originating Codex thread")
    print_json({"codex_thread": bind(Session(args.root / args.session))})


if __name__ == "__main__":
    main()
