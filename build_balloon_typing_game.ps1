$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$entryFile = Join-Path $projectRoot "balloon_typing_game.py"
$assetsDir = Join-Path $projectRoot "assets"
$saveFile = Join-Path $projectRoot "balloon_typing_save.json"
$binDir = Join-Path $projectRoot "bin"
$buildDir = Join-Path $projectRoot "build"
$specDir = $buildDir
$exeName = "BalloonTypingGame"

if (-not (Test-Path $entryFile)) {
    throw "Missing entry file: $entryFile"
}

if (-not (Test-Path $assetsDir)) {
    throw "Missing assets directory: $assetsDir"
}

New-Item -ItemType Directory -Force $binDir | Out-Null
New-Item -ItemType Directory -Force $buildDir | Out-Null

& python -m py_compile $entryFile
if ($LASTEXITCODE -ne 0) {
    throw "Python syntax check failed"
}

$pyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onefile",
    "--name", $exeName,
    "--distpath", $binDir,
    "--workpath", $buildDir,
    "--specpath", $specDir,
    "--add-data", "$assetsDir;assets",
    $entryFile
)

& python @pyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed"
}

$targetSaveFile = Join-Path $binDir "balloon_typing_save.json"
if (Test-Path $saveFile) {
    Copy-Item -Force $saveFile $targetSaveFile
}

Write-Host "Build completed: $(Join-Path $binDir ($exeName + '.exe'))"
