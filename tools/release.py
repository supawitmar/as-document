# -*- coding: utf-8 -*-
"""
ปล่อย patch ให้เครื่องอื่นอัปเดต — รันบนเครื่องพัฒนา (repository git) เมื่องานพร้อมแล้ว

    python tools/release.py "เพิ่มประเภทเอกสาร บฑ.xx ..."  [--no-push] [--allow-names]

ขั้นตอน:
    1. ตรวจ: คอมไพล์ .py ทุกไฟล์, โหลดประเภทเอกสารครบไม่มี error, ไม่มีไฟล์เฉพาะเครื่อง/ไฟล์ตัวอย่างใน git,
       ไม่มีชื่อบุคคลที่ดูเป็นชื่อจริงในโค้ด (repository เป็น Public) — ถ้าเป็นชื่อสมมติจริง ใช้ --allow-names
    2. เพิ่ม build ใน version.json พร้อมข้อความ (เครื่องผู้ใช้เห็นข้อความนี้บนปุ่ม "อัปเดต")
    3. git commit + push ขึ้น GitHub (main) — เครื่องที่เปิดโปรแกรมครั้งถัดไปจะเห็นปุ่มอัปเดต
"""
import argparse
import datetime as dt
import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
VERSION_FILE = ROOT / "version.json"
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
                            and "re.compile" not in line and "(?" not in line:
                        problems.append(f"อาจเป็นชื่อจริง: {f}:{n} “{m[0]}” (ใช้ชื่อสมมติ หรือ --allow-names)")
    print(f"ประเภทเอกสาร: {', '.join(f'{d.id} ({d.name})' for d in dts.values())}")
    return problems


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="ปล่อย patch ให้เครื่องอื่นอัปเดต")
    ap.add_argument("message", help="ข้อความที่ผู้ใช้เครื่องอื่นจะเห็น เช่น 'เพิ่มประเภทเอกสาร บฑ.xx'")
    ap.add_argument("--no-push", action="store_true", help="commit อย่างเดียว ยังไม่ push")
    ap.add_argument("--allow-names", action="store_true", help="ยืนยันว่าชื่อบุคคลที่พบเป็นชื่อสมมติ/ชื่อที่ต้องเผยแพร่")
    args = ap.parse_args(argv)

    if git("rev-parse", "--abbrev-ref", "HEAD").strip() != "main":
        raise SystemExit("ต้องอยู่ที่ branch main")
    problems = checks(args.allow_names)
    if problems:
        git("reset", "-q")
        print("ยังปล่อย patch ไม่ได้:\n  - " + "\n  - ".join(problems))
        return 1

    v = json.loads(VERSION_FILE.read_text(encoding="utf-8")) if VERSION_FILE.exists() else {"build": 0, "changes": []}
    build = int(v.get("build", 0)) + 1
    today = dt.date.today().isoformat()
    v = {"build": build, "date": today,
         "changes": [{"build": build, "date": today, "text": args.message}] + v.get("changes", [])[:49]}
    VERSION_FILE.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    git("add", "-A")
    git("commit", "-q", "-m", f"patch build {build}: {args.message}\n\n{CO_AUTHOR}")
    print(f"commit build {build}: {args.message}")
    if args.no_push:
        print("ยังไม่ได้ push — สั่ง git push origin main เมื่อพร้อม")
        return 0
    git("push", "-q", "origin", "main")
    print("push ขึ้น GitHub แล้ว — เครื่องอื่นจะเห็นปุ่ม “อัปเดต” เมื่อเปิดโปรแกรมครั้งถัดไป")
    return 0


if __name__ == "__main__":
    sys.exit(main())
