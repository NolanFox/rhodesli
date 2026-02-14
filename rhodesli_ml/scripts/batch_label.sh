#!/bin/bash
# Batch labeling wrapper for generate_date_labels.py
# For unattended overnight runs of large photo batches.
#
# Usage:
#   ./rhodesli_ml/scripts/batch_label.sh                          # Default: 50 photos, gemini-3-flash
#   ./rhodesli_ml/scripts/batch_label.sh --model gemini-3-pro-preview --max-cost 20.00
#   ./rhodesli_ml/scripts/batch_label.sh --batch-size 25 --max-cost 5.00
#
# For the next batch of 100 photos, use generate_date_labels.py directly
# to assess if 503 issues were a one-off. This script is insurance for 500+ photos.

set -euo pipefail

# ─── Defaults ───────────────────────────────────────────────────────────────────

MODEL="gemini-3-flash-preview"
MAX_COST="10.00"
BATCH_SIZE=50
INTER_BATCH_SLEEP=60
INTER_REQUEST_SLEEP_MULTIPLIER=1

# ─── Parse Arguments ────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case $1 in
        --model)
            MODEL="$2"
            shift 2
            ;;
        --max-cost)
            MAX_COST="$2"
            shift 2
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--model MODEL] [--max-cost DOLLARS] [--batch-size N]"
            echo ""
            echo "Options:"
            echo "  --model       Gemini model (default: gemini-3-flash-preview)"
            echo "  --max-cost    Max total cost in USD (default: 10.00)"
            echo "  --batch-size  Photos per batch (default: 50)"
            echo ""
            echo "Runs generate_date_labels.py in batches with rate-limit backoff."
            echo "Safe to Ctrl+C — incremental saves protect data every 5 photos."
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1"
            echo "Run with --help for usage."
            exit 1
            ;;
    esac
done

# ─── Setup ──────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/rhodesli_ml/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M)
LOG_FILE="$LOG_DIR/batch_${TIMESTAMP}.log"

mkdir -p "$LOG_DIR"

# Counters
TOTAL_LABELED=0
TOTAL_ERRORS=0
TOTAL_ATTEMPTED=0
BATCH_NUMBER=0
RATE_LIMIT_ADJUSTMENTS=0
CONSECUTIVE_FAILURES=0
FAILED_PHOTOS=""
START_TIME=$(date +%s)

# Cost tracking
COST_PER_PHOTO="0.010"
if [[ "$MODEL" == "gemini-3-pro-preview" ]]; then
    COST_PER_PHOTO="0.037"
elif [[ "$MODEL" == "gemini-2.5-flash" ]]; then
    COST_PER_PHOTO="0.008"
fi

# ─── Functions ──────────────────────────────────────────────────────────────────

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

parse_batch_output() {
    # Parse the output from generate_date_labels.py for labeled/error counts.
    # Expects the final "Results:" line: "Results: N labeled, M errors, T total labels"
    local output="$1"
    local labeled=0
    local errors=0

    # Extract from the "Results:" summary line
    local results_line
    results_line=$(echo "$output" | grep -E "^Results:" | tail -1 || true)
    if [[ -n "$results_line" ]]; then
        labeled=$(echo "$results_line" | grep -oE '[0-9]+ labeled' | grep -oE '[0-9]+' || echo "0")
        errors=$(echo "$results_line" | grep -oE '[0-9]+ errors' | grep -oE '[0-9]+' || echo "0")
    fi

    echo "$labeled $errors"
}

check_failure_rate() {
    # Returns 0 (true) if failure rate is >50%, 1 (false) otherwise.
    local labeled=$1
    local errors=$2
    local total=$((labeled + errors))

    if [[ $total -eq 0 ]]; then
        return 1  # No data, not a failure
    fi

    # >50% failure rate
    if [[ $errors -gt 0 ]] && (( errors * 2 > total )); then
        return 0  # High failure rate
    fi

    return 1  # Acceptable failure rate
}

print_summary() {
    local end_time
    end_time=$(date +%s)
    local elapsed=$((end_time - START_TIME))
    local hours=$((elapsed / 3600))
    local minutes=$(( (elapsed % 3600) / 60 ))
    local seconds=$((elapsed % 60))

    local estimated_cost
    estimated_cost=$(echo "$TOTAL_LABELED * $COST_PER_PHOTO" | bc -l 2>/dev/null || echo "unknown")

    log ""
    log "================================================================"
    log "                    BATCH LABELING COMPLETE"
    log "================================================================"
    log "Total labeled:            $TOTAL_LABELED"
    log "Total attempted:          $TOTAL_ATTEMPTED"
    log "Total errors:             $TOTAL_ERRORS"
    if [[ "$estimated_cost" != "unknown" ]]; then
        log "Estimated cost:           \$$(printf '%.2f' "$estimated_cost")"
    else
        log "Estimated cost:           ~\$$(echo "$TOTAL_LABELED * ${COST_PER_PHOTO}" | awk '{printf "%.2f", $1 * $3}')"
    fi
    log "Time elapsed:             ${hours}h ${minutes}m ${seconds}s"
    log "Batches run:              $BATCH_NUMBER"
    log "Rate-limit adjustments:   $RATE_LIMIT_ADJUSTMENTS"
    log "Model:                    $MODEL"
    log "Batch size:               $BATCH_SIZE"

    if [[ -n "$FAILED_PHOTOS" ]]; then
        log ""
        log "Photos that failed all retries:"
        echo "$FAILED_PHOTOS" | while IFS= read -r line; do
            if [[ -n "$line" ]]; then
                log "  - $line"
            fi
        done
    else
        log ""
        log "No photos failed all retries."
    fi

    log "================================================================"
    log "Log file: $LOG_FILE"
}

# ─── Trap for clean exit ────────────────────────────────────────────────────────

cleanup() {
    log ""
    log "Interrupted! Printing summary of work completed so far..."
    print_summary
    exit 130
}

trap cleanup INT TERM

# ─── Main Loop ──────────────────────────────────────────────────────────────────

log "Starting batch labeling"
log "  Model:       $MODEL"
log "  Max cost:    \$$MAX_COST"
log "  Batch size:  $BATCH_SIZE"
log "  Log file:    $LOG_FILE"
log ""

# Calculate max batches from cost cap (rough upper bound)
MAX_PHOTOS=$(echo "$MAX_COST / $COST_PER_PHOTO" | bc 2>/dev/null || echo "1000")
MAX_PHOTOS=${MAX_PHOTOS%.*}  # Truncate to integer

while true; do
    BATCH_NUMBER=$((BATCH_NUMBER + 1))

    # Calculate remaining cost budget for this batch
    COST_SO_FAR=$(echo "$TOTAL_LABELED * $COST_PER_PHOTO" | awk '{printf "%.2f", $1 * $3}')
    REMAINING_BUDGET=$(echo "$MAX_COST $COST_SO_FAR" | awk '{printf "%.2f", $1 - $2}')

    # Check if we've exhausted the cost budget
    BUDGET_EXHAUSTED=$(echo "$REMAINING_BUDGET" "$COST_PER_PHOTO" | awk '{print ($1 < $2) ? "yes" : "no"}')
    if [[ "$BUDGET_EXHAUSTED" == "yes" ]]; then
        log "Cost budget exhausted (\$$COST_SO_FAR of \$$MAX_COST spent). Stopping."
        break
    fi

    log "--- Batch $BATCH_NUMBER (budget remaining: \$$REMAINING_BUDGET) ---"

    # Run generate_date_labels.py for this batch
    BATCH_OUTPUT=""
    BATCH_EXIT_CODE=0

    BATCH_OUTPUT=$(cd "$PROJECT_ROOT" && python -m rhodesli_ml.scripts.generate_date_labels \
        --model "$MODEL" \
        --batch-size "$BATCH_SIZE" \
        --max-cost "$REMAINING_BUDGET" \
        2>&1) || BATCH_EXIT_CODE=$?

    # Log the full output
    echo "$BATCH_OUTPUT" >> "$LOG_FILE"

    # Parse results
    read -r BATCH_LABELED BATCH_ERRORS <<< "$(parse_batch_output "$BATCH_OUTPUT")"
    BATCH_LABELED=${BATCH_LABELED:-0}
    BATCH_ERRORS=${BATCH_ERRORS:-0}
    BATCH_TOTAL=$((BATCH_LABELED + BATCH_ERRORS))

    TOTAL_LABELED=$((TOTAL_LABELED + BATCH_LABELED))
    TOTAL_ERRORS=$((TOTAL_ERRORS + BATCH_ERRORS))
    TOTAL_ATTEMPTED=$((TOTAL_ATTEMPTED + BATCH_TOTAL))

    log "Batch $BATCH_NUMBER results: $BATCH_LABELED labeled, $BATCH_ERRORS errors"

    # Collect failed photo IDs from output (lines with "SKIP:" or "ERROR:")
    BATCH_FAILURES=$(echo "$BATCH_OUTPUT" | grep -E "(SKIP:|ERROR:.*failed)" | head -20 || true)
    if [[ -n "$BATCH_FAILURES" ]]; then
        FAILED_PHOTOS="${FAILED_PHOTOS}${BATCH_FAILURES}"$'\n'
    fi

    # If nothing was processed, we're done (no more photos to label)
    if [[ $BATCH_TOTAL -eq 0 && $BATCH_LABELED -eq 0 ]]; then
        log "No photos processed in batch $BATCH_NUMBER. All photos may be labeled."
        break
    fi

    # Check for high failure rate
    if check_failure_rate "$BATCH_LABELED" "$BATCH_ERRORS"; then
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        RATE_LIMIT_ADJUSTMENTS=$((RATE_LIMIT_ADJUSTMENTS + 1))
        INTER_REQUEST_SLEEP_MULTIPLIER=$((INTER_REQUEST_SLEEP_MULTIPLIER * 2))

        log "WARNING: Batch $BATCH_NUMBER had >50% failure rate ($BATCH_ERRORS/$BATCH_TOTAL errors)"
        log "  Doubled inter-request sleep multiplier to ${INTER_REQUEST_SLEEP_MULTIPLIER}x"

        if [[ $CONSECUTIVE_FAILURES -ge 3 ]]; then
            log "ALERT: 3 consecutive high-failure batches. Pausing for 10 minutes..."
            sleep 600
            log "Resuming after 10-minute pause (sleep multiplier: ${INTER_REQUEST_SLEEP_MULTIPLIER}x)"
            CONSECUTIVE_FAILURES=0
        fi
    else
        CONSECUTIVE_FAILURES=0
    fi

    # Check if the script hit its own cost cap or completed early
    if echo "$BATCH_OUTPUT" | grep -q "HALT: Running cost"; then
        log "Cost cap reached within batch. Stopping."
        break
    fi

    # If we labeled fewer than the batch size, we may be done
    if [[ $BATCH_LABELED -lt $BATCH_SIZE ]]; then
        # Check if there are remaining photos by looking at "To label:" line
        REMAINING=$(echo "$BATCH_OUTPUT" | grep -oE "To label: [0-9]+" | grep -oE "[0-9]+" || echo "0")
        if [[ "$REMAINING" -eq 0 ]] || [[ $BATCH_LABELED -eq 0 ]]; then
            log "All available photos have been labeled."
            break
        fi
    fi

    # Inter-batch sleep (scaled by failure rate adjustments)
    SLEEP_TIME=$((INTER_BATCH_SLEEP * INTER_REQUEST_SLEEP_MULTIPLIER))
    log "Sleeping ${SLEEP_TIME}s before next batch..."
    sleep "$SLEEP_TIME"
done

# ─── Final Summary ──────────────────────────────────────────────────────────────

print_summary
