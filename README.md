# FileconverterAthome

FileconverterAthome is a private, batch-capable file converter for Windows. It opens a browser interface, but conversion happens entirely in a Python service bound to `127.0.0.1`. Files are never sent to a cloud API.

[Download the latest Windows executable](https://github.com/TL0024/file-converter-athome/releases/latest/download/FileconverterAthome.exe)

## Use the Windows app

1. Download `FileconverterAthome.exe` from the latest GitHub release.
2. Run the executable. A command window opens, followed by FileconverterAthome in your default browser.
3. Add files, choose outputs, convert, and download the results.
4. Close the FileconverterAthome browser page when finished. The local service and its command window close automatically. If several FileconverterAthome tabs are open, the service stays alive until the last one closes.

The executable is not code-signed, so Windows SmartScreen may ask you to confirm that you trust it. Release assets include a SHA-256 checksum for independent verification.

## Run from source

Python 3.11 or newer is required.

```powershell
python -m pip install -r requirements.txt
python app.py
```

Alternatively, double-click `run.bat`; it installs missing runtime dependencies and starts the app. Both methods open `http://127.0.0.1:5174`.

## Conversion coverage

| Category | Inputs | Outputs |
|---|---|---|
| Documents | PDF | optimized PDF, Word (`.docx`), text |
| Documents | Word (`.docx`) | PDF, text, HTML |
| Documents | TXT, Markdown, HTML, RTF | PDF, Word, text |
| Images | PNG, JPG, WebP, BMP, TIFF, ICO | PNG, JPG, WebP, GIF, BMP, TIFF, ICO, PDF, MP4, WebM |
| Animation | GIF | GIF, animated WebP, images, PDF, MP4, WebM |
| Animation | Telegram TGS / Lottie JSON | JSON / TGS |
| Video | MP4, WebM, MOV, MKV, AVI, M4V, MPEG, 3GP | video containers, GIF, images, or extracted audio |
| Audio | MP3, WAV, OGG, FLAC, M4A, AAC, WMA, Opus | all listed audio formats |

FFmpeg is supplied by `imageio-ffmpeg` and is bundled into the Windows executable. Installing LibreOffice adds legacy `.doc`, `.odt`, `.xls`, `.xlsx`, `.ppt`, and `.pptx` input automatically.

## Batch and filename behavior

- Add up to 50 files in one mixed batch.
- Choose one compatible output per file or use **Change all outputs**.
- Keep the original base name; only the extension changes.
- Duplicate target names receive ` (2)`, ` (3)`, and so on instead of overwriting data.
- Download results individually, save separate files to a selected folder in supported browsers, or download a ZIP.
- Temporary working files expire after two hours and are removed when a batch is cleared or the app exits.

Static images exported to MP4 or WebM use a three-second duration. Animated WebP and GIF retain their animation when exported to video. Image exports from video use the first frame.

## Document fidelity

Built-in PDF and Word conversion is content-focused. Text, headings, page breaks, and simple tables are retained, but complex columns, forms, floating images, and exact typography can shift. Legacy Microsoft Office formats use LibreOffice when it is installed.

TGS conversion preserves the Telegram animation as editable Lottie JSON. It does not render the animation visually because that requires a separate Lottie renderer.

## Development and verification

Install the development tools and run the same checks used in CI:

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m mypy app.py converter.py lifecycle.py scripts
python -m bandit -q -c pyproject.toml -r app.py converter.py lifecycle.py scripts
python -m vulture
python -m pip_audit -r requirements.txt --progress-spinner=off
python -m pytest --cov --cov-report=term-missing
npm ci
npm run lint
```

Build and smoke-test the Windows executable with:

```powershell
.\build.ps1
```

More detail is available in [Architecture](docs/ARCHITECTURE.md), [Development](docs/DEVELOPMENT.md), [Security](SECURITY.md), and the [Changelog](CHANGELOG.md).
