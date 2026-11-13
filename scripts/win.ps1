# PowerShell task runner for machines without `make`.
# Uses Git Bash from Git for Windows to run the same shell scripts as CI.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\win.ps1 check
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('setup', 'hooks', 'check', 'up', 'down', 'logs', 'psql', 'reset-db', 'clean')]
    [string]$Task
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

$candidates = @(
    "$env:ProgramFiles\Git\bin\bash.exe",
    "$env:ProgramFiles\Git\usr\bin\bash.exe",
    "${env:ProgramFiles(x86)}\Git\bin\bash.exe"
)
$bash = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $bash) {
    $cmd = Get-Command bash -ErrorAction SilentlyContinue
    if ($cmd) { $bash = $cmd.Source }
}
if (-not $bash) { throw "Git Bash not found. Install Git for Windows or use WSL." }

switch ($Task) {
    'setup'  { & $bash "$root/scripts/setup.sh"; & $bash "$root/scripts/install-hooks.sh" }
    'hooks'  { & $bash "$root/scripts/install-hooks.sh" }
    'check'  { & $bash "$root/scripts/check.sh" }
    'up'     { docker compose up -d --wait }
    'down'   { docker compose down }
    'logs'   { docker compose logs -f --tail=100 }
    'psql'   { docker compose exec db psql -U junction -d junction }
    'reset-db' { docker compose down -v; docker compose up -d --wait }
    'clean'  { Remove-Item -Recurse -Force node_modules, .next, dist, build, coverage -ErrorAction SilentlyContinue }
}
exit $LASTEXITCODE
