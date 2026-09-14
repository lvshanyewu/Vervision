$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) { python -m pip install --disable-pip-version-check "pyinstaller>=6.10" }
$releaseVersion = python -c "from vervision import __version__; print(__version__)"
if ($LASTEXITCODE -ne 0) { throw "Cannot determine release version" }
$packageDist = Join-Path $projectRoot "build\packaging-dist"
$packageWork = Join-Path $projectRoot "build\pyinstaller"
$staticPath = Join-Path $projectRoot "vervision\static"
function Remove-BuildDirectory([string]$target) {
  $resolvedTarget = [IO.Path]::GetFullPath($target)
  $buildRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot "build")) + [IO.Path]::DirectorySeparatorChar
  if (-not $resolvedTarget.StartsWith($buildRoot, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe build cleanup path: $resolvedTarget" }
  if (Test-Path -LiteralPath $resolvedTarget) { Remove-Item -LiteralPath $resolvedTarget -Recurse -Force }
}
Remove-BuildDirectory $packageDist
python -m PyInstaller --noconfirm --clean --onefile --name vervision --paths "." --distpath $packageDist --workpath $packageWork --specpath $packageWork --add-data "$staticPath;vervision\static" "scripts\entry.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
$builtExe = Join-Path $packageDist "vervision.exe"
if (-not (Test-Path -LiteralPath $builtExe)) { throw "Built executable was not found: $builtExe" }

$releaseDir = Join-Path $projectRoot "build\release\Vervision-$releaseVersion-windows-x64"
Remove-BuildDirectory $releaseDir
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
Copy-Item -LiteralPath $builtExe -Destination (Join-Path $releaseDir "vervision.exe")
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\install.ps1") -Destination $releaseDir
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\uninstall.ps1") -Destination $releaseDir
Copy-Item -LiteralPath (Join-Path $projectRoot "start-vervision.cmd") -Destination $releaseDir
New-Item -ItemType Directory -Force -Path (Join-Path $releaseDir "scripts") | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\start-vervision.ps1") -Destination (Join-Path $releaseDir "scripts")
Copy-Item -LiteralPath (Join-Path $projectRoot "templates") -Destination $releaseDir -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $releaseDir
if (Test-Path -LiteralPath (Join-Path $projectRoot "assets\icon.png")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $releaseDir "assets") | Out-Null
  Copy-Item -LiteralPath (Join-Path $projectRoot "assets\icon.png") -Destination (Join-Path $releaseDir "assets")
}
Copy-Item -LiteralPath (Join-Path $projectRoot "FORMAT.md") -Destination $releaseDir
Copy-Item -LiteralPath (Join-Path $projectRoot "ZEN.md") -Destination $releaseDir
Copy-Item -LiteralPath (Join-Path $projectRoot "CHANGELOG.md") -Destination $releaseDir
Compress-Archive -LiteralPath $releaseDir -DestinationPath (Join-Path $projectRoot "dist\Vervision-$releaseVersion-windows-x64.zip") -Force
$versionedExe = Join-Path $projectRoot "dist\vervision-$releaseVersion.exe"
try {
  Copy-Item -LiteralPath $builtExe -Destination $versionedExe -Force
} catch [System.IO.IOException] {
  Write-Warning "$versionedExe is running and could not be replaced. The ZIP contains the new build."
}
Write-Host "Release created at dist\Vervision-$releaseVersion-windows-x64.zip"
