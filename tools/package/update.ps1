# ตัวอัปเดตของระบบปรับเอกสาร (หลักการเดียวกับระบบตรวจเล่ม e-thesis checker) — ใช้ได้ 3 แบบ:

#   1. -Online  : `อัปเดตระบบปรับเอกสาร.bat` ในโฟลเดอร์โปรแกรม — ดาวน์โหลดรุ่นล่าสุดที่ "ออกแล้ว" (ป้าย v<เลข>) จาก GitHub

#   2. แพ็กเกจ  : โฟลเดอร์ "อัปเดต version 1.x" (tools/release.py คัดลอกไฟล์นี้ไปเป็น files\update.ps1 คู่กับ files\program.zip)

#   3. ZIP รุ่นใดก็ได้ที่แตกไว้ (เช่นจาก GitHub): `ติดตั้งอัปเดตจากโฟลเดอร์นี้.bat` — ติดตั้งโฟลเดอร์ที่แตกนั้นทับโปรแกรมในเครื่อง

# ทุกแบบ: หาโปรแกรมในเครื่อง (ตำแหน่งที่โปรแกรมจำไว้ / ไอคอน / Documents\as-document / ให้เลือก) → ปิดโปรแกรมที่เปิดอยู่

#         → ติดตั้งทับด้วยตัวอัปเดตของ "รุ่นใหม่" (core/update.py — ไม่ทับค่าตั้งค่า คำแปล และข้อมูลที่เครื่องนี้เรียนรู้)

#         → ตรวจไลบรารี → เปิดโปรแกรมใหม่

# ไฟล์นี้ต้องบันทึกเป็น UTF-8 แบบมี BOM (PowerShell 5.1 จึงอ่านภาษาไทยถูก)

param(

    [string]$Dest = "",          # โฟลเดอร์ที่ติดตั้ง (ไม่ระบุ = หาเอง)

    [switch]$Online,             # ดาวน์โหลดรุ่นล่าสุดที่ออกแล้วจาก GitHub

    [switch]$NoLaunch,           # อัปเดตเสร็จไม่ต้องเปิดโปรแกรม

    [switch]$NoPause             # ไม่ต้องรอกด Enter ตอนจบ (ใช้ทดสอบ)

)

# Continue: PowerShell 5.1 ถือว่าข้อความ stderr ของ python เป็น error — คำสั่งที่ต้องหยุดเมื่อพลาดใส่ -ErrorAction Stop เอง

$ErrorActionPreference = "Continue"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

$Version = "__VERSION__"          # แพ็กเกจ: tools/release.py แทนค่าเป็นเลขรุ่น

$AppTitle = "ระบบปรับเอกสาร"



function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }

function Warn($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }

function Bad($m)  { Write-Host "  [X]  $m" -ForegroundColor Red }

function Finish($code) {

    if (-not $NoPause) { Write-Host ""; Read-Host "กด Enter เพื่อปิดหน้าต่างนี้" | Out-Null }

    exit $code

}

function Read-Ver($dir) {

    try {

        $vj = Get-Content -LiteralPath (Join-Path $dir "version.json") -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json

        if ($vj.version) { return [string]$vj.version } elseif ($vj.build) { return "1." + ([int]$vj.build - 1) }

    } catch {}

    return "ก่อน 1.0"

}

function Test-Install($dir) { $dir -and (Test-Path -LiteralPath (Join-Path $dir "app.py")) -and (Test-Path -LiteralPath (Join-Path $dir "core")) }

function Same-Dir($a, $b) {

    try { return ((Resolve-Path -LiteralPath $a).Path.TrimEnd("\") -eq (Resolve-Path -LiteralPath $b).Path.TrimEnd("\")) } catch { return $false }

}



# แหล่งของรุ่นใหม่: แพ็กเกจ (files\program.zip ข้างไฟล์นี้) / โฟลเดอร์โปรแกรมที่ไฟล์นี้อยู่ (tools\package) / ออนไลน์

$packageZip = Join-Path $Here "program.zip"

$treeHere = (Resolve-Path -LiteralPath (Join-Path $Here "..\..") -ErrorAction SilentlyContinue).Path

$mode = if ($Online) { "online" } elseif (Test-Path -LiteralPath $packageZip) { "package" } else { "tree" }



Write-Host ""

if ($mode -eq "package") { Write-Host "=== $AppTitle — อัปเดตเป็น version $Version ===" -ForegroundColor Cyan }

elseif ($mode -eq "tree") { Write-Host "=== $AppTitle — ติดตั้ง version $(Read-Ver $treeHere) จากโฟลเดอร์นี้ ===" -ForegroundColor Cyan }

else { Write-Host "=== $AppTitle — อัปเดตเป็นรุ่นล่าสุดที่ออกแล้ว ===" -ForegroundColor Cyan }

Write-Host ""




# ---------- 1) หาโฟลเดอร์ที่ติดตั้ง และ Python ที่โปรแกรมใช้ ----------

Write-Host "1) หาโปรแกรมที่ติดตั้งในเครื่องนี้"

$found = @()          # @{ Dir = ...; Python = ... }

# ตำแหน่งที่โปรแกรมจำไว้ทุกครั้งที่เปิด (app.py -> %LOCALAPPDATA%\as-document\installs.json)

try {

    $known = Get-Content -LiteralPath (Join-Path $env:LOCALAPPDATA "as-document\installs.json") -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json

    foreach ($k in @($known)) { if (Test-Install $k.dir) { $found += @{ Dir = [string]$k.dir; Python = [string]$k.python } } }

} catch {}

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



$isSource = { param($d) $mode -eq "tree" -and (Same-Dir $d $treeHere) }    # โฟลเดอร์ที่แตก ZIP ไม่ใช่ปลายทาง

# ดับเบิลคลิก "ติดตั้งอัปเดตจากโฟลเดอร์นี้" ในโฟลเดอร์โปรแกรมที่ติดตั้ง/ใช้งานอยู่เอง = ไม่ใช่โฟลเดอร์ที่แตก ZIP มา — หยุดทันที

if ($mode -eq "tree") {

    $selfKnown = $found | Where-Object { & $isSource $_.Dir }

    $used = @(".update", "settings.json", ".git") | Where-Object { Test-Path -LiteralPath (Join-Path $treeHere $_) }

    if ($selfKnown -or $used) {

        Warn "โฟลเดอร์นี้คือโปรแกรมที่ติดตั้งอยู่แล้ว — อัปเดตด้วย อัปเดตระบบปรับเอกสาร.bat (ต่ออินเทอร์เน็ต)"

        Warn "หรือแตกไฟล์ ZIP ของรุ่นใหม่ไว้ที่อื่น แล้วดับเบิลคลิก ติดตั้งอัปเดตจากโฟลเดอร์นี้.bat ในโฟลเดอร์ที่แตกได้"

        Finish 1

    }

}

if ($Dest) {

    if (-not (Test-Install $Dest)) { Bad "ไม่พบโปรแกรมใน $Dest"; Finish 1 }

    $target = @{ Dir = (Resolve-Path -LiteralPath $Dest).Path; Python = "" }

} else {

    $target = $found | Where-Object { -not (Test-Path (Join-Path $_.Dir ".git")) -and -not (& $isSource $_.Dir) } | Select-Object -First 1

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

if (& $isSource $App) { Warn "โฟลเดอร์นี้คือโปรแกรมที่ติดตั้งอยู่แล้ว — ใช้ อัปเดตระบบปรับเอกสาร.bat เพื่ออัปเดต"; Finish 1 }

Ok "โปรแกรมอยู่ที่: $App"

$cur = Read-Ver $App

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

$linkPy = ($found | Where-Object { (Same-Dir $_.Dir $App) -and $_.Python } | Select-Object -First 1).Python

if ($linkPy) { $pyCands += (Join-Path (Split-Path $linkPy) "python.exe"), $linkPy }

$pyCands += "py", "python"

$pyCands += @(Get-ChildItem "$env:LOCALAPPDATA\Python\pythoncore-*\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",

                "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object { $_.FullName })

$py = ""

foreach ($c in $pyCands) { $py = Get-RealPython $c; if ($py) { break } }

if (-not $py) { Bad "ไม่พบ Python ในเครื่องนี้ — รัน ติดตั้ง.bat ในโฟลเดอร์โปรแกรมก่อน"; Finish 1 }

Ok "Python: $py"




# ---------- 2) เตรียมรุ่นใหม่ ----------

$work = Join-Path $env:TEMP ("docupdate-" + [guid]::NewGuid().ToString("N").Substring(0, 8))

New-Item -ItemType Directory -Path $work -Force -ErrorAction Stop | Out-Null

$src = ""; $sourceNote = ""

try {

    if ($mode -eq "online") {

        Write-Host "2) ดาวน์โหลดรุ่นล่าสุดที่ออกแล้วจาก GitHub"

        Push-Location $App

        try { $out = & $py -X utf8 -m core.update --fetch $work 2>&1; $code = $LASTEXITCODE } finally { Pop-Location }

        $last = [string]($out | Select-Object -Last 1)

        if ($code -eq 3) { Ok ($last -replace '^!!\s*', ''); Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue; Finish 0 }

        if ($code -ne 0 -or -not (Test-Path -LiteralPath $last.Trim())) { $out | ForEach-Object { Write-Host "     $_" }; throw "ดาวน์โหลดไม่สำเร็จ (ต่ออินเทอร์เน็ตแล้วลองใหม่)" }

        $src = $last.Trim(); $sourceNote = "GitHub v$(Read-Ver $src)"

    } elseif ($mode -eq "package") {

        Write-Host "2) แตกไฟล์โปรแกรม version $Version"

        Expand-Archive -LiteralPath $packageZip -DestinationPath $work -Force -ErrorAction Stop

        $src = (Get-ChildItem -LiteralPath $work -Directory | Select-Object -First 1).FullName

        $sourceNote = "โฟลเดอร์อัปเดต version $Version"

    } else {

        Write-Host "2) ใช้โปรแกรมในโฟลเดอร์นี้"

        $src = $treeHere; $sourceNote = "โฟลเดอร์ $treeHere"

    }

    if (-not $src -or -not (Test-Path (Join-Path $src "core\update.py"))) { throw "ไฟล์โปรแกรมรุ่นใหม่ไม่สมบูรณ์" }

    $new = Read-Ver $src

    Ok "รุ่นใหม่: version $new"

} catch {

    Bad "$($_.Exception.Message)"

    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue

    Finish 1

}



if (-not $Dest -and -not $NoPause) {

    Write-Host ""

    Write-Host "  จะติดตั้ง version $new ทับโปรแกรมที่ $App (version $cur)" -ForegroundColor Cyan

    $ans = Read-Host "  กด Enter เพื่อติดตั้ง หรือพิมพ์ N แล้ว Enter เพื่อยกเลิก"

    if ($ans -match '^\s*[nN]') {

        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue

        Warn "ยกเลิกการอัปเดต"; Finish 1

    }

}




# ---------- 3) ปิดโปรแกรมที่เปิดอยู่ ----------

Write-Host "3) ปิดโปรแกรมที่เปิดอยู่"

$appPy = Join-Path $App "app.py"

$running = Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |

    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($appPy) }

foreach ($p in $running) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }

Get-Process msedge -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq $AppTitle } |

    ForEach-Object { [void]$_.CloseMainWindow() }

if ($running) { Ok "ปิดโปรแกรมแล้ว"; Start-Sleep -Seconds 1 } else { Ok "โปรแกรมไม่ได้เปิดอยู่" }




# ---------- 4) ติดตั้งทับด้วยตัวอัปเดตของรุ่นใหม่ ----------

Write-Host "4) ติดตั้ง version $new"

$code = 1

try {

    Push-Location $src

    try {

        $out = & $py -X utf8 -m core.update --tree $src --dest $App --source $sourceNote 2>&1

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




# ---------- 5) ตรวจไลบรารีที่โปรแกรมต้องใช้ ----------

Write-Host "5) ตรวจไลบรารี (pymupdf, pillow)"

& $py -c "import pymupdf, PIL" 2>$null

if ($LASTEXITCODE -ne 0) {

    Warn "ยังไม่มีไลบรารี — กำลังติดตั้ง (ต้องต่ออินเทอร์เน็ต)…"

    & $py -m pip install --user --upgrade --disable-pip-version-check --no-warn-script-location -q -r (Join-Path $App "requirements.txt")

    & $py -c "import pymupdf, PIL" 2>$null

}

if ($LASTEXITCODE -eq 0) { Ok "ไลบรารีพร้อมใช้งาน" }

else { Bad "ติดตั้งไลบรารีไม่สำเร็จ — ต่ออินเทอร์เน็ตแล้วลองใหม่ หรือรันคำสั่ง: `"$py`" -m pip install --user pymupdf pillow" }




# ---------- 6) เสร็จ: บอกสิ่งที่เปลี่ยน แล้วเปิดโปรแกรมใหม่ ----------

$now = Read-Ver $App

Write-Host ""

Write-Host "อัปเดตเสร็จแล้ว: version $cur → version $now" -ForegroundColor Green

try {

    $vj = Get-Content -LiteralPath (Join-Path $App "version.json") -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json

    foreach ($c in @($vj.changes) | Select-Object -First 3) {

        if ($c.version -eq $cur) { break }

        Write-Host "  version $($c.version): $($c.text)"

        foreach ($i in @($c.items)) { if ($i) { Write-Host "    - $i" } }

    }

} catch {}

if (-not $NoLaunch) {

    $pyw = Join-Path (Split-Path $py) "pythonw.exe"

    if (-not (Test-Path -LiteralPath $pyw)) { $pyw = $py }

    Start-Process -FilePath $pyw -ArgumentList "`"$appPy`"" -WorkingDirectory $App

    Write-Host "กำลังเปิดโปรแกรม…"

}

Finish 0

