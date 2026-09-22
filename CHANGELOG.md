# Changelog

## 1.1.0

- Added an in-app read-only Markdown reader for the bundled guides, replacing the
  external "open with the default app" behaviour. It renders headings, lists, code
  blocks and tables, offers outline navigation and in-document search, and never
  follows a link automatically: a network address is only copied to the clipboard.
- Localised Qt's own standard dialog buttons, so the Chinese interface shows
  "关闭 / 取消 / 确定" instead of "Close / Cancel / OK".
- File dialogs now remember the last used folder per category (audio, image,
  subtitle, output) and restore it on the next launch, falling back to the matching
  Windows user folder when the remembered path no longer exists. The last used
  filter is remembered as well.
- Imports that find nothing now explain why: unsupported extensions are listed with
  their counts next to the formats the page accepts, and missing files are named.
- Added a local task log under `%APPDATA%\MediaAnvilQt\logs`. It records the task
  type, input count, success count and failure reasons only — never file names,
  lyrics or media content — rotates at 1 MB keeping five files, and is never
  uploaded. Settings gained an "Open Log Folder" button.
- Message dialogs gained a "Copy Details" button so an error can be pasted into a
  bug report, and conversions now verify that the output folder is writable before
  the task starts.
- Clearer failure reporting: FFmpeg timeouts name the input file and the stalled
  stage, and moving or deleting the file being played now pauses playback with an
  explicit message.
- Interface polish: expanding the smart-matching area scrolls it into view, and
  switching pages returns to the top so navigation stays predictable.
- Changed the default window target from 1440 × 900 (16:10) to 1440 × 960 (3:2) and
  relaxed the screen-edge allowance from 90% to 95%, so that size is reachable on a
  1920 × 1080 desktop at 125% scaling. Numeric controls on the Settings page now
  share one aligned width.
- The release folder now ships `THIRD_PARTY_NOTICES.md` and `licenses/qt` next to
  the executable, and the build fails if any required document is missing.
- Fixed a shadowed loop variable in `tools/codex_ghost_scan.py` that printed a
  memory address instead of the sidebar field name in its error message.
- Widened the Ruff rule set to the full "F" (pyflakes) group and cleared the unused
  imports it found. Style rules stay off on purpose. The test suite grew from 186
  to 220 tests.

## 1.0.3

- Fixed Windows startup failure caused by an incompatible bundled ICU DLL.
- Strengthened the frozen-app smoke test so an error dialog can no longer be mistaken for a successful launch.

## 1.0.2

- Added cooperative cancellation for background work, including active FFmpeg processes.
- Added FFmpeg timeouts and reliable cleanup of incomplete output files.
- Improved recursive folder scanning by indexing each directory once.
- Added Windows reserved-name and invalid-filename protection.
- Removed settings that had no effect.
- Locked Python dependencies and added Ruff checks to CI.
