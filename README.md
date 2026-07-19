# LocalConvert

LocalConvert is a private, batch-capable file converter that runs on your own computer. The browser sends files only to the Python service at `127.0.0.1`; it does not use a cloud API.

## Start it

On Windows, double-click `run.bat`. It installs the small Python dependency set when needed, starts the private local service, and opens your browser at:

```text
http://127.0.0.1:5174
```

You can also start it from PowerShell:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5174` in a browser.

## Conversion coverage

| Category | Inputs | Outputs |
|---|---|---|
| Documents | PDF | optimized PDF, Word (`.docx`), text |
| Documents | Word (`.docx`) | PDF, text, HTML |
| Documents | TXT, Markdown, HTML, RTF | PDF, Word, text |
| Images | PNG, JPG, WebP, BMP, TIFF, ICO | PNG, JPG, WebP, GIF, BMP, TIFF, ICO, PDF, MP4, WebM |
| Animation | GIF | GIF, animated WebP, PNG, JPG, BMP, TIFF, ICO, PDF, MP4, WebM |
| Animation | Telegram TGS / Lottie JSON | JSON / TGS |
| Video | MP4, WebM, MOV, MKV, AVI, M4V, MPEG, 3GP | all listed video containers, GIF, PNG, JPG, WebP, or extracted audio |
| Audio | MP3, WAV, OGG, FLAC, M4A, AAC, WMA, Opus | all listed audio formats |

Installing LibreOffice adds legacy `.doc`, `.odt`, `.xls`, `.xlsx`, `.ppt`, and `.pptx` input automatically. The app detects it at startup.

## Batch and filename behavior

- Add up to 50 files in one batch, including mixed file types.
- Use **Change all outputs** to update every compatible file at once; incompatible files keep their existing selection.
- Choose a separate compatible output format for every file.
- The original base name is kept; only the extension changes (for example, `Holiday Clip.mp4` becomes `Holiday Clip.webm`).
- If a batch contains duplicate base names targeting the same extension, later files receive ` (2)`, ` (3)`, and so on to prevent data loss.
- Download files individually or download all successful results as one ZIP.
- For batches, **Save separate files** chooses one destination folder in supported browsers; other browsers start the downloads one by one and may ask for each location.
- Temporary working files expire after two hours and can also be removed immediately with **New batch**.

Static images exported to MP4 or WebM use a three-second duration. Animated WebP and GIF retain their animation when exported to video. PNG, JPG, and WebP exports from video use the first frame.

## Notes on document fidelity

PDF-to-Word and Word-to-PDF are built-in, content-focused conversions. Text, headings, page breaks, and simple tables are retained, but complex columns, forms, floating images, and exact typography can shift. Legacy Microsoft Office formats use LibreOffice when it is installed.

TGS conversion preserves the Telegram animation as editable Lottie JSON. Visual TGS rendering is intentionally not claimed because it requires a separate Lottie renderer.

## Tests

```powershell
python -m pytest -q
```
