$ErrorActionPreference = "Stop"
$installDir = "$env:LOCALAPPDATA\Programs\Vervision"
$startLink = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Vervision.lnk"
if (Test-Path -LiteralPath $startLink) { Remove-Item -LiteralPath $startLink -Force }
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$nextPath = (($userPath -split ';') | Where-Object { $_ -and $_ -ne $installDir }) -join ';'
[Environment]::SetEnvironmentVariable("Path", $nextPath, "User")
if (Test-Path -LiteralPath $installDir) { Remove-Item -LiteralPath $installDir -Recurse -Force }
Write-Host "Vervision application files were removed. Project .handoff data and local index data were preserved."
