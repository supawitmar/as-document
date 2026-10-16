# ตัวอัปเดตในโฟลเดอร์ "อัปเดต version 1.x" (tools/release.py คัดลอกไฟล์นี้ไปไว้ในแพ็กเกจ)
# ไม่ต้องใช้อินเทอร์เน็ต: ติดตั้งจาก files\program.zip ทับโปรแกรมที่ติดตั้งไว้ ด้วยตัวอัปเดตของรุ่นใหม่ (core/update.py)
#   - หาโฟลเดอร์ที่ติดตั้งจากไอคอนบน Desktop / Start Menu หรือ Documents\as-document (ไม่เจอ = ให้เลือกเอง)
#   - ปิดโปรแกรมที่เปิดอยู่ → ติดตั้งทับ (ไม่ทับค่าตั้งค่า คำแปล และข้อมูลที่เครื่องนี้เรียนรู้) → ตรวจไลบรารี → เปิดโปรแกรมใหม่
# ไฟล์นี้ต้องบันทึกเป็น UTF-8 แบบมี BOM (PowerShell 5.1 จึงอ่านภาษาไทยถูก)
param(
    [string]$Dest = "",          # โฟลเดอร์ที่ติดตั้ง (ไม่ระบุ = หาเอง)
    [switch]$NoLaunch,           # อัปเดตเสร็จไม่ต้องเปิดโปรแกรม
    [switch]$NoPause             # ไม่ต้องรอกด Enter ตอนจบ (ใช้ทดสอบ)
)
# Continue: PowerShell 5.1 ถือว่าข้อความ stderr ของ python เป็น error — คำสั่งที่ต้องหยุดเมื่อพลาดใส่ -ErrorAction Stop เอง
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = "__VERSION__"
$AppTitle = "ระบบปรับเอกสาร"

function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }
function Bad($m)  { Write-Host "  [X]  $m" -ForegroundColor Red }
function Finish($code) {
    if (-not $NoPause) { Write-Host ""; Read-Host "กด Enter เพื่อปิดหน้าต่างนี้" | Out-Null }
    exit $code
}

Write-Host ""
Write-Host "=== $AppTitle — อัปเดตเป็น version $Version ===" -ForegroundColor Cyan
Write-Host ""

# ---------- 1) หาโฟลเดอร์ที่ติดตั้ง และ Python ที่โปรแกรมใช้ ----------
Write-Host "1) หาโปรแกรมที่ติดตั้งในเครื่องนี้"
function Test-Install($dir) { $dir -and (Test-Path (Join-Path $dir "app.py")) -and (Test-Path (Join-Path $dir "core")) }
$found = @()          # @{ Dir = ...; Python = ... }
$wsh = New-Object -ComObject WScript.Shell
$linkDirs = @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("CommonDesktopDirectory"),
              (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"))
foreach ($ld in $linkDirs) {
    if (-not (Test-Path -LiteralPath $ld)) { continue }
    Get-ChildItem -LiteralPath $ld -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object {
        try { $l = $wsh.CreateShortcut($_.FullName) } catch { return }
        if ($l.Arguments -match '"?([^"]+\\)app\.py"?') {
            $d = $Matches[1].TrimEnd("\")
            if (Test-Install $d) { $found += @{ Dir = $d; Python = $l.TargetPath } }
        }
    }
}
$docs = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "as-document"
if (Test-Install $docs) { $found += @{ Dir = $docs; Python = "" } }

if ($Dest) {
    if (-not (Test-Install $Dest)) { Bad "ไม่พบโปรแกรมใน $Dest"; Finish 1 }
    $target = @{ Dir = (Resolve-Path -LiteralPath $Dest).Path; Python = "" }
} else {
    $target = $found | Where-Object { -not (Test-Path (Join-Path $_.Dir ".git")) } | Select-Object -First 1
}
if (-not $target) {
    if ($found | Where-Object { Test-Path (Join-Path $_.Dir ".git") }) {
        Warn "โปรแกรมที่พบเป็นเครื่องพัฒนา (มีโฟลเดอร์ .git) — เครื่องนี้อัปเดตด้วย git pull ไม่ต้องใช้ตัวอัปเดตนี้"
        Finish 1
    }
    Warn "หาโฟลเดอร์โปรแกรมไม่เจอ — กรุณาเลือกโฟลเดอร์ที่ติดตั้งโปรแกรมไว้ (โฟลเดอร์ที่มีไฟล์ app.py)"
    Add-Type -AssemblyName System.Windows.Forms
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = "เลือกโฟลเดอร์ที่ติดตั้ง $AppTitle (มีไฟล์ app.py)"
    if ($dlg.ShowDialog() -ne "OK" -or -not (Test-Install $dlg.SelectedPath)) { Bad "ไม่ได้เลือกโฟลเดอร์ที่ถูกต้อง — ยกเลิกการอัปเดต"; Finish 1 }
    $target = @{ Dir = $dlg.SelectedPath; Python = "" }
}
$App = $target.Dir
if (Test-Path (Join-Path $App ".git")) { Warn "$App เป็นเครื่องพัฒนา (มีโฟลเดอร์ .git) — อัปเดตด้วย git pull"; Finish 1 }
Ok "โปรแกรมอยู่ที่: $App"

$cur = "ก่อน 1.0"
try {
    $vj = Get-Content -LiteralPath (Join-Path $App "version.json") -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json
    if ($vj.version) { $cur = $vj.version } elseif ($vj.build) { $cur = "1." + ([int]$vj.build - 1) }
} catch {}
Ok "รุ่นที่ใช้อยู่: version $cur"

# Python ตัวจริง (ทางลัดใน WindowsApps ของ Python install manager ใช้ได้ — ถามตำแหน่งจริงจาก Python เอง)
function Get-RealPython($exe) {
    if (-not $exe) { return "" }
    try {
        $r = & $exe -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $r) { return ([string]($r | Select-Object -Last 1)).Trim() }
    } catch {}
    return ""
}
$pyCands = @()
$linkPy = ($found | Where-Object { $_.Dir -eq $App -and $_.Python } | Select-Object -First 1).Python
if ($linkPy) { $pyCands += (Join-Path (Split-Path $linkPy) "python.exe"), $linkPy }
$pyCands += "py", "python"
$pyCands += @(Get-ChildItem "$env:LOCALAPPDATA\Python\pythoncore-*\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
                "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
$py = ""
foreach ($c in $pyCands) { $py = Get-RealPython $c; if ($py) { break } }
if (-not $py) { Bad "ไม่พบ Python ในเครื่องนี้ — รัน ติดตั้ง.bat ในโฟลเดอร์โปรแกรมก่อน"; Finish 1 }
Ok "Python: $py"

# ---------- 2) ปิดโปรแกรมที่เปิดอยู่ ----------
Write-Host "2) ปิดโปรแกรมที่เปิดอยู่"
$appPy = Join-Path $App "app.py"
$running = Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($appPy) }
foreach ($p in $running) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Get-Process msedge -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq $AppTitle } |
    ForEach-Object { [void]$_.CloseMainWindow() }
if ($running) { Ok "ปิดโปรแกรมแล้ว"; Start-Sleep -Seconds 1 } else { Ok "โปรแกรมไม่ได้เปิดอยู่" }

# ---------- 3) ติดตั้งทับด้วยรุ่นใหม่ ----------
Write-Host "3) ติดตั้ง version $Version"
$work = Join-Path $env:TEMP ("docupdate-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $work -Force -ErrorAction Stop | Out-Null
$code = 1
try {
    Expand-Archive -LiteralPath (Join-Path $Here "program.zip") -DestinationPath $work -Force -ErrorAction Stop
    $src = Get-ChildItem -LiteralPath $work -Directory | Select-Object -First 1
    if (-not $src -or -not (Test-Path (Join-Path $src.FullName "core\update.py"))) { throw "ไฟล์ program.zip ไม่สมบูรณ์" }
    Push-Location $src.FullName
    try {
        $out = & $py -X utf8 -m core.update --tree $src.FullName --dest $App 2>&1
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    $out | ForEach-Object { Write-Host "     $_" }
    if ($code -ne 0) { throw "ตัวอัปเดตทำงานไม่สำเร็จ" }
    Ok "ติดตั้งไฟล์โปรแกรมแล้ว (ค่าตั้งค่า คำแปล และข้อมูลที่เครื่องนี้เรียนรู้ ยังอยู่ครบ)"
} catch {
    Bad "อัปเดตไม่สำเร็จ: $($_.Exception.Message)"
    Finish 1
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}

# ---------- 4) ตรวจไลบรารีที่โปรแกรมต้องใช้ ----------
Write-Host "4) ตรวจไลบรารี (pymupdf, pillow)"
& $py -c "import pymupdf, PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    Warn "ยังไม่มีไลบรารี — กำลังติดตั้ง (ต้องต่ออินเทอร์เน็ต)…"
    & $py -m pip install --user --upgrade --disable-pip-version-check --no-warn-script-location -q -r (Join-Path $App "requirements.txt")
    & $py -c "import pymupdf, PIL" 2>$null
}
if ($LASTEXITCODE -eq 0) { Ok "ไลบรารีพร้อมใช้งาน" }
else { Bad "ติดตั้งไลบรารีไม่สำเร็จ — ต่ออินเทอร์เน็ตแล้วลองใหม่ หรือรันคำสั่ง: `"$py`" -m pip install --user pymupdf pillow" }

# ---------- 5) เสร็จ: เปิดโปรแกรมใหม่ ----------
$now = "?"
try { $now = (Get-Content -LiteralPath (Join-Path $App "version.json") -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json).version } catch {}
Write-Host ""
Write-Host "อัปเดตเสร็จแล้ว: version $cur → version $now" -ForegroundColor Green
if (-not $NoLaunch) {
    $pyw = Join-Path (Split-Path $py) "pythonw.exe"
    if (-not (Test-Path -LiteralPath $pyw)) { $pyw = $py }
    Start-Process -FilePath $pyw -ArgumentList "`"$appPy`"" -WorkingDirectory $App
    Write-Host "กำลังเปิดโปรแกรม…"
}
Finish 0
