$ErrorActionPreference = 'Stop'
$galleryRoot = $PSScriptRoot
$config = Get-Content -LiteralPath (Join-Path $galleryRoot 'local.json') -Raw | ConvertFrom-Json
$galleryPort = if ($config.port) { $config.port } else { 8189 }
try {
    $status = Invoke-RestMethod -Uri "http://127.0.0.1:$galleryPort/galleryout/library/api/health" -TimeoutSec 2
    if ($status.service -eq 'smartgallery-library') { Write-Output "SmartGallery is already running: http://127.0.0.1:$galleryPort/galleryout/"; exit 0 }
} catch { }
New-Item -ItemType Directory -Path $config.data_path -Force | Out-Null
$env:PYTHONUTF8 = '1'
$process = Start-Process -FilePath (Join-Path $galleryRoot '.venv\Scripts\python.exe') -ArgumentList @('-u', 'launch.py') -WorkingDirectory $galleryRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $config.data_path 'server.log') -RedirectStandardError (Join-Path $config.data_path 'server-error.log')
$process.Id | Set-Content -LiteralPath (Join-Path $config.data_path 'server.pid')
Write-Output "SmartGallery is starting: http://127.0.0.1:$galleryPort/galleryout/"
