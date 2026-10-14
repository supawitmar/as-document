# -*- coding: utf-8 -*-
"""
แปลงเอกสาร Word HTML เป็น .docx (+ .pdf) ด้วย Microsoft Word — ใช้ร่วมกันทุกประเภทเอกสาร

ประเภทเอกสารส่ง "งาน" มาเป็นรายการ entry:
    {'src': Path, 'outdir': Path, 'stem': ชื่อไฟล์ไม่รวมนามสกุล, 'kind': ชื่อเรียกผลลัพธ์, 'notes': [...],
     'build': ฟังก์ชัน(logo_src) -> Word HTML ทั้งไฟล์}
ทุกงานในรอบเดียวแปลงใน Word ตัวเดียว (assets/to_docx.ps1); path ชั่วคราวเป็น ASCII เพราะส่งผ่าน PowerShell/COM
"""
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from core import ASSETS

LOGO_URL = "https://graduate.mahidol.ac.th/prof/admin/pic/logo_mu1.jpg"
LOGO_FILE = ASSETS / "logo_mu1.jpg"


def logo_source(tmp: Path) -> str:
    """คัดลอกโลโก้ไว้ข้างไฟล์ HTML ชั่วคราว ให้ Word ฝังรูปลงเอกสารได้แม้ไม่มีอินเทอร์เน็ต"""
    if not LOGO_FILE.exists():
        try:
            with urllib.request.urlopen(LOGO_URL, timeout=15) as r:
                LOGO_FILE.write_bytes(r.read())
        except OSError:
            return LOGO_URL
    shutil.copy(LOGO_FILE, tmp / "logo.jpg")
    return "logo.jpg"


def word_convert(jobs: list) -> dict:
    """jobs: [{'in':..., 'docx':..., 'pdf':...}] (path ภาษาอังกฤษใน temp) -> {in: error or ''}"""
    jf = Path(jobs[0]["in"]).parent / "jobs.json"
    jf.write_text(json.dumps(jobs), encoding="utf-8")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(ASSETS / "to_docx.ps1"), "-Jobs", str(jf)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    results = {}
    for ln in r.stdout.splitlines():
        if ln.startswith(("OK\t", "ERR\t")):
            status, path, *msg = ln.split("\t")
            results[path] = "" if status == "OK" else (msg[0] if msg else "error")
    if not results:
        raise RuntimeError((r.stderr or r.stdout or "ไม่สามารถเรียก Microsoft Word").strip())
    return results


def unique(path: Path) -> Path:
    """ไม่เขียนทับไฟล์เดิม: ต่อท้าย (2), (3) …"""
    if not path.exists():
        return path
    n = 2
    while (p := path.with_name(f"{path.stem} ({n}){path.suffix}")).exists():
        n += 1
    return p


def render(entries: list, pdf=False, keep_doc=False, log=print) -> list:
    """สร้างไฟล์จาก entry ทั้งหมด (ดูหัวไฟล์) คืน
    [{'src', 'kind', 'docx': Path|None, 'pdf': Path|None, 'doc': Path|None, 'notes', 'error'}]
    ถ้า Word ใช้ไม่ได้ บันทึกเป็น .doc (Word HTML) แทน"""
    if not entries:
        return []
    tmp = Path(tempfile.mkdtemp(prefix="fixletters_"))
    logo = logo_source(tmp)
    jobs = []
    for n, e in enumerate(entries):
        od, stem = Path(e["outdir"]), e["stem"]
        od.mkdir(parents=True, exist_ok=True)
        tmp_html = tmp / f"doc{n}.htm"
        tmp_html.write_text(e["build"](logo), encoding="utf-8")
        job = {"in": str(tmp_html), "docx": str(tmp / f"doc{n}.docx")}
        if pdf:
            job["pdf"] = str(tmp / f"doc{n}.pdf")
        res = dict(src=e["src"], kind=e["kind"], docx=None, pdf=None, doc=None, notes=e["notes"], error="")
        if keep_doc:
            res["doc"] = unique(od / f"{stem}.doc")
            res["doc"].write_text(e["build"](LOGO_URL), encoding="utf-8")
            log(f"   .doc  -> {res['doc']}")
        jobs.append((job, od, stem, res))

    log("กำลังแปลงด้วย Microsoft Word ...")
    try:
        status = word_convert([j for j, *_ in jobs])
    except RuntimeError as e:
        log(f"!! แปลงเป็น .docx ไม่สำเร็จ ({e}) — บันทึกเป็น .doc แทน")
        status = None

    results = []
    for job, od, stem, res in jobs:
        name = Path(res["src"]).name
        err = "Word ไม่ทำงาน" if status is None else status.get(job["in"], "ไม่ทราบสาเหตุ")
        if err:
            fallback = unique(od / f"{stem}.doc")
            fallback.write_text(Path(job["in"]).read_text(encoding="utf-8")
                                .replace(f'src="{logo}"', f'src="{LOGO_URL}"'), encoding="utf-8")
            res.update(error=err, doc=fallback)
            log(f"!! {name}: {err} -> บันทึกเป็น {fallback}")
        else:
            res["docx"] = unique(od / f"{stem}.docx")
            shutil.move(job["docx"], res["docx"])
            log(f"OK {name} -> {res['docx']}")
            if job.get("pdf") and Path(job["pdf"]).exists():
                res["pdf"] = unique(od / f"{stem}.pdf")
                shutil.move(job["pdf"], res["pdf"])
                log(f"   pdf   -> {res['pdf']}")
            for note in res["notes"]:
                log(f"   หมายเหตุ: {note}")
        results.append(res)
    shutil.rmtree(tmp, ignore_errors=True)
    return results
