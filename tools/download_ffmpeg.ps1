$ErrorActionPreference = "Stop"

$version = "9.0.2"
$expectedSha256 = "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba"
# 下载源固化在本仓库的 Release 里，而不是直接指向 gyan.dev。
# gyan.dev 会在新版发布时下架旧版包（9.0.1 就是这样失效并把 CI 弄红的），
# 本仓库的 Release 资产不会消失，所以钉住的版本不会再失效，SHA-256 校验也照旧保留。
# 升级 FFmpeg：运行 .github/workflows/vendor-ffmpeg.yml 工作流，它会下载、校验并
# 固化新版本，然后在 Job Summary 里给出这里该改成的三行内容。
$downloadUrl = "https://github.com/iMankoppai/MediaAnvil/releases/download/ffmpeg-vendor-$version/ffmpeg-$version-essentials_build.zip"
$vendorDirectory = Join-Path (Split-Path $PSScriptRoot -Parent) "vendor\ffmpeg"
$ffmpegDestination = Join-Path $vendorDirectory "ffmpeg.exe"
$ffplayDestination = Join-Path $vendorDirectory "ffplay.exe"
$temporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("sub2lrc-ffmpeg-" + [guid]::NewGuid())
$archive = Join-Path $temporaryDirectory "ffmpeg.zip"
$expanded = Join-Path $temporaryDirectory "expanded"

New-Item -ItemType Directory -Path $temporaryDirectory -Force | Out-Null
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $archive
    $actualSha256 = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $expectedSha256) {
        throw "FFmpeg download checksum mismatch. Expected $expectedSha256, got $actualSha256."
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $expanded -Force
    $ffmpegExecutable = Get-ChildItem -LiteralPath $expanded -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
    $ffplayExecutable = Get-ChildItem -LiteralPath $expanded -Filter "ffplay.exe" -Recurse | Select-Object -First 1
    if (-not $ffmpegExecutable -or -not $ffplayExecutable) {
        throw "ffmpeg.exe or ffplay.exe was not found in the verified archive."
    }
    New-Item -ItemType Directory -Path $vendorDirectory -Force | Out-Null
    Copy-Item -LiteralPath $ffmpegExecutable.FullName -Destination $ffmpegDestination -Force
    Copy-Item -LiteralPath $ffplayExecutable.FullName -Destination $ffplayDestination -Force
    Write-Host "Verified FFmpeg/FFplay $version prepared in: $vendorDirectory" -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $temporaryDirectory) {
        Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
    }
}
