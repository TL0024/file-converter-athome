"""Track browser pages and stop the local server when the last page closes."""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from threading import Event, Lock, Thread, current_thread


class BrowserSessionManager:
    """Manage browser heartbeats and trigger one graceful server shutdown."""

    def __init__(
        self,
        *,
        heartbeat_timeout: float = 120.0,
        shutdown_grace: float = 1.5,
        poll_interval: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._heartbeat_timeout = heartbeat_timeout
        self._shutdown_grace = shutdown_grace
        self._poll_interval = poll_interval
        self._clock = clock
        self._sessions: dict[str, float] = {}
        self._lock = Lock()
        self._halt_event = Event()
        self._wake_event = Event()
        self._monitor_thread: Thread | None = None
        self._shutdown_callback: Callable[[], None] | None = None
        self._empty_since: float | None = None
        self._has_connected = False
        self._shutdown_requested = False

    def register(self) -> str:
        """Register a newly loaded browser page and return its unguessable token."""
        token = secrets.token_urlsafe(32)
        now = self._clock()
        with self._lock:
            self._sessions[token] = now
            self._has_connected = True
            self._empty_since = None
        return token

    def heartbeat(self, token: str) -> bool:
        """Refresh an existing browser session."""
        now = self._clock()
        with self._lock:
            if token not in self._sessions:
                return False
            self._sessions[token] = now
        return True

    def close(self, token: str) -> bool:
        """Close a browser session and begin the short reload grace period."""
        now = self._clock()
        with self._lock:
            if self._sessions.pop(token, None) is None:
                return False
            if not self._sessions:
                self._empty_since = now
        self._wake_event.set()
        return True

    def start(self, shutdown_callback: Callable[[], None]) -> None:
        """Start the background monitor for abandoned or explicitly closed pages."""
        with self._lock:
            if self._monitor_thread is not None:
                raise RuntimeError("The browser session monitor is already running.")
            self._shutdown_callback = shutdown_callback
            self._halt_event.clear()
            self._wake_event.clear()
            self._monitor_thread = Thread(
                target=self._monitor,
                name="browser-session-monitor",
                daemon=True,
            )
            monitor_thread = self._monitor_thread
        monitor_thread.start()

    def stop(self) -> None:
        """Stop the monitor without requesting server shutdown."""
        self._halt_event.set()
        self._wake_event.set()
        with self._lock:
            monitor_thread = self._monitor_thread
        if monitor_thread and monitor_thread is not current_thread():
            monitor_thread.join(timeout=max(1.0, self._poll_interval * 2))

    def poll(self) -> bool:
        """Expire stale sessions and request shutdown when no page remains."""
        callback: Callable[[], None] | None = None
        now = self._clock()
        with self._lock:
            expired = [
                token
                for token, last_seen in self._sessions.items()
                if now - last_seen >= self._heartbeat_timeout
            ]
            for token in expired:
                self._sessions.pop(token, None)
            if expired and not self._sessions and self._empty_since is None:
                self._empty_since = now

            ready = (
                self._has_connected
                and not self._sessions
                and self._empty_since is not None
                and now - self._empty_since >= self._shutdown_grace
            )
            if ready and not self._shutdown_requested:
                self._shutdown_requested = True
                callback = self._shutdown_callback

        if callback is not None:
            callback()
            return True
        return False

    def _monitor(self) -> None:
        while not self._halt_event.is_set():
            self._wake_event.wait(self._poll_interval)
            self._wake_event.clear()
            if self._halt_event.is_set():
                return
            if self.poll():
                return
