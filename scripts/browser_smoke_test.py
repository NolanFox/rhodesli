#!/usr/bin/env python3
"""Browser-level production verification using Playwright.

Usage:
    python scripts/browser_smoke_test.py [--url URL] [--screenshots DIR]

Runs headless Chromium tests against the target URL and saves screenshots.
"""

import argparse
import sys
import time
from pathlib import Path


def run_tests(base_url: str, screenshot_dir: Path):
    from playwright.sync_api import sync_playwright

    screenshot_dir.mkdir(parents=True, exist_ok=True)
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Test 1: Landing page
        t0 = time.time()
        page.goto(base_url, timeout=30000)
        page.wait_for_load_state("networkidle")
        elapsed = time.time() - t0
        photos = page.query_selector_all("img")
        title = page.title()
        page.screenshot(path=str(screenshot_dir / "landing.png"))
        results.append({
            "test": "Landing page",
            "status": "PASS" if len(photos) > 0 else "FAIL",
            "detail": f"{len(photos)} images, title='{title}'",
            "time": f"{elapsed:.1f}s",
        })

        # Test 2: Timeline
        t0 = time.time()
        page.goto(f"{base_url}/timeline", timeout=30000)
        page.wait_for_load_state("networkidle")
        elapsed = time.time() - t0
        photos_tl = page.query_selector_all("img")
        page.screenshot(path=str(screenshot_dir / "timeline.png"))
        results.append({
            "test": "Timeline",
            "status": "PASS" if len(photos_tl) > 0 else "FAIL",
            "detail": f"{len(photos_tl)} images",
            "time": f"{elapsed:.1f}s",
        })

        # Test 3: Compare page
        t0 = time.time()
        page.goto(f"{base_url}/compare", timeout=30000)
        page.wait_for_load_state("networkidle")
        elapsed = time.time() - t0
        upload_zone = page.query_selector('input[type="file"]')
        page.screenshot(path=str(screenshot_dir / "compare.png"))
        results.append({
            "test": "Compare page",
            "status": "PASS" if upload_zone else "FAIL",
            "detail": f"upload zone {'FOUND' if upload_zone else 'MISSING'}",
            "time": f"{elapsed:.1f}s",
        })

        # Test 4: Estimate page
        t0 = time.time()
        page.goto(f"{base_url}/estimate", timeout=30000)
        page.wait_for_load_state("networkidle")
        elapsed = time.time() - t0
        page.screenshot(path=str(screenshot_dir / "estimate.png"))
        results.append({
            "test": "Estimate page",
            "status": "PASS",
            "detail": f"title='{page.title()}'",
            "time": f"{elapsed:.1f}s",
        })

        # Test 5: People page
        t0 = time.time()
        page.goto(f"{base_url}/people", timeout=30000)
        page.wait_for_load_state("networkidle")
        elapsed = time.time() - t0
        page.screenshot(path=str(screenshot_dir / "people.png"))
        results.append({
            "test": "People page",
            "status": "PASS",
            "detail": f"title='{page.title()}'",
            "time": f"{elapsed:.1f}s",
        })

        # Test 6: Photos page
        t0 = time.time()
        page.goto(f"{base_url}/photos", timeout=30000)
        page.wait_for_load_state("networkidle")
        elapsed = time.time() - t0
        photos_pg = page.query_selector_all("img")
        page.screenshot(path=str(screenshot_dir / "photos.png"))
        results.append({
            "test": "Photos page",
            "status": "PASS" if len(photos_pg) > 0 else "FAIL",
            "detail": f"{len(photos_pg)} images",
            "time": f"{elapsed:.1f}s",
        })

        # Test 7: 404 handling
        t0 = time.time()
        resp = page.goto(
            f"{base_url}/person/nonexistent-id-12345", timeout=30000
        )
        elapsed = time.time() - t0
        status = resp.status if resp else 0
        page.screenshot(path=str(screenshot_dir / "404.png"))
        results.append({
            "test": "404 handling",
            "status": "PASS" if status == 404 else "FAIL",
            "detail": f"HTTP {status}",
            "time": f"{elapsed:.1f}s",
        })

        # Test 8: Health endpoint
        t0 = time.time()
        resp = page.goto(f"{base_url}/health", timeout=15000)
        elapsed = time.time() - t0
        status = resp.status if resp else 0
        content = page.content()
        has_ok = '"ok"' in content or "'ok'" in content
        results.append({
            "test": "Health endpoint",
            "status": "PASS" if status == 200 and has_ok else "FAIL",
            "detail": f"HTTP {status}, ok={'yes' if has_ok else 'no'}",
            "time": f"{elapsed:.1f}s",
        })

        browser.close()

    return results


def print_results(results, screenshot_dir):
    print("\n## Browser Smoke Test Results\n")
    print("| Test | Status | Detail | Time |")
    print("|------|--------|--------|------|")
    for r in results:
        status_icon = "PASS" if r["status"] == "PASS" else "**FAIL**"
        print(f"| {r['test']} | {status_icon} | {r['detail']} | {r['time']} |")

    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print(f"\n**{passed}/{total} passed**")
    print(f"\nScreenshots saved to: {screenshot_dir}/")

    return passed == total


def main():
    parser = argparse.ArgumentParser(description="Browser smoke test")
    parser.add_argument(
        "--url",
        default="https://rhodesli.nolanandrewfox.com",
        help="Base URL to test",
    )
    parser.add_argument(
        "--screenshots",
        default="docs/ux_audit/session_findings/screenshots",
        help="Directory for screenshots",
    )
    args = parser.parse_args()

    screenshot_dir = Path(args.screenshots)
    results = run_tests(args.url, screenshot_dir)
    all_passed = print_results(results, screenshot_dir)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
