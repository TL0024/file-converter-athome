"""Start a packaged app, exercise its browser lifecycle, and verify clean exit."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


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


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: smoke_executable.py <path-to-executable>")
    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)

    port = reserve_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment["LOCALCONVERT_NO_BROWSER"] = "1"
    environment["LOCALCONVERT_PORT"] = str(port)
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        [str(executable)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creation_flags,
    )
    try:
        page = wait_for_page(base_url)
        match = re.search(rb'name="localconvert-session" content="([^"]+)"', page)
        if match is None:
            raise RuntimeError("The app page did not contain a browser session token.")
        token = match.group(1).decode("ascii")
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
    print("Executable startup and browser-close shutdown smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
