$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Join-Path $projectRoot "bin\BalloonTypingGame.exe"

if (-not (Test-Path $exePath)) {
    throw "找不到可执行文件: $exePath。请先运行 build_balloon_typing_game.ps1"
}

Start-Process -FilePath $exePath
Write-Host "已启动: $exePath"
