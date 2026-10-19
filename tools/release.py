# -*- coding: utf-8 -*-
"""
ออกรุ่นใหม่ (version 1.x) ให้เครื่องอื่นอัปเดต — รันบนเครื่องพัฒนา (repository git) เมื่องานพร้อมแล้ว
(หลักการเดียวกับระบบตรวจเล่ม e-thesis checker: ออกรุ่นเมื่อเจ้าของตกลง · push เมื่อเจ้าของสั่งเท่านั้น)

    python tools/release.py "หัวข้อของรุ่น" -i "รายละเอียดข้อ 1" -i "รายละเอียดข้อ 2" ...
                            [--fix] [--version 1.2] [--push] [--allow-names]
    python tools/release.py --push                # เผยแพร่รุ่นที่ออกไว้แล้ว (push main + ป้าย v<เลข>)
    python tools/release.py --package-only        # สร้างโฟลเดอร์อัปเดตของรุ่นปัจจุบันใหม่ (ไม่เพิ่มเวอร์ชัน)

ขั้นตอน:
    1. ตรวจ: คอมไพล์ .py ทุกไฟล์, ชุดทดสอบ tests/ ผ่าน, โหลดประเภทเอกสารครบไม่มี error, ไม่มีไฟล์เฉพาะเครื่อง/
       ไฟล์ตัวอย่างใน git, ไม่มีชื่อบุคคลที่ดูเป็นชื่อจริงในโค้ด (repository เป็น Public) — ชื่อสมมติจริง ใช้ --allow-names
    2. เพิ่มเวอร์ชันใน version.json (build +1) พร้อมหัวข้อและรายละเอียด + เขียน CHANGELOG.md ใหม่ (เจ้าหน้าที่อ่าน)
           เพิ่ม/ปรับฟังก์ชัน   1.2 → 1.3      (ค่าเริ่มต้น; 1.2.1 → 1.3)
           แก้เล็กน้อย --fix    1.2 → 1.2.1    (1.2.1 → 1.2.2) เช่น แก้ข้อความ ป้าย คำผิด
       (เครื่องผู้ใช้เห็นข้อความนี้บนแถบ "มีอัปเดตใหม่" และในไฟล์รายละเอียดของแพ็กเกจ)
    3. git commit + ติดป้าย v<เลข> — ตัวอัปเดตของเครื่องผู้ใช้ติดตั้ง "เฉพาะรุ่นที่มีป้าย" (งานบน main ที่ยังไม่ออกรุ่น
       ไม่ลงเครื่องที่ใช้งาน) · ยังไม่ push จนกว่าจะใส่ --push (หรือสั่ง python tools/release.py --push ภายหลัง)
    4. สร้างโฟลเดอร์ dist/อัปเดต version 1.x/ จากป้ายนั้น (+ ไฟล์ .zip ของโฟลเดอร์นี้ ไว้ส่งทาง LINE/อีเมล):
           คลิกเพื่ออัปเดตเป็น version 1.x.bat     ดับเบิลคลิกเพื่ออัปเดต (ไม่ต้องใช้อินเทอร์เน็ต)
           รายละเอียดการอัปเดต version 1.x.txt    สิ่งที่แก้ไข วิธีอัปเดต และประวัติรุ่นก่อน
           files/program.zip, files/update.ps1     โปรแกรมรุ่นนี้ (จาก git) + ตัวอัปเดต (tools/package/update.ps1)
"""
import argparse
import datetime as dt
import json
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
VERSION_FILE = ROOT / "version.json"
CHANGELOG = ROOT / "CHANGELOG.md"
DIST = ROOT / "dist"
PACKAGE_SCRIPT = ROOT / "tools" / "package" / "update.ps1"
TH_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
             "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
PRIVATE = re.compile(r"(^|/)(settings\.json|converted\.json|translations\.json)$|(^|/)samples/|\.lnk$|assets/example_")
# ชื่อบุคคล: คำนำหน้า + ชื่อ + นามสกุล (ภาษาไทย) — ยกเว้นชื่อสมมติที่ใช้ในตัวอย่าง และผู้ลงนามที่ต้องพิมพ์ในหนังสือ
PERSON = re.compile(r"(?:นาย|นางสาว|นาง|ดร\.)\s?([ก-๙]{2,})\s+([ก-๙]{3,})")
FICTIONAL = {"สมชาย", "สมหญิง", "ใจดี", "รักเรียน", "วรินทร์"}
NOT_NAME = ("และ", "หรือ", "ที่", "เป็น", "ให้", "จาก", "ของ", "เช่น", "ใน", "กับ")   # คำทั่วไปที่ตามหลังคำนำหน้าได้
CO_AUTHOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"


def git(*args, check=True) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(args)} ไม่สำเร็จ: {r.stderr.strip()}")
    return r.stdout


def checks(allow_names: bool) -> list:
    problems = []
    for p in ROOT.rglob("*.py"):
        if "__pycache__" in p.parts or ".git" in p.parts:
            continue
        try:
            py_compile.compile(str(p), doraise=True, cfile=str(Path(__import__("tempfile").gettempdir()) / "rel_check.pyc"))
        except py_compile.PyCompileError as e:
            problems.append(f"คอมไพล์ไม่ผ่าน: {p.relative_to(ROOT)} — {e.msg.strip().splitlines()[-1]}")
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8")
    if tests.returncode:
        problems.append("ชุดทดสอบไม่ผ่าน: " + (tests.stderr or tests.stdout).strip().splitlines()[-1])
    from core import registry
    dts = registry.discover()
    for k, v in registry.errors.items():
        problems.append(f"โหลดประเภทเอกสาร {k} ไม่ได้: {v.strip().splitlines()[-1]}")
    git("add", "-A")
    tracked = git("ls-files").splitlines()
    problems += [f"ไฟล์เฉพาะเครื่อง/ตัวอย่างจะขึ้น GitHub: {f}" for f in tracked if PRIVATE.search(f)]
    if not allow_names:
        for f in tracked:
            if not f.endswith((".py", ".html", ".md", ".json", ".ps1")) or f.endswith("signers.json"):
                continue
            text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
            for n, line in enumerate(text.splitlines(), 1):
                for m in PERSON.finditer(line):
                    if not ({m[1], m[2]} & FICTIONAL) and not m[1].startswith(NOT_NAME) \
                            and "re.compile" not in line and "(?" not in line and "allow-name" not in line:
                        problems.append(f"อาจเป็นชื่อจริง: {f}:{n} “{m[0]}” (ใช้ชื่อสมมติ หรือ --allow-names)")
    print(f"ประเภทเอกสาร: {', '.join(f'{d.id} ({d.name})' for d in dts.values())}")
    return problems


def thai_date(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day} {TH_MONTHS[d.month - 1]} {d.year + 543}"


def next_version(v: dict, fix: bool = False) -> str:
    """รุ่นถัดไป: เพิ่มฟังก์ชัน 1.2 / 1.2.1 → 1.3 — แก้เล็กน้อย (fix) 1.2 → 1.2.1, 1.2.1 → 1.2.2"""
    from core.update import version_label
    cur = version_label(int(v.get("build", 0)), v.get("version", ""))
    m = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", cur)
    if not m:
        return "1.0"
    if fix:
        return f"{m[1]}.{m[2]}.{int(m[3] or 0) + 1}"
    return f"{m[1]}.{int(m[2]) + 1}"


def release_notes(v: dict) -> str:
    """ไฟล์รายละเอียดในแพ็กเกจ (เจ้าหน้าที่อ่าน — ภาษาไทย ไม่ใช้ศัพท์เทคนิค)"""
    ver, changes = v["version"], v.get("changes", [])
    now = changes[0] if changes else {"text": "", "items": []}
    lines = [f"ระบบปรับเอกสาร — อัปเดต version {ver}", f"วันที่ออกรุ่น: {thai_date(v.get('date', ''))}", "=" * 48, "",
             f"สิ่งที่แก้ไข / เพิ่มในรุ่นนี้: {now.get('text', '')}"]
    lines += [f"  {n}. {t}" for n, t in enumerate(now.get("items") or [], 1)]
    lines += ["", "วิธีอัปเดต (ไม่ต้องใช้อินเทอร์เน็ต)",
              f"  1. ดับเบิลคลิกไฟล์ “คลิกเพื่ออัปเดตเป็น version {ver}.bat” ในโฟลเดอร์นี้",
              "  2. ตัวอัปเดตจะหาโปรแกรมในเครื่องเอง ถ้าโปรแกรมเปิดอยู่จะปิดให้ก่อน",
              "  3. รอจนขึ้น “อัปเดตเสร็จแล้ว” — โปรแกรมจะเปิดใหม่เอง แล้วกด Enter เพื่อปิดหน้าต่าง",
              "  * ถ้าแตกไฟล์ ZIP มา ให้แตกไฟล์ออกมาก่อน (คลิกขวา → Extract All) แล้วค่อยดับเบิลคลิก",
              "", "ข้อมูลในเครื่องที่ไม่ถูกเขียนทับ",
              "  - ค่าที่ตั้งไว้ (รูปแบบไฟล์ / โฟลเดอร์ที่บันทึก) และประวัติไฟล์ที่แปลงแล้ว",
              "  - คำแปลภาษาอังกฤษที่เครื่องนี้จำไว้",
              "  - ชื่อวิชาและผู้ลงนามที่เครื่องนี้แก้หรือเรียนรู้เอง (รวมกับข้อมูลของรุ่นใหม่ให้อัตโนมัติ)",
              "", "หมายเหตุ",
              "  - ต้องติดตั้งโปรแกรมในเครื่องไว้ก่อนแล้ว (ถ้ายังไม่เคยติดตั้ง ให้ใช้ ติดตั้งจาก-GitHub.bat)",
              "  - เครื่องที่ยังไม่มีไลบรารีอ่าน PDF ตัวอัปเดตจะติดตั้งให้ (ขั้นตอนนี้ต้องต่ออินเทอร์เน็ต)",
              "  - เครื่องที่ต่ออินเทอร์เน็ตอัปเดตได้อีกทาง: กด “อัปเดตเลย” บนแถบ “มีอัปเดตใหม่” ในโปรแกรม"]
    if len(changes) > 1:
        lines += ["", "ประวัติรุ่นก่อนหน้า"]
        for c in changes[1:10]:
            lines.append(f"  version {c.get('version', '?')} ({thai_date(c.get('date', ''))}): {c.get('text', '')}")
            lines += [f"      - {t}" for t in c.get("items") or []]
    return "\n".join(lines) + "\n"


def changelog(v: dict) -> str:
    """CHANGELOG.md — บันทึกการอัปเดตที่เจ้าหน้าที่อ่าน (สร้างจาก version.json ทุกครั้งที่ออกรุ่น ไม่ต้องแก้เอง)"""
    lines = ["# บันทึกการอัปเดตระบบปรับเอกสาร", "",
             "รุ่นล่าสุดอยู่บนสุด · รุ่นที่ใช้อยู่ดูได้ที่ป้าย **v. <เลข>** หัวหน้าจอโปรแกรม", "",
             "**ติดตั้งอัปเดต (ทุกเครื่อง) — เลือกทางใดทางหนึ่ง:**",
             "- ต่ออินเทอร์เน็ต: กด **อัปเดตเลย** บนแถบ \"มีอัปเดตใหม่\" ในโปรแกรม หรือดับเบิลคลิก "
             "`อัปเดตระบบปรับเอกสาร.bat` ในโฟลเดอร์โปรแกรม → ติดตั้งรุ่นใหม่ บอกว่าเปลี่ยนอะไร แล้วเปิดโปรแกรมใหม่ให้เอง",
             "- ไม่ต้องใช้อินเทอร์เน็ต: โฟลเดอร์ `อัปเดต version <เลข>` → ดับเบิลคลิก `คลิกเพื่ออัปเดตเป็น version <เลข>.bat` "
             "หรือแตกไฟล์ ZIP ของรุ่นนั้น (เช่นจาก GitHub) แล้วดับเบิลคลิก `ติดตั้งอัปเดตจากโฟลเดอร์นี้.bat`", "",
             "ตัวอัปเดตติดตั้งเฉพาะรุ่นที่ออกแล้วเท่านั้น (มีหัวข้อในหน้านี้) — ค่าที่ตั้ง คำแปล และข้อมูลที่เครื่องนั้นเรียนรู้ไม่ถูกเขียนทับ",
             "", "<details>", "<summary>วิธีออกรุ่น (ผู้ดูแลระบบ)</summary>", "",
             "1. งานเสร็จและตรวจแล้ว — `python tools/release.py \"หัวข้อ\" -i \"รายละเอียด\"` (แก้เล็กน้อยใส่ `--fix`)",
             "   เขียนเป็นภาษาของเจ้าหน้าที่ บอกว่าจะเห็นอะไรต่างไป ไม่ใช่ชื่อฟังก์ชัน",
             "2. ตัวออกรุ่นตรวจความพร้อม เพิ่มเลขรุ่น เขียนหน้านี้ใหม่ commit ติดป้าย `v<เลข>` และสร้างโฟลเดอร์ `dist/อัปเดต version <เลข>/`",
             "3. เผยแพร่เมื่อเจ้าของสั่ง: `python tools/release.py --push` — แต่ละเครื่องจะเห็นแถบ \"มีอัปเดตใหม่\"",
             "", "</details>", ""]
    for c in v.get("changes", []):
        lines += [f"## อัปเดต {c.get('version', '?')} — {thai_date(c.get('date', ''))}", "", c.get("text", "")]
        items = [t for t in c.get("items") or [] if t]
        if items:
            lines += [""] + [f"- {t}" for t in items]
        lines.append("")
    return "\n".join(lines)


def push(version: str):
    tag = f"v{version}"
    if not git("tag", "-l", tag).strip():
        raise SystemExit(f"ยังไม่มีป้าย {tag} — ออกรุ่นด้วย tools/release.py ก่อน")
    git("push", "-q", "origin", "main", tag)
    print(f"push main + {tag} ขึ้น GitHub แล้ว — เครื่องอื่นจะเห็นแถบ “มีอัปเดตใหม่: version {version}” เมื่อเปิดโปรแกรมครั้งถัดไป")


def build_package(v: dict) -> Path:
    """dist/อัปเดต version X/ + dist/อัปเดต version X.zip — โปรแกรมจาก commit ล่าสุด (ไฟล์ใน git เท่านั้น)"""
    ver = v["version"]
    name = f"อัปเดต version {ver}"
    out = DIST / name
    shutil.rmtree(out, ignore_errors=True)
    (out / "files").mkdir(parents=True)
    with tempfile.TemporaryDirectory() as t:      # path ภาษาอังกฤษให้ git archive
        z = Path(t) / "program.zip"
        ref = f"v{ver}" if git("tag", "-l", f"v{ver}").strip() else "HEAD"
        git("archive", "--format=zip", f"--prefix=as-document-{ver}/", "-o", str(z), ref)
        shutil.copy(z, out / "files" / "program.zip")
    script = PACKAGE_SCRIPT.read_text(encoding="utf-8-sig").replace("__VERSION__", ver)
    (out / "files" / "update.ps1").write_text(script, encoding="utf-8-sig")     # BOM: PowerShell 5.1 อ่านภาษาไทยถูก
    bat = (f"@echo off\r\nrem Update the document formatting system to version {ver} (no internet needed)\r\n"
           f'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0files\\update.ps1"\r\n')
    (out / f"คลิกเพื่ออัปเดตเป็น version {ver}.bat").write_bytes(bat.encode("ascii"))
    (out / f"รายละเอียดการอัปเดต version {ver}.txt").write_text(release_notes(v), encoding="utf-8-sig", newline="\r\n")
    archive = DIST / f"{name}.zip"
    archive.unlink(missing_ok=True)
    shutil.make_archive(str(DIST / name), "zip", DIST, name)
    return out


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="ปล่อยรุ่นใหม่ (version 1.x) ให้เครื่องอื่นอัปเดต")
    ap.add_argument("message", nargs="?", help="หัวข้อของรุ่นที่ผู้ใช้เครื่องอื่นจะเห็น เช่น 'เพิ่มประเภทเอกสาร บฑ.xx'")
    ap.add_argument("-i", "--item", action="append", default=[], help="รายละเอียดที่แก้ไข (ใส่ได้หลายครั้ง)")
    ap.add_argument("--fix", action="store_true", help="แก้เล็กน้อย (ข้อความ ป้าย คำผิด): เพิ่มเลขย่อย เช่น 1.2 → 1.2.1")
    ap.add_argument("--version", help="เลขเวอร์ชันของรุ่นนี้ (ค่าเริ่มต้น: เพิ่มเลขหลังจุด เช่น 1.2 → 1.3, หรือ 1.2.1 ถ้าใส่ --fix)")
    ap.add_argument("--push", action="store_true", help="push main + ป้าย v<เลข> ขึ้น GitHub (เฉพาะเมื่อเจ้าของสั่ง) — "
                                                          "ไม่มีหัวข้อ = เผยแพร่รุ่นที่ออกไว้แล้ว")
    ap.add_argument("--no-push", action="store_true", help="(ค่าเริ่มต้นอยู่แล้ว) ออกรุ่นในเครื่อง ยังไม่ push")
    ap.add_argument("--allow-names", action="store_true", help="ยืนยันว่าชื่อบุคคลที่พบเป็นชื่อสมมติ/ชื่อที่ต้องเผยแพร่")
    ap.add_argument("--package-only", action="store_true", help="สร้างโฟลเดอร์อัปเดตของรุ่นปัจจุบันใหม่ (ไม่เพิ่มเวอร์ชัน/ไม่ commit)")
    args = ap.parse_args(argv)

    if args.package_only:
        from core.update import version_label
        v = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
        v["version"] = version_label(int(v.get("build", 0)), v.get("version", ""))
        print(f"สร้างแพ็กเกจแล้ว: {build_package(v)}")
        return 0
    if not args.message and args.push:
        from core.update import version_label
        v = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
        push(version_label(int(v.get("build", 0)), v.get("version", "")))
        return 0
    if not args.message:
        ap.error("ต้องใส่หัวข้อของรุ่น เช่น python tools/release.py \"แก้ไขรูปแบบหนังสือ\" -i \"รายละเอียด\"")

    if git("rev-parse", "--abbrev-ref", "HEAD").strip() != "main":
        raise SystemExit("ต้องอยู่ที่ branch main")
    problems = checks(args.allow_names)
    if problems:
        git("reset", "-q")
        print("ยังปล่อย patch ไม่ได้:\n  - " + "\n  - ".join(problems))
        return 1

    v = json.loads(VERSION_FILE.read_text(encoding="utf-8")) if VERSION_FILE.exists() else {"build": 0, "changes": []}
    build = int(v.get("build", 0)) + 1
    version = args.version or next_version(v, args.fix)
    if git("tag", "-l", f"v{version}").strip():
        git("reset", "-q")
        raise SystemExit(f"มีรุ่น v{version} อยู่แล้ว — ใช้เลขอื่น (--version)")
    today = dt.date.today().isoformat()
    change = {"build": build, "version": version, "date": today, "text": args.message, "items": args.item}
    v = {"version": version, "build": build, "date": today, "changes": [change] + v.get("changes", [])[:49]}
    VERSION_FILE.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CHANGELOG.write_text(changelog(v), encoding="utf-8")

    git("add", "-A")
    print("ไฟล์ในรุ่นนี้:\n  " + "\n  ".join(git("diff", "--cached", "--name-only").splitlines()))
    body = "\n".join(f"- {t}" for t in args.item)
    git("commit", "-q", "-m", f"version {version}: {args.message}\n\n{body}\n\n{CO_AUTHOR}".replace("\n\n\n\n", "\n\n"))
    git("tag", "-a", f"v{version}", "-m", f"อัปเดต {version}: {args.message}")
    print(f"ออกรุ่น version {version} (build {build}) + ป้าย v{version}: {args.message}")
    print(f"สร้างโฟลเดอร์อัปเดตแล้ว: {build_package(v)}")
    if not args.push:
        print(f"ยังไม่ได้ push — เมื่อเจ้าของสั่ง: python tools/release.py --push "
              f"(เครื่องที่ใช้ปุ่ม/ไฟล์อัปเดตออนไลน์จะเห็นหลัง push · โฟลเดอร์ dist ส่งต่อได้เลย)")
        return 0
    push(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
