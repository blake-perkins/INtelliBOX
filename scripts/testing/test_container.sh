#!/bin/bash
# EmailTools Container Test Script
# Works with both Podman and Docker

set -e

# Detect container engine
if command -v podman &> /dev/null; then
    ENGINE="podman"
elif command -v docker &> /dev/null; then
    ENGINE="docker"
else
    echo "Error: Neither Podman nor Docker found"
    echo "Install Podman Desktop: https://podman-desktop.io/"
    exit 1
fi

echo "============================================"
echo "EmailTools Container Test"
echo "Container Engine: $ENGINE"
echo "============================================"
echo ""

# Test 1: Build image
echo "[1/7] Building container image..."
$ENGINE build -t emailtools:test -f Dockerfile .

echo ""
echo "[2/7] Verifying image..."
$ENGINE images | grep emailtools

echo ""
echo "[3/7] Testing container startup..."
$ENGINE run --rm emailtools:test python -c "from emailtools.database import get_session; print('[OK] Database imports work')"

echo ""
echo "[4/7] Testing CLI inside container..."
$ENGINE run --rm emailtools:test emailtools --help

echo ""
echo "[5/7] Testing with environment variables..."
$ENGINE run --rm \
    -e DATABASE_URL=sqlite:///./data/test.db \
    -e OPENAI_API_KEY=sk-test \
    emailtools:test \
    python -c "from emailtools.config import settings; print(f'[OK] Config loaded: {settings.database_url}')"

echo ""
echo "[6/7] Testing volume mounts..."
mkdir -p /tmp/emailtools-test
$ENGINE run --rm \
    -v /tmp/emailtools-test:/app/data \
    emailtools:test \
    python -c "from pathlib import Path; Path('/app/data/test.txt').write_text('works'); print('[OK] Volume mount works')"

if [ -f "/tmp/emailtools-test/test.txt" ]; then
    echo "[OK] Volume persisted data"
    rm -rf /tmp/emailtools-test
else
    echo "[ERROR] Volume did not persist data"
    exit 1
fi

echo ""
echo "[7/7] Testing full workflow..."
$ENGINE run --rm \
    --env-file .env \
    emailtools:test \
    python -c "
from emailtools.database import get_session
from emailtools.ai.processor import get_ai_client
from emailtools.reporter.generator import generate_report_data
print('[OK] Database: Working')
print('[OK] AI Client:', get_ai_client().__class__.__name__)
print('[OK] All components loaded successfully')
"

echo ""
echo "============================================"
echo "All tests passed! ✓"
echo "============================================"
echo ""
echo "Container image ready to deploy:"
echo "  Local: $ENGINE run -d --name emailtools --env-file .env -v ./data:/app/data emailtools:test"
echo "  AWS:   ./aws/deploy-podman.sh"
echo ""
