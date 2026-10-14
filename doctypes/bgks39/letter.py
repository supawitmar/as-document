# -*- coding: utf-8 -*-
"""
บฑกศ.39: แบบจำลองหนังสือ + กฎตรวจ/แก้ข้อความ + ชื่อไฟล์

แบ่งเป็น 2 กลุ่ม (กำหนดโดยผู้ใช้ ต.ค. 2569):
  กลุ่มที่ 1 หนังสือเชิญ — ส่งถึงอาจารย์ผู้ทำหน้าที่โดยตรง
      "เรียน" = ตำแหน่งทางวิชาการ/คำนำหน้า + ชื่อ-นามสกุลของผู้ทำหน้าที่เท่านั้น
      เนื้อหาต้องมี "ทั้งนี้ได้แจ้งให้ผู้บังคับบัญชาของท่านทราบแล้ว"
  กลุ่มที่ 2 หนังสือขออนุมัติ/ขออนุญาต — ส่งถึงผู้บังคับบัญชาต้นสังกัดของผู้ทำหน้าที่
      "เรียน" = ตำแหน่งผู้บังคับบัญชา (คณบดี / ผู้อำนวยการ / หัวหน้าภาควิชา ...) ไม่ใช่ชื่ออาจารย์
      ชื่ออาจารย์อยู่ในเนื้อหา: "มีความประสงค์ขอเรียนเชิญ <ชื่อ> จาก <หน่วยงาน> เป็นผู้ทำหน้าที่ ..."

ถ้าระบบใส่ "เรียน" ผิดประเภท (สลับกัน / ใส่ชื่อแทนตำแหน่ง) ให้แก้ทันที:
  ขออนุมัติที่ "เรียน" เป็นชื่อคน -> ตำแหน่งหัวหน้าหน่วยงานจาก "จาก <หน่วยงาน>" ในเนื้อหา
  เชิญที่ "เรียน" เป็นตำแหน่ง   -> ชื่ออาจารย์จากหนังสือขออนุมัติที่ส่งถึงตำแหน่งนั้น (ไฟล์ของนักศึกษาคนเดียวกัน)
  หาไม่ได้ -> หน้าโปรแกรมให้ผู้ใช้กรอกเอง

ประเภทหนังสือ = แท็บที่ผู้ใช้เลือกในหน้าโปรแกรมเสมอ (ทั้งสองแบบจัดหน้าไม่เหมือนกัน — layout.PROFILES)
โปรแกรมดูเนื้อหาเพียงเพื่อเตือนเมื่อไฟล์ไม่ตรงกับแท็บที่เลือก ไม่เปลี่ยนประเภทเอง
"""
import re
from dataclasses import dataclass, field

from core.text import clean, safe_stem

FORM = "บฑกศ.39"
GROUPS = {"invite": (1, "หนังสือเชิญ"), "approve": (2, "หนังสือขออนุมัติ")}

INFORMED = "ทั้งนี้ได้แจ้งให้ผู้บังคับบัญชาของท่านทราบแล้ว"
INFORMED_RE = re.compile(r"\s*ทั้งนี้\s*ได้แจ้งให้ผู้บังคับบัญชาของท่าน\s*ทราบแล้ว")
TIME_RANGE = re.compile(r"(\d{1,2}[.:]\d{2})\s*-\s*(\d{1,2}[.:]\d{2})")
STUDENT = re.compile(r"นักศึกษา\s*(นางสาว|นาง|นาย)?\s*(\S+\s+\S+)\s+รหัสประจำตัวนักศึกษา\s*(\d+)")
LECTURER = re.compile(r"ขอเรียนเชิญ\s*(.+?)\s+จาก\s+(.+?)\s+เป็นผู้ทำหน้าที่")

# ตำแหน่งผู้บังคับบัญชา (ขึ้นต้นช่อง "เรียน")
POSITION = re.compile(r"^(?:รอง)?(?:คณบดี|ผู้อำนวยการ|อธิการบดี|หัวหน้า|ประธาน|เลขาธิการ|อธิบดี|ปลัด|ผู้ว่าราชการ"
                      r"|นายก|ผู้บังคับบัญชา|ผู้จัดการ|กรรมการผู้จัดการ|ผู้บัญชาการ|ผู้บริหาร"
                      r"|Dean|Director|President|Head|Chair)")
# คำนำหน้า/ตำแหน่งทางวิชาการของบุคคล (ขึ้นต้นช่อง "เรียน" ของหนังสือเชิญ)
PERSON = re.compile(r"^(?:ศาสตราจารย์|รองศาสตราจารย์|ผู้ช่วยศาสตราจารย์|อาจารย์|ศ\.|รศ\.|ผศ\.|อ\.|ดร\."
                    r"|นพ\.|พญ\.|ทพ\.|ทพญ\.|ภก\.|ภญ\.|กภ\.|นาย(?!ก)|นางสาว|นาง|น\.ส\."
                    r"|Prof|Assoc|Asst|Dr\.|Mr\.|Mrs\.|Ms\.)")
# หน่วยงานต้นสังกัด -> ตำแหน่งหัวหน้าหน่วยงาน (ตามรูปแบบในไฟล์ตัวอย่าง "คณบดี คณะศึกษาศาสตร์ มหาวิทยาลัยศิลปากร")
HEADS = [(r"ภาควิชา|สาขาวิชา|กลุ่มวิชา", "หัวหน้า{org}"),
         (r"คณะ|วิทยาลัย|บัณฑิตวิทยาลัย", "คณบดี {org}"),
         (r"สถาบัน|สำนัก|ศูนย์|กอง|โรงพยาบาล|โรงเรียน", "ผู้อำนวยการ{org}"),
         (r"มหาวิทยาลัย", "อธิการบดี{org}")]


@dataclass
class Letter:
    kind: str                                    # "invite" | "approve"
    src: str = ""                                # ไฟล์ต้นฉบับ
    index: int = 0                               # ลำดับฉบับในไฟล์ (เริ่ม 0)
    address: list = field(default_factory=list)
    ref: str = ""
    date: str = ""
    subject: str = ""
    to: str = ""
    to_raw: str = ""                             # "เรียน" ตามที่ระบบใส่ (ก่อนแก้)
    body: list = field(default_factory=list)
    closing: str = ""
    sign_off: bool = False                       # มี "ขอแสดงความนับถือ"
    signature: list = field(default_factory=list)
    notes: list = field(default_factory=list)    # หมายเหตุท้ายหนังสือ
    fixes: list = field(default_factory=list)    # สิ่งที่โปรแกรมแก้/เตือน (แสดงในหน้าโปรแกรม)
    to_status: str = "ok"                        # ok | fixed | missing

    @property
    def text(self) -> str:
        return " ".join(self.body)

    @property
    def label(self) -> str:
        return f"{GROUPS[self.kind][1]} ฉบับที่ {self.index + 1}"


# ---------- ปรับข้อความ ----------
def fix_text(s: str) -> str:
    s = TIME_RANGE.sub(r"\1 - \2", clean(s))                       # 13.00-16.00 -> 13.00 - 16.00
    s = re.sub(r"(\d[.:]\d{2})\s*น\.", r"\1 น.", s)
    s = re.sub(r"(?<=นักศึกษา )(นางสาว|นาง|นาย) (?=\S)", r"\1", s)  # "นาย สมชาย" -> "นายสมชาย"
    return s


def is_position(s: str) -> bool:
    return bool(POSITION.match(clean(s)))


def is_person(s: str) -> bool:
    return bool(PERSON.match(clean(s))) and not is_position(s)


def head_of(org: str) -> str:
    """'คณะศึกษาศาสตร์ มหาวิทยาลัยศิลปากร' -> 'คณบดี คณะศึกษาศาสตร์ มหาวิทยาลัยศิลปากร'"""
    org = clean(org)
    for pat, fmt in HEADS:
        if re.match(pat, org):
            return fmt.format(org=org)
    return ""


def detect(d: dict) -> str:
    """ประเภทตามเนื้อหา ("invite" | "approve" | "") — ใช้เตือน/แนะนำช่อง ไม่ใช้ตัดสินแทนผู้ใช้"""
    text = " ".join(d["body"] + [d["closing"]])
    score = 0
    subj = d["subject"]
    if re.match(r"ขออนุมัติ|ขออนุญาต", subj):
        score += 2
    elif re.match(r"เชิญ", subj):
        score -= 2
    score += len(re.findall(r"พิจารณาอนุมัติ|พิจารณาอนุญาต|มีความประสงค์ขอเรียนเชิญ", text))
    score -= len(re.findall(r"จึงขอเรียนเชิญท่าน|ได้พิจารณาเห็นว่าท่าน", text))
    return "approve" if score > 0 else "invite" if score < 0 else ""


def make_letter(d: dict, kind: str, src: str = "", index: int = 0) -> Letter:
    """kind = ประเภทที่ผู้ใช้เลือก"""
    found = detect(d)
    warn = (f"ฉบับที่ {index + 1} เนื้อหาเป็น{GROUPS[found][1]} แต่เลือกแท็บ{GROUPS[kind][1]} — ตรวจว่าเลือกถูกแท็บ"
            if found and found != kind else "")
    L = Letter(kind=kind, src=src, index=index, address=d["address"], ref=d["ref"], date=clean(d["date"]),
               subject=fix_text(d["subject"]), to=fix_text(d["to"]), to_raw=clean(d["to"]),
               body=[fix_text(p) for p in d["body"]], closing=fix_text(d["closing"]), sign_off=d["sign_off"],
               signature=[clean(x) for x in d["signature"]], notes=[fix_text(x) for x in d["notes"]])
    if warn:
        L.fixes.append(warn)
    if kind == "invite":
        if L.body and not INFORMED_RE.search(L.text):
            L.body[-1] = L.body[-1].rstrip() + " " + INFORMED
            L.fixes.append(f"เติม “{INFORMED}”")
    else:
        if INFORMED_RE.search(L.text):
            L.body = [clean(INFORMED_RE.sub("", p)) for p in L.body]
            L.fixes.append("ตัด “ทั้งนี้ได้แจ้งให้ผู้บังคับบัญชาของท่านทราบแล้ว” (หนังสือนี้ส่งถึงผู้บังคับบัญชาเอง)")
    return L


# ---------- ข้อมูลจากเนื้อหา ----------
def student(L: Letter) -> tuple:
    """(ชื่อพร้อมคำนำหน้า เช่น 'นายสมชาย ใจดี', รหัสนักศึกษา)"""
    m = STUDENT.search(L.text)
    return (clean((m.group(1) or "") + m.group(2)), m.group(3)) if m else ("", "")


def lecturer(L: Letter) -> tuple:
    """หนังสือขออนุมัติ: (ชื่ออาจารย์, หน่วยงานต้นสังกัด)"""
    m = LECTURER.search(L.text)
    return (clean(m.group(1)), clean(m.group(2))) if m else ("", "")


# ---------- กฎช่อง "เรียน" ----------
def check_to(letters: list):
    """ตรวจ/แก้ "เรียน" ของทุกฉบับ (ควรส่งทุกฉบับของนักศึกษาคนเดียวกันมาพร้อมกัน เพื่อจับคู่เชิญ-ขออนุมัติ)
    ตั้ง L.to, L.to_status และเพิ่มข้อความใน L.fixes"""
    approves = [L for L in letters if L.kind == "approve"]
    for L in approves:
        if is_position(L.to):
            continue
        name, org = lecturer(L)
        new = head_of(org)
        why = "หนังสือขออนุมัติต้องเรียนตำแหน่งผู้บังคับบัญชา ไม่ใช่ชื่ออาจารย์"
        if new:
            L.fixes.append(f"แก้ “เรียน {L.to}” เป็น “เรียน {new}” ({why})")
            L.to, L.to_status = new, "fixed"
        else:
            L.fixes.append(f"“เรียน {L.to}” ไม่ใช่ตำแหน่งผู้บังคับบัญชา — กรุณากรอกเอง ({why})")
            L.to_status = "missing"
    for L in (L for L in letters if L.kind == "invite"):
        if is_person(L.to):
            continue
        why = "หนังสือเชิญต้องเรียนชื่ออาจารย์ผู้ทำหน้าที่"
        names = [lecturer(A)[0] for A in approves if clean(A.to) == clean(L.to) or clean(A.to_raw) == clean(L.to)]
        names = [n for n in names if n]
        if len(set(names)) == 1:
            L.fixes.append(f"แก้ “เรียน {L.to}” เป็น “เรียน {names[0]}” ({why} — ชื่อจากหนังสือขออนุมัติ)")
            L.to, L.to_status = names[0], "fixed"
        else:
            L.fixes.append(f"“เรียน {L.to}” ไม่ใช่ชื่ออาจารย์ — กรุณากรอกชื่อผู้ทำหน้าที่ ({why})")
            L.to_status = "missing"


def set_to(L: Letter, value: str):
    """ค่าที่ผู้ใช้กรอก/ยืนยันในหน้าโปรแกรม"""
    value = clean(re.sub(r"^\s*เรียน\s*", "", value or ""))
    if value and value != L.to:
        L.fixes.append(f"ใช้ “เรียน {value}” ตามที่กรอก")
        L.to, L.to_status = value, "fixed"


# ---------- ชื่อไฟล์ ----------
def output_stem(kind: str, student_name: str) -> str:
    """หนังสือเชิญ-บฑกศ.39 นายสมชาย ใจดี / หนังสือขออนุมัติ-บฑกศ.39 นายสมชาย ใจดี"""
    return safe_stem(f"{GROUPS[kind][1]}-{FORM} {student_name}")
