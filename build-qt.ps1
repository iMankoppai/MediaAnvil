$ErrorActionPreference = 'Stop'
$qtPython = Join-Path $PSScriptRoot '.build-venv-windows\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $qtPython)) { throw '请使用官方 Windows Python 创建 .build-venv-windows 虚拟环境。' }
$ffmpegDirectory = Join-Path $PSScriptRoot 'vendor\ffmpeg'
$ffmpegFiles = @('ffmpeg.exe', 'ffplay.exe')
if ($ffmpegFiles | Where-Object { -not (Test-Path -LiteralPath (Join-Path $ffmpegDirectory $_)) }) {
    Write-Host '正在下载并校验 FFmpeg/FFplay…' -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot 'tools\download_ffmpeg.ps1')
}
& $qtPython -c 'import PySide6.QtWidgets, PyInstaller, PIL, mutagen'
if ($LASTEXITCODE -ne 0) { throw '请先在该虚拟环境安装 requirements-build.txt。' }
$qtBuildArgs = @(
    '--noconfirm', '--clean', '--onedir', '--windowed',
    '--name', 'MediaAnvilQt', '--exclude-module', 'tkinter', '--exclude-module', 'tkinterdnd2',
    '--icon', (Join-Path $PSScriptRoot 'assets\mediaanvil-icon.png'),
    '--add-data', "$(Join-Path $PSScriptRoot 'assets\mediaanvil-icon.png');assets",
    '--add-data', "$(Join-Path $PSScriptRoot 'assets\qt');assets\qt",
    '--add-data', "$(Join-Path $PSScriptRoot 'README-Qt.md');.",
    '--add-data', "$(Join-Path $PSScriptRoot 'README-Qt.en.md');.",
    '--add-data', "$(Join-Path $PSScriptRoot 'USER_GUIDE.md');.",
    '--add-data', "$(Join-Path $PSScriptRoot 'USER_GUIDE.en.md');.",
    '--add-data', "$(Join-Path $PSScriptRoot 'LICENSE');.",
    '--add-data', "$(Join-Path $PSScriptRoot 'THIRD_PARTY_NOTICES.md');.",
    '--add-data', "$(Join-Path $PSScriptRoot 'licenses\qt');licenses\qt",
    '--add-binary', "$(Join-Path $PSScriptRoot 'vendor\ffmpeg\ffmpeg.exe');.",
    '--add-binary', "$(Join-Path $PSScriptRoot 'vendor\ffmpeg\ffplay.exe');.",
    (Join-Path $PSScriptRoot 'main_qt.py')
)
$qtBase = & $qtPython -c 'import sys; print(sys.base_prefix)'
if ($LASTEXITCODE -ne 0) { throw '无法确定 Windows Python 的运行目录。' }
$qtOriginalPath = $env:PATH
try {
    # The runner resets PATH inside the Python process. This is necessary when
    # the host injects unrelated runtime directories into Python child processes.
    $env:PATH = @(
        (Split-Path -Parent $qtPython), $qtBase,
        (Join-Path $qtBase 'DLLs'),
        (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot
    ) -join [IO.Path]::PathSeparator
    $qtBuildArgs += @('--distpath', (Join-Path $PSScriptRoot 'dist'),
                     '--workpath', (Join-Path $PSScriptRoot 'build'),
                     '--specpath', (Join-Path $PSScriptRoot 'build'))
    & $qtPython (Join-Path $PSScriptRoot 'tools\run_qt_pyinstaller.py') @qtBuildArgs
    if ($LASTEXITCODE -ne 0) { throw 'Qt 版打包失败。' }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'USER_GUIDE.md') -Destination (Join-Path $PSScriptRoot 'dist\MediaAnvilQt\USER_GUIDE.md') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'USER_GUIDE.en.md') -Destination (Join-Path $PSScriptRoot 'dist\MediaAnvilQt\USER_GUIDE.en.md') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README-Qt.md') -Destination (Join-Path $PSScriptRoot 'dist\MediaAnvilQt\README-Qt.md') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README-Qt.en.md') -Destination (Join-Path $PSScriptRoot 'dist\MediaAnvilQt\README-Qt.en.md') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'LICENSE') -Destination (Join-Path $PSScriptRoot 'dist\MediaAnvilQt\LICENSE') -Force
    # The user guide points at THIRD_PARTY_NOTICES.md and licenses/ inside the
    # release folder, so both must be visible next to the executable.
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'THIRD_PARTY_NOTICES.md') -Destination (Join-Path $PSScriptRoot 'dist\MediaAnvilQt\THIRD_PARTY_NOTICES.md') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'licenses\qt') -Destination (Join-Path $PSScriptRoot 'dist\MediaAnvilQt\licenses\qt') -Recurse -Force
    & $qtPython (Join-Path $PSScriptRoot 'tools\verify_qt_build.py')
    if ($LASTEXITCODE -ne 0) { throw 'Qt 成品自检失败，不能交付。' }
} finally {
    $env:PATH = $qtOriginalPath
}
Write-Host '完成：dist\MediaAnvilQt\MediaAnvilQt.exe（请保留整个文件夹）'
