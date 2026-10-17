param(
  [ValidateSet('install','build','dev')]
  [string]$Mode = 'build'
)
$ErrorActionPreference = 'Stop'
$pitProjectRoot = Split-Path -Parent $PSScriptRoot
$pitFrontendRoot = Join-Path $pitProjectRoot 'frontend'
$pitPreviousDirectory = (Get-Location).Path
$pitPnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue
$pitNodeCommand = Get-Command node -ErrorAction SilentlyContinue
$pitBundledPnpm = $null
if (!$pitPnpmCommand -and $pitNodeCommand) {
  $pitNodeRoot = Split-Path -Parent (Split-Path -Parent $pitNodeCommand.Source)
  $pitCandidate = Join-Path $pitNodeRoot 'node_modules\pnpm\bin\pnpm.cjs'
  if (Test-Path -LiteralPath $pitCandidate) { $pitBundledPnpm = $pitCandidate }
}
if (!$pitPnpmCommand -and !$pitBundledPnpm) {
  throw 'Install Node.js and pnpm 11.25.0 first. See README.md for frontend setup.'
}
$pitFrontendArgs = switch ($Mode) {
  'install' { @('install','--frozen-lockfile','--store-dir',(Join-Path $pitProjectRoot '.pnpm-store')) }
  'build' { @('run','build') }
  'dev' { @('run','dev') }
}
try {
  Set-Location -LiteralPath $pitFrontendRoot
  if ($pitPnpmCommand) { & $pitPnpmCommand.Source @pitFrontendArgs }
  else { & $pitNodeCommand.Source $pitBundledPnpm @pitFrontendArgs }
  $pitFrontendExit = $LASTEXITCODE
} finally {
  Set-Location -LiteralPath $pitPreviousDirectory
}
exit $pitFrontendExit
