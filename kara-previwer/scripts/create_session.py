"""Create a new review session and return its browser URL."""

import os

from _common import print_json, review_parser

from kara_previwer.store import Session


def main() -> None:
    parser = review_parser(__doc__, port=True)
    parser.add_argument("title")
    parser.add_argument("--no-notify", action="store_true")
    args = parser.parse_args()
    session = Session.create(args.root, args.title)
    result = {
        "session": session.root.name,
        "url": f"http://127.0.0.1:{args.port}/s/{session.root.name}/",
    }
    if os.environ.get("CODEX_THREAD_ID") and not args.no_notify:
        from kara_previwer.notify import bind

        try:
            result["codex_thread"] = bind(session)
        except (OSError, ValueError) as error:
            result["notification_warning"] = (
                f"{error}. Run wait_for_events.py to listen for events."
            )
    print_json(result)


if __name__ == "__main__":
    main()
