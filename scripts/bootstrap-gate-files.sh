#!/usr/bin/env bash
# bootstrap-gate-files.sh — ML-6 (multimodel-sprint skill): create the session gate-file
# skeletons as the FIRST commit so the Stop hook (which requires assessment + log + audit
# files to exist AND clean git) stops fighting the background-agent model. Fill them at closeout.
#
# Usage: bash scripts/bootstrap-gate-files.sh <session-number>
# Idempotent: never overwrites an existing file.
set -euo pipefail

NN="${1:-}"
if [ -z "$NN" ]; then echo "usage: $0 <session-number>" >&2; exit 2; fi

REPO="$(git rev-parse --show-toplevel)"
DATE="$(date -u +%Y-%m-%d)"
mkdir -p "$REPO/docs/assessments" "$REPO/docs/session_logs" "$REPO/docs/session_context"

ASSESS="$REPO/docs/assessments/session-$NN-assessment.md"
LOG="$REPO/docs/session_logs/session-$NN-log.md"
AUDIT="$REPO/docs/session_context/session-$NN-codex-audit.md"

created=0
if [ ! -f "$ASSESS" ]; then
  cat > "$ASSESS" <<EOF
# Session $NN Assessment (IN PROGRESS)

**Date:** $DATE
**Status:** IN PROGRESS — live skeleton, finalized at closeout.

## Shipped
- [ ] TBD

## Deferred (user-gated, NOT executed)
- TBD

## Red Flags
- TBD

## AI Tool Usage
- TBD (MANDATORY section — every session, even "none used")

## Next Session Should Verify FIRST
- TBD
EOF
  created=$((created+1)); echo "created $ASSESS"
fi

if [ ! -f "$LOG" ]; then
  cat > "$LOG" <<EOF
# Session $NN Log

**Started:** $DATE

## Exclusion list (NEVER dispatch autonomously)
Production data mutation · schema/migration · paid-API spend over cap · global head/layout/nav ·
feature-flag flips · frozen files (core/neighbors.py, core/pfe.py, data/*).

## Phase Checklist
- [ ] Phase 0: Orient + baseline

## Verification Gate
- [ ] All phases re-checked against original prompt
EOF
  created=$((created+1)); echo "created $LOG"
fi

if [ ! -f "$AUDIT" ]; then
  cat > "$AUDIT" <<EOF
# Session $NN — Audit Log (IN PROGRESS)

**Auditor(s):** TBD | **Agent type:** Independent (fresh context) | **Date:** $DATE
**Status:** IN PROGRESS — appended per batch. Auditor is a HARD pre-push gate (multimodel-sprint ML-1);
the orchestrator never audits its own session's output.

## (batches appended at dispatch)
EOF
  created=$((created+1)); echo "created $AUDIT"
fi

echo "bootstrap-gate-files: $created file(s) created (existing files left untouched)."
