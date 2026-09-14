param(
  [string]$InstallDir = "$env:LOCALAPPDATA\Programs\Vervision",
  [switch]$NoShellIntegration
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceExe = Join-Path $scriptRoot "vervision.exe"
if (-not (Test-Path -LiteralPath $sourceExe)) {
  throw "vervision.exe is missing beside this installer."
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -LiteralPath $sourceExe -Destination (Join-Path $InstallDir "vervision.exe") -Force
Copy-Item -LiteralPath (Join-Path $scriptRoot "start-vervision.cmd") -Destination $InstallDir -Force
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "scripts") | Out-Null
Copy-Item -LiteralPath (Join-Path $scriptRoot "scripts\start-vervision.ps1") -Destination (Join-Path $InstallDir "scripts") -Force
Copy-Item -LiteralPath (Join-Path $scriptRoot "templates") -Destination $InstallDir -Recurse -Force
if (Test-Path -LiteralPath (Join-Path $scriptRoot "assets")) {
  Copy-Item -LiteralPath (Join-Path $scriptRoot "assets") -Destination $InstallDir -Recurse -Force
}
$handoffExe = Join-Path $InstallDir "handoff.exe"
if (Test-Path -LiteralPath $handoffExe) { Remove-Item -LiteralPath $handoffExe -Force }
New-Item -ItemType HardLink -Path $handoffExe -Target (Join-Path $InstallDir "vervision.exe") | Out-Null

if (-not $NoShellIntegration) {
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if (($userPath -split ';') -notcontains $InstallDir) {
    [Environment]::SetEnvironmentVariable("Path", (($userPath.TrimEnd(';') + ';' + $InstallDir).Trim(';')), "User")
  }

  $startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut((Join-Path $startMenu "Vervision.lnk"))
  $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
  $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $InstallDir "scripts\start-vervision.ps1") + '"'
  $shortcut.WorkingDirectory = $InstallDir
  $shortcut.Description = "Vervision read-only project browser"
  $shortcut.Save()
}

Write-Host "Vervision installed to $InstallDir"
Write-Host "Open it from the Start menu, or start a new terminal and run: handoff --help"
