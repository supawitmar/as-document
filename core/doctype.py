# -*- coding: utf-8 -*-
"""
DocType — สัญญาระหว่าง hub (app.py + web/index.html) กับประเภทเอกสารแต่ละตัวใน doctypes/

hub ไม่รู้จักรายละเอียดของเอกสารใดเลย: มันแสดงหน้าจอตาม manifest() อ่านไฟล์ด้วย inspect()
และสั่งสร้างไฟล์ด้วย convert() — การเพิ่มประเภทเอกสารใหม่จึงไม่ต้องแก้ hub (ดู doctypes/README.md)

หน้าจอของประเภทเอกสาร (ui):
    modes  แท็บวิธีนำเข้า เช่น "ไฟล์ Export" / "PDF e-Form" — แต่ละแท็บมีช่องวางไฟล์ (slots) และแถวสรุป (summary)
    checks ตัวเลือกติ๊กในแผง "ตัวเลือก" ด้านขวา [{'option', 'label', 'desc'}] (ค่าเก็บใน options)
    slots  ช่องวางไฟล์: นามสกุลที่รับ (accept), สี, ไอคอน, ตัวเลือกติ๊กที่หัวช่อง (toggle), companion (ไฟล์ประกอบ
           เช่นเอกสารแนบ: ไม่ได้ผลลัพธ์ของตัวเอง แต่ส่งไปใน jobs ทุกครั้งที่แปลง/ดูตัวอย่าง),
           max_mb (ขนาดไฟล์สูงสุดของช่องนี้ — ไม่ระบุ = ใช้ max_mb ของประเภทเอกสาร),
           ตัวเลือกที่ต้องเปิดก่อนจึงใช้ช่องได้ (gate)
    ไอคอนที่ใช้ได้: ดูชุด P ใน web/index.html · สีที่ใช้ได้: blue violet teal amber rose green

ผล inspect(path) ต่อไฟล์ (แสดงเป็นแถวในหน้าจอก่อนแปลง):
    ok, reason            อ่านได้/เหตุผลที่ใช้ไม่ได้
    slot                  ช่องที่ไฟล์นี้ควรอยู่ (ถ้าผู้ใช้วางผิดช่อง หน้าจอเสนอให้ย้าย)
    kind                  ชื่อเรียกเอกสาร
    subtitle, subtitle2   บรรทัดรายละเอียดใต้ชื่อไฟล์
    lang, lang_label, lang_source   ป้ายภาษา ('th' แดง / 'en' น้ำเงิน)
    outputs_preview       [{'name': ชื่อไฟล์ที่จะได้, 'requires': ชื่อตัวเลือกที่ต้องเปิด (ไม่บังคับ),
                            'ext': นามสกุลที่ได้เสมอไม่ขึ้นกับรูปแบบที่เลือก เช่น "pdf" (ไม่บังคับ)}]
    fields, fields_title, fields_status
                          ช่องให้ผู้ใช้กรอกก่อนแปลง [{'key','label','hint','value','check','placeholder','requires'}]
                          check: 'english' = ต้องเป็นภาษาอังกฤษ / 'required' = ห้ามว่าง

ผล convert(jobs, ...) -> {job.id: {'ok', 'error', 'notes', 'outputs': [{'kind','label','docx','pdf','doc'}]}}
    pdf=True  ผู้ใช้เลือกรูปแบบไฟล์ "PDF" -> ส่งออก .pdf อย่างเดียว; False = Word (.docx) อย่างเดียว
    pdf="both" ผู้ใช้เลือก "Word + PDF" และตอนดูตัวอย่าง (สร้างทั้งสองแบบในรอบเดียว — hub เก็บไว้แล้วคัดลอกออกตอนบันทึก)
              (ส่งต่อให้ core.render.render(..., fmt=...) ตามค่านี้)

preview(job, ...) -> ผลแบบเดียวกับ convert ของ job นั้น โดยต้องมีไฟล์ 'pdf' ให้หน้าจอแสดง
    ค่าเริ่มต้น: convert แบบ pdf="both" ลงโฟลเดอร์ชั่วคราวที่ hub เตรียมให้ (job.outdir)
"""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Job:
    id: str           # รหัสรายการในหน้าจอ
    path: Path        # ไฟล์ต้นฉบับ
    outdir: Path      # โฟลเดอร์ปลายทาง (hub เลือกให้ตามตัวเลือก "บันทึกไฟล์ที่")


class DocType:
    id = ""                  # ชื่อโฟลเดอร์/รหัส (ตัวอักษรอังกฤษ) เช่น "bt31"
    name = ""                # ชื่อที่แสดง เช่น "บฑ.31 อาจารย์พิเศษ"
    description = ""         # คำอธิบายสั้นใต้ชื่อ
    icon = "file"
    color = "blue"
    order = 100              # ลำดับในหน้าเลือกประเภทเอกสาร (น้อยมาก่อน)
    options = {}             # ตัวเลือกของประเภทนี้และค่าเริ่มต้น (hub จำค่าที่ผู้ใช้เลือกไว้ใน settings.json)
    pickers = {}             # หน้าต่างเลือกไฟล์: {pick: {'title': ..., 'filters': [(ชื่อ, "*.doc *.htm"), ...]}}
    downloads = None         # ปุ่ม "ไฟล์ใหม่ใน Downloads": {'glob': "Export*.doc", 'label': ..., 'title': ...}
    drop_hint = ""           # ข้อความเมื่อวางไฟล์ที่ไม่รองรับ
    max_mb = 10              # ขนาดไฟล์สูงสุดที่รับ (MB) ทุกช่อง — ช่องใดต้องการต่างไปให้ใส่ max_mb ในช่องนั้น (ระบบรับได้ถึง ~570 MB)
    ui = {"modes": [], "slots": []}

    # ---------- hub เรียกใช้ ----------
    def accept_exts(self) -> set:
        return {e.lower() for s in self.ui["slots"] for e in s.get("accept", [])}

    def accepts(self, path: Path) -> bool:
        return Path(path).suffix.lower() in self.accept_exts()

    def collect_dir(self, folder: Path) -> list:
        """ไฟล์ในโฟลเดอร์ที่ลากมาวาง/ส่งทางบรรทัดคำสั่ง"""
        pattern = (self.downloads or {}).get("glob")
        if pattern:
            return sorted(Path(folder).glob(pattern))
        return sorted(p for p in Path(folder).iterdir() if p.is_file() and self.accepts(p))

    def manifest(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description, "icon": self.icon,
                "color": self.color, "options": dict(self.options), "downloads": self.downloads,
                "drop_hint": self.drop_hint, "max_mb": self.max_mb, "accept": sorted(self.accept_exts()), "pickers": sorted(self.pickers),
                **self.ui}

    # ---------- ประเภทเอกสารต้องเขียน ----------
    def inspect(self, path: Path) -> dict:
        raise NotImplementedError

    def convert(self, jobs: list, options: dict, pdf: bool, extra: dict, log=print) -> dict:
        """jobs: [Job], options: ค่าตัวเลือกของประเภทนี้, extra: {job.id: {field key: ค่าที่ผู้ใช้กรอก}}
        pdf: True = ส่งออกเป็น PDF อย่างเดียว / False = Word (.docx) อย่างเดียว"""
        raise NotImplementedError

    def preview(self, job: Job, options: dict, extra: dict, log=print, companions=()) -> dict:
        """ตัวอย่างเอกสาร (ปุ่ม "ดูตัวอย่าง"): สร้าง PDF ลง job.outdir ซึ่งเป็นโฟลเดอร์ชั่วคราว
        companions: ไฟล์ในช่อง companion (เช่นเอกสารแนบ) ที่ต้องใช้ประกอบ"""
        r = self.convert([job, *companions], options, "both", {job.id: extra} if extra else {}, log=log)
        return r.get(job.id) or {"ok": False, "error": "สร้างตัวอย่างไม่สำเร็จ", "notes": [], "outputs": []}
