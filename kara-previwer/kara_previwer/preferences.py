"""Small UTF-8 preference index with immutable versions of reusable recipes."""

import fcntl
import hashlib
import json
import os
import re
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from .store import Conflict

LINK = re.compile(
    r"^- \[([^\[\]\n]+)\]\(templates/([a-z0-9-]+)/(?:([0-9a-f]{32})/)?\)(?: — (.*))?$"
)
LIMIT = 4096


def atomic(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


class Preferences:
    def __init__(self, root=None):
        self.root = Path(
            root
            or Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "vibekara"
        )
        self.file = self.root / "preferences.md"
        self.recovery = self.root / ".last-valid.md"

    def package(self, key, generation=None):
        if not re.fullmatch(r"[a-z0-9-]+", key):
            raise ValueError("invalid template ID")
        directory = self.root / "templates" / key
        if directory.resolve().parent != (self.root.resolve() / "templates"):
            raise ValueError("template outside configuration directory")
        if generation:
            if not re.fullmatch(r"[0-9a-f]{32}", generation):
                raise ValueError("invalid template version")
            directory = directory / generation
        for filename in ("template.json", "template.py"):
            if (
                not (directory / filename)
                .resolve()
                .is_relative_to(self.root.resolve() / "templates" / key)
            ):
                raise ValueError("template file outside collection")
        meta = json.loads((directory / "template.json").read_text())
        if (
            not isinstance(meta, dict)
            or not isinstance(meta.get("template"), str)
            or not isinstance(meta.get("values"), dict)
        ):
            raise ValueError(f"invalid template metadata: {key}")  # noqa: TRY004
        for name in meta.get("resources", []):
            resource = (directory / name).resolve()
            if (
                not resource.is_relative_to(directory.resolve())
                or not resource.is_file()
            ):
                raise ValueError(f"invalid template resource: {name}")
        if not (directory / "template.py").is_file():
            raise ValueError(f"missing template source: {key}")
        return directory, meta

    def lookup(self, key):
        current = self.read()
        if current.get("error"):
            raise ValueError(current["error"])
        for entry in current["templates"]:
            if entry["id"] == key:
                return self.package(key, entry["generation"])
        raise ValueError("unknown collection entry")

    def validate(self, data):
        if len(data) > LIMIT:
            raise ValueError(
                f"{len(data)} UTF-8 bytes, exceeds 4096 by {len(data) - LIMIT}"
            )
        content = data.decode("utf-8")
        items = {}
        collection = False
        for line_no, line in enumerate(content.splitlines(), 1):
            if re.match(r"^#{1,2} ", line):
                collection = line.strip() == "## 我的模板"
            elif collection and line.strip():
                match = LINK.fullmatch(line)
                if not match or match[2] in items:
                    raise ValueError(
                        f"line {line_no}: invalid or duplicate template link"
                    )
                try:
                    self.package(match[2], match[3])
                except (OSError, ValueError) as err:
                    raise ValueError(f"line {line_no}: {err}") from err
                items[match[2]] = {
                    "id": match[2],
                    "generation": match[3],
                    "name": match[1],
                    "description": match[4] or "",
                }
        return items

    def read(self):
        data = self.file.read_bytes() if self.file.exists() else b""
        result = {"digest": hashlib.sha256(data).hexdigest(), "size": len(data)}
        try:
            result.update(
                text=data.decode(), templates=list(self.validate(data).values())
            )
        except (OSError, ValueError) as e:
            result.update(
                text=data.decode(errors="replace"), templates=[], error=str(e)
            )
            if self.recovery.is_file():
                result["last_valid"] = self.recovery.read_text()
        return result

    @contextmanager
    def edit(self, digest):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            current = self.read()
            if current["digest"] != digest:
                raise Conflict("偏好已更改，请重新读取后合并")
            yield current

    def write(self, content):
        data = content.encode()
        self.validate(data)
        # The live index is the commit point; keep a last-known-good text
        # for repairing a later manual edit.
        previous = self.read()
        if not previous.get("error") and self.file.exists():
            atomic(self.recovery, previous["text"].encode())
        atomic(self.file, data)
        # A failed backup refresh cannot roll back an already committed index.
        try:
            atomic(self.recovery, data)
        except OSError:
            pass
        return self.read()

    def save(self, content, digest):
        with self.edit(digest):
            return self.write(content)

    def manage(self, action, digest, key="", name="", description="", package=None):
        import shutil

        if action not in {"add", "update", "rename", "remove"}:
            raise ValueError("unknown library action")
        with self.edit(digest) as current:
            if current.get("error"):
                raise ValueError(current["error"])
            items = {i["id"]: i for i in current["templates"]}
            if action != "add" and key not in items:
                raise ValueError("unknown collection entry")
            if action != "remove" and (
                not name.strip()
                or any(c in name for c in "[]\r\n")
                or "\n" in description
                or "\r" in description
            ):
                raise ValueError("请提供单行名称和说明")
            if any(
                i["name"] == name and (action == "add" or i["id"] != key)
                for i in items.values()
            ):
                raise Conflict("同名收藏已存在，请选择更新目标或另存名称")
            lines = current["text"].splitlines()
            old = next(
                (
                    n
                    for n, l in enumerate(lines)
                    if (m := LINK.fullmatch(l))
                    and m[2] == key
                    and next(
                        (
                            h.strip()
                            for h in reversed(lines[:n])
                            if re.match(r"^#{1,2} ", h)
                        ),
                        "",
                    )
                    == "## 我的模板"
                ),
                None,
            )
            generation = items.get(key, {}).get("generation")
            directory = None
            try:
                if action in {"add", "update"}:
                    if package is None:
                        raise ValueError("保存模板需要可重建的模板输入")
                    # An update switches the index to a complete immutable package.
                    if action == "add":
                        key = uuid.uuid4().hex
                    generation = uuid.uuid4().hex
                    directory = self.root / "templates" / key / generation
                    directory.mkdir(parents=True)
                    script, meta = package
                    shutil.copyfile(script, directory / "template.py")
                    for resource in meta.get("resources", []):
                        dest = directory / resource
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(Path(script).parent / resource, dest)
                    atomic(
                        directory / "template.json",
                        json.dumps(meta, ensure_ascii=False).encode(),
                    )
                suffix = f"{generation}/" if generation else ""
                line = f"- [{name}](templates/{key}/{suffix})" + (
                    f" — {description}" if description else ""
                )
                if action == "remove":
                    lines.pop(old)
                elif action == "add":
                    if "## 我的模板" not in lines:
                        lines.extend(["", "## 我的模板"])
                    lines.insert(lines.index("## 我的模板") + 1, line)
                else:
                    lines[old] = line
                return self.write("\n".join(lines).strip("\n") + "\n")
            except BaseException:
                if directory:
                    shutil.rmtree(directory, ignore_errors=True)
                raise
