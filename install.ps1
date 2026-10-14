# ติดตั้ง "ระบบปรับเอกสาร" (hub — บฑ.31 และประเภทเอกสารอื่นที่เพิ่มภายหลัง) บนเครื่องนี้ (เรียกผ่าน ติดตั้ง.bat)
#   - ตรวจ Python 3.9+, Microsoft Word, Microsoft Edge, ฟอนต์ TH Sarabun New / TH SarabunPSK
#     ถ้าขาด: บอกลิงก์ดาวน์โหลด เสนอเปิดหน้าดาวน์โหลดให้ และติดตั้ง Python อัตโนมัติได้ (winget)
#   - ติดตั้งไลบรารี Python (requirements.txt)
#   - สร้างไอคอน "ระบบปรับเอกสาร" บน Desktop และในโฟลเดอร์โปรแกรม (ลบไอคอนชื่อเดิม "ระบบปรับเอกสาร บฑ.31")
param([switch]$SkipPip)

[Console]::OutputEncoding = [Text.Encoding]::UTF8
$App = Split-Path -Parent $MyInvocation.MyCommand.Path
$Name = "ระบบปรับเอกสาร"
$OldNames = @("ระบบปรับเอกสาร บฑ.31")      # ชื่อไอคอนรุ่นก่อน hub — ลบทิ้งเพื่อไม่ให้มีไอคอนซ้ำ
$problems = 0
$Links = @{
    Python   = "https://www.python.org/downloads/"
    Office   = "https://www.office.com/"
    Edge     = "https://www.microsoft.com/edge/download"
    FontNew  = "https://www.f0nt.com/release/th-sarabun-new/"
    FontPSK  = "https://www.f0nt.com/release/13-free-fonts-from-sipa/"
    Guide    = "https://github.com/supawitmar/as-document/blob/main/INSTALL.md"
}
function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!!] $m" -ForegroundColor Yellow }
function Bad($m)  { Write-Host "  [XX] $m" -ForegroundColor Red; $script:problems++ }
function Info($m) { Write-Host "       $m" }
function Ask($q)  { $a = Read-Host "       $q (Y/N)"; return ($a -match '^\s*[yY]') }
function Offer-Open($url, $what) {
    Info "ดาวน์โหลด: $url"
    if (Ask "เปิดหน้าดาวน์โหลด $what ในเบราว์เซอร์ตอนนี้ไหม?") { Start-Process $url }
}
function Find-Python {
    foreach ($cand in @(@("py", "-3"), @("python"), @("python3"))) {
        try {
            $exe = $cand[0]; $extra = @($cand | Select-Object -Skip 1)
            $out = & $exe @extra -c "import sys; print(sys.executable); print(sys.version_info >= (3, 9))" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out -and $out[1].Trim() -eq "True") { return $out[0].Trim() }
        } catch {}
    }
    return $null
}
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host ""
Write-Host "=== ติดตั้ง $Name ===" -ForegroundColor Cyan
Write-Host "โฟลเดอร์โปรแกรม: $App"
Write-Host "คู่มือ (มีขั้นตอนติดตั้งโปรแกรมที่จำเป็นทุกตัว): INSTALL.md / $($Links.Guide)"
Write-Host ""

# 1) Python 3.9+
Write-Host "1) Python"
$py = Find-Python
if (-not $py) {
    Bad "ไม่พบ Python 3.9 ขึ้นไป"
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget -and (Ask "ติดตั้ง Python 3.12 ให้อัตโนมัติตอนนี้เลยไหม? (ใช้ winget ของ Windows ประมาณ 1-3 นาที)")) {
        winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
        Refresh-Path
        $py = Find-Python
        if ($py) { $script:problems--; Ok "ติดตั้ง Python แล้ว" }
    }
    if (-not $py) {
        Info "ติดตั้งเอง: ดาวน์โหลด Python → เปิดไฟล์ → ติ๊ก 'Add python.exe to PATH' → Install Now"
        Info "(รายละเอียดใน INSTALL.md หัวข้อ 'ติดตั้ง Python') แล้วรัน ติดตั้ง.bat ใหม่"
        Offer-Open $Links.Python "Python"
        Read-Host "กด Enter เพื่อปิด"; exit 1
    }
}
Ok "Python: $py"
$pyw = Join-Path (Split-Path $py) "pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = $py }

# 2) ไลบรารี Python
Write-Host "2) ไลบรารี Python (pymupdf, pillow)"
if ($SkipPip) {
    Warn "ข้าม (SkipPip)"
} else {
    & $py -m pip install --user --upgrade --disable-pip-version-check -q -r (Join-Path $App "requirements.txt")
    if ($LASTEXITCODE -eq 0) { Ok "ติดตั้งแล้ว" }
    else {
        Bad "ติดตั้งไลบรารีไม่สำเร็จ — ตรวจว่าต่ออินเทอร์เน็ตได้ แล้วรัน ติดตั้ง.bat ใหม่"
        Info "เครือข่ายองค์กรที่ต้องใช้ proxy: ดู INSTALL.md หัวข้อแก้ปัญหา"
    }
}

# 3) Microsoft Word (ใช้แปลงเป็น .docx / PDF)
Write-Host "3) Microsoft Word"
try {
    $word = New-Object -ComObject Word.Application
    $ver = $word.Version; $word.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    Ok "Word เวอร์ชัน $ver"
} catch {
    Bad "ไม่พบ Microsoft Word แบบติดตั้งในเครื่อง — จำเป็นสำหรับสร้างไฟล์ .docx / PDF"
    Info "บุคลากรมหาวิทยาลัยติดตั้ง Microsoft 365 ได้: เข้า office.com ด้วยอีเมลมหาวิทยาลัย → Install apps"
    Info "(ขั้นตอนใน INSTALL.md หัวข้อ 'ติดตั้ง Microsoft Word')"
    Offer-Open $Links.Office "Microsoft 365 (Word)"
}

# 4) Microsoft Edge (เปิดหน้าโปรแกรมเป็นหน้าต่างแอป)
Write-Host "4) Microsoft Edge"
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
          "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
          "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe") | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if ($edge) { Ok "พบ Edge" }
else {
    Warn "ไม่พบ Edge — โปรแกรมจะเปิดในเบราว์เซอร์หลักแทน (ใช้งานได้ แต่แนะนำให้ติดตั้ง)"
    Offer-Open $Links.Edge "Microsoft Edge"
}

# 5) ฟอนต์
Write-Host "5) ฟอนต์"
$fontNames = @(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts',
                               'HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts' -ErrorAction SilentlyContinue |
               ForEach-Object { $_.PSObject.Properties.Name }) -join "|"
$fontNames = $fontNames -replace "\s", ""          # ชื่อในรีจิสทรีอาจไม่มีช่องว่าง เช่น "THSarabunNew (TrueType)"
foreach ($f in @(@("TH Sarabun New", $Links.FontNew), @("TH SarabunPSK", $Links.FontPSK))) {
    if ($fontNames -match [regex]::Escape(($f[0] -replace "\s", ""))) { Ok $f[0] }
    else {
        Bad "ไม่พบฟอนต์ $($f[0]) — ถ้าไม่ติดตั้ง หนังสือจะใช้ฟอนต์อื่นแทนและรูปแบบเพี้ยน"
        Info "ดาวน์โหลด → แตกไฟล์ zip → เลือกไฟล์ .ttf ทั้งหมด → คลิกขวา Install (ขั้นตอนใน INSTALL.md หัวข้อฟอนต์)"
        Offer-Open $f[1] "ฟอนต์ $($f[0])"
    }
}

# 6) ไอคอนบน Desktop + ในโฟลเดอร์โปรแกรม
#    WScript.Shell บันทึก path ภาษาไทยไม่ได้ จึงสร้างไฟล์ชั่วคราวแล้วตั้งค่าผ่าน Shell.Application (รองรับ Unicode)
Write-Host "6) ไอคอนเปิดโปรแกรม"
try {
    $tmpDir = $env:TEMP
    $tmpName = "fixletters_tmp.lnk"
    $tmpLnk = Join-Path $tmpDir $tmpName
    $ws = New-Object -ComObject WScript.Shell
    $l = $ws.CreateShortcut($tmpLnk); $l.TargetPath = "$env:WINDIR\System32\cmd.exe"; $l.Save()
    $sh = New-Object -ComObject Shell.Application
    $link = $sh.NameSpace($tmpDir).ParseName($tmpName).GetLink
    $link.Path = $pyw
    $link.Arguments = '"' + (Join-Path $App "app.py") + '"'
    $link.WorkingDirectory = $App
    $link.Description = "$Name — จัดรูปแบบเอกสาร (บฑ.31 ฯลฯ) เป็นไฟล์ Word มาตรฐาน"
    $link.SetIconLocation((Join-Path $App "assets\app.ico"), 0)
    $link.Save()
    $desk = [Environment]::GetFolderPath("Desktop")
    Copy-Item -LiteralPath $tmpLnk -Destination (Join-Path $desk "$Name.lnk") -Force
    Copy-Item -LiteralPath $tmpLnk -Destination (Join-Path $App "$Name.lnk") -Force
    Remove-Item -LiteralPath $tmpLnk -Force
    foreach ($old in $OldNames) {
        foreach ($dir in @($desk, $App)) {
            $oldLnk = Join-Path $dir "$old.lnk"
            if (Test-Path -LiteralPath $oldLnk) { Remove-Item -LiteralPath $oldLnk -Force }
        }
    }
    Ok "สร้างไอคอน '$Name' บน Desktop แล้ว"
} catch {
    Bad "สร้างไอคอนไม่สำเร็จ: $($_.Exception.Message) — เปิดโปรแกรมด้วย ปรับเอกสาร.bat แทนได้"
}

# 7) ทดสอบว่าโปรแกรมโหลดได้
Write-Host "7) ทดสอบโปรแกรม"
Push-Location $App
& $py -c "import app; from core import registry; d = registry.discover(); assert d and not registry.errors, registry.errors; print('ok')" 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Ok "โหลดโปรแกรมและประเภทเอกสารได้" } else { Bad "โหลดโปรแกรมไม่ได้ — ลอง: $py -c `"import app; from core import registry; registry.discover(); print(registry.errors)`" เพื่อดูข้อผิดพลาด" }
Pop-Location

Write-Host ""
if ($problems -eq 0) {
    Write-Host "ติดตั้งเสร็จเรียบร้อย — ดับเบิลคลิกไอคอน '$Name' บน Desktop เพื่อใช้งาน" -ForegroundColor Green
} else {
    Write-Host "ยังมี $problems รายการที่ต้องแก้ (บรรทัด [XX] ด้านบน) — ติดตั้งตามลิงก์แล้วรัน ติดตั้ง.bat ใหม่" -ForegroundColor Yellow
    Write-Host "ขั้นตอนละเอียด: INSTALL.md / $($Links.Guide)"
}
Write-Host ""
Read-Host "กด Enter เพื่อปิด"
