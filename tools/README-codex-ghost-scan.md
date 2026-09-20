# codex-ghost-scan

`codex_ghost_scan.py` only reads local Codex data. It contains no delete,
archive, backup, repair, or other write operation.

Run it with an explicit home path:

```powershell
python .\tools\codex_ghost_scan.py --codex-home 'C:\Users\ABC\.codex'
```

For machine-readable output:

```powershell
python .\tools\codex_ghost_scan.py --codex-home 'C:\Users\ABC\.codex' --json --include-normal
```

To diagnose one sidebar entry, prefer its exact ID:

```powershell
python .\tools\codex_ghost_scan.py --codex-home 'C:\Users\ABC\.codex' --id '00000000-0000-0000-0000-000000000000' --json --include-normal
```

`--title` is exact (not a partial match). A title with zero or multiple matches
is reported as `ambiguous` and remains non-actionable.

`high` means local indexes or active state point to no available local body.
`inconclusive` deliberately includes IDs with no local artifacts, because they
may be valid cloud-only conversations and must never be deleted from an
offline-only finding.
