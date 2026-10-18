param(
  [ValidateSet('test','lint','app','streamlit','frontend-install','frontend-build','frontend-dev','data','pit-demo','doctor','pilot-data','corpus-merge','corpus-coverage','llm-pilot','quote-audit')]
  [string]$Task = 'app',
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$TaskArgs
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) { throw 'Missing .venv. See README.md for setup.' }
switch ($Task) {
  'test' {
    $pitTestRoot = Join-Path $PSScriptRoot 'outputs\test-tmp'
    $pitRunTemp = Join-Path $pitTestRoot ([guid]::NewGuid().ToString('N'))
    if (Test-Path -LiteralPath $pitRunTemp) { throw 'Test temporary directory already exists.' }
    New-Item -ItemType Directory -Path $pitRunTemp -Force | Out-Null
    $pitOriginalTemp = $env:TEMP
    $pitOriginalTmp = $env:TMP
    try {
      $env:TEMP = $pitRunTemp
      $env:TMP = $pitRunTemp
      & $pythonExe -m pytest -q --basetemp (Join-Path $pitRunTemp 'pytest') -p no:cacheprovider @TaskArgs
    } finally {
      $env:TEMP = $pitOriginalTemp
      $env:TMP = $pitOriginalTmp
    }
  }
  'lint' { & $pythonExe -m ruff check app.py src tests }
  'app' {
    if (!(Test-Path -LiteralPath (Join-Path $PSScriptRoot 'frontend\dist\index.html'))) {
      throw 'Missing frontend build. Run pnpm install --frozen-lockfile and pnpm build inside frontend. See README.md.'
    }
    & $pythonExe -m uvicorn pit_haf.ui.api:app --host 127.0.0.1 --port 8501 @TaskArgs
  }
  'streamlit' { & $pythonExe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502 --browser.gatherUsageStats false }
  'frontend-install' { & (Join-Path $PSScriptRoot 'scripts\frontend.ps1') -Mode install }
  'frontend-build' { & (Join-Path $PSScriptRoot 'scripts\frontend.ps1') -Mode build }
  'frontend-dev' { & (Join-Path $PSScriptRoot 'scripts\frontend.ps1') -Mode dev }
  'data' { & $pythonExe -m pit_haf.data.vnstock_provider --symbol FPT --start 2024-01-01 --end 2024-06-30 }
  'pit-demo' { & $pythonExe -m pit_haf.data.point_in_time --demo }
  'doctor' { & $pythonExe -m pit_haf.research.doctor @TaskArgs }
  'pilot-data' { & $pythonExe -m pit_haf.data.pilot @TaskArgs }
  'corpus-coverage' { & $pythonExe -m pit_haf.data.coverage @TaskArgs }
  'corpus-merge' { & $pythonExe -m pit_haf.data.corpus @TaskArgs }
  'llm-pilot' { & $pythonExe -m pit_haf.llm.pilot @TaskArgs }
  'quote-audit' { & $pythonExe -m pit_haf.research.quote_replay @TaskArgs }
}
exit $LASTEXITCODE
