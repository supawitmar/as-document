# -*- coding: utf-8 -*-
"""
ฟอร์มกรอกข้อมูล (ไม่มีไฟล์ต้นฉบับ) — ผู้ใช้กรอกครั้งเดียว ได้บันทึกข้อความขออนุมัติ + หนังสือแจ้งผล

FORM คือสเปกหน้าจอที่ส่งให้ hub ใน manifest (ui["form"]) — ความหมายของแต่ละคีย์ดูที่ core/doctype.py
ช่องนักศึกษาใช้ชื่อเดียวกับ ext_ebook และ core.student_profile จึงเติมจาก Student Profile ได้ตรง ๆ
ช่องเงินรับ "18,520" / "18520.50" / "18,520 บาท" — ระบบเขียนจำนวนเงินเป็นตัวหนังสือเอง (core.thaidate.baht_text)
"ยอดที่ต้องชำระ" แสดงและบังคับเฉพาะเมื่อเลือก "ลดหย่อน" (show_if — ช่องที่ซ่อนอยู่ถือเป็นค่าว่าง แบบเดียวกับ hub)
"""
import datetime as dt
import re

from core.doctype import field_shown
from core.text import clean
from core.thaidate import money, parse_date, parse_money, thai_date

WAIVE, REDUCE = "ยกเว้น", "ลดหย่อน"
PROGRAM_TYPES = ["หลักสูตรนานาชาติ", "ภาคปกติ", "ภาคพิเศษ"]


def _f(key, label, type="text", required=True, **kw) -> dict:
    return {"key": key, "label": label, "type": type, "required": required, **kw}


FORM = {
    "title": "ข้อมูลการขอยกเว้น/ลดหย่อนค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้า",
    "submit_label": "สร้างเอกสาร",
    "clear_label": "ล้างฟอร์ม",
    "sections": [
        {"title": "ประเภทคำขอ", "fields": [
            _f("mode", "ขอยกเว้น หรือ ลดหย่อนค่าปรับ", "select", options=[WAIVE, REDUCE], width="half",
               hint="ยกเว้น = ไม่ต้องชำระค่าปรับ · ลดหย่อน = ชำระบางส่วน (กรอกยอดที่ต้องชำระด้านล่าง)"),
        ]},
        {"title": "หนังสือของหลักสูตร", "fields": [
            _f("prog_ref", "เลขที่หนังสือ", placeholder="บฑ. 253/2569", width="half"),
            _f("prog_date", "ลงวันที่", "date", width="half"),
            _f("prog_subject", "เรื่อง (ตามหนังสือของหลักสูตร)",
               placeholder="ขอยกเว้นค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้า",
               hint="พิมพ์ตามหนังสือของหลักสูตร ไม่ต้องมีคำว่า “เรื่อง” — ระบบต่อ “ของ <ชื่อนักศึกษา>” ให้"),
        ]},
        {"title": "นักศึกษา", "fields": [
            _f("student", "ชื่อ-สกุล (มีคำนำหน้า)", placeholder="นางสาวสมหญิง รักเรียน"),
            _f("student_id", "รหัสนักศึกษา", placeholder="6512345", width="half",
               pattern=r"^\d{7}$", pattern_msg="ตัวเลข 7 หลัก"),
            _f("program_code", "รหัสหลักสูตร", placeholder="EGCH/M", width="half",
               pattern=r"^[A-Za-z]{2,6}/[A-Za-z]$", pattern_msg="ตัวอักษรอังกฤษ / ระดับ เช่น EGCH/M"),
            _f("degree", "หลักสูตร (ชื่อปริญญา)", placeholder="วิศวกรรมศาสตรมหาบัณฑิต", width="half"),
            _f("major", "สาขาวิชา", placeholder="วิศวกรรมเคมี", width="half", hint="ไม่ต้องพิมพ์คำว่า “สาขาวิชา”"),
            _f("program_type", "ประเภทหลักสูตร", "select", required=False, options=PROGRAM_TYPES,
               allow_other=True, width="half", hint="แสดงในวงเล็บหลังสาขาวิชา — เว้นว่าง = ไม่มีวงเล็บ"),
            _f("faculty", "คณะ / ส่วนงาน", placeholder="คณะวิศวกรรมศาสตร์", width="half"),
            _f("to", "เรียน (หนังสือแจ้งผล)", required=False, placeholder="คณบดีคณะวิศวกรรมศาสตร์",
               hint="เว้นว่าง = “คณบดี” + คณะ (สถาบัน/ศูนย์ = “ผู้อำนวยการ”)"),
            _f("advisor", "อาจารย์ที่ปรึกษาวิทยานิพนธ์หลัก", placeholder="ผู้ช่วยศาสตราจารย์ ดร. สมชาย ใจดี",
               hint="ตำแหน่งทางวิชาการ + ชื่อ-สกุล (พิมพ์ย่อ ผศ./รศ./ศ. ได้ ระบบเขียนเต็มให้)"),
        ]},
        {"title": "การส่งล่าช้าและค่าปรับ", "fields": [
            _f("pass_date", "วันที่สอบวิทยานิพนธ์ “ผ่าน”", "date", width="half"),
            _f("submit_date", "วันที่ส่งไฟล์ E-thesis เข้าสู่ระบบ", "date", width="half"),
            _f("late_days", "จำนวนวันที่ส่งล่าช้า", placeholder="259", width="third",
               pattern=r"^\s*[\d,]+\s*(วัน)?\s*$", pattern_msg="ตัวเลขจำนวนวัน เช่น 259"),
            _f("fine", "ค่าปรับเต็ม (บาท)", placeholder="92,600", width="third",
               pattern=r"^\s*[\d,]+(\.\d{1,2})?\s*(บาท)?\s*$", pattern_msg="จำนวนเงิน เช่น 92,600",
               hint="กรอกตามที่หลักสูตรแจ้ง ระบบไม่คำนวณให้"),
            _f("pay", "ยอดที่ต้องชำระ (บาท)", placeholder="18,520", width="third", show_if={"mode": REDUCE},
               pattern=r"^\s*[\d,]+(\.\d{1,2})?\s*(บาท)?\s*$", pattern_msg="จำนวนเงิน เช่น 18,520",
               hint="ต้องน้อยกว่าค่าปรับเต็ม — ระบบเขียนจำนวนเงินเป็นตัวหนังสือให้"),
            _f("reason", "เหตุผล (บันทึกข้อความ)", "textarea", rows=3,
               placeholder="นักศึกษาประสบปัญหาสุขภาพอย่างต่อเนื่อง",
               hint="ระบบเติม “เนื่องจาก” ข้างหน้า และ “จึงทำให้นักศึกษาส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้า"
                    "และทำให้มีค่าปรับในการส่งล่าช้า (รายละเอียดตามเอกสารแนบ)” ต่อท้ายให้"),
        ]},
        {"title": "บันทึกข้อความ", "fields": [
            _f("memo_date", "วันที่บันทึก", "date", default="today", width="half"),
            _f("proposer", "ผู้เสนอ (ชื่อ-สกุล ไม่ต้องมีคำนำหน้า)", remember=True, width="half"),
            _f("proposer_title", "ตำแหน่งผู้เสนอ", default="นักวิชาการศึกษา", remember=True, width="half"),
        ]},
    ],
}

FIELDS = {f["key"]: f for s in FORM["sections"] for f in s["fields"]}
DATE_KEYS = [k for k, f in FIELDS.items() if f["type"] == "date"]
MONEY_KEYS = ("fine", "pay")


def parse_days(s) -> "int | None":
    """"259" / "1,020 วัน" -> จำนวนวัน (มากกว่า 0) — อ่านไม่ได้ = None"""
    s = re.sub(r"[,\s]|วัน$", "", clean(str(s or "")))
    return int(s) if s.isdigit() and int(s) > 0 else None


def defaults(today: dt.date = None) -> dict:
    """ค่าเริ่มต้นของฟอร์ม ("today" = วันนี้ ในรูป ISO)"""
    today = today or dt.date.today()
    return {k: today.isoformat() if f.get("default") == "today" else f.get("default", "")
            for k, f in FIELDS.items()}


def check(values: dict) -> tuple:
    """ตรวจค่าที่กรอก -> (errors {key: ข้อความ}, warnings [ข้อความ]) — errors ว่าง = สร้างเอกสารได้"""
    errors, warnings = {}, []
    v = {k: clean(str(values.get(k) or "")) for k in FIELDS}
    shown = {k for k, f in FIELDS.items() if field_shown(f, v)}
    v = {k: x if k in shown else "" for k, x in v.items()}          # ช่องที่ซ่อนอยู่ = ไม่ได้กรอก ไม่บังคับ ไม่ตรวจ
    for k, f in FIELDS.items():
        if k not in shown:
            continue
        if not v[k]:
            if f["required"]:
                errors[k] = "ต้องกรอก"
            continue
        if f["type"] == "date" and parse_date(v[k]) is None:
            errors[k] = "อ่านวันที่ไม่ได้ (เช่น 11 พฤษภาคม 2569)"
        elif k in MONEY_KEYS and parse_money(v[k]) is None:
            errors[k] = f.get("pattern_msg") or "อ่านจำนวนเงินไม่ได้"
        elif k == "late_days" and parse_days(v[k]) is None:
            errors[k] = f.get("pattern_msg")
        elif f.get("pattern") and not re.search(f["pattern"], v[k]):
            errors[k] = f.get("pattern_msg") or "รูปแบบไม่ถูกต้อง"
    if v["mode"] and v["mode"] not in (WAIVE, REDUCE):
        errors["mode"] = f"เลือก “{WAIVE}” หรือ “{REDUCE}”"
    fine, pay = parse_money(v["fine"]), parse_money(v["pay"])
    if v["mode"] == REDUCE and "pay" not in errors:          # ว่าง = "ต้องกรอก" จากลูปด้านบนแล้ว
        if fine is not None and pay >= fine:
            errors["pay"] = f"ต้องน้อยกว่าค่าปรับเต็ม ({money(fine)} บาท)"
        elif pay == 0:
            errors["pay"] = f"ยอด 0 บาท = ไม่ต้องชำระ ให้เลือก “{WAIVE}”"
    if fine == 0:
        errors["fine"] = "ค่าปรับต้องมากกว่า 0"
    d = {k: parse_date(v[k]) for k in DATE_KEYS}
    order = [("pass_date", "submit_date", "วันที่ส่งไฟล์อยู่ก่อนวันสอบผ่าน"),
             ("submit_date", "prog_date", "หนังสือหลักสูตรลงวันที่ก่อนวันที่ส่งไฟล์"),
             ("prog_date", "memo_date", "วันที่บันทึกอยู่ก่อนวันที่ของหนังสือหลักสูตร")]
    for a, b, msg in order:
        if d[a] and d[b] and d[b] < d[a]:
            warnings.append(f"{msg} ({FIELDS[a]['label']} {thai_date(d[a])} · {FIELDS[b]['label']} {thai_date(d[b])})")
    if v["student"] and not re.match(r"(นาย|นาง|ว่าที่|Mr|Ms|Mrs|Miss)", v["student"]):
        warnings.append("ชื่อนักศึกษาไม่มีคำนำหน้า (นาย / นาง / นางสาว)")
    return errors, warnings
