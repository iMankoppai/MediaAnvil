$ErrorActionPreference = "Stop"

$version = "9.0.1"
$expectedSha256 = "fec81ae03971d9dd4be3ebe02e263bd2ec1d789483f931bdba5f5715e65da2e9"
$downloadUrl = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-$version-essentials_build.zip"
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
