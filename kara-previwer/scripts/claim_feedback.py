"""Claim a review feedback event and return it with its design selections."""

from _common import print_json, review_parser

from kara_previwer.store import Session

if __name__ == "__main__":
    parser = review_parser(__doc__, session=True)
    parser.add_argument("token")
    args = parser.parse_args()
    print_json({"event": Session(args.root / args.session).claim(args.token)})
