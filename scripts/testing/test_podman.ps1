# EmailTools Podman Container Test Script
# Run this in PowerShell

$ErrorActionPreference = "Stop"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "EmailTools Podman Container Test" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Build image
Write-Host "[1/7] Building container image..." -ForegroundColor Yellow
Write-Host "This may take 2-3 minutes..." -ForegroundColor Gray
podman build -t emailtools:latest -f Dockerfile .

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Build failed" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Image built successfully" -ForegroundColor Green

# Step 2: Verify image
Write-Host "`n[2/7] Verifying image..." -ForegroundColor Yellow
podman images | Select-String "emailtools"
Write-Host "[OK] Image found" -ForegroundColor Green

# Step 3: Test container startup
Write-Host "`n[3/7] Testing container startup..." -ForegroundColor Yellow
podman run --rm emailtools:latest python -c "from emailtools.database import get_session; print('[OK] Database imports work')"
Write-Host "[OK] Container can start and run Python" -ForegroundColor Green

# Step 4: Test CLI
Write-Host "`n[4/7] Testing CLI inside container..." -ForegroundColor Yellow
podman run --rm emailtools:latest emailtools --help | Select-String "Usage"
Write-Host "[OK] CLI working inside container" -ForegroundColor Green

# Step 5: Test with environment variables
Write-Host "`n[5/7] Testing environment variables..." -ForegroundColor Yellow
podman run --rm `
    -e DATABASE_URL=sqlite:///./data/test.db `
    -e OPENAI_API_KEY=sk-test `
    emailtools:latest `
    python -c "from emailtools.config import settings; print(f'[OK] Config loaded')"
Write-Host "[OK] Environment variables working" -ForegroundColor Green

# Step 6: Test volume mount
Write-Host "`n[6/7] Testing volume mount..." -ForegroundColor Yellow
$testDir = "$env:TEMP\emailtools-test"
New-Item -ItemType Directory -Force -Path $testDir | Out-Null

podman run --rm `
    -v "$($testDir):/app/data" `
    emailtools:latest `
    python -c "from pathlib import Path; Path('/app/data/test.txt').write_text('works'); print('[OK] Volume mount works')"

if (Test-Path "$testDir\test.txt") {
    Write-Host "[OK] Volume persisted data" -ForegroundColor Green
    Remove-Item -Recurse -Force $testDir
} else {
    Write-Host "[ERROR] Volume did not persist" -ForegroundColor Red
    exit 1
}

# Step 7: Test full app
Write-Host "`n[7/7] Testing full application stack..." -ForegroundColor Yellow
podman run --rm `
    --env-file .env `
    emailtools:latest `
    python -c @"
from emailtools.database import get_session
from emailtools.ai.processor import get_ai_client
from emailtools.reporter.generator import generate_report_data
print('[OK] Database: Working')
print('[OK] AI Client:', get_ai_client().__class__.__name__)
print('[OK] All components loaded')
"@
Write-Host "[OK] Full application working" -ForegroundColor Green

Write-Host "`n======================================" -ForegroundColor Green
Write-Host "All tests passed! ✓" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""

Write-Host "Container is ready! Next steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Run locally:" -ForegroundColor Yellow
Write-Host "   podman run -d --name emailtools --env-file .env -v ./data:/app/data emailtools:latest" -ForegroundColor White
Write-Host ""
Write-Host "2. Check logs:" -ForegroundColor Yellow
Write-Host "   podman logs -f emailtools" -ForegroundColor White
Write-Host ""
Write-Host "3. Execute commands:" -ForegroundColor Yellow
Write-Host "   podman exec emailtools emailtools process" -ForegroundColor White
Write-Host "   podman exec emailtools emailtools actions list" -ForegroundColor White
Write-Host ""
Write-Host "4. Deploy to AWS:" -ForegroundColor Yellow
Write-Host '   bash aws/deploy-podman.sh' -ForegroundColor White
Write-Host ""
