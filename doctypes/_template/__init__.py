# -*- coding: utf-8 -*-
"""
แม่แบบประเภทเอกสารใหม่ — คัดลอกทั้งโฟลเดอร์นี้เป็น doctypes/<รหัส>/ (ชื่อห้ามขึ้นต้นด้วย _) แล้วแก้ตามจุด TODO
ขั้นตอนเต็ม (เก็บตัวอย่าง -> เทียบรูปแบบ -> เขียนกฎ -> ตรวจ): doctypes/README.md

โฟลเดอร์ที่ขึ้นต้นด้วย _ จะไม่ถูกโหลดเข้าหน้าโปรแกรม ไฟล์นี้จึงเป็นแค่ตัวอย่างที่รันได้จริง:
อ่านไฟล์ HTML ที่ระบบ export (แบบเดียวกับไฟล์ Export ของบฑ.31) -> ดึงหัวเรื่องและย่อหน้า -> จัดเป็น TH Sarabun New 16pt
"""
import re
from pathlib import Path

from core import render
from core.doctype import DocType
from core.text import clean, is_word_saved, paragraphs, read_source, safe_stem, to_lines
from core.wordhtml import esc, font_css, paragraph, wrap_document

# ---------- รูปแบบ (layout) — ค่าที่ได้จาก tools/learn.py inspect <ไฟล์ตัวอย่างที่เจ้าหน้าที่จัดแล้ว> ----------
FONT = font_css("TH Sarabun New", 16)                 # TODO: ฟอนต์/ขนาดตามตัวอย่าง
LINE = "line-height:18.0pt;mso-line-height-rule:exactly;"   # TODO: ระยะบรรทัดตามตัวอย่าง
FIRST_LINE_INDENT = "text-indent:2.0cm;"              # TODO: ย่อหน้าบรรทัดแรก


def parse(src: str) -> dict:
    """TODO: แยกส่วนของเอกสารจากไฟล์ต้นฉบับ — เริ่มจากดูว่าไฟล์ดิบมีโครงสร้างอย่างไร"""
    body = re.sub(r"(?is)<style.*?</style>|<!--.*?-->", "", src)
    lines = to_lines(body)
    paras = paragraphs(lines)
    return {"title": paras[0] if paras else "", "body": paras[1:]}


def build_html(doc: dict, logo_src: str) -> str:
    """TODO: จัดหน้าตามไฟล์ตัวอย่าง (ดูตัวอย่างที่ละเอียดกว่าใน doctypes/bt31/layout.py)"""
    out = [paragraph(f'<img width=90 height=90 src="{logo_src}">', align="center", font=FONT),
           paragraph(esc(doc["title"]), align="center", style=LINE, font=FONT)]
    for p in doc["body"]:
        out.append(paragraph(esc(p), style=LINE + FIRST_LINE_INDENT + "text-align:justify;text-justify:inter-cluster;",
                             font=FONT))
    return wrap_document(out)


class Template(DocType):
    id = "_template"                      # TODO: รหัสภาษาอังกฤษ = ชื่อโฟลเดอร์
    name = "ชื่อเอกสาร"                    # TODO: ชื่อที่แสดงในหน้าเลือกประเภทเอกสาร
    description = "คำอธิบายสั้น ๆ ว่ารับไฟล์อะไร ได้ไฟล์อะไร"
    icon = "file"                         # ไอคอน: invite approve file form cert calendar book users (web/index.html)
    color = "amber"                       # สี: blue violet teal amber rose green
    order = 50
    options = {}                          # ตัวเลือกของประเภทนี้ เช่น {"with_attachment": False}
    pickers = {"src": {"title": "เลือกไฟล์", "filters": [("ไฟล์จากระบบ", "*.doc *.htm *.html"), ("ทุกไฟล์", "*.*")]}}
    downloads = None                      # หรือ {"glob": "Export*.doc", "label": "ไฟล์ใหม่ใน Downloads", "title": "...", "empty": "..."}
    drop_hint = "รองรับไฟล์ .doc / .html จากระบบ"
    ui = {
        "modes": [],                      # ไม่มีแท็บ = แสดงทุกช่อง
        "slots": [
            {"id": "src", "title": "ไฟล์ต้นฉบับ", "desc": "ไฟล์ที่ดาวน์โหลดจากระบบ", "icon": "file", "color": "amber",
             "accept": [".doc", ".htm", ".html"], "pick": "src", "pick_label": "เลือกไฟล์",
             "zone_title": "ลากไฟล์มาวางที่นี่", "zone_desc": "ไฟล์ .doc ที่ดาวน์โหลดจากระบบ"},
        ],
    }

    def inspect(self, path: Path) -> dict:
        try:
            src = read_source(path)
        except OSError as e:
            return {"ok": False, "reason": str(e)}
        if is_word_saved(src):
            return {"ok": False, "reason": "เป็นไฟล์ Word แล้ว (ไม่ใช่ไฟล์จากระบบ)"}
        doc = parse(src)
        if not doc["title"]:
            return {"ok": False, "reason": "ไม่พบเนื้อหาเอกสาร"}
        return {"ok": True, "slot": "src", "kind": self.name, "subtitle": doc["title"],
                "outputs_preview": [{"name": self.output_stem(doc)}]}

    def output_stem(self, doc: dict) -> str:
        return safe_stem(f"{self.name} {clean(doc['title'])[:60]}")      # TODO: รูปแบบชื่อไฟล์ที่เจ้าหน้าที่ใช้

    def convert(self, jobs: list, options: dict, pdf: bool, extra: dict, log=lambda m: None) -> dict:
        entries, ids = [], []
        for j in jobs:
            doc = parse(read_source(j.path))
            entries.append(dict(src=j.path, outdir=j.outdir, stem=self.output_stem(doc), kind=self.name, notes=[],
                                build=lambda logo, d=doc: build_html(d, logo)))
            ids.append(j.id)
        out = {}
        for jid, r in zip(ids, render.render(entries, log=log, fmt="both" if pdf == "both" else "pdf" if pdf else "docx")):
            done = bool(r["docx"] or r["pdf"])
            out[jid] = {"ok": done, "error": r["error"], "notes": r["notes"],
                        "outputs": [{"kind": r["kind"], "docx": r["docx"], "pdf": r["pdf"], "doc": r["doc"]}]
                        if done else []}
        return out


DOCTYPE = Template()
