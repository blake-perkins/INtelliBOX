# INtelliBOX Podman Build and Test
$ErrorActionPreference = "Stop"

Write-Host "======================================"
Write-Host "Building INtelliBOX Container"
Write-Host "======================================"
Write-Host ""

Write-Host "[1/5] Building image..."
podman build -t intellibox:latest .

Write-Host ""
Write-Host "[2/5] Testing Python imports..."
podman run --rm intellibox:latest python -c "from intellibox.database import get_session; print('OK')"

Write-Host ""
Write-Host "[3/5] Testing CLI..."
podman run --rm intellibox:latest intellibox --help

Write-Host ""
Write-Host "[4/5] Testing with .env file..."
podman run --rm --env-file .env intellibox:latest python -c "from intellibox.config import settings; print('Config OK')"

Write-Host ""
Write-Host "[5/5] Running full app test..."
podman run --rm --env-file .env intellibox:latest python -c "from intellibox.ai.processor import get_ai_client; print('AI Client:', get_ai_client().__class__.__name__)"

Write-Host ""
Write-Host "======================================"
Write-Host "All tests passed!"
Write-Host "======================================"
Write-Host ""
Write-Host "Image ready: intellibox:latest"
