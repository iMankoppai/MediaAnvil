"""Extract one CHANGELOG section so a GitHub release carries real notes.

The release workflow used ``gh release create --generate-notes``, which builds
the body from commit subjects. Those are often terse, so releases shipped with
little more than an auto-generated changelog link. Using CHANGELOG.md keeps one
source of truth and fails the release when a version has no entry.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"


def section_for(tag: str, changelog: Path | None = None) -> str | None:
    """Return the CHANGELOG body for ``tag`` (``v1.1.0`` or ``1.1.0``)."""
    text = (changelog or CHANGELOG).read_text(encoding="utf8")
    version = tag.strip().lstrip("vV")
    heading = re.search(r"^##\s+" + re.escape(version) + r"\s*$", text, re.MULTILINE)
    if heading is None:
        return None
    rest = text[heading.end():]
    following = re.search(r"^##\s+", rest, re.MULTILINE)
    body = rest[: following.start()] if following else rest
    return body.strip() or None


def notes_for(tag: str, changelog: Path | None = None) -> str | None:
    """Return release notes for ``tag``, or ``None`` when it has no entry."""
    body = section_for(tag, changelog)
    if body is None:
        return None
    return f"## MediaAnvil Windows {tag.strip().lstrip('vV')}\n\n{body}\n"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: release_notes.py <tag> [output-file]", file=sys.stderr)
        return 2
    tag = argv[1]
    notes = notes_for(tag)
    if notes is None:
        print(f"CHANGELOG.md has no section for '{tag}'; refusing to publish empty notes", file=sys.stderr)
        return 1
    if len(argv) > 2:
        Path(argv[2]).write_text(notes, encoding="utf8")
        print(f"Wrote release notes for {tag} to {argv[2]}")
    else:
        print(notes, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
