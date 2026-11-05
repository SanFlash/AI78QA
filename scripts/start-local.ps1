param()

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker CLI was not found. Install Docker Desktop and start its engine, then run this script again."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
  throw "Docker Engine is not running. Start Docker Desktop, wait until it is ready, and retry."
}

function New-LocalSecret {
  $bytes = New-Object byte[] 36
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

if (-not (Test-Path ".env")) {
  $envText = [System.IO.File]::ReadAllText((Join-Path $RepoRoot ".env.example"))
} else {
  $envText = [System.IO.File]::ReadAllText((Join-Path $RepoRoot ".env"))
}
$originalEnvText = $envText
if ($envText.Contains("replace-with-a-long-random-value")) {
  $envText = $envText.Replace("replace-with-a-long-random-value", (New-LocalSecret))
}
if ($envText.Contains("replace-with-a-strong-local-password")) {
  $envText = $envText.Replace("replace-with-a-strong-local-password", (New-LocalSecret))
}
if ($envText.Contains("local-development-only")) {
  $envText = $envText.Replace("local-development-only", (New-LocalSecret))
}
if ($envText -ne $originalEnvText -or -not (Test-Path ".env")) {
  [System.IO.File]::WriteAllText((Join-Path $RepoRoot ".env"), $envText, [System.Text.UTF8Encoding]::new($false))
  Write-Host "Created or secured .env with random local-only secrets."
}

$ComposeArgs = @("--env-file", ".env", "-f", "infra/docker-compose.yml")
docker compose @ComposeArgs config --quiet
if ($LASTEXITCODE -ne 0) { throw "Docker Compose configuration validation failed." }

docker compose @ComposeArgs up --build -d
if ($LASTEXITCODE -ne 0) { throw "One or more AI78QA containers failed to build or start. Run scripts/diagnose-local.ps1." }

Write-Host ""
Write-Host "AI78QA containers are starting. Waiting for API health..."
$healthy = $false
for ($i = 0; $i -lt 60; $i++) {
  try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 3
    if ($health.status -eq "ok") { $healthy = $true; break }
  } catch {}
  Start-Sleep -Seconds 2
}

if (-not $healthy) {
  Write-Warning "API did not become healthy within 120 seconds. Inspect scripts/diagnose-local.ps1 output."
  docker compose @ComposeArgs ps
  exit 1
}

Write-Host ""
Write-Host "Checking the dashboard-to-API proxy..."
$proxyReady = $false
for ($i = 0; $i -lt 30; $i++) {
  try {
    $null = Invoke-RestMethod -Uri "http://localhost:3000/api/ai78qa/training/websites" -TimeoutSec 3
    $proxyReady = $true
    break
  } catch {}
  Start-Sleep -Seconds 2
}
if (-not $proxyReady) {
  Write-Warning "The dashboard/API proxy did not respond. Run scripts/diagnose-local.ps1."
  docker compose @ComposeArgs logs --tail 80 web api worker
  exit 1
}

$runningServices = docker compose @ComposeArgs ps --status running --services
if ($runningServices -notcontains "worker") {
  Write-Warning "The Playwright worker is not running. Run scripts/diagnose-local.ps1."
  docker compose @ComposeArgs logs --tail 100 worker
  exit 1
}

Write-Host ""
Write-Host "AI78QA local stack is healthy:"
Write-Host "  Dashboard : http://localhost:3000"
Write-Host "  API docs  : http://localhost:8000/docs"
Write-Host "  API health: http://localhost:8000/health"
Write-Host "  Worker    : running (Celery / Playwright)"
Write-Host ""
Write-Host "The SauceDemo starter website is seeded. Open Training Lab and start an observe-only exploration."
