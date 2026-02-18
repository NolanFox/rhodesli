# Feature Matrix: Testing + Docs + Roles + Vision

For navigation see [docs/BACKLOG.md](../BACKLOG.md). For bugs/frontend see FEATURE_MATRIX_FRONTEND.md.

---

## 7. TESTING & QUALITY

### 7.1 Current Test Coverage

2342 tests passing (v0.48.0) across ~30+ test files including:
- `tests/test_auth.py` — auth flow tests
- `tests/test_permissions.py` — permission matrix tests
- `tests/test_ui_elements.py` — UI content tests
- `tests/test_photo_context.py` — photo display tests
- `tests/test_regression.py` — regression guards
- `tests/test_lightbox.py` — 16 lightbox regression tests (BUG-001)
- `tests/test_merge_direction.py` — 18 merge direction tests (BUG-003)
- `tests/test_face_count.py` — face count accuracy tests (BUG-002, BUG-005)
- `tests/test_skipped_faces.py` — 9 skipped face tests
- `tests/test_sync_api.py` — 12 sync API permission matrix tests
- `tests/e2e/` — Playwright E2E tests (19 critical path tests)

### 7.2 Testing Improvements (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| QA-001 | Lightbox regression tests | DONE | 16 tests (2026-02-08) |
| QA-002 | Merge direction tests | DONE | 18 tests (2026-02-08) |
| QA-003 | Face count accuracy tests | DONE | Count matches visible boxes (2026-02-08) |
| QA-004 | End-to-end browser tests | DONE | Playwright + Chromium, 19 tests (2026-02-08) |
| QA-005 | Mobile viewport tests | OPEN | Test at 375px, 414px, 768px widths. |
| QA-006 | Claude Code UX walkthrough | OPEN | Simulate user workflows, identify friction. |
| QA-007 | Performance benchmarking | OPEN | Automated page load measurements + thresholds. |

### 7.3 Meta: Reducing Bug Recurrence (PROCESS)

Recurring bugs (lightbox arrows 3x, multi-merge 3x, collection stats 3x). Root causes:

1. **Tests are server-side only** — HTTP responses pass but browser behavior (HTMX swaps, JS handlers, CSS) can be broken.
2. **HTMX lifecycle is tricky** — elements break after swaps because JS event handlers aren't re-bound.
3. **No visual regression testing** — CSS changes and responsive behavior untestable server-side.

**Mitigations**:
- Playwright E2E tests for critical workflows
- Consistent use of `htmx:afterSwap` for JS re-initialization
- Smoke test script (headless browser + screenshots)
- Bug fix requires: (a) reproduction test, (b) fix, (c) test passes, (d) manual verification

---

## 8. DOCUMENTATION & HARNESS

### 8.1 Internal Documentation (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| DOC-001 | CLAUDE.md audit | OPEN | Keep short, prune regularly. |
| DOC-002 | Path-scoped rules review | DONE | `.claude/rules/` for ML, data, deployment, planning |
| DOC-003 | ALGORITHMIC_DECISIONS.md | PARTIAL | AD-001 through AD-096. Needs entries for temporal priors, detection threshold. |
| DOC-004 | OPS_DECISIONS.md | DONE | OD-001 through OD-005 |
| DOC-005 | Auto-update documentation rule | DONE | Dual-update rule for ROADMAP + BACKLOG + CHANGELOG (2026-02-10) |
| DOC-006 | Living lessons.md | DONE | 71+ lessons across 6 topic files |

### 8.2 User-Facing Documentation (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| DOC-010 | In-app help / FAQ | OPEN | "How do I identify someone?", "What does Skip mean?" |
| DOC-011 | About page | OPEN | Rhodesli community history, how to contribute. |
| DOC-012 | Admin guide | OPEN | Process uploads, run ML, review matches. |
| DOC-013 | Contributor onboarding | OPEN | Sign up, browse, help identify, upload instructions. |

### 8.3 Harness Engineering Best Practices

- **CLAUDE.md should be concise** — ~150-200 instruction limit. Keep only universal rules.
- **@imports** for detailed docs: `See @docs/ml/ALGORITHMIC_DECISIONS.md`
- **Path-scoped rules** load domain context only when relevant — zero token cost otherwise
- **Subagents for parallel work** — up to 10 parallel, each with own context window
- **Hooks for quality gates** — run linter/formatter/tests automatically after changes
- **Commit after every phase** — non-negotiable for overnight/unattended sessions

---

## 9. USER ROLES & COLLABORATION

### 9.1 Permission Model Evolution (MEDIUM-LONG TERM)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| ROLE-001 | Public=view, Admin=all | DONE | Locked down |
| ROLE-002 | Contributor role | DONE | User.role field, CONTRIBUTOR_EMAILS, _check_contributor() (2026-02-10) |
| ROLE-003 | Trusted contributor | DONE | Auto-promotes after 5+ approved annotations (2026-02-10) |
| ROLE-004 | Family member self-identification | OPEN | "That's me!" button on face cards. Special trust level. |
| ROLE-005 | Activity feed | DONE | /activity with action log (2026-02-10) |
| ROLE-006 | Email notifications | OPEN | "Someone identified a face", "New photos added." |
| ROLE-007 | Contributor merge suggestions | DONE | Role-aware buttons, suggest-merge endpoint (2026-02-10) |

---

## 10. LONG-TERM VISION

### 10.1 Generalization (IF TRACTION)

| ID | Item | Notes |
|----|------|-------|
| GEN-001 | Multi-tenant architecture | Per-community isolation |
| GEN-002 | Self-service community creation | "Start your own heritage archive" |
| GEN-003 | Cross-community discovery | "Someone in another archive might be related" |
| GEN-004 | White-label / embedding | Organizations embed identification UI |

### 10.2 AI Enhancements

| ID | Item | Notes |
|----|------|-------|
| AI-001 | Auto-caption generation | Vision models describe photo content |
| AI-002 | Photo era estimation | IN PROGRESS — CORAL + Gemini pipeline built, UX integrated |
| AI-003 | Photo restoration | AI cleanup of damaged/faded photos |
| AI-004 | Handwriting recognition | Text on photo backs (common in old archives) |
| AI-005 | Story generation | Biographical narrative from photo sets |

### 10.3 Social & Geographic Intelligence

| ID | Item | Notes |
|----|------|-------|
| SOC-001 | Photo co-occurrence graph | DONE | 21 edges from 20 photos (2026-02-15) |
| SOC-002 | "Six degrees" connection finder | DONE | BFS + D3.js at /connect (2026-02-16) |
| SOC-003 | Proximity scoring | DONE | (1/path_length)*avg_edge_weight (2026-02-16) |
| GEO-001 | Geographic migration analysis | DONE | 267/271 photos geocoded (2026-02-16) |
| GEO-002 | Map view with photo markers | DONE | Leaflet.js at /map (2026-02-16) |
| GEO-003 | Community-specific context events | Montgomery, Atlanta, Asheville, Havana, Buenos Aires, Congo |
| KIN-001 | Kinship recalibration post-GEDCOM | Compute true parent/child/sibling distributions |
| UX-001 | Timeline navigation scrubber | Google Photos-style year scrubber |
| UX-002 | Life events tagging | Tag photos with events connecting people, places, dates |

---

## Appendix: Key Files & References

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Claude Code harness (with dual-update rules) |
| `.claude/rules/*.md` | Path-scoped rules (ML, data, deployment, planning) |
| `docs/ml/ALGORITHMIC_DECISIONS.md` | AD-001 through AD-096 |
| `docs/ml/MODEL_INVENTORY.md` | Current model stack |
| `docs/ops/OPS_DECISIONS.md` | OD-001 through OD-005 |
| `tasks/todo.md` | Session-level task tracking |
| `tasks/lessons.md` | 71+ accumulated lessons |
| `data/identities.json` | Identity data (Railway volume) |
| `data/photo_index.json` | Photo metadata |
| `data/embeddings.npy` | Face embeddings (~550 faces) |
| `rhodesli_ml/` | ML pipeline package |

## Appendix: Lessons That Should Inform Future Work

1. Every UX bug found in manual testing is a missing automated test.
2. Permission regressions are the most dangerous bugs — test route x auth-state matrix.
3. HTMX endpoints behave differently than browser requests (401 vs 303). Test both.
4. Algorithmic decisions need structured logs separate from operational lessons.
5. Never average embeddings (AD-001) — heritage archives span decades; centroids create ghost vectors.
6. Default to admin-only for new data-modifying features.
7. Path-scoped rules are free when not triggered. Use them liberally.
8. Commit after every phase — non-negotiable for overnight sessions.
9. JSON won't scale. Plan the Postgres migration before 500 photos.
10. Family resemblance is the hardest problem. Relative-distance scoring > absolute thresholds.
