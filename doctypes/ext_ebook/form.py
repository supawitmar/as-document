# -*- coding: utf-8 -*-
"""
ฟอร์มกรอกข้อมูล (ไม่มีไฟล์ต้นฉบับ) — ผู้ใช้กรอกครั้งเดียว ได้หนังสือแจ้งผล (A) และบันทึกข้อความขออนุมัติ (B)

FORM คือสเปกหน้าจอที่ส่งให้ hub ใน manifest (ui["form"]) — ความหมายของแต่ละคีย์ดูที่
โน้ต "ext_ebook-hub-form-spec.md" ที่ส่งให้ผู้ดูแล hub (type / required / pattern / default / remember / width)
ช่อง date: hub ส่งค่าเป็น ISO YYYY-MM-DD (ค.ศ.) — parse_date() รับวันที่ไทยแบบพิมพ์เองได้ด้วย
"""
import datetime as dt
import re

from core.text import clean

MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
          "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
MONTHS_SHORT = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
PROGRAM_TYPES = ["หลักสูตรนานาชาติ", "ภาคปกติ", "ภาคพิเศษ"]


def _f(key, label, type="text", required=True, **kw) -> dict:
    return {"key": key, "label": label, "type": type, "required": required, **kw}


FORM = {
    "title": "ข้อมูลการขอขยายเวลาการส่งรูปเล่มอิเล็กทรอนิกส์",
    "submit_label": "สร้างเอกสาร",
    "clear_label": "ล้างฟอร์ม",
    "sections": [
        {"title": "หนังสือของหลักสูตร", "fields": [
            _f("prog_ref", "เลขที่หนังสือ", placeholder="อว 78.102/1033", width="half",
               pattern=r"^อว\s*\d", pattern_msg="ขึ้นต้นด้วย “อว” ตามด้วยเลขที่ เช่น อว 78.102/1033"),
            _f("prog_date", "ลงวันที่", "date", width="half"),
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
        {"title": "ผลสอบและการขยายเวลา", "fields": [
            _f("pass_date", "วันที่สอบวิทยานิพนธ์ “ผ่าน” (คงสภาพผลสอบ ณ วันนี้)", "date", width="half"),
            _f("old_deadline", "กำหนดส่งรูปเล่มเดิม", "date", width="half"),
            _f("new_deadline", "ขอขยายเวลาถึงวันที่", "date", width="half"),
            _f("reason", "เหตุผลการขอขยายเวลา (บันทึกข้อความ)", "textarea", rows=3,
               placeholder="คอมพิวเตอร์ที่นักศึกษาใช้จัดทำวิทยานิพนธ์เกิดขัดข้อง และต้องส่งซ่อม",
               hint="ระบบเติม “เนื่องจาก …” ข้างหน้า และ “ทำให้ไม่สามารถดำเนินการจัดทำรูปเล่มอิเล็กทรอนิกส์ได้ทัน"
                    "ในระยะเวลาที่กำหนด ภายในวันที่ <กำหนดส่งเดิม>” ต่อท้ายให้"),
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


def parse_date(s) -> "dt.date | None":
    """ค่าวันที่จากฟอร์ม -> date (ปี ค.ศ.)
    รับ ISO "2026-05-11" (ปี > 2400 ถือเป็น พ.ศ.), "11 พฤษภาคม 2569", "11 พ.ค. 69", "11/5/2569" — อ่านไม่ได้ = None"""
    if isinstance(s, dt.date):
        return s
    s = clean(str(s or ""))
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
    else:
        m = re.fullmatch(r"(\d{1,2})\s*(?:[/.\-]\s*(\d{1,2})\s*[/.\-]|\s+([ก-๙.\s]+?)\s*)\s*(\d{2,4})", s)
        if not m:
            return None
        d, y = int(m[1]), int(m[4])
        if m[2]:
            mo = int(m[2])
        else:
            name = m[3].replace(" ", "")
            mo = next((i + 1 for i, (full, short) in enumerate(zip(MONTHS, MONTHS_SHORT))
                       if name in (full, short, short.replace(".", ""))), 0)
        if y < 100:
            y += 2500                      # "69" = พ.ศ. 2569
    if y > 2400:
        y -= 543
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def thai_date(d: dt.date) -> str:
    """11 พฤษภาคม 2569"""
    return f"{d.day} {MONTHS[d.month - 1]} {d.year + 543}"


def defaults(today: dt.date = None) -> dict:
    """ค่าเริ่มต้นของฟอร์ม ("today" = วันนี้ ในรูป ISO)"""
    today = today or dt.date.today()
    return {k: today.isoformat() if f.get("default") == "today" else f.get("default", "")
            for k, f in FIELDS.items()}


def check(values: dict) -> tuple:
    """ตรวจค่าที่กรอก -> (errors {key: ข้อความ}, warnings [ข้อความ]) — errors ว่าง = สร้างเอกสารได้"""
    errors, warnings = {}, []
    v = {k: clean(str(values.get(k) or "")) for k in FIELDS}
    for k, f in FIELDS.items():
        if not v[k]:
            if f["required"]:
                errors[k] = "ต้องกรอก"
            continue
        if f["type"] == "date" and parse_date(v[k]) is None:
            errors[k] = "อ่านวันที่ไม่ได้ (เช่น 11 พฤษภาคม 2569)"
        elif f.get("pattern") and not re.search(f["pattern"], v[k]):
            errors[k] = f.get("pattern_msg") or "รูปแบบไม่ถูกต้อง"
    d = {k: parse_date(v[k]) for k in DATE_KEYS}
    order = [("pass_date", "old_deadline", "กำหนดส่งเดิมอยู่ก่อนวันสอบผ่าน"),
             ("old_deadline", "new_deadline", "วันที่ขยายถึงไม่ได้อยู่หลังกำหนดส่งเดิม"),
             ("pass_date", "new_deadline", "วันที่ขยายถึงอยู่ก่อนวันสอบผ่าน"),
             ("prog_date", "memo_date", "วันที่บันทึกอยู่ก่อนวันที่ของหนังสือหลักสูตร")]
    for a, b, msg in order:
        if d[a] and d[b] and d[b] <= d[a] and not (a == "prog_date" and d[b] == d[a]):
            warnings.append(f"{msg} ({FIELDS[a]['label']} {thai_date(d[a])} · {FIELDS[b]['label']} {thai_date(d[b])})")
    if v["student"] and not re.match(r"(นาย|นาง|ว่าที่|Mr|Ms|Mrs|Miss)", v["student"]):
        warnings.append("ชื่อนักศึกษาไม่มีคำนำหน้า (นาย / นาง / นางสาว)")
    return errors, warnings
