#Requires -Version 7.2
param([string]$Plan = 'configs/calendar_sources_v0_1.json')
$ErrorActionPreference = 'Stop'
$pitRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pitSourcePlan = Get-Content -LiteralPath (Join-Path $pitRoot $Plan) -Raw | ConvertFrom-Json
if ($pitSourcePlan.protocol -ne 'calendar_source_capture_v0.1' -or $pitSourcePlan.sources.Count -gt 12 -or $pitSourcePlan.sources.Count -lt 1) { throw 'Unsupported source plan' }
$pitSeenSources = @{}
foreach ($pitSource in $pitSourcePlan.sources) {
  if ($pitSource.id -cnotmatch '^[a-z][a-z0-9_]{1,60}$' -or $pitSeenSources.ContainsKey($pitSource.id) -or $pitSource.url -cnotmatch '^https://vsdc\.vn/vi/ad/[0-9]+$') { throw 'Only uniquely named public VSDC notices are supported' }
  $pitSeenSources[$pitSource.id] = $true
}
$pitRunId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ-') + [guid]::NewGuid().ToString('N').Substring(0,8)
$pitOutput = Join-Path $pitRoot ('outputs\calendar-sources\' + $pitRunId)
$pitExpectedBase = [IO.Path]::GetFullPath((Join-Path $pitRoot 'outputs\calendar-sources'))
if ((Test-Path -LiteralPath $pitExpectedBase -PathType Leaf) -or ((Test-Path -LiteralPath $pitExpectedBase) -and (Get-Item -LiteralPath $pitExpectedBase).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) -or (Get-Item -LiteralPath (Join-Path $pitRoot 'outputs')).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Refusing redirected output path' }
New-Item -ItemType Directory -Path $pitOutput | Out-Null
$pitUtf8 = [Text.UTF8Encoding]::new($false)
function Write-PitJson($Path, $Value) { [IO.File]::WriteAllText($Path, (($Value | ConvertTo-Json -Depth 12) + "`n"), $pitUtf8) }
Copy-Item -LiteralPath (Join-Path $pitRoot $Plan) -Destination (Join-Path $pitOutput 'source_plan.json')
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $pitOutput 'capture-calendar-sources.ps1')
$pitHandler = [Net.Http.HttpClientHandler]::new()
$pitHandler.AllowAutoRedirect = $false
$pitHandler.UseCookies = $false
$pitClient = [Net.Http.HttpClient]::new($pitHandler)
$pitClient.Timeout = [TimeSpan]::FromSeconds(25)
$pitClient.DefaultRequestHeaders.UserAgent.ParseAdd('PiT-HAF-Research/0.1')
$pitStatuses = @()
try {
  foreach ($pitSource in $pitSourcePlan.sources) {
    $pitResponse = $null
    $pitInputStream = $null
    $pitMemory = [IO.MemoryStream]::new()
    $pitRow = [ordered]@{id=$pitSource.id;url=$pitSource.url;captured_at=[DateTime]::UtcNow.ToString('o');status='failed';certificate_verification_disabled=$false;automatic_retries=0;authentication_used=$false}
    try {
      $pitResponse = $pitClient.GetAsync($pitSource.url, [Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
      $pitRow.http_status = [int]$pitResponse.StatusCode
      if ([int]$pitResponse.StatusCode -ne 200 -or $null -ne $pitResponse.Content.Headers.ContentRange) { throw 'Require HTTP 200 and complete response without redirect' }
      $pitExpectedBytes = $pitResponse.Content.Headers.ContentLength
      if ($pitExpectedBytes -gt 8MB) { throw 'Source exceeds 8 MiB' }
      $pitInputStream = $pitResponse.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
      $pitBuffer = [byte[]]::new(16384)
      $pitBodyDeadline = [DateTime]::UtcNow.AddSeconds(25)
      while ($true) {
        if ([DateTime]::UtcNow -gt $pitBodyDeadline) { throw 'Source body deadline exceeded' }
        $pitRead = $pitInputStream.ReadAsync($pitBuffer, 0, $pitBuffer.Length).WaitAsync([TimeSpan]::FromSeconds(25)).GetAwaiter().GetResult()
        if ($pitRead -eq 0) { break }
        $pitMemory.Write($pitBuffer,0,$pitRead)
        if ($pitMemory.Length -gt 8MB) { throw 'Source exceeds 8 MiB' }
      }
      if ($null -ne $pitExpectedBytes -and $pitMemory.Length -ne $pitExpectedBytes) { throw 'Incomplete source body' }
      [IO.File]::WriteAllBytes((Join-Path $pitOutput ($pitSource.id + '.raw')), $pitMemory.ToArray())
      $pitRow.status = 'captured'
      $pitRow.bytes = $pitMemory.Length
      $pitRow.sha256 = (Get-FileHash -LiteralPath (Join-Path $pitOutput ($pitSource.id + '.raw')) -Algorithm SHA256).Hash.ToLowerInvariant()
      $pitRow.content_type = [string]$pitResponse.Content.Headers.ContentType
    } catch {
      $pitRow.error_type = $_.Exception.GetType().FullName
      $pitRow.error = $_.Exception.Message
    } finally {
      if ($null -ne $pitInputStream) { $pitInputStream.Dispose() }
      if ($null -ne $pitResponse) { $pitResponse.Dispose() }
      $pitMemory.Dispose()
    }
    Write-PitJson (Join-Path $pitOutput ($pitSource.id + '.json')) $pitRow
    $pitStatuses += $pitRow
  }
} finally { $pitClient.Dispose(); $pitHandler.Dispose() }
Write-PitJson (Join-Path $pitOutput 'manifest.json') @{protocol=$pitSourcePlan.protocol;sources=$pitStatuses;research_result=$false;engine='Windows .NET HttpClient default TLS verification';no_retries=$true}
$pitHashes = [ordered]@{}
Get-ChildItem -LiteralPath $pitOutput -File | Sort-Object Name | ForEach-Object { $pitHashes[$_.Name] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
Write-PitJson (Join-Path $pitOutput 'integrity.json') @{files=$pitHashes}
Write-Output $pitOutput
if (@($pitStatuses | Where-Object { $_.status -ne 'captured' }).Count -gt 0) { exit 2 }
