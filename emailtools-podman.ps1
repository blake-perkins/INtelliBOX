# EmailTools Podman Helper Script
# Easy commands for managing the EmailTools container

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

function Show-Help {
    Write-Host "EmailTools Container Helper" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\emailtools-podman.ps1 <command>" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Green
    Write-Host "  status     - Show container status"
    Write-Host "  logs       - View container logs"
    Write-Host "  process    - Process emails from inbox"
    Write-Host "  actions    - List all actions"
    Write-Host "  report     - Generate report (dry-run)"
    Write-Host "  db         - Show database summary"
    Write-Host "  shell      - Open shell in container"
    Write-Host "  restart    - Restart container"
    Write-Host "  stop       - Stop container"
    Write-Host "  start      - Start container"
    Write-Host "  rebuild    - Rebuild and restart container"
    Write-Host ""
}

switch ($Command.ToLower()) {
    "status" {
        Write-Host "Container Status:" -ForegroundColor Yellow
        wsl -d podman-machine-default podman ps -f name=emailtools
    }
    "logs" {
        Write-Host "Container Logs (Ctrl+C to exit):" -ForegroundColor Yellow
        wsl -d podman-machine-default podman logs -f emailtools
    }
    "process" {
        Write-Host "Processing emails..." -ForegroundColor Yellow
        wsl -d podman-machine-default podman exec emailtools sh -c "emailtools process"
    }
    "actions" {
        Write-Host "Listing actions..." -ForegroundColor Yellow
        wsl -d podman-machine-default podman exec emailtools sh -c "emailtools actions list --unassigned"
    }
    "report" {
        Write-Host "Generating report..." -ForegroundColor Yellow
        wsl -d podman-machine-default podman exec emailtools sh -c "emailtools report send --dry-run"
    }
    "db" {
        Write-Host "Database Summary:" -ForegroundColor Yellow
        wsl -d podman-machine-default podman exec emailtools sh -c "emailtools db show"
    }
    "shell" {
        Write-Host "Opening shell in container..." -ForegroundColor Yellow
        wsl -d podman-machine-default podman exec -it emailtools sh
    }
    "restart" {
        Write-Host "Restarting container..." -ForegroundColor Yellow
        podman restart emailtools
        Write-Host "Container restarted" -ForegroundColor Green
    }
    "stop" {
        Write-Host "Stopping container..." -ForegroundColor Yellow
        podman stop emailtools
        Write-Host "Container stopped" -ForegroundColor Green
    }
    "start" {
        Write-Host "Starting container..." -ForegroundColor Yellow
        podman start emailtools
        Write-Host "Container started" -ForegroundColor Green
    }
    "rebuild" {
        Write-Host "Rebuilding container..." -ForegroundColor Yellow
        podman stop emailtools
        podman rm emailtools
        podman build -t emailtools:latest .
        podman run -d --name emailtools --env-file .env -v ./data:/app/data emailtools:latest emailtools report schedule
        Write-Host "Container rebuilt and started" -ForegroundColor Green
    }
    default {
        Show-Help
    }
}
