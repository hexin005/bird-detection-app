param([string]$Python = '', [int]$Port = 8008, [string]$ListenAddress = '127.0.0.1')
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
# FFmpeg：视频管线生成可播放视频必需。优先 BIRD_FFMPEG / PATH，
# 否则探测 winget 安装位置，避免因启动终端 PATH 不同而"缺少 FFmpeg"。
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -and -not $env:BIRD_FFMPEG) {
    $links = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\ffmpeg.exe'
    if (Test-Path $links) {
        $env:BIRD_FFMPEG = $links
    } else {
        $pkgs = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
        if (Test-Path $pkgs) {
            $found = Get-ChildItem $pkgs -Recurse -Filter 'ffmpeg.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) { $env:BIRD_FFMPEG = $found.FullName }
        }
    }
}
if ($env:BIRD_FFMPEG) {
    Write-Host ('FFmpeg: ' + $env:BIRD_FFMPEG)
} elseif (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host ('FFmpeg: ' + (Get-Command ffmpeg).Source)
} else {
    Write-Host 'FFmpeg: 未找到 —— 视频分析将无法生成可播放视频（可 winget install ffmpeg）'
}
if (-not $Python) {
    # 优先使用项目内虚拟环境，其次退回系统 python
    $LocalPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    if (Test-Path $LocalPython) { $Python = $LocalPython }
    else { $Python = 'python' }
}
& $Python -c "from backend.config import Settings; s=Settings.load(); print('Account:', s.username); print('Password:', s.password); print('Video:',s.video_path); print('Model:',s.model_path)"
if ($LASTEXITCODE -ne 0) { throw 'Python initialization failed' }
Write-Host "MVP: http://127.0.0.1:$Port"
& $Python -m uvicorn backend.main:create_app --factory --host $ListenAddress --port $Port --no-access-log
