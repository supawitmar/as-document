# -*- coding: utf-8 -*-
"""
แบบจำลองคำขอ (Request) + ข้อความของเอกสารทั้ง 2 ฉบับ + ชื่อไฟล์

ข้อความตามสเปกที่เจ้าของยืนยัน (3 พ.ย. 2569) โดยใช้ตัวอย่างที่เจ้าหน้าที่จัด (samples/) เป็นต้นแบบประโยค
    บันทึกข้อความ = memo_reduce (27 ต.ค. 2569) · หนังสือแจ้งผล = letter_waive (ฉบับลดหย่อนเติมยอดที่ต้องชำระ)
ตัวอย่างจริงมีจุดผิดที่ไม่ทำตาม: "หลักสูตรหลักสูตร" ซ้ำ (ตัดคำว่าหลักสูตรหน้าชื่อปริญญา), "หัวงานบริการการศึกษา",
และเรียกตัวงานปนกัน ("Thesis Submission", "ไฟล์รูปเล่มวิทยานิพนธ์ในรูปแบบดิจิทัล") — ใช้ "รูปเล่มอิเล็กทรอนิกส์" ทุกที่
ยกเว้นชื่อเรื่องของหนังสือหลักสูตรที่ยกมาอ้าง (ใช้ตามที่ผู้ใช้กรอก)
ยกเว้น = ไม่ต้องชำระ จึงไม่ใส่ยอดเงินในย่อหน้า "ทั้งนี้" (เจ้าของแก้จากตัวอย่าง)
"""
import re
from dataclasses import dataclass

from core.student_profile import faculty_name, full_title, head_of, strip_prefix
from core.text import clean, safe_stem
from core.thaidate import baht_text, money, parse_date, parse_money, thai_date

from .form import FIELDS, REDUCE, WAIVE, parse_days

WORK = "รูปเล่มอิเล็กทรอนิกส์"
REASON_TAIL = f"จึงทำให้นักศึกษาส่ง{WORK}ล่าช้าและทำให้มีค่าปรับในการส่งล่าช้า"
ATTACHED = "(รายละเอียดตามเอกสารแนบ)"
CLOSING_MEMO = "จึงเรียนมาเพื่อโปรดพิจารณา"
FORWARD_MEMO = ["เรียน คณบดีบัณฑิตวิทยาลัย", "- เพื่อโปรดพิจารณา"]
APPROVE_BOXES = ("อนุมัติ", "ไม่อนุมัติ")
CLOSING_LETTER = "จึงเรียนมาเพื่อโปรดทราบ และกรุณาแจ้งให้นักศึกษาได้รับทราบ จักขอบคุณยิ่ง"


@dataclass
class Request:
    mode: str               # ยกเว้น / ลดหย่อน
    prog_ref: str
    prog_date: str          # วันที่ไทย เช่น "22 ตุลาคม 2569"
    prog_subject: str
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
    submit_date: str
    late_days: str          # "259"
    fine: str               # "92,600"
    pay: str                # "18,520" (ยกเว้น = "")
    pay_text: str           # "หนึ่งหมื่นแปดพันห้าร้อยยี่สิบบาทถ้วน"
    reason: str
    memo_date: str
    proposer: str
    proposer_title: str

    @property
    def program(self) -> str:
        """ปรัชญาดุษฎีบัณฑิต สาขาวิชาสังคมศาสตร์สุขภาพ (หลักสูตรนานาชาติ)"""
        kind = f" ({self.program_type})" if self.program_type else ""
        return f"{self.degree} สาขาวิชา{self.major}{kind}"

    @property
    def matter(self) -> str:
        """"ยกเว้นค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้า" / "ลดหย่อน…" """
        return f"{self.mode}ค่าปรับการส่ง{WORK}ล่าช้า"

    @property
    def student_line(self) -> str:
        """ข้อความเดียวกันทั้งบันทึกและหนังสือแจ้งผล (ย่อหน้าแรก ก่อนเหตุผล/ท้ายย่อหน้า)"""
        return (f"ตามที่ หลักสูตรฯ มีหนังสือที่ {self.prog_ref} ลงวันที่ {self.prog_date} เรื่อง {self.prog_subject}ของ "
                f"{self.student} รหัสประจำตัว {self.student_id} {self.program_code} นักศึกษาหลักสูตร{self.program} "
                f"{self.faculty} ซึ่งสอบวิทยานิพนธ์ “ผ่าน” ตั้งแต่วันที่ {self.pass_date} และได้ดำเนินการส่งไฟล์ "
                f"E-thesis เข้าสู่ระบบเมื่อวันที่ {self.submit_date} ทำให้มีค่าปรับในการส่งเล่มล่าช้า "
                f"จำนวน {self.late_days} วัน เป็นเงิน {self.fine} บาท")

    # ---------- บันทึกข้อความขออนุมัติ ----------
    @property
    def subject_memo(self) -> str:
        return f"เสนอพิจารณาขออนุมัติขอ{self.matter}"

    def reason_text(self) -> str:
        """เนื่องจาก<เหตุผล> จึงทำให้…ค่าปรับในการส่งล่าช้า (รายละเอียดตามเอกสารแนบ) — ท้ายประโยคตามตัวอย่าง memo_reduce"""
        r = strip_prefix(self.reason, "เนื่องจาก").replace(ATTACHED, " ")
        r = clean(r).rstrip(" .")
        if "ทำให้มีค่าปรับ" not in r:
            r += " " + REASON_TAIL
        return f"เนื่องจาก{r} {ATTACHED}"

    def body_memo(self) -> list:
        if self.mode == WAIVE:
            ask = f"ทั้งนี้ หลักสูตรฯ ขอความอนุเคราะห์{self.matter}ทั้งหมด"
        else:
            ask = (f"ทั้งนี้ หลักสูตรฯ ขอความอนุเคราะห์{self.matter} โดยคงชำระทั้งหมดจำนวน {self.pay} บาท "
                   f"({self.pay_text})")
        return [f"{self.student_line} {self.reason_text()}", ask]

    # ---------- หนังสือแจ้งผลถึงคณบดี ----------
    @property
    def subject_letter(self) -> str:
        return f"อนุมัติ{self.matter}"

    def body_letter(self) -> list:
        result = f"บัณฑิตวิทยาลัยพิจารณาแล้ว เห็นสมควรอนุมัติ{self.matter} ตามที่หลักสูตรฯ เสนอมา"
        if self.mode == REDUCE:
            result += f" โดยให้นักศึกษาชำระค่าปรับจำนวน {self.pay} บาท ({self.pay_text})"
        return [f"{self.student_line} ตามรายละเอียดที่แจ้งมาแล้วนั้น", result]

    def cc_letter(self) -> list:
        return [f"ประธานหลักสูตร{self.program}", f"{self.advisor} อาจารย์ที่ปรึกษาวิทยานิพนธ์หลัก"]


def subject_of(s: str, student: str) -> str:
    """เรื่องของหนังสือหลักสูตร: ตัด "เรื่อง" ข้างหน้า และ "ของ <ชื่อนักศึกษา>" ท้าย (ระบบต่อให้เอง)"""
    s = strip_prefix(clean(s), "เรื่อง")
    if student and s.endswith(student):
        s = clean(s[: -len(student)])
    return clean(re.sub(r"\s*ของ$", "", s))


def make_request(values: dict) -> Request:
    """ค่าจากฟอร์ม (ผ่าน form.check แล้ว) -> Request ที่จัดข้อความแล้ว"""
    v = {k: clean(str(values.get(k) or "")) for k in FIELDS}
    for k in ("prog_date", "pass_date", "submit_date", "memo_date"):
        d = parse_date(v[k])
        v[k] = thai_date(d) if d else v[k]
    v["program_code"] = v["program_code"].upper()
    v["degree"] = strip_prefix(v["degree"], "หลักสูตร")        # ตัวอย่างพิมพ์ "หลักสูตรหลักสูตร…" ซ้ำ
    v["major"] = strip_prefix(v["major"], "สาขาวิชา")
    v["program_type"] = v["program_type"].strip("()")
    v["faculty"] = faculty_name(v["faculty"])
    v["to"] = v["to"] or head_of(v["faculty"])
    v["advisor"] = full_title(v["advisor"])
    v["prog_subject"] = subject_of(v["prog_subject"], v["student"])
    days = parse_days(v["late_days"])
    v["late_days"] = f"{days:,}" if days else v["late_days"]
    fine = parse_money(v["fine"])
    v["fine"] = money(fine) if fine is not None else v["fine"]
    pay = parse_money(v["pay"]) if v["mode"] == REDUCE else None
    v["pay"], v["pay_text"] = (money(pay), baht_text(pay)) if pay is not None else ("", "")
    v["proposer"] = re.sub(r"^(?:นางสาว|นาง|นาย|น\.\s*ส\.)\s*", "", v["proposer"].strip("()"))   # ตัวอย่าง: "(ชื่อ นามสกุล)" ไม่มีคำนำหน้า
    return Request(**v)


def kinds(r: Request) -> tuple:
    """ชื่อเรียกผลลัพธ์ (บันทึก, หนังสือแจ้งผล) — แสดงเป็นแท็บดูตัวอย่าง/รายการผลลัพธ์ในหน้าโปรแกรม"""
    return f"บันทึกข้อความขออนุมัติ{r.mode}ค่าปรับ", f"หนังสือแจ้งผล{r.mode}ค่าปรับ"


def output_stems(r: Request) -> tuple:
    """(บันทึก, หนังสือแจ้งผล) ทำนองเดียวกับ ext_ebook:
    "บันทึกขออนุมัติยกเว้นค่าปรับ 6512345 EGCH-M นางสาว…" / "ยกเว้นค่าปรับ 6512345 EGCH-M นางสาว…" """
    tail = f"{r.student_id} {r.program_code.replace('/', '-')} {r.student}"
    return safe_stem(f"บันทึกขออนุมัติ{r.mode}ค่าปรับ {tail}"), safe_stem(f"{r.mode}ค่าปรับ {tail}")
