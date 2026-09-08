$ErrorActionPreference = 'Stop'

$version = '78.3'
$expectedSha256 = '446b671f9437227daa79e221d4521d75793f9ecd65ac44c06e34dd848f201ac2'
$downloadUrl = "https://github.com/unicode-org/icu/releases/download/release-$version/icu4c-$version-Win64-MSVC2022.zip"
$vendorDirectory = Join-Path (Split-Path $PSScriptRoot -Parent) 'vendor\icu'
$licenseDirectory = Join-Path (Split-Path $PSScriptRoot -Parent) 'licenses'
$temporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("mediaanvil-icu-" + [guid]::NewGuid())
$archive = Join-Path $temporaryDirectory 'icu.zip'
$expanded = Join-Path $temporaryDirectory 'expanded'

New-Item -ItemType Directory -Path $temporaryDirectory -Force | Out-Null
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $archive
    $actualSha256 = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $expectedSha256) {
        throw "ICU download checksum mismatch. Expected $expectedSha256, got $actualSha256."
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $expanded -Force
    $binDirectory = Join-Path $expanded 'bin64'
    foreach ($name in @('icudt78.dll', 'icuin78.dll', 'icuuc78.dll')) {
        if (-not (Test-Path -LiteralPath (Join-Path $binDirectory $name))) {
            throw "Verified ICU archive did not contain $name."
        }
    }
    New-Item -ItemType Directory -Path $vendorDirectory -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $binDirectory 'icudt78.dll') -Destination (Join-Path $vendorDirectory 'icudt78.dll') -Force
    Copy-Item -LiteralPath (Join-Path $binDirectory 'icuin78.dll') -Destination (Join-Path $vendorDirectory 'icuin78.dll') -Force
    Copy-Item -LiteralPath (Join-Path $binDirectory 'icuuc78.dll') -Destination (Join-Path $vendorDirectory 'icuuc78.dll') -Force
    Copy-Item -LiteralPath (Join-Path $binDirectory 'icuuc78.dll') -Destination (Join-Path $vendorDirectory 'icuuc.dll') -Force
    Copy-Item -LiteralPath (Join-Path $expanded 'LICENSE') -Destination (Join-Path $licenseDirectory 'ICU-LICENSE.txt') -Force
    Write-Host "Verified ICU $version prepared in: $vendorDirectory" -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $temporaryDirectory) {
        Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
    }
}
