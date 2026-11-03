param(
    [Parameter(Mandatory=$true)][string]$ComfyPath,
    [string]$DataPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'SmartGallery-Data'),
    [string]$LibraryPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'Media-Library'),
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$comfyRoot = (Resolve-Path -LiteralPath $ComfyPath).Path
if (!(Test-Path -LiteralPath (Join-Path $comfyRoot 'main.py'))) { throw 'Choose the ComfyUI folder containing main.py.' }
if (!(Test-Path -LiteralPath (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'))) {
    & $Python -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE) { throw 'Could not create the gallery environment.' }
}
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -m pip install -r (Join-Path $PSScriptRoot 'requirements-agent.txt')
if ($LASTEXITCODE) { throw 'Could not install gallery dependencies.' }
$configPath = Join-Path $PSScriptRoot 'local.json'
if (!(Test-Path -LiteralPath $configPath)) {
    $settings = @{comfy_path=$comfyRoot; data_path=[IO.Path]::GetFullPath($DataPath); library_path=[IO.Path]::GetFullPath($LibraryPath); port=8189}
    $ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
    if ($ffprobe) { $settings.ffmpeg_directory = Split-Path $ffprobe.Source -Parent }
    $settings | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
}
$nodePath = Join-Path $comfyRoot 'custom_nodes\comfyui_smartgallery'
New-Item -ItemType Directory -Path $nodePath -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'integrations\comfyui_smartgallery\__init__.py') -Destination $nodePath -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'integrations\comfyui_smartgallery\prestartup_script.py') -Destination $nodePath -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'integrations\comfyui_smartgallery\web') -Destination $nodePath -Recurse -Force
@{gallery_path=$PSScriptRoot} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $nodePath 'gallery.local.json') -Encoding UTF8
Write-Output 'Installed. Run Start-SmartGallery.ps1 and restart ComfyUI to see its sidebar icon.'
