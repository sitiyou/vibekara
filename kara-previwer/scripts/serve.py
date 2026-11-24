"""Open the local browser review service."""

from _common import review_parser

from kara_previwer.server import serve


def main() -> None:
    args = review_parser(__doc__, port=True).parse_args()
    serve(args.root, args.port)


if __name__ == "__main__":
    main()
