from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import threading
import time

import httpx
import pytest


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(base_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base_url}/api/v1/health/live", timeout=0.5)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.05)

    raise AssertionError("Server did not become ready in time")


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM semantics are not reliable on Windows")
def test_sigterm_allows_in_flight_request_and_exits_cleanly() -> None:
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "test",
            "SHUTDOWN_TIMEOUT_MS": "2000",
        }
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.fixtures.graceful_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=".",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        _wait_for_server(base_url, timeout_seconds=10)

        result: dict[str, object] = {}

        def _send_slow_request() -> None:
            try:
                response = httpx.get(f"{base_url}/api/v1/test/slow?delay_ms=800", timeout=5)
                result["status_code"] = response.status_code
                result["body"] = response.json()
            except Exception as exc:
                result["error"] = exc

        request_thread = threading.Thread(target=_send_slow_request)
        request_thread.start()

        time.sleep(0.2)
        process.send_signal(signal.SIGTERM)

        request_thread.join(timeout=6)
        assert not request_thread.is_alive(), "In-flight request did not complete before timeout"
        assert "error" not in result, f"In-flight request failed: {result.get('error')}"
        assert result["status_code"] == 200

        return_code = process.wait(timeout=6)
        assert return_code == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
