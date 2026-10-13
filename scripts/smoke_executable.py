"""Start a packaged app, exercise its browser lifecycle, and verify clean exit."""

from __future__ import annotations

import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import wave
import zipfile
from pathlib import Path

CREATE_NO_WINDOW = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def reserve_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_page(url: str, timeout: float = 45.0) -> bytes:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # nosec B310
                return bytes(response.read())
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    raise RuntimeError(f"The executable did not start within {timeout:.0f} seconds.")


def check_conversions(base_url: str) -> None:
    """Exercise bundled document and FFmpeg engines plus both download routes."""
    audio_data = io.BytesIO()
    with wave.open(audio_data, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 4000)
    boundary = uuid.uuid4().hex
    body = bytearray()
    for filename, content, target in (
        ("notes.txt", b"Packaged conversion works", "pdf"),
        ("tone.wav", audio_data.getvalue(), "mp3"),
    ):
        body.extend(
            f'--{boundary}\r\nContent-Disposition: form-data; name="files"; '
            f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
        )
        body.extend(content)
        body.extend(
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="targets"\r\n\r\n'
            f"{target}\r\n".encode()
        )
    body.extend(f"--{boundary}--\r\n".encode())
    conversion_request = urllib.request.Request(
        f"{base_url}/api/convert",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(conversion_request, timeout=60) as response:  # nosec B310
        payload = json.load(response)
    if payload["success_count"] != 2:
        raise RuntimeError(f"Packaged conversion failed: {payload['results']}")
    with urllib.request.urlopen(f"{base_url}{payload['download_all_url']}", timeout=15) as response:  # nosec B310
        archive_data = response.read()
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        if archive.testzip() is not None or archive.namelist() != ["notes.pdf", "tone.mp3"]:
            raise RuntimeError("Packaged batch archive was invalid.")
        if not archive.read("notes.pdf").startswith(b"%PDF"):
            raise RuntimeError("Packaged document conversion did not produce a PDF.")
        for result in payload["results"]:
            url = f"{base_url}/api/jobs/{payload['job_id']}/files/{result['file_id']}"
            with urllib.request.urlopen(url, timeout=15) as response:  # nosec B310
                if response.read() != archive.read(result["output_name"]):
                    raise RuntimeError("Individual download did not match the batch archive.")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: smoke_executable.py <path-to-executable>")
    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)

    port = reserve_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment["FILECONVERTERATHOME_NO_BROWSER"] = "1"
    environment["FILECONVERTERATHOME_PORT"] = str(port)
    process = subprocess.Popen(
        [str(executable)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=CREATE_NO_WINDOW,
    )
    try:
        page = wait_for_page(base_url)
        match = re.search(rb'name="fileconverterathome-session" content="([^"]+)"', page)
        if match is None:
            raise RuntimeError("The app page did not contain a browser session token.")
        token = match.group(1).decode("ascii")
        check_conversions(base_url)
        close_request = urllib.request.Request(
            f"{base_url}/api/browser/{token}/closed",
            method="POST",
        )
        with urllib.request.urlopen(close_request, timeout=5) as response:  # nosec B310
            if response.status != 204:
                raise RuntimeError(f"Unexpected close response: {response.status}")
        return_code = process.wait(timeout=15)
        if return_code != 0:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"The executable exited with {return_code}:\n{output}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    print(
        "Executable startup, conversions, downloads and browser-close shutdown smoke test passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
