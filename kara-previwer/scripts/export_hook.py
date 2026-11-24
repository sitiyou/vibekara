"""Build a whole-song Hook from the accepted review proposal."""

from pathlib import Path

from _common import frame_rate, print_json, review_parser

from kara_previwer.bundle import local_config
from kara_previwer.delivery import accepted_build, build_hook, snapshot
from kara_previwer.store import Session


def main() -> None:
    parser = review_parser(__doc__, session=True)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fps", type=frame_rate, default=60)
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    session = Session(args.root / args.session)
    try:
        proposal, item = accepted_build(session)
        if args.snapshot:
            snapshot(session, proposal, item, args.fps, args.snapshot)
        build_hook(
            local_config(session, proposal),
            proposal,
            item["values"],
            args.fps,
            args.output,
        )
    except ValueError as error:
        parser.error(str(error))
    print_json(
        {
            "version": item["version"],
            "values": item["values"],
            "output": str(args.output),
        }
    )


if __name__ == "__main__":
    main()
