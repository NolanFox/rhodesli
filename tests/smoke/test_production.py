#!/usr/bin/env python3
"""
Production smoke tests.
Run after every deploy: python tests/smoke/test_production.py

Checks that key features are actually visible on the live site.
Does NOT require auth or browser — just HTTP requests.
"""
import sys
import requests

PROD_URL = "https://rhodesli.nolanandrewfox.com"
TIMEOUT = 15

passed = 0
failed = 0
errors = []


def check(name, url, expected=None, unexpected=None, status=200):
    """Check that a page contains expected content."""
    global passed, failed
    expected = expected or []
    unexpected = unexpected or []
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != status:
            errors.append(f"{name}: expected status {status}, got {resp.status_code}")
            failed += 1
            print(f"  FAIL {name} (status {resp.status_code})")
            return False
        html = resp.text
        for s in expected:
            if s not in html:
                errors.append(f"{name}: missing '{s}' in response")
                failed += 1
                print(f"  FAIL {name} (missing '{s}')")
                return False
        for s in unexpected:
            if s in html:
                errors.append(f"{name}: unexpected '{s}' found in response")
                failed += 1
                print(f"  FAIL {name} (found unexpected '{s}')")
                return False
        passed += 1
        print(f"  PASS {name}")
        return True
    except requests.exceptions.RequestException as e:
        errors.append(f"{name}: {e}")
        failed += 1
        print(f"  FAIL {name} ({e})")
        return False


def main():
    print("Production Smoke Tests")
    print("=" * 50)
    print(f"Target: {PROD_URL}")
    print()

    # === Basic health ===
    print("--- Basic Health ---")
    check("Homepage loads", f"{PROD_URL}/", ["Rhodesli"])
    check("Login page loads", f"{PROD_URL}/login", ["Sign In"])

    # === Public pages ===
    print("\n--- Public Pages ---")
    check("Public /photos loads", f"{PROD_URL}/photos", ["Photos"])
    check("Public /people loads", f"{PROD_URL}/people", ["People"])

    # === Discovery Layer (v0.34.0) ===
    print("\n--- Discovery Layer ---")

    # Date badges on photo cards
    check("Date badges on /photos",
          f"{PROD_URL}/photos",
          ["c. 19", "data-testid=\"date-badge\""])

    # Decade pills
    check("Decade pills displayed",
          f"{PROD_URL}/photos",
          ["data-testid=\"decade-pill\""])

    # Search input
    check("Search input present",
          f"{PROD_URL}/photos",
          ["data-testid=\"photo-search\""])

    # Tag pills
    check("Tag pills displayed",
          f"{PROD_URL}/photos",
          ["data-testid=\"tag-pill\""])

    # Decade filtering returns results (not "No photos match")
    check("Decade filter works",
          f"{PROD_URL}/photos?decade=1920",
          ["data-testid=\"date-badge\""],
          ["No photos match your filters"])

    # Keyword search returns results
    check("Keyword search works",
          f"{PROD_URL}/photos?search_q=portrait",
          [],
          ["No photos match your filters"])

    # Tag filtering returns results
    check("Tag filter works",
          f"{PROD_URL}/photos?tag=group_photo",
          [],
          ["No photos match your filters"])

    # === Photo detail pages ===
    print("\n--- Photo Detail ---")

    # Known photo ID — check that public photo page renders
    check("Public photo page loads",
          f"{PROD_URL}/photo/a3d2695fe0804844",
          ["Rhodesli"])

    # AI Analysis section on public photo page
    check("AI Analysis on public photo page",
          f"{PROD_URL}/photo/a3d2695fe0804844",
          ["AI Analysis", "Estimated by AI"])

    # === Person pages ===
    print("\n--- Person Pages ---")
    check("Person page loads",
          f"{PROD_URL}/people",
          ["People"])

    # === Summary ===
    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        print("\nFailures:")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print("\nAll smoke tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
