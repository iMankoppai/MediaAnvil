import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("codex_ghost_scan", Path(__file__).parents[1] / "tools" / "codex_ghost_scan.py")
scanner = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = scanner
SPEC.loader.exec_module(scanner)

ORPHAN = "11111111-1111-1111-1111-111111111111"
GOOD = "22222222-2222-2222-2222-222222222222"
REMOTE = "33333333-3333-3333-3333-333333333333"


class ScannerTests(unittest.TestCase):
    def home(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        home = Path(temp.name) / ".codex"
        home.mkdir()
        (home / ".codex-global-state.json").write_text(json.dumps({"pinned-thread-ids": [ORPHAN], "projectless-thread-ids": [GOOD, REMOTE]}), encoding="utf-8")
        (home / "session_index.jsonl").write_text(json.dumps({"id": ORPHAN, "thread_name": "stale"}) + "\n" + json.dumps({"id": GOOD, "thread_name": "good"}) + "\n", encoding="utf-8")
        folder = home / "sessions" / "2026" / "09" / "05"
        folder.mkdir(parents=True)
        rollout = folder / f"rollout-2026-09-05T00-00-00-{GOOD}.jsonl"
        rollout.write_text("{}\n", encoding="utf-8")
        db = sqlite3.connect(home / "state_5.sqlite")
        db.execute("create table threads (id text,title text,rollout_path text,archived integer,source text,thread_source text)")
        db.execute("insert into threads values (?,?,?,?,?,?)", (GOOD, "good", str(rollout), 0, "vscode", "user"))
        db.commit(); db.close()
        history = sqlite3.connect(home / "thread_history_1.sqlite")
        history.execute("create table thread_turns (thread_id text)")
        history.execute("insert into thread_turns values (?)", (GOOD,))
        history.commit(); history.close()
        return home

    def test_stale_index_and_remote_only_are_distinguished(self):
        report = scanner.scan(self.home())
        rows = {row["id"]: row for row in report["suspected_ghosts"]}
        self.assertEqual(rows[ORPHAN]["confidence"], "high")
        self.assertEqual(rows[REMOTE]["confidence"], "inconclusive")
        self.assertEqual(report["normal_count"], 1)

    def test_writer_lock_forces_inconclusive(self):
        home = self.home()
        locks = home / "thread-writer-locks"
        locks.mkdir(); (locks / f"{ORPHAN}.lock").write_text("")
        rows = {row["id"]: row for row in scanner.scan(home)["suspected_ghosts"]}
        self.assertEqual(rows[ORPHAN]["confidence"], "inconclusive")

    def test_title_query_requires_exactly_one_match(self):
        home = self.home()
        with (home / "session_index.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"id": REMOTE, "thread_name": "stale"}) + "\n")
        focused = scanner.focus_report(scanner.scan(home), title="stale")
        self.assertTrue(focused["query"]["ambiguous"])
        self.assertEqual(focused["query"]["matches"], 2)

    def test_id_query_returns_one_exact_record(self):
        focused = scanner.focus_report(scanner.scan(self.home()), thread_id=ORPHAN.upper())
        self.assertFalse(focused["query"]["ambiguous"])
        self.assertEqual(focused["query"]["matches"], 1)
