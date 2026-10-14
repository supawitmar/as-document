# -*- coding: utf-8 -*-
"""
ประเภทเอกสาร: บฑ.31 / GR.31 — หนังสือเชิญเป็นอาจารย์พิเศษ และหนังสือขออนุมัติต่อผู้บังคับบัญชา (ไทย/อังกฤษ)

    letter.py   แบบจำลองหนังสือ + กฎข้อความ + ชื่อไฟล์
    layout.py   รูปแบบหน้ากระดาษ (Word HTML) ตามไฟล์ตัวอย่าง
    export.py   ทางเข้า 1: ไฟล์ Export (xx).doc จากระบบ
    eform.py    ทางเข้า 2: PDF หน้า บฑ.31 (e-Form)
    data/       courses.json (ชื่อวิชาภาษาอังกฤษ), signers.json (ผู้ลงนาม), translations.json (เฉพาะเครื่อง)
"""
from pathlib import Path

from core.doctype import DocType

from . import eform, export
from .letter import load_courses, save_courses, learn_course, short_label

EXPORT_EXTS = [".doc", ".htm", ".html"]
APPROVE_TOGGLE = "want_approve"
ATTACHMENT = "see_attachment"     # สอนมากกว่า 1 รายการ -> รายละเอียดตามเอกสารแนบ


class Bt31(DocType):
    id = "bt31"
    name = "บฑ.31 อาจารย์พิเศษ"
    description = "หนังสือเชิญ / หนังสือขออนุมัติอาจารย์พิเศษ (ไทย · English) → ไฟล์ Word หรือ PDF รูปแบบมาตรฐาน"
    icon = "invite"
    color = "blue"
    order = 10
    options = {APPROVE_TOGGLE: False, ATTACHMENT: False, "mode": "export"}
    pickers = {
        "export": {"title": "เลือกไฟล์ Export", "filters": [("ไฟล์ Export", "*.doc *.htm *.html"), ("ทุกไฟล์", "*.*")]},
        "pdf": {"title": "เลือกไฟล์ PDF หน้า บฑ.31", "filters": [("PDF หน้า บฑ.31", "*.pdf"), ("ทุกไฟล์", "*.*")]},
        "schedule": {"title": "เลือกไฟล์ตารางสอน (PDF)", "filters": [("ตารางสอน PDF", "*.pdf"), ("ทุกไฟล์", "*.*")]},
    }
    downloads = {"glob": "Export*.doc", "label": "ไฟล์ใหม่ใน Downloads",
                 "title": "ดึงไฟล์ Export ที่ดาวน์โหลดภายใน 3 วัน และจัดลงช่องให้อัตโนมัติ",
                 "empty": "ไม่พบไฟล์ Export ใหม่ใน Downloads"}
    drop_hint = "รองรับไฟล์ .doc จากระบบ หรือ PDF หน้า บฑ.31"
    ui = {
        "modes": [
            {"id": "export", "label": "ไฟล์ Export จากระบบ (.doc)", "icon": "upload",
             "summary": [{"slot": "invite"}, {"slot": "approve", "off": "ไม่ต้องการ"},
                         {"slot": "schedule", "label": "ตารางสอนแนบ", "off": "ไม่ใช้"}]},
            {"id": "eform", "label": "สร้างจาก PDF ระบบ บฑ.31 (e-Form)", "icon": "form", "color": "teal",
             "summary": [{"slot": "eform", "label": "PDF บฑ.31"},
                         {"option": APPROVE_TOGGLE, "label": "หนังสือขออนุมัติ", "icon": "approve", "color": "violet",
                          "on": "สร้างด้วย", "off": "ไม่สร้าง"},
                         {"slot": "schedule", "label": "ตารางสอนแนบ", "off": "ไม่ใช้"}]},
        ],
        "slots": [
            {"id": "eform", "mode": "eform", "title": "PDF หน้า บฑ.31 คำร้องขอเชิญอาจารย์พิเศษ",
             "desc": "ระบบอ่านข้อมูลจากแบบฟอร์ม แล้วสร้างหนังสือเชิญให้ทันที", "icon": "form", "color": "teal",
             "accept": [".pdf"], "pick": "pdf", "pick_label": "เลือกไฟล์ PDF",
             "zone_title": "ลากไฟล์ PDF บฑ.31 มาวางที่นี่", "zone_desc": "ได้หนังสือเชิญ และหนังสือขออนุมัติ (ถ้าติ๊ก)",
             "toggle": {"option": APPROVE_TOGGLE, "label": "สร้างหนังสือขออนุมัติด้วย"},
             "steps": ["เปิดหน้า บฑ.31 ในระบบ", "กด Ctrl+P แล้วบันทึกเป็น PDF", "ลากไฟล์ PDF มาวางด้านล่าง"]},
            {"id": "invite", "mode": "export", "num": 1, "title": "หนังสือเชิญ",
             "desc": "ไฟล์ Export หนังสือเชิญเป็นอาจารย์พิเศษ — ภาษาไทยหรืออังกฤษ", "icon": "invite", "color": "blue",
             "accept": EXPORT_EXTS, "pick": "export", "pick_label": "เลือกไฟล์",
             "zone_title": "ลากไฟล์หนังสือเชิญมาวางที่นี่", "zone_desc": "ไฟล์ .doc ที่ดาวน์โหลดจากระบบ"},
            {"id": "approve", "mode": "export", "num": 2, "title": "หนังสือขออนุมัติ",
             "desc": "ไฟล์ Export หนังสือขออนุมัติอาจารย์พิเศษ — ภาษาไทยหรืออังกฤษ", "icon": "approve", "color": "violet",
             "accept": EXPORT_EXTS, "pick": "export", "pick_label": "เลือกไฟล์",
             "zone_title": "ลากไฟล์หนังสือขออนุมัติมาวางที่นี่", "zone_desc": "ไฟล์ .doc ที่ดาวน์โหลดจากระบบ",
             "toggle": {"option": APPROVE_TOGGLE, "label": "ต้องการหนังสือขออนุมัติ"}, "gate": APPROVE_TOGGLE,
             "gate_note": "ติ๊ก “ต้องการหนังสือขออนุมัติ” เพื่อเปิดใช้ช่องนี้ · ถ้าไม่ติ๊ก หนังสือเชิญภาษาไทยจะตัดประโยค "
                          "“ทั้งนี้ได้แจ้งให้ผู้บังคับบัญชาของท่านทราบแล้ว” ออก"},
            # ไม่มี mode = แสดงทุกแท็บ · companion = ไม่แปลงเอง แต่ส่งไปพร้อมหนังสือทุกฉบับ (แปลง/ดูตัวอย่าง)
            {"id": "schedule", "title": "ตารางสอน (สอนมากกว่า 1 รายการ)",
             "desc": "หัวข้อ / วันที่ / เวลา / สถานที่ ในหนังสือเป็น “รายละเอียดตามเอกสารแนบ” (See attachment) "
                     "แล้วต่อตารางสอนท้ายไฟล์ PDF ของหนังสือทุกฉบับ", "icon": "calendar", "color": "amber",
             "accept": [".pdf"], "pick": "schedule", "pick_label": "เลือกไฟล์ PDF", "companion": True,
             "zone_title": "ลากไฟล์ตารางสอน (PDF) มาวางที่นี่",
             "zone_desc": "ต่อท้ายเฉพาะเมื่อเลือกรูปแบบ PDF · ไฟล์ Word เป็นหนังสืออย่างเดียว",
             "toggle": {"option": ATTACHMENT, "label": "สอนมากกว่า 1 รายการ"}, "gate": ATTACHMENT,
             "gate_note": "ติ๊ก “สอนมากกว่า 1 รายการ” เมื่อสอนหลายครั้ง แล้วแนบไฟล์ตารางสอน (PDF) ในช่องนี้"},
        ],
    }

    @staticmethod
    def is_pdf(path: Path) -> bool:
        return Path(path).suffix.lower() == ".pdf"

    @staticmethod
    def schedule_info(path: Path) -> dict:
        try:
            import pymupdf
            with pymupdf.open(str(path)) as doc:
                pages = doc.page_count
        except Exception as e:
            return {"ok": False, "slot": "schedule", "kind": "ตารางสอน", "reason": f"เปิดไฟล์ PDF ไม่ได้: {e}"}
        return {"ok": True, "slot": "schedule", "kind": "ตารางสอน", "kind_code": "schedule",
                "subtitle": f"ตารางสอน {pages} หน้า — ต่อท้ายหนังสือทุกฉบับในรอบนี้", "outputs_preview": []}

    def is_schedule(self, path: Path) -> bool:
        return self.is_pdf(path) and not eform.is_form(path)

    def inspect(self, path: Path) -> dict:
        if self.is_schedule(path):
            return self.schedule_info(path)
        if self.is_pdf(path):
            info = eform.inspect(path)
            out = {**info, "slot": "eform",
                   "subtitle": " · ".join(x for x in (info.get("to"), info.get("summary")) if x),
                   "subtitle2": ("ต้องขออนุมัติจาก " + info["approver"] if info.get("approver")
                                 else "ไม่ต้องขออนุมัติผู้บังคับบัญชา") if info["ok"] else "",
                   "outputs_preview": [{"name": n, **({"requires": APPROVE_TOGGLE} if n.startswith("หนังสือขออนุมัติ") else {})}
                                       for n in info.get("outputs_preview", [])]}
            if info.get("en_fields"):
                out["fields_title"] = "ข้อมูลภาษาอังกฤษสำหรับหนังสือ — ตรวจ/กรอกช่องที่มี * (โปรแกรมจำไว้ใช้ครั้งต่อไป)"
                out["fields_status"] = "กรอกข้อมูล EN"
                out["fields"] = [{"key": f["key"], "label": f["label"], "hint": f["th"], "value": f["value"],
                                  "check": "english", "placeholder": "กรอกเป็นภาษาอังกฤษ",
                                  **({"requires": APPROVE_TOGGLE} if f["key"] == "approver" else {})}
                                 for f in info["en_fields"]]
            return out
        info = export.inspect(path)
        to = info.get("to")
        return {**info, "slot": "approve" if info.get("kind_code") == "approve" else "invite",
                "subtitle": (("Dear " if info.get("lang") == "en" else "เรียน ") + to) if to else "",
                "outputs_preview": [{"name": n} for n in info.get("outputs_preview", [])]}

    def convert(self, jobs: list, options: dict, pdf: bool, extra: dict, log=lambda m: None) -> dict:
        want = bool(options.get(APPROVE_TOGGLE))
        attach = bool(options.get(ATTACHMENT))
        schedule = [j for j in jobs if self.is_schedule(j.path)] if attach else []
        files = [j.path for j in schedule]
        jobs = [j for j in jobs if not self.is_schedule(j.path)]
        no_file = ["ยังไม่ได้แนบไฟล์ตารางสอน — หนังสือระบุ “รายละเอียดตามเอกสารแนบ” แต่ไม่มีเอกสารแนบ"] \
            if attach and not files else []
        # เลือก PDF = ได้ไฟล์ PDF อย่างเดียว / Word = .docx อย่างเดียว / "both" = ตอนดูตัวอย่าง (hub เก็บไว้ใช้ตอนบันทึก)
        fmt = "both" if pdf == "both" else "pdf" if pdf else "docx"
        out = {}
        # PDF หน้า บฑ.31: สร้างหนังสือจากข้อมูลในแบบฟอร์ม
        for j in (j for j in jobs if self.is_pdf(j.path)):
            r = eform.convert(j.path, outdir=j.outdir, want_approve=want, en=extra.get(j.id), log=log, fmt=fmt,
                              attachment=attach, attach_files=files)
            out[j.id] = {"ok": r["ok"], "error": r["error"], "notes": r["notes"] + no_file,
                         "outputs": [{"kind": o["kind"], "label": short_label(o["kind"]), "docx": o["docx"],
                                      "pdf": o["pdf"], "doc": o["doc"]} for o in r["outputs"]]}

        exports = [j for j in jobs if not self.is_pdf(j.path)]
        # เรียนรู้ชื่อวิชาภาษาอังกฤษจากทุกไฟล์ก่อน เผื่อแยกแปลงหลายกลุ่ม (ปลายทางต่างกัน)
        courses = load_courses()
        for j in exports:
            try:
                learn_course(export.parse(export.read_source(j.path)), courses)
            except OSError:
                pass
        save_courses(courses)
        groups = {}
        for j in exports:
            groups.setdefault(j.outdir, []).append(j)
        for dest, group in groups.items():
            by_path = {Path(j.path).resolve(): j.id for j in group}
            # ไม่ติ๊ก "ต้องการหนังสือขออนุมัติ" = ไม่ต้องขออนุมัติผู้บังคับบัญชา -> ตัดประโยคแจ้งผู้บังคับบัญชาในหนังสือเชิญ
            for r in export.convert(list(by_path), outdir=dest, log=log, inform_supervisor=want, fmt=fmt,
                                     attachment=attach, attach_files=files):
                jid = by_path.get(Path(r["src"]).resolve())
                done = bool(r["docx"] or r["pdf"])
                if jid:
                    out[jid] = {"ok": done, "error": r["error"], "notes": r["notes"] + (no_file if done else []),
                                "outputs": [{"kind": r["kind"], "label": "", "docx": r["docx"], "pdf": r["pdf"],
                                             "doc": r["doc"]}] if done else []}
        letters = sum(len(r["outputs"]) for r in out.values())
        for j in schedule:
            out[j.id] = {"ok": True, "error": "", "notes": [f"แนบท้ายหนังสือ {letters} ฉบับ"], "outputs": []}
        return out


DOCTYPE = Bt31()
