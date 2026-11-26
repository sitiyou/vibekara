"""Transactional revisions, feedback and acceptance for one review session."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


class Conflict(ValueError):
    pass


class Session:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.db = self.root / "session.sqlite3"

    @classmethod
    def create(cls, parent, title):
        session = cls(Path(parent) / uuid.uuid4().hex)
        session.root.mkdir(parents=True)
        with session.transaction(create=True) as db:
            db.executescript("""
                CREATE TABLE session(title TEXT, version INTEGER, accepted TEXT);
                CREATE TABLE revisions(version INTEGER PRIMARY KEY, proposal TEXT, feedback TEXT UNIQUE);
                CREATE TABLE events(id INTEGER PRIMARY KEY, kind TEXT, payload TEXT);
                CREATE TABLE submissions(token TEXT PRIMARY KEY, payload TEXT, result INTEGER);
            """)
            db.execute("INSERT INTO session VALUES(?,0,NULL)", (title,))
        return session

    @contextmanager
    def transaction(self, create=False):
        if not create and not self.db.is_file():
            raise FileNotFoundError(self.db)
        db = sqlite3.connect(self.db, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        finally:
            db.close()

    @staticmethod
    def emit(db, kind, payload):
        return db.execute(
            "INSERT INTO events(kind,payload) VALUES(?,?)",
            (kind, json.dumps(payload, ensure_ascii=False)),
        ).lastrowid

    @staticmethod
    def ensure_drafts(db):
        db.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                version INTEGER NOT NULL, direction INTEGER NOT NULL,
                revision INTEGER NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(version,direction)
            )
        """)

    def save_draft(self, version, direction, revision, values, composition):
        if type(revision) is not int or revision < 0:
            raise ValueError("无效的草稿版本")
        payload = {"values": values, "composition": composition}
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        with self.transaction() as db:
            self.ensure_drafts(db)
            if db.execute("SELECT accepted FROM session").fetchone()[0]:
                raise Conflict("这次评审已采用")
            row = db.execute(
                "SELECT revision,payload FROM drafts WHERE version=? AND direction=?",
                (version, direction),
            ).fetchone()
            current = row["revision"] if row else 0
            if current != revision:
                if row and current == revision + 1 and row["payload"] == encoded:
                    return {"revision": current}
                raise Conflict("草稿在另一个窗口更新，请刷新后继续")
            db.execute(
                "INSERT OR REPLACE INTO drafts VALUES(?,?,?,?)",
                (version, direction, current + 1, encoded),
            )
            return {"revision": current + 1}

    def state(self):
        with self.transaction() as db:
            self.ensure_drafts(db)
            row = db.execute("SELECT * FROM session").fetchone()
            revisions = [
                json.loads(r[0])
                for r in db.execute("SELECT proposal FROM revisions ORDER BY version")
            ]
            submission = db.execute(
                "SELECT payload FROM submissions WHERE coalesce(json_extract(payload,'$.base'),json_extract(payload,'$.version'))=? ORDER BY result DESC LIMIT 1",
                (row["version"],),
            ).fetchone()
            saved = json.loads(submission[0]) if submission else None
            working = (
                saved
                and db.execute(
                    "SELECT 1 FROM events WHERE kind='working' AND json_extract(payload,'$.token')=?",
                    (saved["token"],),
                ).fetchone()
            )
            return {
                "saved": saved,
                "working": bool(working),
                "title": row["title"],
                "version": row["version"],
                "accepted": row["accepted"],
                "revisions": revisions,
                "drafts": {
                    f"{draft['version']}:{draft['direction']}": {
                        **json.loads(draft["payload"]), "revision": draft["revision"],
                    }
                    for draft in db.execute("SELECT * FROM drafts")
                },
                "cursor": db.execute(
                    "SELECT coalesce(max(id),0) FROM events"
                ).fetchone()[0],
            }

    def events(self, after):
        with self.transaction() as db:
            return [
                dict(id=r["id"], kind=r["kind"], **json.loads(r["payload"]))
                for r in db.execute(
                    "SELECT * FROM events WHERE id>? ORDER BY id", (after,)
                )
            ]

    def pending(self):
        with self.transaction() as db:
            return [
                json.loads(r[0])
                for r in db.execute("""
                SELECT payload FROM submissions WHERE token NOT IN
                (SELECT feedback FROM revisions WHERE feedback IS NOT NULL) ORDER BY result
            """)
            ]

    def claim(self, token):
        with self.transaction() as db:
            row = db.execute(
                "SELECT payload FROM submissions WHERE token=?", (token,)
            ).fetchone()
            if not row or json.loads(row[0])["action"] not in ("feedback", "continue"):
                raise ValueError("unknown feedback")
            for event in db.execute(
                "SELECT id,payload FROM events WHERE kind='working'"
            ):
                if json.loads(event["payload"])["token"] == token:
                    return event["id"]
            return self.emit(db, "working", {"token": token})

    def publish(self, base, proposal, feedback=None):
        with self.transaction() as db:
            if feedback:
                prior = db.execute(
                    "SELECT proposal FROM revisions WHERE feedback=?", (feedback,)
                ).fetchone()
                if prior:
                    existing = json.loads(prior[0])
                    if existing != dict(proposal, version=base + 1):
                        raise Conflict("feedback already has a different revision")
                    return existing
                item = db.execute(
                    "SELECT payload FROM submissions WHERE token=?", (feedback,)
                ).fetchone()
                if not item or json.loads(item[0])["action"] not in ("feedback", "continue"):
                    raise Conflict("unknown feedback")
                submitted = json.loads(item[0])
                if submitted.get("base", submitted["version"]) != base:
                    raise Conflict("feedback belongs to another base version")
            current, accepted = db.execute(
                "SELECT version,accepted FROM session"
            ).fetchone()
            if base != current or accepted:
                raise Conflict("session changed; read current state")
            proposal = dict(proposal, version=base + 1)
            db.execute(
                "INSERT INTO revisions VALUES(?,?,?)",
                (base + 1, json.dumps(proposal, ensure_ascii=False), feedback),
            )
            db.execute("UPDATE session SET version=?", (base + 1,))
            self.emit(db, "published", {"version": base + 1, "feedback": feedback})
            return proposal

    def submit(self, payload):
        submitted_version = payload.get("version")
        if type(submitted_version) is not int:
            raise ValueError("invalid submission version")
        token = str(uuid.UUID(payload["token"]))
        payload = dict(payload, token=token)
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        action = payload["action"]
        if action not in ("feedback", "continue", "accept"):
            raise ValueError("unknown action")
        with self.transaction() as db:
            prior = db.execute(
                "SELECT payload,result FROM submissions WHERE token=?", (token,)
            ).fetchone()
            if prior:
                if prior[0] != encoded:
                    raise Conflict("submission ID already used")
                return prior[1]
            version, accepted = db.execute(
                "SELECT version,accepted FROM session"
            ).fetchone()
            if (
                accepted
                or version != payload.get("base", submitted_version)
                or not 1 <= submitted_version <= version
            ):
                raise Conflict("review version changed")
            event = self.emit(db, action, payload)
            db.execute("INSERT INTO submissions VALUES(?,?,?)", (token, encoded, event))
            if action == "accept":
                db.execute("UPDATE session SET accepted=?", (token,))
            return event
