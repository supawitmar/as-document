# -*- coding: utf-8 -*-
"""
บฑ.31 ทางเข้าที่ 1: ไฟล์ "Export (xx).doc" จากระบบฐานข้อมูลวิทยานิพนธ์/สารนิพนธ์
(HTML นามสกุล .doc — หนังสือเชิญ / หนังสือขออนุมัติอาจารย์พิเศษ ไทย/อังกฤษ) -> Letter -> จัดรูปแบบ -> .docx

    python fix_letters.py "Export (90).doc" "Export (91).doc" [--pdf] [-o DIR] [--doc] [--no-supervisor]
"""
import argparse
import re
import sys
from pathlib import Path

from core.text import NB, THAI, clean, is_word_saved, paragraphs, read_source, to_lines

from .layout import render_letters
from .letter import (EN_LABELS, NO_TITLE_TH, SUPERVISOR_INFORMED, Letter, course_of, fix_degree, fix_en, subject_of, use_attachment,
                     fix_text, kind_name, lang_label, learn_course, load_courses, output_stem, save_courses)

SIGN_OFF = r"ขอแสดงความนับถือ|Sincerely|Yours|Best regards|Kind regards"
LANG_SIGNALS = {
    "th": ("เรียน", "เรื่อง", "ขอแสดงความนับถือ", "ที่ อว", "จึงเรียน", "จึงขอเรียนเชิญ", "บัณฑิตวิทยาลัย มหาวิทยาลัยมหิดล"),
    "en": ("Dear ", "Sincerely", "Ref.No", "COURSE :", "would like to invite", "request your approval",
           "Faculty of Graduate Studies, Mahidol University"),
}


# ---------- อ่านไฟล์ ----------
def detect_lang(text: str) -> str:
    """ภาษาของหนังสือจากถ้อยคำในเอกสาร: 'th' / 'en' / '' (ตัดสินไม่ได้)"""
    score = {lang: sum(k in text for k in keys) for lang, keys in LANG_SIGNALS.items()}
    if score["th"] == score["en"]:
        return ""
    return max(score, key=score.get)


WORD_SAVED_NOTE = "อ่านจากไฟล์ที่เปิดแก้ไขใน Word แล้ว — โปรดตรวจความถูกต้องในตัวอย่างก่อนใช้"


def from_word_html(src: str) -> str:
    """ไฟล์ Export ที่เปิดแก้ไขใน Word แล้วบันทึก -> โครง HTML แบบไฟล์ดิบจากระบบ เพื่อใช้ตัวอ่านเดิม
    Word เปลี่ยน <div>/<br> ของระบบเป็น <p class=MsoNormal> (ชิดขวา = align=right) และแตกข้อความเป็น <span> ย่อย ๆ"""
    s = re.sub(r"(?is)<!\[if !supportLineBreakNewLine\]>.*?<!\[endif\]>", "", src)   # <br> ที่ Word เติมท้ายย่อหน้า
    s = re.sub(r"(?is)<!\[(?:if|endif)[^\]]*\]>", "", s)
    s = re.sub(r"(?is)<o:p>.*?</o:p>", "", s)
    s = re.sub(r"(?is)</?(?:span|b|i|u|font|a)\b[^>]*>", "", s)

    def block(m):
        right = re.search(r"align=\"?right|text-align:\s*right", m.group(1), re.I)
        return f'<div align="right">{m.group(2)}</div>' if right else f"<div>{m.group(2)}</div>"
    return re.sub(r"(?is)<p\b([^>]*)>(.*?)</p>", block, s)


def parse(src: str) -> Letter:
    if is_word_saved(src):
        src = from_word_html(src)
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    src = re.sub(r"(?is)<style.*?</style>|<link[^>]*>|<img[^>]*>", "", src)
    # ขึ้นบรรทัดใหม่ในซอร์ส = ช่องว่าง (เขียนแบบไม่ย้อนรอย: ช่องว่างยาวมากไม่ทำให้ช้า)
    src = re.sub(r"\s+", lambda m: " " if "\n" in m.group() or "\r" in m.group() else m.group(), src)
    i = src.lower().find("<body")
    body = src[i:] if i >= 0 else src

    L = Letter()
    m = re.search(r"(?is)<table.*?</table>", body)
    pre, table, post = (body[:m.start()], m.group(0), body[m.end():]) if m else (body, "", "")
    L.lang = detect_lang(" ".join(clean(x) for x in to_lines(body)))

    if L.lang == "en":
        parse_header_en(L, to_lines(pre))
    else:
        # ที่อยู่ส่วนราชการ (div ชิดขวาก่อน "ที่")
        am = re.search(r'(?is)<div[^>]*align="?right"?[^>]*>(.*?)</div>', pre)
        if am:
            L.address = [clean(x) for x in to_lines(am.group(1)) if clean(x)]
            pre = pre[am.end():]

        # หัวหนังสือ + เนื้อความก่อนตาราง
        lines = to_lines(pre)
        keys = [("ref", "ที่ "), ("date", "วันที่"), ("subject", "เรื่อง"), ("to", "เรียน")]
        rest_at = 0
        for idx, ln in enumerate(lines):
            c = clean(ln)
            for k, prefix in keys:
                if k not in L.header and c.startswith(prefix):
                    L.header[k] = c
                    rest_at = idx + 1
                    break
            if "to" in L.header:
                break
        L.body = paragraphs(lines[rest_at:])

    # ตาราง
    for tr in re.findall(r"(?is)<tr\b.*?</tr>", table):
        cells = [clean(" ".join(to_lines(td))) for td in re.findall(r"(?is)<td\b[^>]*>(.*?)</td>", tr)]
        if len(cells) >= 2:
            L.rows.append((cells[0].rstrip(": ").strip(), cells[1]))

    # คำลงท้าย / ลายมือชื่อ / ข้อมูลติดต่อ
    sm = re.search(rf'(?is)<div[^>]*align="?right"?[^>]*>\s*(?={SIGN_OFF})', post)
    if sm:
        closing_html, after = post[:sm.start()], post[sm.end():]
        end = after.lower().find("</div>")
        sig_html, contact_html = (after[:end], after[end + 6:]) if end >= 0 else (after, "")
    else:
        closing_html, sig_html, contact_html = post, "", ""
    L.closing = paragraphs(to_lines(closing_html), en=L.lang == "en")
    L.signature = [ln.strip(" ") for ln in to_lines(sig_html) if clean(ln)]
    L.contact = [clean(x) for x in to_lines(contact_html) if clean(x)]

    if L.lang == "en":
        text = " ".join(L.body).lower()
        L.kind = "approve" if "approv" in text else "invite" if "invit" in text else "generic"
    else:
        subj = L.header.get("subject", "")
        L.kind = "approve" if "อนุมัติ" in subj else "invite" if "เชิญ" in subj else "generic"
    return L


def parse_header_en(L: Letter, lines: list):
    """ภาษาอังกฤษ: [ชื่อสถาบัน] / Ref.No... / เดือน , ปี / Dear ... / เนื้อความ"""
    cl = [clean(x) for x in lines]
    ref = next((i for i, c in enumerate(cl) if re.match(r"(?i)ref\b", c)), None)
    dear = next((i for i, c in enumerate(cl) if c.startswith("Dear")), len(cl))
    top = ref if ref is not None else dear
    L.address = [c for c in cl[:top] if c]
    if ref is not None:
        L.header["ref"] = cl[ref]
        date = [c for c in cl[ref + 1:dear] if c and not c.startswith("Subject")]
        if date:
            L.header["date"] = " ".join(date)
    start = dear + 1
    if dear < len(cl):
        # ผู้รับยาวที่ถูกตัดบรรทัดเอง (แก้ใน Word) — บรรทัดต่อเนื่องก่อนบรรทัดว่างเป็นส่วนของ "Dear ..."
        to = [cl[dear]]
        while start < len(cl) and cl[start] and len(cl[start]) < 100 and not cl[start].endswith("."):
            to.append(cl[start])
            start += 1
        L.header["to"] = " ".join(to)
    L.body = paragraphs(lines[start:], en=True)


# ---------- ปรับเนื้อหา ----------
def normalize_en(L: Letter, courses: dict) -> list:
    if "to" in L.header:
        L.header["to"] = fix_en(L.header["to"])
    if "date" in L.header:
        d = clean(L.header["date"])
        m = re.fullmatch(r"([A-Za-z]+)\s*,\s*(\d{4})", d)       # "April , 2026" -> เว้นที่ให้เติมวัน
        L.header["date"] = f"{m[1]}{NB * 5}, {m[2]}" if m else d
    L.address = L.address or ["Mahidol University"]
    if subject_of(L):
        L.header["subject"] = subject_of(L)
    L.body = [fix_en(p) for p in L.body]
    L.body = [p + "." if re.search(r"[A-Za-z0-9)]$", p) else p for p in L.body]
    L.closing = [fix_en(p) for p in L.closing]

    rows = []
    c = course_of(L)
    for i, (label, value) in enumerate(L.rows):
        if c and i == c[0]:
            name = c[2]
            if THAI.search(name) and c[1] in courses:
                name = courses[c[1]]
            rows.append(("COURSE", f"{c[1]} {name}".strip()))
            continue
        label = EN_LABELS.get(label, label.upper())
        value = fix_text(value)
        if label == "TIME":
            value = re.sub(r"\s*น\.$", "", value)
        elif label != "DATE":
            value = fix_en(value)
        rows.append((label, value))
    L.rows = rows
    return []


def normalize(L: Letter, courses: dict, inform_supervisor: bool = True) -> list:
    """inform_supervisor=False: ไม่ต้องขออนุมัติผู้บังคับบัญชา -> ตัดประโยค "ทั้งนี้ได้แจ้งให้ผู้บังคับบัญชาของท่านทราบแล้ว" """
    if L.lang == "en":
        return normalize_en(L, courses)
    notes = []
    L.header = {k: NO_TITLE_TH.sub("", fix_text(v)) for k, v in L.header.items()}
    if "subject" in L.header:
        L.header["subject"] = subject_of(L)
    if "date" in L.header:
        L.header["date"] = "วันที่ " + NB * 4 + " " + L.header["date"][len("วันที่"):].strip()
    L.body = [NO_TITLE_TH.sub("", fix_degree(fix_text(p))) for p in L.body]
    L.closing = [fix_degree(fix_text(p)) for p in L.closing]
    if not inform_supervisor:
        L.closing = [SUPERVISOR_INFORMED.sub("", p) for p in L.closing]

    c = course_of(L)
    if c:
        i, code, name = c
        if THAI.search(name):     # ใช้ชื่อวิชาภาษาอังกฤษเสมอ
            if code in courses:
                name = courses[code]
            else:
                notes.append(f"ไม่พบชื่อวิชาภาษาอังกฤษของ {code} (ใช้ชื่อภาษาไทย) — "
                             f"แปลงหนังสือเชิญของวิชานี้ก่อน หรือเพิ่มใน courses.json")
        L.rows[i] = ("วิชา", f"{code} {name}".strip())
        # ข้อความ "...ในการสอนวิชา" ซ้ำกับหัวตาราง "วิชา :" จึงตัดออก
        if L.body and L.body[-1].endswith("วิชา"):
            L.body[-1] = L.body[-1][:-len("วิชา")].rstrip()
    L.rows = [(label, fix_text(v)) for label, v in L.rows]
    return notes


# ---------- ใช้จากโปรแกรม ----------
def collect(args_files: list) -> list:
    files = []
    for a in args_files:
        p = Path(a)
        if p.is_dir():
            files += sorted(x for x in p.glob("Export*.doc"))
        elif p.exists():
            files.append(p)
        else:
            print(f"!! ไม่พบไฟล์: {a}")
    return files


def pick_files() -> list:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    names = filedialog.askopenfilenames(
        title="เลือกไฟล์ Export ที่ต้องการปรับ",
        initialdir=str(Path.home() / "Downloads"),
        filetypes=[("Word export", "*.doc *.htm *.html"), ("All files", "*.*")])
    root.destroy()
    return [Path(n) for n in names]


def inspect(path: Path) -> dict:
    """อ่านไฟล์แบบเร็วเพื่อแสดงในหน้าจอ: ประเภทหนังสือ และผู้รับ"""
    try:
        src = read_source(path)
    except OSError as e:
        return {"ok": False, "kind": "", "kind_code": "", "lang": "", "to": "", "reason": str(e)}
    L = parse(src)
    if not L.header:
        return {"ok": False, "kind": "", "kind_code": "", "lang": "", "to": "",
                "reason": "ไม่พบหัวหนังสือ (ที่/วันที่/เรื่อง/เรียน หรือ Dear)"}
    if not L.lang:
        return {"ok": False, "kind": "", "kind_code": L.kind, "lang": "", "to": "",
                "reason": "ระบุไม่ได้ว่าเป็นหนังสือภาษาไทยหรือภาษาอังกฤษ — ตรวจไฟล์ต้นฉบับ"}
    to = L.header.get("to", "").removeprefix("เรียน").removeprefix("Dear")
    to = clean(fix_en(to) if L.lang == "en" else NO_TITLE_TH.sub("", to))
    normalize(L, load_courses())          # เพื่อแสดงชื่อไฟล์ที่จะได้ก่อนแปลง
    return {"ok": True, "kind": kind_name(L), "kind_code": L.kind, "lang": L.lang, "lang_label": lang_label(L.lang),
            "lang_source": "ตามถ้อยคำในไฟล์ Export", "to": to, "outputs_preview": [output_stem(L)], "reason": ""}


def convert(files: list, outdir=None, pdf=False, keep_doc=False, log=print, inform_supervisor=True, fmt=None,
            attachment=False, attach_files=()) -> list:
    """attachment=True: สอนมากกว่า 1 รายการ -> แถวหัวข้อ/วันที่/เวลา/สถานที่ เป็น "รายละเอียดตามเอกสารแนบ"
    attach_files: PDF ตารางสอนที่ต่อท้ายหนังสือทุกฉบับ"""
    """แปลงไฟล์ทั้งหมด คืนรายการผลลัพธ์
    [{'src': Path, 'kind': str, 'docx': Path|None, 'pdf': Path|None, 'doc': Path|None, 'notes': [...], 'error': str}]"""
    courses = load_courses()
    results, letters = [], []
    for f in files:
        f = Path(f)
        try:
            src = read_source(f)
        except OSError as e:
            results.append(dict(src=f, kind="", docx=None, pdf=None, doc=None, notes=[], error=str(e)))
            continue
        L = parse(src)
        L.word_saved = is_word_saved(src)
        if not L.lang:
            msg = "ระบุไม่ได้ว่าเป็นหนังสือภาษาไทยหรือภาษาอังกฤษ"
            log(f"!! {f.name}: {msg}")
            results.append(dict(src=f, kind="", docx=None, pdf=None, doc=None, notes=[], error=msg))
            continue
        learn_course(L, courses)
        letters.append((f, L))
    save_courses(courses)
    # หนังสือเชิญก่อน เพื่อให้หนังสืออนุมัติใช้ชื่อวิชาภาษาอังกฤษจากหนังสือเชิญได้
    letters.sort(key=lambda x: x[1].kind != "invite")
    if not letters:
        return results

    entries = []
    for f, L in letters:
        notes = normalize(L, courses, inform_supervisor)
        if getattr(L, "word_saved", False):
            notes.insert(0, WORD_SAVED_NOTE)
        if attachment:
            use_attachment(L)
        if clean(re.sub(r"^(?:เรียน|Dear)", "", L.header.get("to", ""))) in ("", "-"):
            notes.append("ไฟล์ต้นฉบับไม่มีชื่อผู้รับ (บรรทัด เรียน/Dear ว่าง) — กรอกในระบบแล้ว export ใหม่ หรือแก้ในไฟล์ Word")
        od = Path(outdir) if outdir else f.parent
        entries.append(dict(src=f, letter=L, outdir=od, stem=output_stem(L), notes=notes, attach=list(attach_files)))
    return results + render_letters(entries, pdf=pdf, keep_doc=keep_doc, log=log, fmt=fmt)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="ปรับไฟล์ Export จากระบบบัณฑิตวิทยาลัยให้เป็นรูปแบบมาตรฐาน")
    ap.add_argument("files", nargs="*")
    ap.add_argument("-o", "--outdir")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--doc", action="store_true")
    ap.add_argument("--no-supervisor", action="store_true",
                    help="ไม่ต้องขออนุมัติผู้บังคับบัญชา: ตัดประโยค 'ทั้งนี้ได้แจ้งให้ผู้บังคับบัญชาของท่านทราบแล้ว'")
    args = ap.parse_args(argv)

    files = collect(args.files) if args.files else pick_files()
    if not files:
        print("ไม่มีไฟล์ให้ปรับ")
        return 1
    # PDF หน้า บฑ.31 -> สร้างหนังสือจากข้อมูลแบบฟอร์ม (หนังสือขออนุมัติด้วย ถ้าแบบฟอร์มระบุ)
    pdfs = [f for f in files if f.suffix.lower() == ".pdf"]
    files = [f for f in files if f.suffix.lower() != ".pdf"]
    total = ok = 0
    if pdfs:
        from . import eform
        for f in pdfs:
            r = eform.convert(f, args.outdir, args.pdf, want_approve=not args.no_supervisor)
            for n in r["notes"]:
                print(f"   หมายเหตุ: {n}")
            if r["error"]:
                print(f"!! {f.name}: {r['error']}")
            total += 1
            ok += r["ok"]
    if files:
        results = convert(files, args.outdir, args.pdf, args.doc, inform_supervisor=not args.no_supervisor)
        total += len(results)
        ok += sum(1 for r in results if r["docx"])
    print(f"\nเสร็จ {ok}/{total} ไฟล์")
    return 0 if total and ok == total else 2
