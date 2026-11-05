param()

$ErrorActionPreference = "Continue"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
$ComposeArgs = @("--env-file", ".env", "-f", "infra/docker-compose.yml")

Write-Host "=== Container status ==="
docker compose @ComposeArgs ps
Write-Host ""
Write-Host "=== API health ==="
try { Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5 | Format-List } catch { Write-Warning $_ }
Write-Host ""
Write-Host "=== Training websites ==="
try { Invoke-RestMethod -Uri "http://localhost:8000/api/v1/training/websites" -TimeoutSec 5 | ConvertTo-Json -Depth 6 } catch { Write-Warning $_ }
Write-Host ""
Write-Host "=== Dashboard response ==="
try { (Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 10).StatusCode } catch { Write-Warning $_ }
Write-Host ""
Write-Host "=== Recent API / worker / web logs ==="
docker compose @ComposeArgs logs --tail 100 api worker web
