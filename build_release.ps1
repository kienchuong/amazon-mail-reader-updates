param(
  [string]$Version = "0.6.9"
)

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path $project "dist"
$stage = Join-Path $env:TEMP ("amazon-mail-reader-release-" + [guid]::NewGuid().ToString("N"))
$packageName = "amazon-mail-reader-$Version-win64.zip"
$package = Join-Path $dist $packageName

New-Item -ItemType Directory -Path $dist -Force | Out-Null
New-Item -ItemType Directory -Path $stage -Force | Out-Null

try {
    Copy-Item -LiteralPath (Join-Path $project "app.py") -Destination $stage
    Copy-Item -LiteralPath (Join-Path $project "run_app.bat") -Destination $stage
    Copy-Item -LiteralPath (Join-Path $project "run_app.vbs") -Destination $stage
    Copy-Item -LiteralPath (Join-Path $project "README.md") -Destination $stage
    Copy-Item -LiteralPath (Join-Path $project "HUONG_DAN_MICROSOFT.md") -Destination $stage
    Copy-Item -LiteralPath (Join-Path $project "HUONG_DAN_GOOGLE.md") -Destination $stage
    Copy-Item -LiteralPath (Join-Path $project "HUONG_DAN_MOBILE.md") -Destination $stage
    Copy-Item -LiteralPath (Join-Path $project "HUONG_DAN_CLOUDFLARE.md") -Destination $stage
    Copy-Item -LiteralPath (Join-Path $project "requirements.txt") -Destination $stage
    Copy-Item -LiteralPath (Join-Path $project "google_sheets_webhook.gs") -Destination $stage
    Copy-Item -LiteralPath (Join-Path $project "build_release.ps1") -Destination $stage
    Copy-Item -LiteralPath (Join-Path $project "amzmail") -Destination $stage -Recurse
    Copy-Item -LiteralPath (Join-Path $project "assets") -Destination $stage -Recurse
    Copy-Item -LiteralPath (Join-Path $project "cloudflare") -Destination $stage -Recurse
    Get-ChildItem -LiteralPath $stage -Directory -Recurse |
        Where-Object { $_.Name -in @("__pycache__", "node_modules", ".wrangler") } |
        Sort-Object { $_.FullName.Length } -Descending |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $stage -File -Recurse |
        Where-Object { $_.Name -in @(".env", ".dev.vars") -or $_.Extension -in @(".pyc", ".pyo") } |
        Remove-Item -Force
    if (Test-Path -LiteralPath $package) { Remove-Item -LiteralPath $package -Force }
    Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $package -CompressionLevel Optimal
    $hash = (Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath ($package + ".sha256") -Value "$hash  $packageName" -Encoding ascii
    Write-Host "Đã tạo: $package"
    Write-Host "SHA-256: $hash"
}
finally {
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
