param([ValidateRange(0,65535)][int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$logDir = Join-Path $env:LOCALAPPDATA "Vervision\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$readyFile = Join-Path $logDir "webui-$Port.json"
$stdoutLog = Join-Path $logDir "webui.log"
$stderrLog = Join-Path $logDir "webui-error.log"
$packageExe = Join-Path $projectRoot "vervision.exe"
$distDir = Join-Path $projectRoot "dist"
$versionedExe = $null
if (Test-Path -LiteralPath $distDir) {
  $versionedExe = Get-ChildItem -LiteralPath $distDir -Filter 'vervision-*.exe' -File |
    Where-Object BaseName -Match '^vervision-\d+\.\d+\.\d+$' |
    Sort-Object { [version]($_.BaseName -replace '^vervision-', '') } -Descending | Select-Object -First 1
}
$executable = $null
$prefixArgs = @()
foreach ($candidate in @($packageExe, $versionedExe.FullName, (Join-Path $env:LOCALAPPDATA 'Programs\Vervision\vervision.exe'))) {
  if ($candidate -and (Test-Path -LiteralPath $candidate)) { $executable = $candidate; break }
}
if (-not $executable -and (Test-Path -LiteralPath (Join-Path $projectRoot 'vervision'))) {
  $executable = (Get-Command python -ErrorAction Stop).Source
  $prefixArgs = @('-m','vervision')
}
if (-not $executable) { throw 'Vervision executable was not found. Run install.ps1 or keep the dist directory.' }
Push-Location $projectRoot
try { $expectedVersion = (& $executable @prefixArgs --version | Out-String).Trim() }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw "Cannot run $executable --version" }
function Test-Ready([string]$address) {
  if ($address -notmatch '^http://127\.0\.0\.1:\d+/$') { return $false }
  try {
    $health = Invoke-RestMethod -Uri "${address}api/health" -TimeoutSec 1
    return $health.service -eq 'vervision' -and $health.version -eq $expectedVersion
  } catch { return $false }
}
function Show-Reader([string]$address) {
  Write-Host "Vervision $expectedVersion is ready: $address"
  if (-not $NoBrowser) { Start-Process $address }
}
if (Test-Path -LiteralPath $readyFile) {
  try {
    $previous = Get-Content -LiteralPath $readyFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if (Test-Ready $previous.url) { Show-Reader $previous.url; exit 0 }
  } catch { }
  Remove-Item -LiteralPath $readyFile -Force
}
$requestedUrl = "http://127.0.0.1:$Port/"
if ($Port -ne 0 -and (Test-Ready $requestedUrl)) { Show-Reader $requestedUrl; exit 0 }
$arguments = @($prefixArgs) + @('gui','--host','127.0.0.1','--port',"$Port",'--no-browser','--ready-file',('"' + $readyFile + '"'))
$process = Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
$deadline = [DateTime]::UtcNow.AddSeconds(30)
while ([DateTime]::UtcNow -lt $deadline) {
  if (Test-Path -LiteralPath $readyFile) {
    try {
      $ready = Get-Content -LiteralPath $readyFile -Raw -Encoding UTF8 | ConvertFrom-Json
      if (Test-Ready $ready.url) { Show-Reader $ready.url; exit 0 }
    } catch { }
  }
  if ($process.HasExited) {
    $detail = Get-Content -LiteralPath $stderrLog -Tail 12 -Encoding UTF8 -ErrorAction SilentlyContinue
    throw "Vervision exited (code $($process.ExitCode)). $($detail -join [Environment]::NewLine) See: $stderrLog"
  }
  Start-Sleep -Milliseconds 250
}
throw "Vervision did not become ready within 30 seconds. See: $stderrLog and $stdoutLog"
