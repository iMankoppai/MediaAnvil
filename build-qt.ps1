$ErrorActionPreference = 'Stop'
$qtPython = Join-Path $PSScriptRoot '.build-venv-windows\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $qtPython)) { throw '请使用官方 Windows Python 创建 .build-venv-windows 虚拟环境。' }
$icuDirectory = Join-Path $PSScriptRoot 'vendor\icu'
foreach ($required in @('icuuc.dll', 'icudt78.dll', 'icuin78.dll')) {
    if (-not (Test-Path -LiteralPath (Join-Path $icuDirectory $required))) {
        throw "缺少 Qt 所需的 ICU 运行时：$required。请先运行 .\tools\download_icu.ps1。"
    }
}
& $qtPython -c 'import PySide6.QtWidgets, PyInstaller, PIL, mutagen'
if ($LASTEXITCODE -ne 0) { throw '请先在该虚拟环境安装 requirements-qt.txt 和 pyinstaller。' }
$qtBuildArgs = @(
    '--noconfirm', '--clean', '--onedir', '--windowed',
    '--name', 'MediaAnvilQt', '--exclude-module', 'tkinter', '--exclude-module', 'tkinterdnd2',
    '--icon', (Join-Path $PSScriptRoot 'assets\mediaanvil-icon.png'),
    '--add-data', "$(Join-Path $PSScriptRoot 'assets\mediaanvil-icon.png');assets",
    '--add-data', "$(Join-Path $PSScriptRoot 'assets\qt');assets\qt",
    '--add-data', "$(Join-Path $PSScriptRoot 'README-Qt.md');.",
    '--add-data', "$(Join-Path $PSScriptRoot 'USER_GUIDE.md');.",
    '--add-data', "$(Join-Path $PSScriptRoot 'THIRD_PARTY_NOTICES.md');.",
    '--add-data', "$(Join-Path $PSScriptRoot 'licenses\qt');licenses\qt",
    '--add-data', "$(Join-Path $PSScriptRoot 'licenses\ICU-LICENSE.txt');licenses",
    '--add-binary', "$(Join-Path $PSScriptRoot 'vendor\ffmpeg\ffmpeg.exe');.",
    '--add-binary', "$(Join-Path $PSScriptRoot 'vendor\ffmpeg\ffplay.exe');.",
    # Qt6Core.dll is collected into _internal\PySide6. Keep ICU beside it so
    # Windows resolves the dependency on ordinary double-click startup.
    '--add-binary', "$(Join-Path $icuDirectory 'icuuc.dll');PySide6",
    '--add-binary', "$(Join-Path $icuDirectory 'icudt78.dll');PySide6",
    '--add-binary', "$(Join-Path $icuDirectory 'icuin78.dll');PySide6",
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
    & $qtPython (Join-Path $PSScriptRoot 'tools\verify_qt_build.py')
    if ($LASTEXITCODE -ne 0) { throw 'Qt 成品自检失败，不能交付。' }
} finally {
    $env:PATH = $qtOriginalPath
}
Write-Host '完成：dist\MediaAnvilQt\MediaAnvilQt.exe（请保留整个文件夹）'
