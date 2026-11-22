"""Forward committed review submissions to the Codex thread that opened the review."""

import logging
import os
import shutil
import sqlite3
import subprocess
import time
import uuid
from contextlib import closing
from pathlib import Path
from threading import Event

from .store import Session

LOG = logging.getLogger(__name__)
BINDING = "codex-notifications.sqlite3"


def bind(session):
    thread = str(uuid.UUID(os.environ["CODEX_THREAD_ID"]))
    binary = shutil.which("codex")
    if not binary:
        raise ValueError("codex executable missing")
    if not session.db.is_file():
        raise ValueError("unknown review session")
    home = os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    with closing(sqlite3.connect(session.root / BINDING)) as db, db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS binding (singleton INTEGER PRIMARY KEY, thread TEXT, home TEXT, binary TEXT, cursor INTEGER)"
        )
        prior = db.execute("SELECT thread, home FROM binding").fetchone()
        if prior and prior != (thread, home):
            raise ValueError("review already belongs to another Codex thread")
        db.execute(
            "INSERT OR IGNORE INTO binding VALUES (1,?,?,?,0)", (thread, home, binary)
        )
    return thread


def forward(session):
    with closing(sqlite3.connect(session.root / BINDING, timeout=20)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        binding = db.execute("SELECT thread,home,binary,cursor FROM binding").fetchone()
        if binding is None:
            return
        thread, home, binary, cursor = binding
        for event in session.events(cursor):
            if event["kind"] in ("feedback", "accept"):
                notice = (
                    f"kara-previwer 评审事件 {event['token']}：会话 {session.root.name} "
                    f"第 {event['version']} 版，操作 {event['kind']}。"
                    f"请从评审目录 {session.root.parent} 读取本次提交的参数和意见，"
                    "按本对话约定处理。"
                )
                if event["kind"] == "accept":
                    notice += "将本次采用的 values 应用到制作工程，重建并核对约定的交付物。"
                notice += "同编号对应的交付物已核实完成时仅确认收件。"
                result = subprocess.run(
                    [
                        binary,
                        "queue",
                        "--thread",
                        thread,
                        "--message",
                        notice,
                        "--resume",
                    ],
                    env={**os.environ, "CODEX_HOME": home},
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
                if result.returncode:
                    raise RuntimeError(result.stderr.strip() or "codex queue failed")
                LOG.warning(
                    "Review event %s queued for %s. %s",
                    event["id"],
                    thread,
                    result.stderr.strip(),
                )
            db.execute("UPDATE binding SET cursor=?", (event["id"],))
            db.commit()
            # Only one dispatcher may claim the next ID.
            return


def watch(root, stop: Event):
    backoff = {}
    while not stop.is_set():
        for marker in root.glob(f"*/{BINDING}"):
            if time.monotonic() < backoff.get(marker, 0):
                continue
            try:
                forward(Session(marker.parent))
            except (
                OSError,
                RuntimeError,
                sqlite3.Error,
                subprocess.TimeoutExpired,
            ) as error:
                LOG.warning(
                    "Review delivery delayed for %s: %s", marker.parent.name, error
                )
                backoff[marker] = time.monotonic() + 30
        stop.wait(1)
