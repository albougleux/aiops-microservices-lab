#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

TEST_NAME="${1:-oom-test}"
AGENT="${2:-ai-agent}"
NUM_RUNS="${3:-5}"

RESULTS_DIR="$PROJECT_ROOT/results/$AGENT/logs/$TEST_NAME-logs"
OUTPUT_FILE="$PROJECT_ROOT/results/$AGENT/results_${TEST_NAME}.md"

mkdir -p "$PROJECT_ROOT/results/$AGENT"
> "$OUTPUT_FILE"

declare -A AI_LOG_HASHES

echo "Starting log aggregation for $OUTPUT_FILE..."

for N in $(seq 1 "$NUM_RUNS"); do
  echo "Processing Run $N..."

  echo "Run $N:" >> "$OUTPUT_FILE"
  echo "" >> "$OUTPUT_FILE"

  # K6 logs
  echo "k6:" >> "$OUTPUT_FILE"
  K6_FILE="$RESULTS_DIR/k6-$TEST_NAME-run$N.log"
  if [[ -f "$K6_FILE" ]]; then
    grep -E 'level=(warning|error)' "$K6_FILE" | \
      sed -E 's/time="[^"]+" //' | \
      sed -E 's/[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+->/[CLIENT_IP]:[PORT]->/g' | \
      sort | uniq -c | while read -r count error_msg; do
      echo "[Occurred $count times] $error_msg" >> "$OUTPUT_FILE"
    done

    if grep -q -E 'level=(warning|error)' "$K6_FILE"; then
      echo "" >> "$OUTPUT_FILE"
    fi

    sed -n '/TOTAL RESULTS/,$p' "$K6_FILE" >> "$OUTPUT_FILE"
  else
    echo "<K6 log file not found>" >> "$OUTPUT_FILE"
  fi
  echo "" >> "$OUTPUT_FILE"

  # Container restarts
  RESTARTS_FILE="$RESULTS_DIR/restarts-$TEST_NAME-run$N.log"
  echo -n "checkoutservice restart count: " >> "$OUTPUT_FILE"
  if [[ -f "$RESTARTS_FILE" ]]; then
    cat "$RESTARTS_FILE" >> "$OUTPUT_FILE"
  else
    echo "<Not found>" >> "$OUTPUT_FILE"
  fi
  echo "" >> "$OUTPUT_FILE"

  # Container stats
  STATS_FILE="$RESULTS_DIR/stats-$TEST_NAME-run$N.log"
  echo "stats:" >> "$OUTPUT_FILE"
  if [[ -f "$STATS_FILE" ]]; then
    cat "$STATS_FILE" >> "$OUTPUT_FILE"
  else
    echo "<Stats log file not found>" >> "$OUTPUT_FILE"
  fi
  echo "" >> "$OUTPUT_FILE"

  # AI analysis (with deduplication via content fingerprinting)
  AI_FILE="$RESULTS_DIR/$AGENT-$TEST_NAME-run$N.log"
  echo "AI analysis:" >> "$OUTPUT_FILE"
  if [[ -f "$AI_FILE" ]]; then
    FILE_HASH=$(grep -vE "(Latency|Tokens Used|POST /webhook|\[AIOps\]|\[CONTINUOUS AIOps\]|\[CHATOPS\]|FINOPS METRICS|^[=-]+$)" "$AI_FILE" | sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.,0-9]*Z?//g' | sed -E 's/[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[IP]/g' | md5sum | awk '{print $1}')

    if [[ -n "${AI_LOG_HASHES[$FILE_HASH]}" ]]; then
      echo "[Report identical to Run ${AI_LOG_HASHES[$FILE_HASH]}]" >> "$OUTPUT_FILE"
    else
      AI_LOG_HASHES[$FILE_HASH]=$N
      cat "$AI_FILE" >> "$OUTPUT_FILE"
    fi
  else
    echo "<AI agent log file not found>" >> "$OUTPUT_FILE"
  fi

  echo "" >> "$OUTPUT_FILE"
  echo "--------------------------------------------------" >> "$OUTPUT_FILE"
  echo "" >> "$OUTPUT_FILE"
done

echo "All logs aggregated successfully to: $OUTPUT_FILE"