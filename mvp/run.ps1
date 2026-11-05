$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.11 or newer and enable Add Python to PATH."
}

if (-not (Test-Path ".venv")) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv } else { python -m venv .venv }
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip. Check your Python installation and internet connection." }

& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Review the pip error above." }

& $Python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium installation failed." }

& $Python -m py_compile app.py
if ($LASTEXITCODE -ne 0) { throw "AI78QA has a Python syntax error. The app was not started." }

Write-Host ""
Write-Host "Starting AI78QA MVP at http://127.0.0.1:5000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop."
& $Python app.py
