param([string]$Python = '', [int]$Port = 8008, [string]$ListenAddress = '127.0.0.1')
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
if (-not $Python) {
    $LocalPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    $ExistingPython = Join-Path (Split-Path -Parent $ProjectRoot) 'bird-detection-web\backend\.venv\Scripts\python.exe'
    if (Test-Path $LocalPython) { $Python = $LocalPython }
    elseif (Test-Path $ExistingPython) { $Python = $ExistingPython }
    else { $Python = 'python' }
}
& $Python -c "from backend.config import Settings; s=Settings.load(); print('Account:', s.username); print('Password:', s.password); print('Video:',s.video_path); print('Model:',s.model_path)"
if ($LASTEXITCODE -ne 0) { throw 'Python initialization failed' }
Write-Host "MVP: http://127.0.0.1:$Port"
& $Python -m uvicorn backend.main:create_app --factory --host $ListenAddress --port $Port --no-access-log
