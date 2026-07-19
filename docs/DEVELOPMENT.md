# Development guide

## Prerequisites

- Python 3.11 or newer
- Node.js 22.13 or newer for ESLint
- Windows when building the `.exe`
- Optional LibreOffice for legacy Office conversions

Create a virtual environment and install all tools:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
npm ci
```

Run `python app.py` for a normal browser-opening session. Automation can set `FILECONVERTERATHOME_NO_BROWSER=1` and select an unused port with `FILECONVERTERATHOME_PORT`.

## Test and analysis suite

The `Quality` workflow separates concerns so branch protection can identify the failing layer:

| Check | Coverage |
|---|---|
| Ruff | Python correctness, imports, modernization, and common bug patterns |
| Ruff formatter | Deterministic Python formatting |
| mypy | Typed application, lifecycle, conversion, and build-support code |
| Bandit | Python security patterns |
| Vulture | High-confidence dead code |
| pip-audit | Published vulnerabilities in runtime dependencies |
| pytest + coverage | Behavior and branch coverage, including lifecycle routes |
| ESLint | Browser JavaScript correctness |
| CodeQL | Extended security and quality queries for Python and JavaScript |
| zizmor | GitHub Actions supply-chain and workflow security |
| Dependency review | Pull-request pip and npm advisory audits without requiring GitHub Advanced Security |

Tests run on Python 3.11, 3.12, and 3.13. The Windows job also builds the one-file executable and runs `scripts/smoke_executable.py`, which verifies startup, page rendering, the close endpoint, and a clean process exit.

## Building Windows releases

```powershell
.\build.ps1
```

The script installs declared development requirements, builds `dist/FileconverterAthome.exe`, runs the executable smoke test, and prints its SHA-256 digest. Use `-SkipInstall` in a prepared environment.

For a clean build on a machine with a large global Python environment, create an isolated environment and select it explicitly:

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
.\build.ps1 -SkipInstall -PythonExecutable .\.build-venv\Scripts\python.exe
```

Update both `package.json` and `packaging/windows-version-info.txt` when changing the release version. Release notes belong in `CHANGELOG.md`.

## Pull requests

Keep changes focused and include the relevant local check output. All review conversations should be resolved, required checks must pass, and the branch must be current with `main` before merge. Dependabot maintains pip, npm, and GitHub Actions dependencies weekly.
