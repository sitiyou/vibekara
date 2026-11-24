"""Read a session's revisions, accepted token and latest event cursor."""

from _common import print_json, review_parser

from kara_previwer.store import Session

if __name__ == "__main__":
    args = review_parser(__doc__, session=True).parse_args()
    print_json(Session(args.root / args.session).state())
