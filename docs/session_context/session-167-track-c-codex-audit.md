# Session 167 Track C — Codex Audit (Self-Service Archive / PRD-060)

**Auditor**: Codex CLI v0.142.4 (gpt-5.5, xhigh)
**Agent type**: Independent (fresh context)
**Scope**: `app/onboarding_routes.py` + `tests/test_onboarding_routes.py`
**Date**: 2026-06-30
**Raw transcript**: `session-167-track-c-codex-audit.raw.txt` (sibling file)

## Verdict
> No P0, one P1 fail-open write-path bug; fix before enabling `SELF_SERVICE_ARCHIVE_ENABLED`.

The actual write is behind a default-OFF flag, so none of these reached production.
All P0/P1 + the cheap P2/P3s were fixed in the same session before commit.

## Findings & disposition

| ID | Sev | Finding | Disposition |
|----|-----|---------|-------------|
| 1 | P1 | `_existing_communities()` failed open to `[]` → POST could bypass slug-dedup + per-user cap when `load_communities()` errors | **FIXED** — replaced with `_load_communities_or_none()`; POST now FAILS CLOSED (returns error, no write) when load returns None. +`test_post_fails_closed_when_community_load_fails`. |
| 2 | P2 | POST had no IP/session throttle (only per-user cap, which is bypassable when auth disabled) | **FIXED** — added `request` param + `check_rate_limit("create-archive:<ip>", 10/hr)` before write. +`test_post_ip_throttle_blocks_after_limit`. |
| 3 | P2 | Contact validation only checked for `@` → malformed/control-char emails into `admin_emails` (header-injection vector) | **FIXED** — strict `_EMAIL_RE` (no whitespace/CR/LF, dotted domain). +`test_post_rejects_malformed_contact` (incl. newline payload). |
| 4 | P2 | 303 trusted `created["slug"]` (not open-redirect since `/c/` is fixed, but could be unroutable) | **FIXED** — redirect uses locally-validated `slug` unless returned slug matches `_SLUG_RE`. |
| 5 | P3 | `_dedupe_slug()` random fallback didn't check existence | **FIXED** — re-rolls until absent. |
| 6 | P3 | Auth gate ran before feature flag → auth-on + flag-off showed sign-in, not coming-soon | **FIXED** — flag checked FIRST in GET+POST. +`test_get_flag_off_with_auth_shows_coming_soon_not_signin`. |
| 7 | P3 | No XSS-escaping regression for rejected name/description/contact | **FIXED** — `test_post_rejected_name_is_html_escaped` (FastHTML auto-escapes; asserts no raw `<script>`). |
| 8 | P3 | Create failure only tested for `None`, not raised exception; load-failure untested | **FIXED** — `test_post_create_exception_reforms_with_error` + fail-closed test. |
| 9 | P3 | Validation coverage gaps (description-too-long, newline email) | **FIXED** — `test_post_description_too_long_reforms_with_error` + parametrized malformed-contact. |

**Value assessment**: STRONG — finding #1 (fail-open write path) is a real
defense-in-depth bug that mocks/tests would not have surfaced; would likely have
bitten once the flag was enabled. The P2/P3 set materially hardened the input
surface. ~10 min total to apply.

**Would we have found this ourselves?** #1 and #3 (email header-injection): unlikely
without an adversarial pass. The rest: eventually.
