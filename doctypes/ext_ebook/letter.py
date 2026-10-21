# -*- coding: utf-8 -*-
"""
แบบจำลองคำขอ (Request) + ข้อความของหนังสือทั้ง 2 ฉบับ + ชื่อไฟล์

ข้อความทุกประโยคมาจากตัวอย่างที่เจ้าหน้าที่จัด (samples/A = หนังสือแจ้งผล, samples/B = บันทึกข้อความ ต.ค. 2569)
ทุกค่ากรอกที่เดียวแล้วเติมทุกที่ — ตัวอย่างจริงเคยพิมพ์วันคงสภาพผลสอบใน B ไม่ตรงกับย่อหน้าแรก
และชื่อไฟล์เป็นของนักศึกษาคนอื่น จึงห้ามแยกพิมพ์ค่าเดียวกันหลายที่

ตกลงกับผู้ใช้ (21 ต.ค. 2569): ทุกปริญญาใช้ข้อความเดียวกัน · ประโยคค่าปรับใส่ใน A ทุกครั้ง · ได้ A และ B ทุกครั้ง
"""
import re
from dataclasses import dataclass

from core.text import clean, safe_stem

from .form import FIELDS, parse_date, thai_date

KIND_A = "หนังสือแจ้งผลขยายเวลาส่งรูปเล่ม"
KIND_B = "บันทึกข้อความขออนุมัติขยายเวลา"
SUBJECT_A = "ขอขยายเวลาการส่งรูปเล่มอิเล็กทรอนิกส์และคงสภาพผลสอบ"
SUBJECT_B = "ขออนุมัติขยายเวลาการส่งรูปเล่มอิเล็กทรอนิกส์"
FINE = "และนักศึกษาต้องชำระค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้าตามระเบียบซึ่งได้กำหนดไว้แล้ว"
REASON_TAIL = "ทำให้ไม่สามารถดำเนินการจัดทำรูปเล่มอิเล็กทรอนิกส์ได้ทันในระยะเวลาที่กำหนด"
CLOSING_A = "จึงเรียนมาเพื่อโปรดทราบ และกรุณาแจ้งให้นักศึกษาได้รับทราบ จักขอบคุณยิ่ง"
CLOSING_B = "จึงเรียนมาเพื่อโปรดพิจารณา"
APPROVE = "อนุมัติ"

# ตำแหน่งทางวิชาการแบบย่อ -> เต็ม (ตัวอย่างเขียนเต็ม: "ผู้ช่วยศาสตราจารย์ ดร. ...")
ACADEMIC = [(r"ผศ\.\s*", "ผู้ช่วยศาสตราจารย์ "), (r"รศ\.\s*", "รองศาสตราจารย์ "), (r"(?<![ก-๙])ศ\.\s*", "ศาสตราจารย์ ")]
HEAD_DIRECTOR = ("สถาบัน", "ศูนย์")          # ส่วนงานที่หัวหน้าเป็น "ผู้อำนวยการ" (ที่เหลือ "คณบดี")
UNIT_PREFIX = ("คณะ", "สถาบัน", "วิทยาลัย", "ศูนย์", "โครงการ", "บัณฑิตวิทยาลัย")


def full_title(name: str) -> str:
    """ผศ.ดร.สมชาย -> ผู้ช่วยศาสตราจารย์ ดร. สมชาย"""
    s = clean(name)
    for pat, rep in ACADEMIC:
        s = re.sub(pat, rep, s)
    return clean(re.sub(r"ดร\.\s*", "ดร. ", s))


def faculty_name(s: str) -> str:
    s = clean(s)
    return s if not s or s.startswith(UNIT_PREFIX) else "คณะ" + s


def strip_prefix(s: str, prefix: str) -> str:
    s = clean(s)
    return clean(s[len(prefix):]) if s.startswith(prefix) else s


@dataclass
class Request:
    prog_ref: str
    prog_date: str          # วันที่ไทย เช่น "28 สิงหาคม 2569"
    student: str
    student_id: str
    program_code: str
    degree: str
    major: str
    program_type: str
    faculty: str
    to: str
    advisor: str
    pass_date: str
    old_deadline: str
    new_deadline: str
    reason: str
    memo_date: str
    proposer: str
    proposer_title: str

    @property
    def program(self) -> str:
        """วิศวกรรมศาสตรมหาบัณฑิต สาขาวิชาวิศวกรรมเคมี (หลักสูตรนานาชาติ)"""
        kind = f" ({self.program_type})" if self.program_type else ""
        return f"{self.degree} สาขาวิชา{self.major}{kind}"

    @property
    def student_line(self) -> str:
        """ข้อความเดียวกันทั้ง A และ B ย่อหน้าแรก"""
        return (f"ตามที่ หลักสูตรฯ มีหนังสือที่ {self.prog_ref} ลงวันที่ {self.prog_date} เรื่อง {SUBJECT_A}ของ "
                f"{self.student} เลขประจำตัว {self.student_id} {self.program_code} นักศึกษาหลักสูตร "
                f"{self.program} {self.faculty} ซึ่งสอบวิทยานิพนธ์ “ผ่าน” ตั้งแต่วันที่ {self.pass_date} "
                f"โดยขอคงสภาพผลสอบและขอขยายเวลาการส่งรูปเล่มอิเล็กทรอนิกส์ ถึงภายในวันที่ {self.new_deadline} "
                f"ตามรายละเอียดที่หลักสูตรแจ้งมาแล้วนั้น")

    # ---------- A: หนังสือแจ้งผลถึงคณบดี ----------
    def body_a(self) -> list:
        return [self.student_line,
                f"บัณฑิตวิทยาลัยพิจารณาอนุมัติให้ขอขยายเวลาการส่งรูปเล่มอิเล็กทรอนิกส์ถึงวันที่ {self.new_deadline} "
                f"โดยให้คงสภาพผลสอบวิทยานิพนธ์ “ผ่าน” ณ วันที่ {self.pass_date} {FINE}"]

    def cc_a(self) -> list:
        return [f"ประธานหลักสูตร{self.program}",
                f"{self.advisor} อาจารย์ที่ปรึกษาวิทยานิพนธ์หลัก",
                self.student]

    # ---------- B: บันทึกข้อความขออนุมัติ ----------
    def reason_text(self) -> str:
        r = strip_prefix(self.reason, "เนื่องจาก").rstrip(" .")
        if REASON_TAIL not in r:
            r += " " + REASON_TAIL
        if self.old_deadline not in r:
            r += f" ภายในวันที่ {self.old_deadline}"
        return "เนื่องจาก" + r

    def body_b(self) -> list:
        return [f"{self.student_line} {self.reason_text()}",
                f"หลักสูตรฯ ขออนุมัติขยายเวลาการส่งรูปเล่มอิเล็กทรอนิกส์ถึงวันที่ {self.new_deadline} "
                f"โดยให้คงสภาพผลสอบวิทยานิพนธ์ “ผ่าน” ณ วันที่ {self.pass_date} เพื่อที่นักศึกษาสามารถดำเนินการส่งรูปเล่ม"
                f"อิเล็กทรอนิกส์ และสำเร็จศึกษาต่อไปได้ ทั้งนี้ ได้ผ่านการพิจารณาเห็นชอบจากอาจารย์ที่ปรึกษาหลัก"
                f"และประธานหลักสูตรแล้ว"]


def make_request(values: dict) -> Request:
    """ค่าจากฟอร์ม (ผ่าน form.check แล้ว) -> Request ที่จัดข้อความแล้ว"""
    v = {k: clean(str(values.get(k) or "")) for k in FIELDS}
    for k in ("prog_date", "pass_date", "old_deadline", "new_deadline", "memo_date"):
        d = parse_date(v[k])
        v[k] = thai_date(d) if d else v[k]
    v["prog_ref"] = re.sub(r"^อว\s*", "อว ", v["prog_ref"])
    v["program_code"] = v["program_code"].upper()
    v["degree"] = strip_prefix(v["degree"], "หลักสูตร")
    v["major"] = strip_prefix(v["major"], "สาขาวิชา")
    v["program_type"] = v["program_type"].strip("()")
    v["faculty"] = faculty_name(v["faculty"])
    if not v["to"] and v["faculty"]:
        head = "ผู้อำนวยการ" if v["faculty"].startswith(HEAD_DIRECTOR) else "คณบดี"
        v["to"] = head + v["faculty"]
    v["advisor"] = full_title(v["advisor"])
    v["proposer"] = re.sub(r"^(?:นางสาว|นาง|นาย|น\.\s*ส\.)\s*", "", v["proposer"].strip("()"))   # ตัวอย่าง B: "(ชื่อ นามสกุล)" ไม่มีคำนำหน้า
    return Request(**v)


def output_stems(r: Request) -> tuple:
    """ชื่อไฟล์ตามที่เจ้าหน้าที่ใช้ ("ขยายส่งเล่ม <รหัส> <รหัสหลักสูตรไม่มี /> <ชื่อ>") — B ขึ้นต้นด้วย "บันทึกขออนุมัติ" """
    tail = f"{r.student_id} {r.program_code.replace('/', '')} {r.student}"
    return safe_stem(f"ขยายส่งเล่ม {tail}"), safe_stem(f"บันทึกขออนุมัติขยายส่งเล่ม {tail}")
