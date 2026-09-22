# Changelog

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
