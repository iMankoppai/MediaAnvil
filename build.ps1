$ErrorActionPreference = "Stop"

$venvDir = Join-Path $PSScriptRoot ".build-venv"

if (-not (Test-Path $venvDir)) {
    Write-Host "Creating isolated build environment..."
    python -m venv $venvDir
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

& $buildPython -c "import mutagen" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing application dependencies..."
    & $buildPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install application dependencies."
    }
}

Write-Host "Building Sub2LRC.exe..."
& $buildPython -m PyInstaller --noconfirm --clean --onefile --windowed --name Sub2LRC (Join-Path $PSScriptRoot "main.py")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "Build complete: dist\Sub2LRC.exe" -ForegroundColor Green
