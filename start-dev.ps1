$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

if (-not (Test-Path $python)) {
    Write-Host "Creating Python virtual environment..."
    python -m venv (Join-Path $root ".venv")
}

Write-Host "Installing backend dependencies..."
& $python -m pip install -r (Join-Path $backend "requirements.txt") | Out-Host

Write-Host "Applying migrations and seeding demo data..."
Push-Location $backend
& $python manage.py migrate | Out-Host
& $python manage.py seed_demo --load-samples | Out-Host
Pop-Location

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Installing frontend dependencies..."
    Push-Location $frontend
    npm install | Out-Host
    Pop-Location
}

Write-Host ""
Write-Host "Starting ESG platform..."
Write-Host "Backend:  http://127.0.0.1:8000/api"
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "Press Ctrl+C to stop both servers."
Write-Host ""

$backendJob = Start-Job -Name "esg-backend" -ScriptBlock {
    param($backend, $python)
    Set-Location $backend
    & $python manage.py runserver 127.0.0.1:8000
} -ArgumentList $backend, $python

$frontendJob = Start-Job -Name "esg-frontend" -ScriptBlock {
    param($frontend)
    Set-Location $frontend
    npm run dev -- --port 5173
} -ArgumentList $frontend

try {
    while ($true) {
        Receive-Job $backendJob, $frontendJob -Keep | Out-Host
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "Stopping servers..."
    Stop-Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob, $frontendJob -Force -ErrorAction SilentlyContinue
}
