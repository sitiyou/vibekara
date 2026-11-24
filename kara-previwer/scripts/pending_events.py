"""Read unresolved feedback and acceptance events."""

from _common import print_json, review_parser

from kara_previwer.store import Session

if __name__ == "__main__":
    args = review_parser(__doc__, session=True).parse_args()
    session = Session(args.root / args.session)
    print_json(
        [{**event, "session_dir": str(session.root)} for event in session.pending()]
    )
