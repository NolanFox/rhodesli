# Discoveries Feature Audit — Session 71D Phase 1

## 1. Route & Code Path

- **Page route**: `@rt("/discoveries")` (app/main.py:23592) — full page with sidebar, admin-only
- **HTMX API**: `@rt("/api/discoveries")` (app/main.py:23709) — renders discovery cards
- **Reject API**: `@rt("/api/discovery/reject")` (app/main.py:23883) — adds negative_id
- **Core logic**: `_compute_discoveries()` (app/main.py:4814) — finds high-confidence matches
- **Cache**: `_discovery_cache` with key `(len(inbox), len(proposed), len(confirmed))`
- **Sidebar**: `nav_item("/discoveries", "✨", "Discoveries", count, "discoveries", "amber")` (line 3260)

## 2. How Discoveries Are Generated

`_compute_discoveries()` iterates all INBOX + PROPOSED identities and finds ONE best match per identity:
1. First checks proposals (cheap) — if best proposal target is CONFIRMED and distance < 1.0
2. Falls back to batch neighbor computation for identities without proposals
3. Returns `{source_id, source_name, target_id, target_name, distance, confidence}`
4. Sorted by distance ascending (best first)

**Key**: Returns one discovery per IDENTITY, not per face or per photo.

## 3. The Percentage Formula (LINE 23741)

```python
confidence_pct = max(0, min(100, int((1 - distance / 2.0) * 100)))
```

For distance 0.91: `(1 - 0.91/2.0) * 100 = (1 - 0.455) * 100 = 54.5%` → **54%**

**This is fundamentally misleading.** Distance 0.91 is HIGH confidence (tier boundary at 1.0), but 54% sounds uncertain. The system already has proper labels in `_CONFIDENCE_LABEL`:
- VERY HIGH (<0.80): "Strong match"
- HIGH (0.80-1.00): "Good match"
- MODERATE (1.00-1.20): "Possible match"
- LOW (>1.20): "Weak match"

These labels are NOT used on the discoveries page — only the misleading percentage.

## 4. Why Only Leon, Not Nace

- `DISCOVERY_DISTANCE_THRESHOLD = 1.0` (line 4811)
- Leon (Identity 768): distance 0.91 to Big Leon Capeluto → **0.91 < 1.0 → DISCOVERY**
- Nace (Identity 767): distance 1.01 to Nace Capeluto → **1.01 >= 1.0 → NOT a discovery**

The threshold excludes borderline HIGH matches. Nace at 1.01 is essentially the same confidence tier as Leon at 0.91 but fails the cutoff by 0.01.

## 5. Navigation Dead Ends

- **Source face image**: NOT clickable — just an `<img>` tag, no wrapper link
- **Source name**: Just a `<p>` tag, not linked to person page
- **Target name**: Links to `/person/{target_id}` ✓ (line 23820)
- **No photo link**: Can't navigate to the source photo
- **No co-occurrence context**: Doesn't show other faces in the same photo

## 6. Three-Section Routing

| Section | URL | Content | Filter |
|---------|-----|---------|--------|
| New Matches | `/?section=to_review` | INBOX + PROPOSED | Triage bar: ready/rediscovered/unmatched |
| Discoveries | `/discoveries` | High-confidence → CONFIRMED | None (separate page) |
| Help Identify | `/?section=skipped` | SKIPPED | Focus/browse modes |

**Overlap**: "Ready to Confirm" in New Matches triage bar ALSO shows high-confidence matches. The difference: Ready includes matches to ANY identity, Discoveries only to CONFIRMED identities.

## 7. Existing Tests

`tests/test_discoveries.py`: 15 tests covering:
- `_count_discoveries` (4 tests)
- `_compute_discoveries` (6 tests)
- Sidebar integration (4 tests)
- Route access control (2 tests)
- API card rendering (1 test)
- Reject endpoint (2 tests)
- Cache invalidation (3 tests)
- Threshold value assertion (1 test — checks == 1.0)
