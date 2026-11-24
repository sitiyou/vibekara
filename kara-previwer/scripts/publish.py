"""Publish a full set of design proposals to a review session."""

from pathlib import Path

from _common import print_json, review_parser

from kara_previwer.proposals import directions
from kara_previwer.store import Session


def main() -> None:
    parser = review_parser(__doc__, session=True)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--base", required=True, type=int)
    parser.add_argument("--feedback")
    args = parser.parse_args()
    session = Session(args.root / args.session)
    inherit = {}
    if args.feedback:
        feedback = next(
            (
                event
                for event in session.events(0)
                if event.get("token") == args.feedback and event["kind"] == "feedback"
            ),
            None,
        )
        if feedback is None:
            parser.error("unknown feedback")
        inherit = feedback["values"]
    print_json(
        session.publish(
            args.base, directions(session, args.manifest, inherit), args.feedback
        )
    )


if __name__ == "__main__":
    main()
