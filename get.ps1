# One-step setup: download the program from GitHub, extract it, then run install.ps1.
# Run on a new computer (Win+R, paste, Enter):
#   powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/supawitmar/as-document/main/get.ps1 | iex"
# Running it again updates the program; local files (settings.json, converted.json,
# doctypes/*/data/translations.json) are kept.
# This file is intentionally ASCII-only so it runs correctly however it is downloaded.
param(
    [string]$Repo = "supawitmar/as-document",
    [string]$Branch = "main",
    [string]$Dest = (Join-Path ([Environment]::GetFolderPath("MyDocuments")) "as-document"),
    [string]$ZipPath = ""          # for testing: use a local zip instead of downloading
)
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

Write-Host ""
Write-Host "=== Document formatting system (BT.31 and more) - download and install ===" -ForegroundColor Cyan
Write-Host "Install folder: $Dest"
Write-Host ""

$work = Join-Path $env:TEMP ("as-document-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $work -Force | Out-Null
try {
    $zip = Join-Path $work "src.zip"
    if ($ZipPath) {
        Copy-Item -LiteralPath $ZipPath -Destination $zip
    } else {
        $url = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
        Write-Host "1) Downloading $url"
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    }
    Write-Host "2) Extracting"
    Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $work "x") -Force
    $src = Get-ChildItem -LiteralPath (Join-Path $work "x") -Directory | Select-Object -First 1
    if (-not $src -or -not (Test-Path (Join-Path $src.FullName "install.ps1"))) { throw "install.ps1 not found in the downloaded files" }

    Write-Host "3) Copying to $Dest"
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    # The archive never contains the per-computer files (they are in .gitignore), so copying over keeps them.
    Get-ChildItem -LiteralPath $src.FullName -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Dest -Recurse -Force
    }
    Get-ChildItem -LiteralPath $Dest -Recurse -File | Unblock-File -ErrorAction SilentlyContinue
} catch {
    Write-Host ""
    Write-Host "Download/extract failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Check the internet connection, or download the ZIP manually: https://github.com/$Repo" -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "4) Running the installer"
Write-Host ""
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Dest "install.ps1")
