# Session 54B Context — Verification, Testing Infrastructure, Harness Evolution

**Source:** Claude (Opus 4.6) conversation with Nolan, Feb 20 2026.
**Purpose:** Complete Session 54's unfinished verification work + establish automated testing.
**Breadcrumbs:** Follows Session 54 (architecture + quick fixes). Addresses gaps in 54's output.

---

## What Session 54 Left Incomplete

1. **buffalo_sc investigation was wrong** — Claude Code concluded "incompatible, different recognition backbone" but missed the hybrid approach (see research below)
2. **No real upload test was performed** — the exact "tests pass but production untested" pattern we're trying to break
3. **UX issue tracker coverage unverified** — no explicit "X/X covered" verification logged

---

## buffalo_sc Research (Critical Finding)

### Model Bundle Contents

**buffalo_l** (the current model):
- `det_10g.onnx` — SCRFD face detector, 10G FLOPs, ~17MB
- `w600k_r50.onnx` — ArcFace recognition, ResNet50 backbone, 174MB, 512-dim embeddings
- `1k3d68.onnx` — 3D landmarks (68 points)
- `2d106det.onnx` — 2D landmarks (106 points)
- `genderage.onnx` — Gender/age estimation

**buffalo_sc** (the lightweight model):
- `det_500m.onnx` — SCRFD face detector, 500M FLOPs (~20x lighter than det_10g)
- `w600k_mbf.onnx` — ArcFace recognition, MobileFaceNet backbone, ~16MB, 512-dim embeddings

### Why Claude Code's Conclusion Was Wrong

Claude Code said "buffalo_sc is incompatible, different recognition backbone, cannot switch without re-embedding all 550 faces." This is HALF right:

- **Correct:** `w600k_r50.onnx` (ResNet50) and `w600k_mbf.onnx` (MobileFaceNet) produce embeddings in different vector spaces. You cannot compare embeddings from one against the other. Both are 512-dim, both ArcFace, both WebFace600K trained, but different architectures = different embedding spaces.
- **Wrong conclusion:** Claude Code treated the buffalo bundles as monolithic. They're NOT. Detection and recognition are separate ONNX files loaded independently.

### The Hybrid Approach (What Should Have Been Done)

InsightFace's `FaceAnalysis` loads models by type, not as a bundle. You can:
1. Use `det_500m.onnx` from buffalo_sc for **detection** (20x less compute = ~3-5x faster)
2. Use `w600k_r50.onnx` from buffalo_l for **recognition** (keeps embedding compatibility)

This gives you:
- **Fast detection** — the bottleneck in compare (finding faces in the uploaded image)
- **Compatible embeddings** — same recognition model = same vector space as archive
- **No re-embedding needed** — archive embeddings stay valid

### How To Implement

```python
import insightface
from insightface.model_zoo import get_model

# Load fast detector from buffalo_sc
detector = get_model('path/to/det_500m.onnx')
detector.prepare(ctx_id=0, input_size=(640, 640))

# Load accurate recognizer from buffalo_l (same as archive)
recognizer = get_model('path/to/w600k_r50.onnx')
recognizer.prepare(ctx_id=0)

# OR: Use FaceAnalysis with allowed_modules to mix
# The key is ensuring the recognition model is w600k_r50, not w600k_mbf
```

Alternative: Use `insightface.model_zoo.get_model()` to load individual ONNX files directly, bypassing the bundle system entirely.

### Expected Performance Impact

| Configuration | Detection FLOPs | Estimated Compare Time (19-face photo, Railway CPU) |
|--------------|----------------|---------------------------------------------------|
| buffalo_l det_10g + 640px | 10G | ~15-25s (current after 640px fix) |
| buffalo_sc det_500m + 640px | 500M | ~3-8s (estimated) |
| buffalo_l det_10g + 1024px | 10G | ~40-65s (previous) |

### Decision: AD-114

This should be documented as AD-114: Hybrid Detection (buffalo_sc detector + buffalo_l recognizer).

---

## Automated Production Testing Research

### The Current Gap

Rhodesli has 2481 unit tests but zero automated production tests. Every production failure has been discovered manually. The "tests pass but production broken" pattern persists because:
- Unit tests validate data logic in isolation
- No tests verify the uploaded photo appears in the browser
- No tests verify the compare flow end-to-end
- No tests verify HTMX indicators actually display

### Playwright MCP — The Modern Solution

Playwright now ships as an MCP server that Claude Code can use directly. This means Claude Code can:
- Navigate to production URLs
- Upload files through the browser
- Take screenshots and verify visual output
- Click buttons and verify HTMX responses
- Run full end-to-end flows as a real user would

**Setup:**
```json
// .mcp.json in project root
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

**Key insight from research:** Playwright's specialized agents (planner, generator, healer) work as Claude Code subagents. The planner explores the app and produces test plans, the generator creates tests, and the healer auto-fixes broken tests.

### Production Smoke Test Script

Beyond Playwright MCP, we should have a Python-based smoke test that Claude Code runs after every deployment-touching session:

```python
# scripts/production_smoke_test.py
# Tests every critical path against the production URL
# Logs results to docs/ux_audit/SMOKE_TEST_LOG.md
# Can be run by Claude Code as part of session verification
```

### Harness Rule: Mandatory Production Verification

New rule for `.claude/rules/production-verification.md`:
- After any code change that affects UI or uploads: run production smoke test
- After any deployment: verify critical paths with real HTTP requests
- Compare endpoint: must be tested with an actual image upload
- Results logged to session log with timing data

---

## UX Issue Tracking Best Practices

### The Problem

The UX_ISSUE_TRACKER.md was created but Session 54 didn't verify complete coverage. Issues could have been missed.

### Nested File Structure (300-line limit compliance)

```
docs/ux_audit/
├── UX_ISSUE_TRACKER.md          # Master index (< 150 lines)
│   Links to session-specific files below
├── UX_AUDIT_README.md           # How to use the framework
├── PRODUCTION_SMOKE_TEST.md     # Session 53 smoke test results
├── UX_FINDINGS.md               # Session 53 findings
├── PROPOSALS.md                 # Prioritized proposals
├── FIX_LOG.md                   # Fixes applied, by session
├── REGRESSION_LOG.md            # Regressions found
└── session_findings/            # NEW: per-session detail
    ├── session_53_findings.md   # Detailed findings from 53
    ├── session_54_findings.md   # Detailed findings from 54
    └── session_54b_findings.md  # This session's findings
```

### The Tracker Pattern

UX_ISSUE_TRACKER.md stays lean (index only):
- ID, one-line description, status, session reference
- Breadcrumb to detail file: "See session_findings/session_54_findings.md#UX-003"
- Any file approaching 300 lines gets split

### Coverage Verification Rule

After creating or updating the tracker, Claude Code must:
1. `grep -c` every source file for issues
2. Cross-reference against tracker entries
3. Log "X/X covered" explicitly in session log
4. Any missing item = session incomplete

---

## Local ML Overnight Run Design

### Concept: `scripts/ml_pipeline.py`

A unified local ML script that runs the full pipeline:

```
Usage:
  python scripts/ml_pipeline.py --mode overnight   # Full pipeline, low priority
  python scripts/ml_pipeline.py --mode interactive  # Quick tasks only
  python scripts/ml_pipeline.py --mode validate     # Re-validate compare results against ground truth
```

### Overnight Mode

- Runs at low CPU priority (nice level)
- Checks if user is active (skip if screen not locked / load average high)
- Full pipeline: detect → embed → cluster → estimate → validate
- Validate compare results: re-run compare matches with buffalo_l and flag any where buffalo_sc detection produced different face crops
- Push results to R2 when complete
- Log everything to `docs/session_context/overnight_YYYY-MM-DD.md`

### Validation Loop

When compare runs on Railway with the hybrid detector (fast det_500m + accurate w600k_r50):
1. Save the detection bounding boxes alongside the comparison results
2. Overnight run re-detects with det_10g (higher quality detector)
3. If bounding boxes differ significantly → flag for review
4. If re-detection finds MORE faces → add them to compare results
5. This creates a quality feedback loop without blocking the interactive UX

---

## Files To Create/Update

- [ ] AD-114 in ALGORITHMIC_DECISIONS.md (hybrid detection approach)
- [ ] .claude/rules/production-verification.md (new rule)
- [ ] .mcp.json (Playwright MCP setup)
- [ ] scripts/production_smoke_test.py (automated production tests)
- [ ] docs/ux_audit/session_findings/ directory (nested structure)
- [ ] UX_ISSUE_TRACKER.md coverage verification
- [ ] BACKLOG.md: overnight ML pipeline item
- [ ] docs/session_context/session_54b_context.md (this file)
- [ ] docs/session_context/session_54b_prompt.md (the prompt)
- [ ] docs/session_context/session_54b_log.md (session log)
