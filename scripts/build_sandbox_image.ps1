# Helix AI Studio — Sandbox Docker イメージビルド (Windows)
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "Building helix-sandbox Docker image..."
docker build -t helix-sandbox:latest -f "$ProjectRoot\docker\sandbox\Dockerfile" "$ProjectRoot\docker\sandbox\"
Write-Host "Done: helix-sandbox:latest"
