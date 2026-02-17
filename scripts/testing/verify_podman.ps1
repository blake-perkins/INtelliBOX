# Podman Installation Verification Script
# Run this in PowerShell

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Podman Installation Verification" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if podman command exists
Write-Host "[1/5] Checking for podman command..." -ForegroundColor Yellow
$podmanCmd = Get-Command podman -ErrorAction SilentlyContinue

if ($podmanCmd) {
    Write-Host "[OK] Podman found at: $($podmanCmd.Source)" -ForegroundColor Green

    # Check version
    Write-Host "`n[2/5] Checking Podman version..." -ForegroundColor Yellow
    podman --version

    # Check machine status
    Write-Host "`n[3/5] Checking Podman machine..." -ForegroundColor Yellow
    podman machine list

    # Check if machine is running
    Write-Host "`n[4/5] Checking machine status..." -ForegroundColor Yellow
    $machineStatus = podman machine list --format "{{.Running}}"

    if ($machineStatus -eq "true" -or $machineStatus -eq "currently running") {
        Write-Host "[OK] Podman machine is running" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Podman machine is not running" -ForegroundColor Yellow
        Write-Host "Starting Podman machine..." -ForegroundColor Yellow
        podman machine start
    }

    # Test podman
    Write-Host "`n[5/5] Testing Podman..." -ForegroundColor Yellow
    podman run --rm hello-world

    Write-Host "`n======================================" -ForegroundColor Green
    Write-Host "Podman is ready to use!" -ForegroundColor Green
    Write-Host "======================================" -ForegroundColor Green
    Write-Host "`nNext steps:" -ForegroundColor Cyan
    Write-Host "  cd d:\dev\EmailTools" -ForegroundColor White
    Write-Host "  podman build -t emailtools:latest ." -ForegroundColor White
    Write-Host ""

} else {
    Write-Host "[ERROR] Podman not found in PATH" -ForegroundColor Red
    Write-Host "`nPossible solutions:" -ForegroundColor Yellow
    Write-Host "1. Restart your terminal/PowerShell" -ForegroundColor White
    Write-Host "2. Verify Podman Desktop is installed" -ForegroundColor White
    Write-Host "3. Reinstall Podman Desktop from: https://podman-desktop.io/" -ForegroundColor White
    Write-Host "`nChecking for Podman Desktop installation..." -ForegroundColor Yellow

    $podmanDesktop = Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
                     Where-Object { $_.DisplayName -like "*Podman*" }

    if ($podmanDesktop) {
        Write-Host "[FOUND] Podman Desktop is installed" -ForegroundColor Green
        Write-Host "Location: $($podmanDesktop.InstallLocation)" -ForegroundColor White
        Write-Host "`nPlease restart your terminal and try again." -ForegroundColor Yellow
    } else {
        Write-Host "[NOT FOUND] Podman Desktop is not installed" -ForegroundColor Red
        Write-Host "Please install from: https://podman-desktop.io/" -ForegroundColor Yellow
    }
}

Write-Host "`nPress any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
