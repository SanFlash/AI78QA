param([switch]$RemoveData)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot
$ComposeArgs = @("--env-file", ".env", "-f", "infra/docker-compose.yml")

if ($RemoveData) {
  Write-Warning "This removes the local PostgreSQL, Redis and evidence volumes. All local sessions and observations will be lost."
  $confirm = Read-Host "Type DELETE-LOCAL-DATA to continue"
  if ($confirm -ne "DELETE-LOCAL-DATA") { Write-Host "Cancelled."; exit 0 }
  docker compose @ComposeArgs down -v
} else {
  docker compose @ComposeArgs down
}
