from __future__ import annotations

import re

from app import app
from lifecycle import BrowserSessionManager


def test_last_closed_browser_session_requests_shutdown_after_grace_period():
    now = [10.0]
    shutdowns: list[str] = []
    manager = BrowserSessionManager(
        heartbeat_timeout=30.0,
        shutdown_grace=2.0,
        poll_interval=60.0,
        clock=lambda: now[0],
    )
    manager.start(lambda: shutdowns.append("shutdown"))
    try:
        first = manager.register()
        second = manager.register()
        assert manager.heartbeat(first)
        assert manager.close(first)

        now[0] = 11.0
        assert not manager.poll()
        assert manager.close(second)

        now[0] = 12.9
        assert not manager.poll()
        now[0] = 13.0
        assert manager.poll()
        assert shutdowns == ["shutdown"]
        assert not manager.poll()
    finally:
        manager.stop()


def test_browser_session_routes_accept_heartbeat_and_close():
    with app.test_client() as client:
        page = client.get("/")
        assert page.status_code == 200
        match = re.search(rb'name="localconvert-session" content="([^"]+)"', page.data)
        assert match is not None
        token = match.group(1).decode("ascii")

        assert client.post(f"/api/browser/{token}/heartbeat").status_code == 204
        assert client.post(f"/api/browser/{token}/closed").status_code == 204
        assert client.post(f"/api/browser/{token}/heartbeat").status_code == 404
