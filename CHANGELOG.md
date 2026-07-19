# Changelog

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
