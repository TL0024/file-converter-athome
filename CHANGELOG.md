# Changelog

## 1.2.1 - 2026-10-31

- Upgrade Pillow to 13.0 to satisfy the existing release dependency-security gate.

- Verify the application and Windows executable on Python 3.14.
- Add Python 3.14 to continuous tests and build Windows executables with it.
- Run CodeQL only for pull requests targeting main; retain merge-time analysis.

## 1.2.0 - 2026-10-14

- Added live per-file batch progress and result recovery when the upload response is interrupted.
- Locked batch controls during conversion and folder saves; empty files and oversized batches are rejected before upload.
- Serialized conversion batches to protect the document engine and return a clear busy response to other tabs.
- Protected in-flight downloads from cleanup and shutdown; concurrent ZIP requests share one atomically created archive.
- Removed source and failed output files promptly, reducing temporary disk usage.
- Preserved photo EXIF orientation, avoided decoding unused animation frames, and retained Word table order.
- Fixed Windows reserved and long filenames, common text encodings, Office timeouts and profile isolation, and scanned PDF error messages.
- Streamed folder saves and avoided overwriting existing filenames.
- Added local host and origin validation, bounded Lottie expansion, and disabled stale API and session caching.
- Consolidated pending Python, npm, and workflow updates, patched the vulnerable npm dependency, and kept CodeQL init and analyze versions aligned.
- Expanded Python, frontend, and packaged executable regression checks.

## 1.1.0 - 2026-07-20

- Renamed the application and its browser interface to FileconverterAthome.
- Renamed the Windows executable, build artifact, PyInstaller specification, icon asset, batch archive, and product metadata.
- Renamed application-specific environment variables and internal browser-session identifiers.
- Updated user, architecture, development, packaging, and release documentation for the new product identity.

## 1.0.0 - 2026-07-19

- Added the first packaged Windows release with a branded icon and version metadata.
- Added automatic process and command-window shutdown when the last browser page closes.
- Added a heartbeat fallback for browsers that terminate without sending a close event.
- Added Python 3.11-3.13 tests, branch coverage, Ruff, mypy, Bandit, Vulture, pip-audit, ESLint, CodeQL, dependency review, and GitHub Actions security analysis.
- Added reproducible PyInstaller packaging and an executable startup/shutdown smoke test.
- Updated Pillow to the secure 12.3 release line.
- Expanded user, architecture, development, security, and release documentation.
