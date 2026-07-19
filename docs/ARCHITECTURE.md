# Architecture

## Runtime model

LocalConvert is a desktop-style application built from a loopback-only web service and a browser UI.

```text
Browser page
  |  HTTP on 127.0.0.1 only
  v
Flask routes in app.py
  |-- browser lifecycle manager (lifecycle.py)
  |-- conversion manager (converter.py)
  |     |-- Pillow
  |     |-- PyMuPDF and python-docx
  |     |-- bundled FFmpeg
  |     `-- optional LibreOffice
  `-- per-job temporary directory
```

`app.py` owns request validation, job records, downloads, cleanup, and the local WSGI server. `converter.py` detects formats, validates conversion pairs, and calls the relevant local engine. `static/app.js` owns the batch UI and browser lifecycle signals.

## Browser-close shutdown

Each render of `/` creates an unguessable browser session token and embeds it in a page-only metadata element. JavaScript sends a heartbeat every five seconds and sends a `pagehide` beacon when the page closes or navigates away.

The server tracks every open LocalConvert page independently. When the last page closes, it waits 1.5 seconds before stopping; this prevents an ordinary page reload from killing the replacement page. If a browser is terminated so abruptly that no beacon is delivered, the heartbeat expires after 120 seconds. The manager then invokes Werkzeug's graceful shutdown callback, removes temporary jobs, and lets the process and command window exit normally.

The close and heartbeat endpoints require the per-page token. A different web origin cannot read that token because the browser's same-origin policy protects the page response.

## Conversion jobs

An upload creates a uniquely named directory under the operating system's temporary location. Source and output paths use generated UUIDs; user-provided names are used only for sanitized download names. A successful job remains available for individual or ZIP downloads until one of these events occurs:

- the user starts a new batch;
- the two-hour time-to-live expires; or
- the application exits.

The global job map is protected by a lock because the local WSGI server handles requests in multiple threads.

## Packaging

`FileConverterAtHome.spec` creates a one-file Windows console executable. It embeds:

- the Flask templates and static assets;
- the `imageio-ffmpeg` Windows binary;
- the icon under `assets/`; and
- Windows product and version metadata from `packaging/windows-version-info.txt`.

The console remains visible so startup or conversion errors are diagnosable. It exits when the browser lifecycle manager shuts down the server.
