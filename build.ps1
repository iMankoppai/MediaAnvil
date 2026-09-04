$ErrorActionPreference = "Stop"

$venvDir = Join-Path $PSScriptRoot ".build-venv"
$ffmpegPath = Join-Path $PSScriptRoot "vendor\ffmpeg\ffmpeg.exe"
$ffplayPath = Join-Path $PSScriptRoot "vendor\ffmpeg\ffplay.exe"
$ffmpegDownloadScript = Join-Path $PSScriptRoot "tools\download_ffmpeg.ps1"

if (-not (Test-Path $venvDir)) {
    Write-Host "Creating isolated build environment..."
    # System packages allow MSYS2 Python to reuse its official Pillow build;
    # regular Windows Python still installs missing packages from requirements.
    python -m venv --system-site-packages $venvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the isolated build environment."
    }
}

$windowsPython = Join-Path $venvDir "Scripts\python.exe"
$msysPython = Join-Path $venvDir "bin\python.exe"
if (Test-Path $windowsPython) {
    $buildPython = $windowsPython
} elseif (Test-Path $msysPython) {
    $buildPython = $msysPython
} else {
    throw "Python executable was not found in the build environment."
}

& $buildPython -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller in the isolated environment..."
    & $buildPython -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install PyInstaller."
    }
}

& $buildPython -c "import mutagen; from PIL import Image, ImageTk" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing application dependencies..."
    & $buildPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install application dependencies."
    }
}

Write-Host "Building Sub2LRC.exe..."
if (-not (Test-Path $ffmpegPath) -or -not (Test-Path $ffplayPath)) {
    Write-Host "Downloading verified FFmpeg/FFplay for the standalone EXE..."
    & powershell -ExecutionPolicy Bypass -File $ffmpegDownloadScript
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $ffmpegPath)) {
        throw "Failed to prepare the bundled FFmpeg/FFplay executables."
    }
}

$pyinstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", "Sub2LRC",
    "--add-binary", "$ffmpegPath;."
    "--add-binary", "$ffplayPath;."
    "--add-data", "$(Join-Path $PSScriptRoot 'THIRD_PARTY_NOTICES.md');."
    (Join-Path $PSScriptRoot "main.py")
)
& $buildPython @pyinstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "Build complete: dist\Sub2LRC.exe" -ForegroundColor Green
