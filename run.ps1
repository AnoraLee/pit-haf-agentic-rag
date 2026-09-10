param([ValidateSet('test','lint','app','data')][string]$Task = 'app')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) { throw 'Missing .venv. See README.md for setup.' }
switch ($Task) {
  'test' { & $pythonExe -m pytest -q }
  'lint' { & $pythonExe -m ruff check app.py src tests }
  'app' { & $pythonExe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false }
  'data' { & $pythonExe -m pit_haf.data.vnstock_provider --symbol FPT --start 2024-01-01 --end 2024-06-30 }
}
exit $LASTEXITCODE
