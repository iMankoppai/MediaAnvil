#!/usr/bin/env python3
"""Read-only scanner for stale local Codex Desktop thread references."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")

SIDEBAR_FIELDS = ("pinned-thread-ids", "projectless-thread-ids")
UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
ROLLOUT_ID = re.compile(r"rollout-.+-(" + UUID + r")\.jsonl$", re.I)
LOCK_ID = re.compile("(" + UUID + r")\.lock$", re.I)


@dataclass
class Evidence:
    id: str
    title: str | None = None
    found_in: list[str] = field(default_factory=list)
    index_rows: int = 0
    state_rows: list[dict[str, Any]] = field(default_factory=list)
    rollouts: list[Path] = field(default_factory=list)
    history: list[Path] = field(default_factory=list)
    locked: bool = False

    def found(self, source: str) -> None:
        if source not in self.found_in:
            self.found_in.append(source)


def readonly_db(path: Path) -> sqlite3.Connection:
    # Do not use immutable=1: that can ignore a live WAL and yield false ghosts.
    return sqlite3.connect("file:" + path.resolve().as_posix() + "?mode=ro", uri=True)


def has_table(db: sqlite3.Connection, table: str) -> bool:
    return db.execute("select 1 from sqlite_master where type='table' and name=?", (table,)).fetchone() is not None


def db_candidates(home: Path, pattern: str) -> list[Path]:
    """Select the newest same-name DB; old migration copies are not merged."""
    selected: dict[str, Path] = {}
    for folder in (home, home / "sqlite"):
        if not folder.is_dir():
            continue
        for path in folder.glob(pattern):
            previous = selected.get(path.name)
            if previous is None or path.stat().st_mtime_ns > previous.stat().st_mtime_ns:
                selected[path.name] = path
    return sorted(selected.values())


def file_state(paths: Iterable[Path]) -> dict[Path, tuple[int, int]]:
    result: dict[Path, tuple[int, int]] = {}
    for path in paths:
        for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
            try:
                stat = candidate.stat()
                result[candidate] = (stat.st_size, stat.st_mtime_ns)
            except FileNotFoundError:
                pass
    return result


def add_sidebar(home: Path, records: dict[str, Evidence], errors: list[str]) -> None:
    state_path = home / ".codex-global-state.json"
    with state_path.open(encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict):
        raise ValueError(".codex-global-state.json is not an object")
    for sidebar_field in SIDEBAR_FIELDS:
        values = state.get(sidebar_field, [])
        if not isinstance(values, list):
            errors.append(f".codex-global-state.json:{sidebar_field} is not an array")
            continue
        for value in values:
            if not isinstance(value, str):
                errors.append(f".codex-global-state.json:{sidebar_field} has a non-string ID")
                continue
            item = records.setdefault(value.lower(), Evidence(value.lower()))
            item.found(f".codex-global-state.json:{sidebar_field}")


def add_index(home: Path, records: dict[str, Evidence], errors: list[str]) -> None:
    path = home / "session_index.jsonl"
    if not path.is_file():
        return
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                thread_id = str(row["id"]).lower()
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                errors.append(f"{path.name}:{number}: {error}")
                continue
            item = records.setdefault(thread_id, Evidence(thread_id))
            item.index_rows += 1
            item.found("session_index.jsonl:id")
            if not item.title and isinstance(row.get("thread_name"), str):
                item.title = row["thread_name"]


def add_rollouts(home: Path, records: dict[str, Evidence], errors: list[str]) -> None:
    for name in ("sessions", "archived_sessions"):
        root = home / name
        if not root.is_dir():
            continue
        try:
            for path in root.rglob("rollout-*.jsonl"):
                match = ROLLOUT_ID.search(path.name)
                if not match:
                    continue
                thread_id = match.group(1).lower()
                item = records.setdefault(thread_id, Evidence(thread_id))
                item.rollouts.append(path)
                item.found(str(path.relative_to(home)))
        except OSError as error:
            errors.append(f"{root}: {error}")


def add_locks(home: Path, records: dict[str, Evidence]) -> None:
    root = home / "thread-writer-locks"
    if not root.is_dir():
        return
    for path in root.glob("*.lock"):
        match = LOCK_ID.search(path.name)
        if match:
            thread_id = match.group(1).lower()
            item = records.setdefault(thread_id, Evidence(thread_id))
            item.locked = True
            item.found(str(path.relative_to(home)))


def add_state(paths: Iterable[Path], records: dict[str, Evidence], errors: list[str]) -> list[Path]:
    usable: list[Path] = []
    for path in paths:
        db: sqlite3.Connection | None = None
        try:
            db = readonly_db(path)
            if not has_table(db, "threads"):
                continue
            usable.append(path)
            available = {row[1] for row in db.execute("pragma table_info(threads)")}
            fields = [field for field in ("id", "title", "rollout_path", "archived", "source", "thread_source") if field in available]
            if "id" not in fields:
                continue
            query = "select " + ",".join('"' + field + '"' for field in fields) + " from threads"
            for row in db.execute(query):
                value = dict(zip(fields, row, strict=True))
                thread_id = str(value["id"]).lower()
                item = records.setdefault(thread_id, Evidence(thread_id))
                item.state_rows.append({"database": path.name, **value})
                item.found(f"{path.name}:threads")
                if not item.title and isinstance(value.get("title"), str) and value["title"]:
                    item.title = value["title"]
        except (OSError, sqlite3.Error) as error:
            errors.append(f"{path}: {error}")
        finally:
            if db is not None:
                db.close()
    return usable


def add_history(paths: Iterable[Path], records: dict[str, Evidence], errors: list[str]) -> list[Path]:
    usable: list[Path] = []
    for path in paths:
        db: sqlite3.Connection | None = None
        try:
            db = readonly_db(path)
            tables = [name for name in ("thread_turns", "thread_items", "thread_history_projection_state") if has_table(db, name)]
            if not tables:
                continue
            usable.append(path)
            ids: set[str] = set()
            for table in tables:
                ids.update(str(row[0]).lower() for row in db.execute(f'select distinct thread_id from "{table}"'))
            for thread_id in ids:
                item = records.setdefault(thread_id, Evidence(thread_id))
                item.history.append(path)
                item.found(f"{path.name}:projected-history")
        except (OSError, sqlite3.Error) as error:
            errors.append(f"{path}: {error}")
        finally:
            if db is not None:
                db.close()
    return usable


def sidebar_reference(item: Evidence) -> bool:
    return any(source.startswith(".codex-global-state.json:") for source in item.found_in)


def path_rollout(item: Evidence) -> bool:
    return any(isinstance(row.get("rollout_path"), str) and row["rollout_path"] and Path(row["rollout_path"]).is_file() for row in item.state_rows)


def classify(item: Evidence, unstable: bool) -> tuple[str, list[str]]:
    missing: list[str] = []
    referenced = sidebar_reference(item)
    body_exists = bool(item.rollouts or item.history or path_rollout(item))
    if referenced and not item.state_rows:
        missing.append("state database:threads")
    if referenced and not (item.rollouts or path_rollout(item)):
        missing.append("sessions/archived_sessions rollout")
    if referenced and not item.history:
        missing.append("thread history projection")
    if unstable or item.locked:
        return "inconclusive", missing
    if not referenced:
        return "normal", missing
    if not body_exists and item.index_rows and not item.state_rows:
        return "high", missing
    active = [row for row in item.state_rows if row.get("archived") in (0, False, None)]
    if not body_exists and active:
        kinds = {str(row.get("thread_source") or "") for row in active}
        return ("high" if kinds & {"user", "cli", "vscode"} else "medium"), missing
    if not body_exists and item.index_rows:
        return "medium", missing
    if not body_exists and not item.state_rows:
        # A valid cloud-only task is indistinguishable from a deleted Web task
        # without a supported online lookup, so never label it an orphan.
        return "inconclusive", missing
    return "normal", missing


def scan(codex_home: Path) -> dict[str, Any]:
    home = codex_home.expanduser().resolve()
    global_state = home / ".codex-global-state.json"
    if not global_state.is_file():
        raise FileNotFoundError(f"not a detected Codex home: {global_state} is missing")
    states = db_candidates(home, "state_*.sqlite")
    histories = db_candidates(home, "thread_history_*.sqlite")
    tracked = [global_state, home / "session_index.jsonl", *states, *histories]
    before = file_state(tracked)
    records: dict[str, Evidence] = {}
    errors: list[str] = []
    add_sidebar(home, records, errors)
    add_index(home, records, errors)
    add_rollouts(home, records, errors)
    add_locks(home, records)
    usable_states = add_state(states, records, errors)
    usable_histories = add_history(histories, records, errors)
    unstable = before != file_state(tracked)
    normal: list[dict[str, Any]] = []
    suspects: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for item in sorted(records.values(), key=lambda record: record.id):
        confidence, missing = classify(item, unstable)
        counts[confidence] += 1
        record = {"id": item.id, "title": item.title or "(untitled)", "found_in": item.found_in, "missing": missing, "confidence": confidence}
        (normal if confidence == "normal" else suspects).append(record)
    return {
        "scanner": "codex-ghost-scan", "mode": "read-only", "codex_home": str(home),
        "source_changed_during_scan": unstable, "state_databases": [str(path) for path in usable_states],
        "history_databases": [str(path) for path in usable_histories], "normal_count": len(normal),
        "suspect_count": len(suspects), "confidence_counts": dict(sorted(counts.items())),
        "normal": normal, "suspected_ghosts": suspects, "errors": errors,
    }


def focus_report(report: dict[str, Any], thread_id: str | None = None, title: str | None = None) -> dict[str, Any]:
    """Restrict a completed scan to one exact ID or exact displayed title."""
    if thread_id is None and title is None:
        return report
    records = [*report["normal"], *report["suspected_ghosts"]]
    if thread_id is not None:
        matches = [record for record in records if record["id"] == thread_id.lower()]
        query = {"kind": "id", "value": thread_id, "matches": len(matches), "ambiguous": False}
    else:
        assert title is not None
        matches = [record for record in records if record["title"].casefold() == title.casefold()]
        query = {"kind": "title", "value": title, "matches": len(matches), "ambiguous": len(matches) != 1}
    result = {**report, "query": query}
    result["normal"] = [record for record in matches if record["confidence"] == "normal"]
    result["suspected_ghosts"] = [record for record in matches if record["confidence"] != "normal"]
    result["normal_count"] = len(result["normal"])
    result["suspect_count"] = len(result["suspected_ghosts"])
    result["confidence_counts"] = dict(sorted(Counter(record["confidence"] for record in matches).items()))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Codex Desktop ghost-thread scanner")
    parser.add_argument("--codex-home", type=Path, required=True, help="Codex home to inspect; pass an explicit path")
    exact = parser.add_mutually_exclusive_group()
    exact.add_argument("--id", help="inspect one exact thread UUID")
    exact.add_argument("--title", help="inspect one exact displayed title; multiple matches stay ambiguous")
    parser.add_argument("--include-normal", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args(argv)
    try:
        report = scan(args.codex_home)
    except (FileNotFoundError, PermissionError, ValueError, json.JSONDecodeError) as error:
        print(f"scan failed: {error}", file=sys.stderr)
        return 2
    report = focus_report(report, thread_id=args.id, title=args.title)
    if not args.include_normal:
        report["normal"] = []
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if "query" in report:
            print("精确查询：", json.dumps(report["query"], ensure_ascii=False))
        print("正常：", report["normal_count"])
        print("疑似幽灵：", report["suspect_count"])
        print(json.dumps(report["suspected_ghosts"], ensure_ascii=False, indent=2))
        for error in report["errors"]:
            print("警告：" + error, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
