"""Wait for review events after a cursor, or return an empty list on timeout."""

import time

from _common import print_json, review_parser

from kara_previwer.store import Session


def main() -> None:
    parser = review_parser(__doc__, session=True)
    parser.add_argument("--after", default=0, type=int)
    parser.add_argument("--timeout", default=30, type=float)
    args = parser.parse_args()
    session = Session(args.root / args.session)
    deadline = time.monotonic() + args.timeout
    while not (events := session.events(args.after)) and time.monotonic() < deadline:
        time.sleep(0.15)
    print_json([{**event, "session_dir": str(session.root)} for event in events])


if __name__ == "__main__":
    main()
