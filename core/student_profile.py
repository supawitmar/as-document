# -*- coding: utf-8 -*-
"""
เติมฟอร์มจาก PDF หน้า "Student Profile" (สั่งพิมพ์จากระบบฐานข้อมูลนักศึกษา) + ตัวจัดชื่อคน/ส่วนงาน
ใช้ร่วมกันทุกประเภทเอกสารที่กรอกฟอร์ม (ย้ายจาก doctypes/ext_ebook/profile.py และ letter.py 3 พ.ย. 2569)

หน้าเป็นแบบ "ป้าย :ค่า" ทีละบรรทัด — อ่านด้วย PyMuPDF รวมข้อความที่อยู่แนวเดียวกันเป็นแถว แล้วหาตามชื่อป้าย
เติมเฉพาะช่องที่อ่านได้ (ช่องอื่นผู้ใช้กรอกเอง): รหัสนักศึกษา + รหัสหลักสูตร, ชื่อ (ขยาย น.ส./นาย/นาง),
หลักสูตร(TH) -> ปริญญา / สาขาวิชา / ประเภท, คณะ, วันที่สอบวิทยานิพนธ์ผ่าน (-> ISO), อาจารย์ที่ปรึกษาหลัก
คีย์ที่คืนเป็นชื่อช่องมาตรฐาน: student, student_id, program_code, degree, major, program_type, faculty, pass_date, advisor
— ประเภทที่ใช้ชื่อช่องต่างจากนี้ให้แปลงเองก่อนส่งให้ hub
ชื่อป้ายมาจากหน้าระบบ (ต.ค. 2569) — ถ้าระบบเปลี่ยนป้าย ให้แก้ LABELS
"""
import re
from pathlib import Path

from core.text import clean
from core.thaidate import parse_date

LABELS = {
    "student_id": r"รหัสนักศึกษา",
    "student": r"ชื่อ\s*-?\s*นามสกุล",
    "program": r"หลักสูตร\s*\(\s*TH\s*\)",
    "faculty": r"คณะ",
    "pass_date": r"วันที่สอบวิทยานิพนธ์\s*ผ่าน",
    "advisor": r"อาจารย์ที่ปรึกษาหลัก",
}
PREFIX = [(r"น\.\s*ส\.\s*", "นางสาว"), (r"นางสาว\s*", "นางสาว"), (r"นาง\s*", "นาง"), (r"นาย\s*", "นาย")]
ROW_TOLERANCE = 3.0          # pt — ข้อความที่ baseline ต่างกันไม่เกินนี้ถือเป็นแถวเดียวกัน
COLUMN_GAP = 12.0            # pt — ช่องว่างระหว่างข้อความในแถวที่กว้างกว่านี้ = คนละคอลัมน์

# ตำแหน่งทางวิชาการแบบย่อ -> เต็ม (หนังสือเขียนเต็ม: "ผู้ช่วยศาสตราจารย์ ดร. ...")
ACADEMIC = [(r"ผศ\.\s*", "ผู้ช่วยศาสตราจารย์ "), (r"รศ\.\s*", "รองศาสตราจารย์ "), (r"(?<![ก-๙])ศ\.\s*", "ศาสตราจารย์ ")]
HEAD_DIRECTOR = ("สถาบัน", "ศูนย์")          # ส่วนงานที่หัวหน้าเป็น "ผู้อำนวยการ" (ที่เหลือ "คณบดี")
UNIT_PREFIX = ("คณะ", "สถาบัน", "วิทยาลัย", "ศูนย์", "โครงการ", "บัณฑิตวิทยาลัย")


# ---------- ตัวจัดชื่อ ----------
def full_title(name: str) -> str:
    """ผศ.ดร.สมชาย -> ผู้ช่วยศาสตราจารย์ ดร. สมชาย"""
    s = clean(name)
    for pat, rep in ACADEMIC:
        s = re.sub(pat, rep, s)
    return clean(re.sub(r"ดร\.\s*", "ดร. ", s))


def faculty_name(s: str) -> str:
    """วิศวกรรมศาสตร์ -> คณะวิศวกรรมศาสตร์ (ขึ้นต้นด้วยชื่อประเภทส่วนงานอยู่แล้ว = คงเดิม)"""
    s = clean(s)
    return s if not s or s.startswith(UNIT_PREFIX) else "คณะ" + s


def head_of(faculty: str) -> str:
    """"คณบดี" / "ผู้อำนวยการ" + ส่วนงาน — ใช้เป็นค่าเริ่มต้นของ "เรียน" ในหนังสือถึงส่วนงาน"""
    faculty = faculty_name(faculty)
    if not faculty:
        return ""
    return ("ผู้อำนวยการ" if faculty.startswith(HEAD_DIRECTOR) else "คณบดี") + faculty


def strip_prefix(s: str, prefix: str) -> str:
    s = clean(s)
    return clean(s[len(prefix):]) if s.startswith(prefix) else s


def full_name(s: str) -> str:
    """น.ส. สมหญิง รักเรียน -> นางสาวสมหญิง รักเรียน (คำนำหน้าติดชื่อตามที่หนังสือใช้)"""
    s = clean(s)
    for pat, rep in PREFIX:
        m = re.match(pat, s)
        if m:
            return rep + s[m.end():]
    return s


def split_program(s: str) -> dict:
    """วิศวกรรมศาสตรมหาบัณฑิต สาขาวิชาวิศวกรรมเคมี (หลักสูตรนานาชาติ) -> degree / major / program_type"""
    m = re.match(r"(.*?)\s*สาขาวิชา\s*(.*?)\s*(?:\(([^()]*)\))?$", clean(s))
    if not m:
        return {"degree": clean(s)} if s else {}
    return {k: v for k, v in (("degree", m[1]), ("major", m[2]), ("program_type", m[3] or "")) if v}


# ---------- อ่าน PDF ----------
def read_rows(path: Path) -> list:
    """ข้อความใน PDF เป็นแถว ๆ (ซ้ายไปขวา, บนลงล่าง) — คอลัมน์ในแถวเดียวกันคั่นด้วย 3 ช่องว่าง"""
    import pymupdf
    rows = []
    with pymupdf.open(str(path)) as doc:
        for page in doc:
            spans = [(s["origin"][1], s["bbox"][0], s["bbox"][2], s["text"])
                     for b in page.get_text("dict")["blocks"] for ln in b.get("lines", [])
                     for s in ln["spans"] if s["text"].strip()]
            spans.sort()
            row, y0 = [], None
            for y, x0, x1, t in spans + [(None, 0, 0, "")]:
                if row and (y is None or abs(y - y0) > ROW_TOLERANCE):
                    row.sort(key=lambda s: s[0])
                    text, end = "", None
                    for sx0, sx1, st in row:
                        text += ("   " if end is not None and sx0 - end > COLUMN_GAP else "") + st
                        end = sx1
                    rows.append(clean(text) if "   " not in text else text.strip())
                    row = []
                if y is not None:
                    if not row:
                        y0 = y
                    row.append((x0, x1, t))
    return rows


def find(rows: list, label: str) -> str:
    """ค่าหลัง "ป้าย :" — ตัดที่คอลัมน์ถัดไปในแถวเดียวกัน (ป้ายอื่นที่มี ":")"""
    for r in rows:
        m = re.search(rf"(?:^|\s){label}\s*:\s*(.*)", r)
        if m:
            value = re.split(r"\s{3,}", m[1])[0]
            return clean(value)
    return ""


def is_profile(rows: list) -> bool:
    text = "\n".join(rows)
    return "Student Profile" in text or (re.search(LABELS["student_id"], text) and re.search(LABELS["program"], text))


def parse(rows: list) -> dict:
    """แถวข้อความ -> {ชื่อช่องมาตรฐาน: ค่า} เฉพาะช่องที่อ่านได้"""
    raw = {k: find(rows, lab) for k, lab in LABELS.items()}
    v = {}
    m = re.match(r"(\d{7})\s*([A-Za-z]{2,6}\s*/\s*[A-Za-z])?", raw["student_id"])
    if m:
        v["student_id"] = m[1]
        if m[2]:
            v["program_code"] = re.sub(r"\s", "", m[2]).upper()
    if raw["student"]:
        v["student"] = full_name(raw["student"])
    v.update(split_program(raw["program"]))
    if raw["faculty"]:
        v["faculty"] = raw["faculty"]
    d = parse_date(raw["pass_date"])
    if d:
        v["pass_date"] = d.isoformat()
    if raw["advisor"]:
        v["advisor"] = full_title(raw["advisor"])
    return v


def prefill(path: Path) -> dict:
    """-> {"values": {ชื่อช่อง: ค่า}, "notes": [...], "error": ""} (รูปแบบผลของ DocType.prefill_form)"""
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        return {"values": {}, "notes": [], "error": "รองรับเฉพาะไฟล์ PDF หน้า Student Profile"}
    try:
        rows = read_rows(path)
    except Exception as e:                       # ไฟล์เสีย/ไม่ใช่ PDF
        return {"values": {}, "notes": [], "error": f"อ่านไฟล์ PDF ไม่ได้ ({e})"}
    if not rows:
        return {"values": {}, "notes": [], "error": "ไม่พบข้อความใน PDF (อาจเป็นไฟล์สแกน)"}
    if not is_profile(rows):
        return {"values": {}, "notes": [], "error": "ไม่ใช่ PDF หน้า Student Profile (ไม่พบช่องรหัสนักศึกษา/หลักสูตร)"}
    values = parse(rows)
    notes = []
    missing = [name for key, name in (("student", "ชื่อ-สกุล"), ("student_id", "รหัสนักศึกษา"),
                                      ("major", "หลักสูตร/สาขาวิชา"), ("faculty", "คณะ"),
                                      ("pass_date", "วันที่สอบวิทยานิพนธ์ผ่าน"), ("advisor", "อาจารย์ที่ปรึกษาหลัก"))
               if key not in values]
    if missing:
        notes.append("อ่านจาก Student Profile ไม่ได้: " + ", ".join(missing) + " — กรอกเอง")
    return {"values": values, "notes": notes, "error": ""}
