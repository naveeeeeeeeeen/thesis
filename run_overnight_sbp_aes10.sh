#!/usr/bin/env bash
#
# run_overnight_sbp_aes10.sh - Phase 1 overnight batch.
#
# Runs, SEQUENTIALLY (not in parallel with each other - each config
# already uses -m 4 cores internally, so running configs concurrently on
# top of that would oversubscribe the machine), the following AES10
# configurations at H=26:
#
#   1. baseline        (original Sum-then-Norm-then-random selection)
#   2. --sbp-pool 2
#   3. --sbp-pool 3
#   4. --sbp-pool 5
#   5. --sbp-pool 8
#   6. --sbp-pool 12
#
# ASSUMPTION (noted per task instructions): given the confirmed ~4-5 hour
# runtime per AES10/H=26 attempt (see PROJECT_CONTEXT.md, Section 4.4),
# six sequential configs could take on the order of a full day or more of
# wall-clock time. This script is designed to be started and left running
# unattended (that is the entire point of using nohup here), and it
# deliberately does NOT try to run configs concurrently to keep total
# machine load bounded and predictable.
#
# Usage (see README section below for the recommended invocation):
#   nohup ./run_overnight_sbp_aes10.sh > logs/_driver_$(date +%Y%m%d_%H%M%S).log 2>&1 &
#
# Each individual configuration's own main.py stdout/stderr additionally
# goes to its own timestamped file under logs/, independent of the
# top-level nohup redirection above, so a single config's output can be
# inspected without wading through the whole batch's combined log.

set -u  # error on unset variables - but NOT -e, since a single failed
        # config must not abort the rest of the batch (see the per-config
        # error handling below).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DRIVER_LOG="$LOG_DIR/_driver_${TIMESTAMP}.log"

# Tell the user where output is going BEFORE redirecting (this line still
# goes to the actual terminal/nohup.out, not into DRIVER_LOG itself).
echo "Driver log for this run: $REPO_ROOT/$DRIVER_LOG"
echo "Per-config logs will appear under: $REPO_ROOT/$LOG_DIR/aes10_*_${TIMESTAMP}.log"

# Redirect this script's own stdout/stderr to its own driver log FROM
# THIS POINT ON. This happens only after mkdir -p above, so - unlike an
# external `command > logs/file.log` redirect set up by the calling
# shell - there is no possible race against logs/ not existing yet.
# Recommended invocation is now simply:
#   nohup ./run_overnight_sbp_aes10.sh &
# with no manual redirect or pre-created directory required.
exec > "$DRIVER_LOG" 2>&1

# Each entry: "label|extra_args"
CONFIGS=(
    "baseline|"
    "sbp_pool2|--sbp --sbp-pool 2"
    #"sbp_pool3|--sbp --sbp-pool 3"
    "sbp_pool5|--sbp --sbp-pool 5"
    #"sbp_pool8|--sbp --sbp-pool 8"
    "sbp_pool12|--sbp --sbp-pool 12"
)

FAILED_CONFIGS=()

echo "=== Overnight AES10/H=26 batch started at $(date) ==="
echo "Repository root: $REPO_ROOT"
echo "Logs will be written under: $REPO_ROOT/$LOG_DIR"
echo ""

for entry in "${CONFIGS[@]}"; do
    label="${entry%%|*}"
    extra_args="${entry#*|}"
    log_file="$LOG_DIR/aes10_${label}_${TIMESTAMP}.log"

    echo "--- [$(date)] Starting config: $label (args: ${extra_args:-<none>}) ---"
    echo "    Logging to: $log_file"

    # nohup here protects this individual run from a hangup signal too,
    # in addition to the outer nohup wrapping the whole script (belt and
    # suspenders - see the usage note above).
    nohup python3 main.py -f AES10 -a BPD -H 26 -m 4 ${extra_args} \
        > "$log_file" 2>&1
    exit_code=$?

    if [ $exit_code -ne 0 ]; then
        echo "    !! Config '$label' exited with code $exit_code - continuing with remaining configs."
        FAILED_CONFIGS+=("$label")
    else
        echo "    Config '$label' finished successfully."
    fi
    echo ""
done

echo "=== All configs attempted. Batch finished at $(date) ==="
if [ ${#FAILED_CONFIGS[@]} -gt 0 ]; then
    echo "Configs that reported a non-zero exit code: ${FAILED_CONFIGS[*]}"
    echo "(Their logs are still present under $LOG_DIR and may contain partial results.)"
fi
echo ""

# --- Summary: best (minimum) XOR count found per configuration ---
# Relies on main.py's print line format:
#   "Write AES10 (H = 26) by using <N>XORs in core00_<tag> (time : ...)"
# where <tag> is "orig" for baseline or "sbp<pool_size>" for SBP runs -
# see _mode_tag() in main.py. Each config's log contains one such line
# per core (4 cores per config here), so we take the minimum across them.

echo "=== Summary: best XOR count per configuration ==="
printf "%-14s %-10s %s\n" "CONFIG" "BEST_XOR" "ALL_CORE_RESULTS"
printf "%-14s %-10s %s\n" "------" "--------" "----------------"

for entry in "${CONFIGS[@]}"; do
    label="${entry%%|*}"
    log_file="$LOG_DIR/aes10_${label}_${TIMESTAMP}.log"

    if [ ! -f "$log_file" ]; then
        printf "%-14s %-10s %s\n" "$label" "N/A" "(log file not found)"
        continue
    fi

    # Extract every "using <N>XORs" occurrence from this config's log.
    xor_counts=$(grep -oP 'using \K[0-9]+(?=XORs)' "$log_file" | sort -n)

    if [ -z "$xor_counts" ]; then
        printf "%-14s %-10s %s\n" "$label" "N/A" "(no completed runs found in log - check for errors)"
        continue
    fi

    best=$(echo "$xor_counts" | head -1)
    all_joined=$(echo "$xor_counts" | paste -sd, -)
    printf "%-14s %-10s %s\n" "$label" "$best" "$all_joined"
done

echo ""
echo "Full per-config logs are in: $REPO_ROOT/$LOG_DIR/aes10_*_${TIMESTAMP}.log"
echo "Look for '[Circuit_Cleanup]' lines in any of them to see Phase 0 dead-gate findings per run."