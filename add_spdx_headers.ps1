<#
SPDX-FileCopyrightText: 2026 Helix AI Studio Contributors
SPDX-License-Identifier: MIT
#>

param(
  [string]$Root = ".",
  [string]$CopyrightText = "2026 Helix AI Studio Contributors"
)

$ErrorActionPreference = "Stop"

# Folders to skip (common build/artifact dirs)
$skipDirs = @(
  ".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__",
  ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode"
)

# Files to skip (license files should stay canonical for GitHub detection)
$skipFileRegex = '(^|\\)(LICENSE|LICENCE|COPYING|NOTICE)(\..*)?$'

function Get-CommentStyle([string]$ext) {
  switch ($ext.ToLowerInvariant()) {
    ".py"   { return @{ kind="hash" } }
    ".ps1"  { return @{ kind="hash" } }
    ".sh"   { return @{ kind="hash" } }
    ".bash" { return @{ kind="hash" } }
    ".zsh"  { return @{ kind="hash" } }
    ".js"   { return @{ kind="slash" } }
    ".ts"   { return @{ kind="slash" } }
    ".tsx"  { return @{ kind="slash" } }
    ".jsx"  { return @{ kind="slash" } }
    ".css"  { return @{ kind="block" } }
    ".scss" { return @{ kind="block" } }
    ".html" { return @{ kind="html" } }
    ".htm"  { return @{ kind="html" } }
    ".md"   { return @{ kind="html" } }
    ".yml"  { return @{ kind="hash" } }
    ".yaml" { return @{ kind="hash" } }
    ".toml" { return @{ kind="hash" } }
    ".ini"  { return @{ kind="hash" } }
    ".cfg"  { return @{ kind="hash" } }
    ".txt"  { return @{ kind="hash" } }
    ".xml"  { return @{ kind="block" } }
    default { return $null }
  }
}

function Has-Spdx([string[]]$lines) {
  $head = $lines | Select-Object -First 30
  return ($head -match "SPDX-License-Identifier\s*:")
}

function Insert-Header([string]$path, [hashtable]$style) {
  $content = Get-Content -LiteralPath $path -Raw -Encoding UTF8
  $lines = $content -split "`r?`n", -1

  if (Has-Spdx $lines) { return }

  $copy = "SPDX-FileCopyrightText: $CopyrightText"
  $id   = "SPDX-License-Identifier: MIT"

  $header = switch ($style.kind) {
    "hash"  { @("# $copy", "# $id", "") }
    "slash" { @("// $copy", "// $id", "") }
    "html"  { @("<!-- $copy -->", "<!-- $id -->", "") }
    "block" { @("/* $copy", " * $id", " */", "") }
    default { @() }
  }

  # If file has a shebang, keep it as the very first line.
  if ($lines.Length -gt 0 -and $lines[0].StartsWith("#!")) {
    $newLines = @($lines[0]) + $header + ($lines | Select-Object -Skip 1)
  } else {
    $newLines = $header + $lines
  }

  $newContent = ($newLines -join "`r`n")
  Set-Content -LiteralPath $path -Value $newContent -Encoding UTF8
}

function Ensure-LicenseSidecar([string]$path) {
  $side = "$path.license"
  if (Test-Path -LiteralPath $side) { return }
  $body = @(
    "SPDX-FileCopyrightText: $CopyrightText",
    "SPDX-License-Identifier: MIT",
    ""
  ) -join "`r`n"
  Set-Content -LiteralPath $side -Value $body -Encoding UTF8
}

# Walk files
Get-ChildItem -LiteralPath $Root -Recurse -File | ForEach-Object {
  $full = $_.FullName

  # Skip dir segments
  foreach ($d in $skipDirs) {
    if ($full -match "([/\\])$([Regex]::Escape($d))([/\\])") { return }
  }

  # Skip license files
  if ($full -match $skipFileRegex) { return }

  $ext = $_.Extension
  if ($ext -eq ".json") {
    # JSON is often uncommentable -> use .license sidecar (REUSE style)
    Ensure-LicenseSidecar $full
    return
  }

  $style = Get-CommentStyle $ext
  if ($null -eq $style) { return }

  Insert-Header $full $style
}

Write-Host "Done. SPDX headers added where possible, and .license sidecars created for JSON."
