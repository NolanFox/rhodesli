"""E2E test fixtures: starts a real FastHTML server for Playwright to test against."""

import os
import socket
import subprocess
import sys
import time

import pytest
import requests


def _find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(url: str, timeout: float = 15) -> None:
    """Poll a URL until it responds or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(0.3)
    raise TimeoutError(f"Server at {url} did not start within {timeout}s")


@pytest.fixture(scope="session")
def app_server():
    """Start the FastHTML app on a random port, yield its base URL, then tear down.

    The server runs as a subprocess with auth disabled so that all routes
    are accessible without mocking Supabase.
    """
    port = _find_free_port()
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    env = {
        **os.environ,
        "PORT": str(port),
        "HOST": "127.0.0.1",
        "DEBUG": "false",  # no reload in tests
        # Auth disabled — no Supabase env vars set, so is_auth_enabled() returns False
        "STORAGE_MODE": "local",
    }
    # Remove any existing auth env vars so auth is truly disabled
    env.pop("SUPABASE_URL", None)
    env.pop("SUPABASE_ANON_KEY", None)

    proc = subprocess.Popen(
        [sys.executable, "app/main.py"],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base_url, timeout=15)
    except TimeoutError:
        proc.terminate()
        proc.wait(timeout=5)
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        stdout = proc.stdout.read().decode() if proc.stdout else ""
        raise RuntimeError(
            f"App server failed to start on port {port}.\n"
            f"STDOUT:\n{stdout[-2000:]}\n"
            f"STDERR:\n{stderr[-2000:]}"
        )

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture(scope="session")
def browser_context_args():
    """Override default Playwright browser context args."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(autouse=True)
def _block_heavy_resources(page):
    """Block images, fonts, and external CDN scripts to prevent TCP pool exhaustion.

    The single-threaded uvicorn server can't handle 124 concurrent image requests
    per page load across 19 tests. We block heavy resources so tests focus on
    DOM structure and interactivity, not asset loading.
    """
    page.route(
        "**/*.{jpg,jpeg,png,gif,webp,svg,woff,woff2,ttf,eot}",
        lambda route: route.abort(),
    )
    # Block external CDN scripts (Tailwind JIT, etc.) that keep connections alive
    page.route("https://cdn.tailwindcss.com/**", lambda route: route.abort())
    yield
