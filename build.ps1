$ErrorActionPreference = "Stop"

$venvDir = Join-Path $PSScriptRoot ".build-venv-windows"
$ffmpegPath = Join-Path $PSScriptRoot "vendor\ffmpeg\ffmpeg.exe"
$ffplayPath = Join-Path $PSScriptRoot "vendor\ffmpeg\ffplay.exe"
$ffmpegDownloadScript = Join-Path $PSScriptRoot "tools\download_ffmpeg.ps1"

# Build the Windows GUI with native MSVC CPython. An MSYS2/MinGW Python can
# create an EXE, but its Tk window integration is not equivalent to the
# standard Windows runtime and can behave poorly during move/resize handling.
$pythonCandidates = @()
$pythonManagerShim = Join-Path $env:LOCALAPPDATA "Python\bin\python.exe"
if (Test-Path $pythonManagerShim) {
    $pythonCandidates += $pythonManagerShim
}
$pythonCandidates += @(
    Get-Command python -All -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty Source
)

$basePython = $null
foreach ($candidate in ($pythonCandidates | Select-Object -Unique)) {
    & $candidate -c "import sys; raise SystemExit(0 if sys.platform == 'win32' and 'MSC' in sys.version else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $basePython = $candidate
        break
    }
}
if (-not $basePython) {
    throw "A native Windows CPython (MSVC build) is required. Install Python from python.org or the Windows Python Install Manager."
}

if (-not (Test-Path $venvDir)) {
    Write-Host "Creating isolated native Windows build environment with $basePython..."
    & $basePython -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the isolated build environment."
    }
}

$windowsPython = Join-Path $venvDir "Scripts\python.exe"
if (Test-Path $windowsPython) {
    $buildPython = $windowsPython
} else {
    throw "Python executable was not found in the build environment."
}

& $buildPython -c "import sys; raise SystemExit(0 if sys.platform == 'win32' and 'MSC' in sys.version else 1)" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "The build environment is not using native Windows CPython. Remove .build-venv-windows and rebuild."
}

$previousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $buildPython -c "import PyInstaller" 2>$null
$pyinstallerImportExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorPreference
if ($pyinstallerImportExitCode -ne 0) {
    Write-Host "Installing PyInstaller in the isolated environment..."
    & $buildPython -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install PyInstaller."
    }
}

$previousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $buildPython -c "import mutagen; from PIL import Image, ImageTk" 2>$null
$dependencyImportExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorPreference
if ($dependencyImportExitCode -ne 0) {
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
