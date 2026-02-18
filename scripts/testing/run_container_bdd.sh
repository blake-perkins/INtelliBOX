#!/bin/bash
# Run BDD tests against a Podman container.
# Usage: ./scripts/testing/run_container_bdd.sh
#
# Prerequisites:
#   - podman and podman-compose installed
#   - .env.test file exists at project root

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_DIR"

# --- Detect compose command ---
COMPOSE_CMD=""
if command -v podman-compose &>/dev/null; then
    COMPOSE_CMD="podman-compose"
elif podman compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="podman compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "ERROR: No compose command found."
    echo "Install with: pip install podman-compose"
    exit 1
fi
echo "Using compose command: $COMPOSE_CMD"

SERVICE="intellibox-test"
BASE_URL="http://localhost:8001"
DB_PATH="data/test/intellibox.db"
MAX_WAIT=60  # seconds

# --- Cleanup function ---
cleanup() {
    echo ""
    echo "=== Tearing down test container ==="
    $COMPOSE_CMD --profile testing down 2>/dev/null || true
    rm -rf data/test
}
trap cleanup EXIT

# --- Setup ---
echo "=== Preparing test data directory ==="
mkdir -p data/test/inbox data/test/emails

echo "=== Building container image ==="
$COMPOSE_CMD build $SERVICE

echo "=== Starting test container ==="
$COMPOSE_CMD --profile testing up -d $SERVICE

# --- Wait for health ---
echo "=== Waiting for container to be healthy (max ${MAX_WAIT}s) ==="
elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    if curl -sf "$BASE_URL/health" > /dev/null 2>&1; then
        echo "Container is healthy after ${elapsed}s"
        break
    fi
    sleep 2
    elapsed=$((elapsed + 2))
    echo "  ...waiting (${elapsed}s)"
done

if [ $elapsed -ge $MAX_WAIT ]; then
    echo "ERROR: Container failed to become healthy within ${MAX_WAIT}s"
    echo "Container logs:"
    $COMPOSE_CMD --profile testing logs $SERVICE
    exit 1
fi

# --- Run BDD tests ---
echo ""
echo "=== Running BDD tests against container at $BASE_URL ==="
export TEST_BASE_URL="$BASE_URL"
export TEST_DB_PATH="$DB_PATH"

# Detect behave executable
if [ -f "venv/Scripts/behave.exe" ]; then
    BEHAVE="venv/Scripts/behave.exe"
elif [ -f "venv/bin/behave" ]; then
    BEHAVE="venv/bin/behave"
else
    BEHAVE="behave"
fi

$BEHAVE features/ --no-capture
BDD_EXIT=$?

echo ""
if [ $BDD_EXIT -eq 0 ]; then
    echo "=== ALL BDD SCENARIOS PASSED against container ==="
else
    echo "=== SOME BDD SCENARIOS FAILED (exit code: $BDD_EXIT) ==="
fi

exit $BDD_EXIT
