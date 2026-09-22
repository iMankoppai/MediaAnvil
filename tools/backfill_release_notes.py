"""Push the CHANGELOG body of each given tag onto its GitHub release.

Used once to backfill the 1.0.x releases, whose bodies only held an
auto-generated "Full Changelog" link. Reads the token from git's credential
helper so no secret is written to disk or passed on the command line.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.release_notes import notes_for  # noqa: E402

REPO = "iMankoppai/MediaAnvil"


def token() -> str:
    completed = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, check=True,
    )
    for line in completed.stdout.splitlines():
        if line.startswith("password="):
            return line[len("password="):]
    raise SystemExit("no GitHub credential available")


def gh(args: list[str], token_value: str) -> subprocess.CompletedProcess:
    # Inherit the full environment: a minimal one drops SystemRoot, which gh
    # needs on Windows for TLS, and it then fails to reach api.github.com.
    environment = os.environ.copy()
    environment["GH_TOKEN"] = token_value
    return subprocess.run(["gh", *args], capture_output=True, text=True, env=environment)


def main(tags: list[str]) -> int:
    token_value = token()
    failures = 0
    for tag in tags:
        notes = notes_for(tag)
        if notes is None:
            print(f"SKIP {tag}: no CHANGELOG section")
            failures += 1
            continue
        notes_path = Path(f"release-notes-{tag}.md")
        notes_path.write_text(notes, encoding="utf8")
        try:
            result = gh(["release", "edit", tag, "--repo", REPO, "--notes-file", str(notes_path)], token_value)
            if result.returncode != 0:
                print(f"FAIL {tag}: {result.stderr.strip()}")
                failures += 1
            else:
                print(f"OK   {tag}: notes updated ({len(notes)} chars)")
        finally:
            notes_path.unlink(missing_ok=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
