# -*- coding: utf-8 -*-
"""
เติมฟอร์มจาก PDF หน้า "Student Profile" (สั่งพิมพ์จากระบบฐานข้อมูลนักศึกษา)

หน้าเป็นแบบ "ป้าย :ค่า" ทีละบรรทัด — อ่านด้วย PyMuPDF รวมข้อความที่อยู่แนวเดียวกันเป็นแถว แล้วหาตามชื่อป้าย
เติมเฉพาะช่องที่อ่านได้ (ช่องอื่นผู้ใช้กรอกเอง): รหัสนักศึกษา + รหัสหลักสูตร, ชื่อ (ขยาย น.ส./นาย/นาง),
หลักสูตร(TH) -> ปริญญา / สาขาวิชา / ประเภท, คณะ, วันที่สอบวิทยานิพนธ์ผ่าน (-> ISO), อาจารย์ที่ปรึกษาหลัก
ชื่อป้ายมาจากหน้าระบบ (ต.ค. 2569) — ถ้าระบบเปลี่ยนป้าย ให้แก้ LABELS
"""
import re
from pathlib import Path

from core.text import clean

from .form import parse_date
from .letter import full_title

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


def is_profile(rows: list) -> bool:
    text = "\n".join(rows)
    return "Student Profile" in text or (re.search(LABELS["student_id"], text) and re.search(LABELS["program"], text))


def parse(rows: list) -> dict:
    """แถวข้อความ -> {key ของฟอร์ม: ค่า} เฉพาะช่องที่อ่านได้"""
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
    """-> {"values": {key: ค่า}, "notes": [...], "error": ""}"""
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
