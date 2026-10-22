# -*- coding: utf-8 -*-
"""
แปลงเอกสาร Word HTML เป็น .docx (+ .pdf) ด้วย Microsoft Word — ใช้ร่วมกันทุกประเภทเอกสาร

ประเภทเอกสารส่ง "งาน" มาเป็นรายการ entry:
    {'src': Path, 'outdir': Path, 'stem': ชื่อไฟล์ไม่รวมนามสกุล, 'kind': ชื่อเรียกผลลัพธ์, 'notes': [...],
     'build': ฟังก์ชัน(logo_src) -> Word HTML ทั้งไฟล์, 'attach': [PDF ที่ต่อท้ายเอกสาร] (ไม่บังคับ)}
    ไฟล์ชื่อเดียวกันในปลายทางถูกเขียนทับ (ฉบับปรับปรุง) — ยกเว้นไฟล์เดิมเปิดค้างอยู่ จะได้ชื่อใหม่ (2) … แทน
    หรือแทน 'build' ด้วย 'source': ไฟล์ Word ที่จัดรูปแบบแล้ว (.docx) — เปิดแล้วบันทึกตามต้นฉบับ ไม่สร้างใหม่
เอกสารแนบต่อท้ายเฉพาะไฟล์ .pdf (หน้าจริงของ PDF) — ไฟล์ .docx เป็นหนังสืออย่างเดียว
ทุกงานในรอบเดียวแปลงใน Word ตัวเดียว (assets/to_docx.ps1); path ชั่วคราวเป็น ASCII เพราะส่งผ่าน PowerShell/COM
"""
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from core import ASSETS, NO_WINDOW

LOGO_URL = "https://graduate.mahidol.ac.th/prof/admin/pic/logo_mu1.jpg"
LOGO_FILE = ASSETS / "logo_mu1.jpg"


def logo_source(tmp: Path) -> str:
    """คัดลอกโลโก้ไว้ข้างไฟล์ HTML ชั่วคราว ให้ Word ฝังรูปลงเอกสารได้แม้ไม่มีอินเทอร์เน็ต"""
    if not LOGO_FILE.exists():
        try:
            req = urllib.request.Request(LOGO_URL, headers={"User-Agent": "as-document (+https://github.com/supawitmar/as-document)"})
            with urllib.request.urlopen(req, timeout=15) as r:
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
        capture_output=True, text=True, encoding="utf-8", errors="replace", **NO_WINDOW)
    results = {}
    for ln in r.stdout.splitlines():
        if ln.startswith(("OK\t", "ERR\t")):
            status, path, *msg = ln.split("\t")
            results[path] = "" if status == "OK" else (msg[0] if msg else "error")
    if not results:
        raise RuntimeError((r.stderr or r.stdout or "ไม่สามารถเรียก Microsoft Word").strip())
    return results


def save_file(src: Path, dest: Path, notes: list = None, move: bool = True) -> Path:
    """บันทึกไฟล์ผลลัพธ์: มีไฟล์ชื่อเดียวกันอยู่แล้ว = เขียนทับ (ถือเป็นฉบับปรับปรุง)
    ถ้าไฟล์เดิมเปิดค้างอยู่ (Word / โปรแกรมอ่าน PDF ล็อกไฟล์) บันทึกเป็นชื่อใหม่ (2), (3) … แทน และจดหมายเหตุ"""
    src, dest = Path(src), Path(dest)
    try:
        shutil.copyfile(src, dest)
    except PermissionError:
        alt = unique(dest)
        shutil.copyfile(src, alt)
        if notes is not None:
            notes.append(f"ไฟล์ “{dest.name}” เปิดค้างอยู่ จึงบันทึกเป็น “{alt.name}” แทน — "
                         "ปิดไฟล์เดิมแล้วกดสร้างใหม่ ถ้าต้องการเขียนทับ")
        dest = alt
    if move:
        src.unlink(missing_ok=True)
    return dest


def unique(path: Path) -> Path:
    """ชื่อที่ยังไม่มีไฟล์: ต่อท้าย (2), (3) … (ใช้เมื่อเขียนทับไฟล์เดิมไม่ได้)"""
    if not path.exists():
        return path
    n = 2
    while (p := path.with_name(f"{path.stem} ({n}){path.suffix}")).exists():
        n += 1
    return p


FORMATS = ("docx", "pdf", "both")


def merge_pdf(letter: Path, pdfs: list):
    """ต่อหน้าของ PDF แนบท้ายไฟล์ PDF หนังสือ"""
    import pymupdf
    merged = letter.with_name(letter.stem + "_m.pdf")
    with pymupdf.open(str(letter)) as out:
        for p in pdfs:
            with pymupdf.open(str(p)) as src:
                out.insert_pdf(src)
        out.save(str(merged), garbage=3, deflate=True)
    merged.replace(letter)


def render(entries: list, pdf=False, keep_doc=False, log=print, fmt=None) -> list:
    """สร้างไฟล์จาก entry ทั้งหมด (ดูหัวไฟล์) คืน
    [{'src', 'kind', 'docx': Path|None, 'pdf': Path|None, 'doc': Path|None, 'notes', 'error'}]
    fmt: 'docx' = Word อย่างเดียว / 'pdf' = PDF อย่างเดียว / 'both' — ไม่ระบุ = แบบเดิม (pdf=True -> 'both')
    ถ้า Word ใช้ไม่ได้ บันทึกเป็น .doc (Word HTML) แทน"""
    if not entries:
        return []
    fmt = fmt if fmt in FORMATS else ("both" if pdf else "docx")
    tmp = Path(tempfile.mkdtemp(prefix="fixletters_"))
    logo = logo_source(tmp)
    jobs = []
    for n, e in enumerate(entries):
        od, stem = Path(e["outdir"]), e["stem"]
        od.mkdir(parents=True, exist_ok=True)
        if e.get("source"):                     # ไฟล์ Word ที่มีอยู่แล้ว: คัดลอกไปที่ path ภาษาอังกฤษ แล้วให้ Word เปิด
            tmp_html = tmp / f"doc{n}{Path(e['source']).suffix.lower()}"
            shutil.copy2(e["source"], tmp_html)
        else:
            tmp_html = tmp / f"doc{n}.htm"
            tmp_html.write_text(e["build"](logo), encoding="utf-8")
        job = {"in": str(tmp_html), "tighten": bool(e.get("tighten"))}
        if fmt != "pdf":
            job["docx"] = str(tmp / f"doc{n}.docx")
        if fmt != "docx":
            job["pdf"] = str(tmp / f"doc{n}.pdf")
        attach = [Path(a) for a in e.get("attach") or [] if Path(a).exists()]
        res = dict(src=e["src"], kind=e["kind"], docx=None, pdf=None, doc=None, notes=e["notes"], error="")
        if keep_doc and not e.get("source"):
            doc_tmp = tmp / f"doc{n}_keep.doc"
            doc_tmp.write_text(e["build"](LOGO_URL), encoding="utf-8")
            res["doc"] = save_file(doc_tmp, od / f"{stem}.doc", res["notes"])
            log(f"   .doc  -> {res['doc']}")
        jobs.append((job, od, stem, res, attach))

    log("กำลังแปลงด้วย Microsoft Word ...")
    try:
        status = word_convert([j for j, *_ in jobs])
    except RuntimeError as e:
        log(f"!! แปลงเป็น .docx ไม่สำเร็จ ({e}) — บันทึกเป็น .doc แทน")
        status = None

    results = []
    for job, od, stem, res, attach in jobs:
        name = Path(res["src"]).name
        err = "Word ไม่ทำงาน" if status is None else status.get(job["in"], "ไม่ทราบสาเหตุ")
        if err and job["in"].endswith((".docx", ".doc")):      # ไฟล์ Word ต้นฉบับ: ไม่มีอะไรให้บันทึกแทน
            res.update(error=f"แปลงด้วย Word ไม่สำเร็จ: {err}")
            log(f"!! {name}: {err}")
        elif err:
            fb_tmp = tmp / f"doc{n}_fallback.doc"
            fb_tmp.write_text(Path(job["in"]).read_text(encoding="utf-8")
                              .replace(f'src="{logo}"', f'src="{LOGO_URL}"'), encoding="utf-8")
            fallback = save_file(fb_tmp, od / f"{stem}.doc", res["notes"])
            res.update(error=err, doc=fallback)
            log(f"!! {name}: {err} -> บันทึกเป็น {fallback}")
        else:
            for ext in ("docx", "pdf"):
                if job.get(ext) and Path(job[ext]).exists():
                    if ext == "pdf" and attach:
                        merge_pdf(Path(job[ext]), attach)
                    res[ext] = save_file(Path(job[ext]), od / f"{stem}.{ext}", res["notes"])
                    log(f"OK {name} -> {res[ext]}")
            for note in res["notes"]:
                log(f"   หมายเหตุ: {note}")
        results.append(res)
    shutil.rmtree(tmp, ignore_errors=True)
    return results
