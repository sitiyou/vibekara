"""Command-line access to a local review service's durable sessions."""

import argparse
import json
import os
import time
from pathlib import Path

from .bundle import compiled
from .proposals import CATALOG, check_fonts, decorate, directions, revise, selected
from .store import Session


def main():
    parser = argparse.ArgumentParser(prog="review")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(
            os.environ.get(
                "KARA_REVIEW_ROOT", Path.home() / ".local/state/kara-previwer"
            )
        ),
    )
    parser.add_argument("--port", type=int, default=18673)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("title")
    create.add_argument("--no-notify", action="store_true")
    commands.add_parser("connect-codex").add_argument("session")
    commands.add_parser("serve")
    commands.add_parser("catalog")
    rebuild = commands.add_parser("rebuild")
    rebuild.add_argument("snapshot", type=Path)
    rebuild.add_argument("output", type=Path)
    rebuild.add_argument("--python")
    prefs = commands.add_parser("preferences")
    prefs.add_argument("--write", type=Path)
    prefs.add_argument("--digest")
    for name in ("publish", "revise", "wait", "state", "pending", "claim", "export"):
        command = commands.add_parser(name)
        command.add_argument("session")
        if name == "export":
            command.add_argument("output", type=Path)
            command.add_argument("--fps", type=int, default=60, help="delivery frame rate (default: 60)")
            command.add_argument("--snapshot", type=Path)
        if name == "claim":
            command.add_argument("token")
        if name in {"publish", "revise"}:
            command.add_argument("manifest", type=Path)
            command.add_argument("--base", required=True, type=int)
            command.add_argument("--feedback", required=name == "revise")
        if name == "wait":
            command.add_argument("--after", default=0, type=int)
            command.add_argument("--timeout", default=30, type=float)
    args = parser.parse_args()
    if args.command == "serve":
        from .server import serve

        serve(args.root, args.port)
        return
    if args.command == "rebuild":
        from .delivery import rebuild

        result = rebuild(args.snapshot, args.output, args.python)
    elif args.command == "preferences":
        from .preferences import Preferences

        prefs = Preferences()
        result = (
            prefs.save(args.write.read_bytes().decode(), args.digest)
            if args.write
            else prefs.read()
        )
        if result.get("error"):
            # Leave the invalid source on disk for repair; keep Agent context bounded.
            result.pop("text", None)
            result["path"] = str(prefs.file)
    elif args.command == "catalog":
        result = CATALOG
    elif args.command == "create":
        session = Session.create(args.root, args.title)
        result = {
            "session": session.root.name,
            "url": f"http://127.0.0.1:{args.port}/s/{session.root.name}/",
        }
        if os.environ.get("CODEX_THREAD_ID") and not args.no_notify:
            from .notify import bind

            try:
                result["codex_thread"] = bind(session)
            except (OSError, ValueError) as e:
                result["notification_warning"] = f"{e}; use review wait"
    elif args.command == "connect-codex":
        from .notify import bind

        if not os.environ.get("CODEX_THREAD_ID"):
            parser.error("run connect-codex from the originating Codex thread")
        result = {"codex_thread": bind(Session(args.root / args.session))}
    else:
        session = Session(args.root / args.session)
        if args.command == "publish":
            inherit = {}
            if args.feedback:
                item = next(
                    (
                        e
                        for e in session.events(0)
                        if e.get("token") == args.feedback and e["kind"] == "feedback"
                    ),
                    None,
                )
                if not item:
                    parser.error("unknown feedback")
                inherit = item["values"]
            result = session.publish(
                args.base, directions(session, args.manifest, inherit), args.feedback
            )
        elif args.command == "revise":
            result = revise(
                session,
                args.base,
                args.feedback,
                json.loads(args.manifest.read_text()),
                args.manifest.parent,
            )
        elif args.command == "claim":
            result = {"event": session.claim(args.token)}
        elif args.command == "export":
            state = session.state()
            item = next(
                (e for e in session.pending() if e["token"] == state["accepted"]), None
            )
            if item is None:
                parser.error("review has no accepted revision")
            proposal = selected(
                state["revisions"][item["version"] - 1], item.get("direction", 0)
            )
            decorate(proposal, require_selected=False)
            check_fonts(proposal, item["values"])
            if not 1 <= args.fps <= 240:
                parser.error("invalid fps")
            proposal = dict(proposal, clip=dict(proposal["clip"], fps=args.fps))
            if "config" not in proposal:
                parser.error("this precompiled review has no whole-song compiler")
            if args.snapshot:
                from .delivery import snapshot

                snapshot(
                    session, proposal, item, proposal["clip"]["fps"], args.snapshot
                )
            compiled(session, proposal, item["values"], full=args.output)
            result = {
                "version": item["version"],
                "values": item["values"],
                "output": str(args.output),
            }
        elif args.command == "state":
            result = session.state()
        elif args.command == "pending":
            result = session.pending()
        else:
            deadline = time.monotonic() + args.timeout
            while (
                not (result := session.events(args.after))
                and time.monotonic() < deadline
            ):
                time.sleep(0.15)
    if args.command in {"wait", "pending"}:
        for event in result:
            event["session_dir"] = str(session.root.resolve())
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
