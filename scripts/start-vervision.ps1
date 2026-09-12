param(
  [int]$Port = 8765,
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$url = "http://127.0.0.1:$Port/"
$healthUrl = "${url}api/projects"

function Test-VervisionRunning {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 1
    $null = $response.Content | ConvertFrom-Json
    return $response.StatusCode -eq 200
  } catch {
    return $false
  }
}

if (Test-VervisionRunning) {
  if (-not $NoBrowser) { Start-Process $url }
  exit 0
}

$installedExe = Join-Path $env:LOCALAPPDATA "Programs\Vervision\vervision.exe"
$packageExe = Join-Path $projectRoot "vervision.exe"
$versionedExe = Get-ChildItem -LiteralPath (Join-Path $projectRoot "dist") -Filter "vervision-*.exe" -File -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
$legacyExe = Join-Path $projectRoot "dist\vervision.exe"

$executable = $null
$arguments = @()
foreach ($candidate in @($packageExe, $versionedExe.FullName, $installedExe, $legacyExe)) {
  if ($candidate -and (Test-Path -LiteralPath $candidate)) {
    $executable = $candidate
    $arguments = @("gui", "--host", "127.0.0.1", "--port", "$Port", "--no-browser")
    break
  }
}

if (-not $executable) {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python -and (Test-Path -LiteralPath (Join-Path $projectRoot "vervision"))) {
    $executable = $python.Source
    $arguments = @("-m", "vervision", "gui", "--host", "127.0.0.1", "--port", "$Port", "--no-browser")
  }
}

if (-not $executable) {
  throw "Vervision executable was not found. Run install.ps1 or keep the dist directory."
}

$logDir = Join-Path $env:LOCALAPPDATA "Vervision\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdoutLog = Join-Path $logDir "webui.log"
$stderrLog = Join-Path $logDir "webui-error.log"
$process = Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $projectRoot `
  -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru

for ($attempt = 0; $attempt -lt 40; $attempt++) {
  if (Test-VervisionRunning) {
    if (-not $NoBrowser) { Start-Process $url }
    exit 0
  }
  if ($process.HasExited) {
    throw "Vervision exited before startup. See: $stderrLog"
  }
  Start-Sleep -Milliseconds 250
}

throw "Vervision did not start within 10 seconds. See: $stderrLog"
