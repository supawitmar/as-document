# -*- coding: utf-8 -*-
"""
บฑ.31 ทางเข้าที่ 3: ไฟล์ Word (.docx) — แยก 3 แบบ (classify) โดยไม่ต้องเปิด Word:
    "formatted"  หนังสือที่ระบบจัดแล้วนำไปแก้ (ข้อความส่วนใหญ่เป็นฟอนต์ TH Sarabun — ไฟล์ Export ใช้ฟอนต์เว็บ Sarabun 17px)
                 → แปลงเป็น PDF ตามต้นฉบับทุกตัวอักษร (ไม่จัดรูปแบบซ้ำ) ชื่อไฟล์ PDF = ชื่อไฟล์ Word
    "export"     ไฟล์ Export จากระบบที่ถูกบันทึกเป็น .docx (Save As) — โครงเป็นหนังสือ (มีผู้รับ + ตารางวิชา) แต่ยังไม่ได้จัด
                 → แปลงเป็น HTML แบบไฟล์ที่ Word บันทึก (as_export) แล้วจัดรูปแบบเหมือนไฟล์ Export
    "other"      ไฟล์ Word อื่น → แปลงเป็น PDF ตามต้นฉบับ
ทุกแบบต่อตารางสอนท้าย PDF ได้เหมือนหนังสืออื่น
"""
import hashlib
import html
import re
import tempfile
import zipfile
from pathlib import Path

from core import render
from core.text import clean

from .letter import lang_label

EXTS = [".docx"]
NOTE = "แปลงจากไฟล์ Word ตามต้นฉบับ (ไม่จัดรูปแบบซ้ำ) — ได้เป็นไฟล์ PDF"
EXPORT_NOTE = "ไฟล์ Export ที่บันทึกเป็น .docx (ยังไม่ได้จัดรูปแบบ) — จัดรูปแบบให้ตามมาตรฐาน"
CACHE = Path(tempfile.gettempdir()) / "fixletters_docx"      # HTML ที่แปลงจาก .docx (ใช้กับตัวอ่านไฟล์ Export)
FORMATTED_SHARE = 0.5      # สัดส่วนข้อความที่เป็นฟอนต์ TH Sarabun ขั้นต่ำ ที่ถือว่าระบบจัดรูปแบบแล้ว


def is_word_file(path: Path) -> bool:
    return Path(path).suffix.lower() in EXTS


def _xml(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode("utf-8", "replace")


def th_sarabun_share(xml: str) -> float:
    """สัดส่วนช่วงข้อความ (run) ที่ใช้ฟอนต์ TH Sarabun New / TH SarabunPSK — หนังสือที่ระบบจัด ≈ 0.75–1.0"""
    runs = [r for r in re.findall(r"(?s)<w:r(?: [^>]*)?>.*?</w:r>", xml) if re.search(r"<w:t(?: [^>]*)?>[^<]*\S", r)]
    return sum("TH Sarabun" in r for r in runs) / len(runs) if runs else 0.0


def docx_to_html(xml: str) -> str:
    """เนื้อหา .docx → HTML แบบที่ Word บันทึก (ย่อหน้า <p> ชิดขวา/ปกติ, <br>, ตาราง) เพื่อให้ export.from_word_html อ่านได้"""
    def para(p: str) -> str:
        right = re.search(r'<w:jc w:val="(?:right|end)"', p)
        body = re.sub(r"(?s)<w:pPr>.*?</w:pPr>", "", p)
        parts = []
        for m in re.finditer(r"(?s)<w:t(?: [^>]*)?>(.*?)</w:t>|<w:(?:br|cr)\b[^>]*/>|<w:tab\b[^>]*/>", body):
            tok = m.group(0)
            parts.append(m.group(1) if m.group(1) is not None else "<br>" if tok.startswith(("<w:br", "<w:cr")) else " ")
        content = "".join(parts) or "&nbsp;"
        return f"<p class=MsoNormal align=right>{content}</p>\n" if right else f"<p class=MsoNormal>{content}</p>\n"

    out = []
    body = xml.split("<w:body>", 1)[-1]
    for m in re.finditer(r"(?s)<w:tbl>.*?</w:tbl>|<w:p(?: [^>]*)?/>|<w:p[ >].*?</w:p>", body):
        block = m.group(0)
        if block.startswith("<w:tbl>"):
            rows = []
            for tr in re.findall(r"(?s)<w:tr[ >].*?</w:tr>", block):
                cells = ["<td>" + "".join(para(p) for p in re.findall(r"(?s)<w:p[ >].*?</w:p>", tc)) + "</td>"
                         for tc in re.findall(r"(?s)<w:tc>.*?</w:tc>", tr)]
                rows.append("<tr>" + "".join(cells) + "</tr>")
            out.append("<table>" + "".join(rows) + "</table>\n")
        elif block.endswith("/>"):
            out.append("<p class=MsoNormal>&nbsp;</p>\n")
        else:
            out.append(para(block))
    return ("<html><head><meta name=ProgId content=Word.Document></head>\n<body><div class=WordSection1>\n"
            + "".join(out) + "</div></body></html>\n")


def as_export(path: Path) -> Path:
    """ไฟล์ HTML (นามสกุล .doc) ที่แปลงจาก .docx ไว้ใช้กับตัวอ่านไฟล์ Export — เก็บแคชตามเนื้อไฟล์"""
    data = Path(path).read_bytes()
    out = CACHE / hashlib.sha1(data).hexdigest()[:16] / f"{Path(path).stem}.doc"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(docx_to_html(_xml(Path(path))), encoding="utf-8")
    return out


def classify(path: Path) -> str:
    """'formatted' | 'export' | 'other' (ดูหัวไฟล์)"""
    xml = _xml(Path(path))
    if th_sarabun_share(xml) >= FORMATTED_SHARE:
        return "formatted"
    from .export import parse, read_source            # นำเข้าตอนใช้ (export นำเข้าโมดูลนี้ไม่ได้ — วนกัน)
    L = parse(read_source(as_export(path)))
    return "export" if L.lang and L.header.get("to") and L.rows else "other"


def paragraphs(path: Path) -> list:
    """ข้อความแต่ละย่อหน้าใน .docx (อ่านจาก word/document.xml — ไม่ต้องเปิด Word)"""
    xml = _xml(path)
    out = []
    for p in re.findall(r"(?s)<w:p[ >].*?</w:p>", xml):
        p = re.sub(r"<w:(?:br|cr)\b[^>]*/>", "\n", p)
        p = re.sub(r"<w:tab\b[^>]*/>", " ", p)
        text = "".join(a or b for a, b in re.findall(r"(?s)<w:t(?: [^>]*)?>(.*?)</w:t>|(\n)", p))
        out += [clean(html.unescape(t)) for t in text.split("\n")]
    return [t for t in out if t]


def inspect(path: Path) -> dict:
    from .export import detect_lang          # export นำเข้าโมดูลนี้ไม่ได้ (วนกัน) — นำเข้าตอนใช้
    try:
        lines = paragraphs(Path(path))
    except (OSError, KeyError, zipfile.BadZipFile) as e:
        return {"ok": False, "kind": "", "kind_code": "", "lang": "", "to": "", "reason": f"เปิดไฟล์ Word ไม่ได้: {e}"}
    if not lines:
        return {"ok": False, "kind": "", "kind_code": "", "lang": "", "to": "", "reason": "ไฟล์ Word ไม่มีข้อความ"}
    text = " ".join(lines)
    lang = detect_lang(text) or "th"
    head = " ".join(lines[:12])              # หัวหนังสือ (เรื่อง / Subject)
    kind = "approve" if re.search(r"อนุมัติ|(?i:approv)", head) else "invite"
    to = next((re.sub(r"^(?:เรียน|Dear)\s*", "", t) for t in lines if re.match(r"(?:เรียน|Dear)\b", t)), "")
    return {"ok": True, "kind": {"approve": "หนังสือขออนุมัติ", "invite": "หนังสือเชิญ"}[kind] + " (ไฟล์ Word)",
            "kind_code": kind, "lang": lang, "lang_label": lang_label(lang), "lang_source": "ตามข้อความในไฟล์ Word",
            "to": to, "subtitle2": "ไฟล์ Word ที่จัดรูปแบบแล้ว — แปลงเป็น PDF ตามต้นฉบับ (ไม่จัดรูปแบบซ้ำ)",
            "outputs_preview": [Path(path).stem], "reason": ""}


def convert(path: Path, outdir=None, attach_files=(), log=print) -> dict:
    """คืนผลแบบเดียวกับ core.render.render (หนึ่งรายการ) — ได้ .pdf เสมอ ไม่ว่าเลือกรูปแบบไหน (.docx คือไฟล์ต้นฉบับอยู่แล้ว)"""
    path = Path(path)
    info = inspect(path)
    if not info["ok"]:
        return dict(src=path, kind="", docx=None, pdf=None, doc=None, notes=[], error=info["reason"])
    entry = dict(src=path, outdir=Path(outdir) if outdir else path.parent, stem=path.stem, kind=info["kind"],
                 notes=[NOTE], source=path, attach=list(attach_files))
    return render.render([entry], log=log, fmt="pdf")[0]
