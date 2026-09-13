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
  $shortcut.TargetPath = Join-Path $InstallDir "vervision.exe"
  $shortcut.Arguments = "gui"
  $shortcut.WorkingDirectory = $env:USERPROFILE
  $shortcut.Description = "Vervision project handoff manager"
  $shortcut.Save()
}

Write-Host "Vervision installed to $InstallDir"
Write-Host "Open it from the Start menu, or start a new terminal and run: handoff --help"
