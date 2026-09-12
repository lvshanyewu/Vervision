$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

python -m pip install --disable-pip-version-check "pyinstaller>=6.10"
$packageDist = Join-Path $projectRoot "build\packaging-dist"
$packageWork = Join-Path $projectRoot "build\pyinstaller"
$staticPath = Join-Path $projectRoot "vervision\static"
if (Test-Path -LiteralPath $packageDist) { Remove-Item -LiteralPath $packageDist -Recurse -Force }
python -m PyInstaller --noconfirm --clean --onefile --name vervision --paths "." --distpath $packageDist --workpath $packageWork --specpath $packageWork --add-data "$staticPath;vervision\static" "scripts\entry.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
$builtExe = Join-Path $packageDist "vervision.exe"
if (-not (Test-Path -LiteralPath $builtExe)) { throw "Built executable was not found: $builtExe" }

$releaseDir = Join-Path $projectRoot "build\release\Vervision-0.2.1-windows-x64"
if (Test-Path -LiteralPath $releaseDir) { Remove-Item -LiteralPath $releaseDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
Copy-Item -LiteralPath $builtExe -Destination (Join-Path $releaseDir "vervision.exe")
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\install.ps1") -Destination $releaseDir
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\uninstall.ps1") -Destination $releaseDir
Copy-Item -LiteralPath (Join-Path $projectRoot "start-vervision.cmd") -Destination $releaseDir
New-Item -ItemType Directory -Force -Path (Join-Path $releaseDir "scripts") | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\start-vervision.ps1") -Destination (Join-Path $releaseDir "scripts")
Copy-Item -LiteralPath (Join-Path $projectRoot "templates") -Destination $releaseDir -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $releaseDir
if (Test-Path -LiteralPath (Join-Path $projectRoot "icon.png")) {
  Copy-Item -LiteralPath (Join-Path $projectRoot "icon.png") -Destination $releaseDir
}
Compress-Archive -LiteralPath $releaseDir -DestinationPath (Join-Path $projectRoot "dist\Vervision-0.2.1-windows-x64.zip") -Force
$versionedExe = Join-Path $projectRoot "dist\vervision-0.2.1.exe"
try {
  Copy-Item -LiteralPath $builtExe -Destination $versionedExe -Force
} catch [System.IO.IOException] {
  Write-Warning "$versionedExe is running and could not be replaced. The ZIP contains the new build."
}
Write-Host "Release created at dist\Vervision-0.2.1-windows-x64.zip"
