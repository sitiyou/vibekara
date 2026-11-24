"""Save the accepted template, project and settings for a rebuild."""

from pathlib import Path

from _common import frame_rate, print_json, review_parser

from kara_previwer.delivery import accepted_build, snapshot
from kara_previwer.store import Session


def main() -> None:
    parser = review_parser(__doc__, session=True)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--fps", type=frame_rate, default=60)
    args = parser.parse_args()
    session = Session(args.root / args.session)
    try:
        proposal, item = accepted_build(session)
        result = snapshot(session, proposal, item, args.fps, args.directory)
    except ValueError as error:
        parser.error(str(error))
    print_json({**result, "snapshot": str(args.directory)})


if __name__ == "__main__":
    main()
