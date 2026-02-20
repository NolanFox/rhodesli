#!/usr/bin/env python3
"""Production smoke test for Rhodesli.

Tests every critical path against a target URL. Returns non-zero if any
critical test fails. Results logged as a markdown table.

Usage:
    python scripts/production_smoke_test.py [--url URL] [--output PATH]

Defaults:
    --url: https://rhodesli.nolanandrewfox.com
    --output: stdout (use --output to save to file)
"""
import argparse
import sys
import time
from datetime import datetime, timezone


def _get_ssl_context():
    """Get an SSL context that works on macOS with Python venvs."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    # macOS: try system cert store
    ctx = ssl.create_default_context()
    return ctx


def fetch(url, timeout=30):
    """Fetch a URL and return (status_code, body, elapsed_seconds)."""
    import urllib.request
    import urllib.error

    start = time.time()
    try:
        ctx = _get_ssl_context()
        req = urllib.request.Request(url, headers={"User-Agent": "RhodesliSmokeTest/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body, time.time() - start
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body, time.time() - start
    except Exception as e:
        return 0, str(e), time.time() - start


def check_contains(body, *keywords):
    """Check if body contains all keywords. Returns list of missing ones."""
    return [k for k in keywords if k.lower() not in body.lower()]


def run_tests(base_url):
    """Run all smoke tests. Returns (results, failures)."""
    results = []
    failures = []

    tests = [
        {
            "name": "Health",
            "path": "/health",
            "expected_status": 200,
            "required_content": ["status", "ok"],
            "critical": True,
        },
        {
            "name": "Landing page",
            "path": "/",
            "expected_status": 200,
            "required_content": ["rhodesli", "rhodes"],
            "critical": True,
        },
        {
            "name": "Timeline",
            "path": "/photos",
            "expected_status": 200,
            "required_content": ["photo"],
            "critical": True,
        },
        {
            "name": "People",
            "path": "/people",
            "expected_status": 200,
            "required_content": ["people"],
            "critical": True,
        },
        {
            "name": "Compare page",
            "path": "/compare",
            "expected_status": 200,
            "required_content": ["compare", "upload"],
            "critical": True,
        },
        {
            "name": "Estimate page",
            "path": "/estimate",
            "expected_status": 200,
            "required_content": ["estimate"],
            "critical": True,
        },
        {
            "name": "Collections",
            "path": "/collections",
            "expected_status": 200,
            "required_content": ["collection"],
            "critical": False,
        },
        {
            "name": "Search API",
            "path": "/api/search?q=cohen",
            "expected_status": 200,
            "required_content": [],
            "critical": False,
        },
        {
            "name": "Invalid person 404",
            "path": "/person/nonexistent-id-12345",
            "expected_status": 404,
            "required_content": [],
            "critical": False,
        },
        {
            "name": "Invalid photo 404",
            "path": "/photo/nonexistent-id-12345",
            "expected_status": 404,
            "required_content": [],
            "critical": False,
        },
        {
            "name": "Login page",
            "path": "/login",
            "expected_status": 200,
            "required_content": ["sign", "log"],
            "critical": False,
        },
    ]

    for test in tests:
        url = f"{base_url.rstrip('/')}{test['path']}"
        status, body, elapsed = fetch(url)
        missing = check_contains(body, *test["required_content"])

        passed = (status == test["expected_status"] and not missing)
        result = {
            "name": test["name"],
            "path": test["path"],
            "status": status,
            "expected": test["expected_status"],
            "time": elapsed,
            "missing": missing,
            "passed": passed,
            "critical": test["critical"],
        }
        results.append(result)
        if not passed:
            failures.append(result)

    return results, failures


def format_results(results, failures, base_url):
    """Format results as markdown."""
    lines = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"# Production Smoke Test — {now}")
    lines.append(f"")
    lines.append(f"**Target:** {base_url}")
    lines.append(f"**Tests:** {len(results)} total, {len(results) - len(failures)} passed, {len(failures)} failed")
    lines.append(f"")
    lines.append("| Test | Path | Status | Expected | Time | Result |")
    lines.append("|------|------|--------|----------|------|--------|")

    for r in results:
        icon = "PASS" if r["passed"] else "FAIL"
        crit = " (CRITICAL)" if r["critical"] and not r["passed"] else ""
        extra = ""
        if r["missing"]:
            extra = f" missing: {', '.join(r['missing'])}"
        lines.append(
            f"| {r['name']} | `{r['path']}` | {r['status']} | {r['expected']} "
            f"| {r['time']:.2f}s | {icon}{crit}{extra} |"
        )

    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- **{f['name']}** (`{f['path']}`): got {f['status']}, "
                         f"expected {f['expected']}"
                         + (f", missing: {', '.join(f['missing'])}" if f["missing"] else ""))

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Rhodesli production smoke test")
    parser.add_argument("--url", default="https://rhodesli.nolanandrewfox.com",
                        help="Base URL to test (default: production)")
    parser.add_argument("--output", help="Save results to file (default: stdout)")
    args = parser.parse_args()

    print(f"Running smoke tests against {args.url}...")
    results, failures = run_tests(args.url)
    report = format_results(results, failures, args.url)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report + "\n")
        print(f"Results saved to {args.output}")
    else:
        print(report)

    critical_failures = [f for f in failures if f["critical"]]
    if critical_failures:
        print(f"\nFAILED: {len(critical_failures)} critical test(s) failed")
        return 1
    elif failures:
        print(f"\nWARNING: {len(failures)} non-critical test(s) failed")
        return 0
    else:
        print(f"\nAll {len(results)} tests passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
