#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

TARGET_HOST="${TARGET_HOST:?ERROR: TARGET_HOST is required (e.g. export TARGET_HOST=1.2.3.4)}"
SSH_KEY="${SSH_KEY:?ERROR: SSH_KEY is required (e.g. export SSH_KEY=~/.ssh/id_rsa)}"
SSH_USER="${SSH_USER:?ERROR: SSH_USER is required (e.g. export SSH_USER=myuser)}"
REMOTE_USER="${REMOTE_USER:?ERROR: REMOTE_USER is required (e.g. export REMOTE_USER=myuser)}"
REMOTE_PROJECT_DIR="${REMOTE_PROJECT_DIR:-~/aiops-microservices-lab}"

TEST_NAME="${1:-oom-test}"
NUM_RUNS="${2:-5}"

LOAD_TESTS_DIR="$PROJECT_ROOT/load-tests"
RESULTS_DIR="$PROJECT_ROOT/results/ai-agent/$TEST_NAME-logs"

if [[ -f "$LOAD_TESTS_DIR/$TEST_NAME.ts" ]]; then
  TEST_FILE="$TEST_NAME.ts"
else
  TEST_FILE="$TEST_NAME.js"
fi

SSH_CMD="ssh -F /dev/null -o ConnectTimeout=10 -i $SSH_KEY $SSH_USER@$TARGET_HOST"
REMOTE_EXEC="sudo su - $REMOTE_USER -c"

mkdir -p "$RESULTS_DIR"

for N in $(seq 1 "$NUM_RUNS"); do
  echo "========== RUN $N =========="

  echo "Phase 1: Resetting environment..."
  $SSH_CMD "$REMOTE_EXEC 'cd $REMOTE_PROJECT_DIR && docker compose down -v && docker compose up -d --build'"

  echo "Waiting 10s for containers to initialize..."
  sleep 10

  echo "Phase 2: Validation..."
  $SSH_CMD "$REMOTE_EXEC 'docker ps --format \"{{.Names}} | {{.Status}}\" | grep ai-agent'"
  $SSH_CMD "$REMOTE_EXEC 'docker logs ai-agent --tail 5'"

  echo "Phase 3: Warmup (60s)..."
  sleep 60

  echo "Phase 4: Running K6 load test..."
  docker run --rm -i grafana/k6 run -e TARGET_HOST=$TARGET_HOST - < "$LOAD_TESTS_DIR/$TEST_FILE" > "$RESULTS_DIR/k6-$TEST_NAME-run$N.log" 2>&1 &
  K6_PID=$!

  sleep 30
  echo "Phase 5: Collecting container stats at peak load..."
  $SSH_CMD "$REMOTE_EXEC 'docker stats --no-stream --format \"{{.Name}} | {{.CPUPerc}} | {{.MemUsage}}\"'" > "$RESULTS_DIR/stats-$TEST_NAME-run$N.log"

  echo "Waiting for K6 to finish (PID $K6_PID)..."
  wait $K6_PID || echo "K6 finished with non-zero exit code"

  echo "Phase 6: Cooldown (90s)..."
  sleep 90

  echo "Phase 7: Collecting AI agent logs and restart count..."
  $SSH_CMD "$REMOTE_EXEC 'docker logs ai-agent 2>&1'" > "$RESULTS_DIR/ai-agent-$TEST_NAME-run$N.log"
  $SSH_CMD "$REMOTE_EXEC 'docker inspect --format={{.RestartCount}} checkoutservice'" > "$RESULTS_DIR/restarts-$TEST_NAME-run$N.log"

  echo "========== END RUN $N =========="
done

echo "All $NUM_RUNS runs completed!"
