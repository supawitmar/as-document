# -*- coding: utf-8 -*-
"""
บฑ.31: แบบจำลองหนังสือ (Letter) + กฎข้อความที่ใช้ทั้งไฟล์ Export และ PDF e-Form
(แก้ตัวพิมพ์/เวลา, ชื่อวิชาภาษาอังกฤษ, ชื่อไฟล์ผลลัพธ์)
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from core import BASE
from core.store import JsonFile
from core.text import NB, THAI, clean, safe_stem

DATA = Path(__file__).resolve().parent / "data"
COURSES = JsonFile(DATA / "courses.json", legacy=BASE / "courses.json", sort_keys=True)   # รหัสวิชา -> ชื่อภาษาอังกฤษ
COURSES_FILE = COURSES.path

COURSE_CODE = re.compile(r"^(?:วิชา\s*)?([A-Z]{2,6}\s?\d{3,4})\s*:?$")
CREDITS = re.compile(r"\s*\d+(?:\s*\([\d\s\-]+\))?\s*(?:หน่วยกิต|credits?)\s*$", re.I)
COURSE_LABELS = {"วิชา", "COURSE", "SUBJECT"}
EN_LABELS = {"วิชา": "COURSE", "หัวข้อ": "TOPIC", "วันที่": "DATE", "เวลา": "TIME", "สถานที่": "PLACE"}
SMALL_WORDS = r"Of|In|And|For|The|At|On|To|With|From|By"
NO_TITLE_TH = re.compile(r"(?<!\S)อื่น\s?ๆ\s+")   # ระบบใส่ "อื่นๆ" แทนตำแหน่งทางวิชาการที่ไม่ได้ระบุ
SUPERVISOR_INFORMED = re.compile(r"\s*ทั้งนี้\s*ได้แจ้งให้ผู้บังคับบัญชาของท่าน\s*ทราบแล้ว")
TIME_RANGE = re.compile(r"(\d{1,2}[.:]\d{2})\s*-\s*(\d{1,2}[.:]\d{2})")
# ระดับปริญญาที่ระบบใส่หลังคำว่า "หลักสูตร" (เช่น "หลักสูตร ปริญญาโท X", "หลักสูตร และ ปริญญาเอก X") — ตัดออก
#   "และ" ต้องเป็นคำเดี่ยว (มีช่องว่างทั้งสองข้าง) เพื่อไม่ให้กระทบชื่อหลักสูตรเช่น "หลักสูตรและการสอน"
DEGREE_WORDS = re.compile(r"หลักสูตร(?:\s*ปริญญา(?:ตรี|โท|เอก)|\s+และ(?=\s))+\s*")
KIND_NAMES = {"approve": "หนังสืออนุมัติ", "invite": "หนังสือเชิญ", "generic": "หนังสือ"}


@dataclass
class Letter:
    kind: str = "generic"                        # "invite" | "approve" | "generic"
    lang: str = "th"                             # "th" | "en"
    address: list = field(default_factory=list)  # ที่อยู่ (TH) / ชื่อสถาบันกึ่งกลาง (EN)
    header: dict = field(default_factory=dict)   # ref, date, subject, to
    body: list = field(default_factory=list)     # ย่อหน้าก่อนตาราง
    rows: list = field(default_factory=list)     # [(label, value)]
    closing: list = field(default_factory=list)  # ย่อหน้าหลังตาราง
    signature: list = field(default_factory=list)
    contact: list = field(default_factory=list)


# ---------- ปรับข้อความ ----------
def fix_text(s: str) -> str:
    s = TIME_RANGE.sub(r"\1 - \2", clean(s))
    return re.sub(r"(\d[.:]\d{2})\s*น\.", r"\1 น.", s)     # "12.00น." -> "12.00 น."


def fix_degree(s: str) -> str:
    """ตัดระดับปริญญาหลังคำว่า "หลักสูตร":
    'หลักสูตร ปริญญาโท วิทยาศาสตรมหาบัณฑิต' -> 'หลักสูตร วิทยาศาสตรมหาบัณฑิต'
    'หลักสูตร และ ปริญญาเอก ปรัชญาดุษฎีบัณฑิต' -> 'หลักสูตร ปรัชญาดุษฎีบัณฑิต'"""
    return DEGREE_WORDS.sub("หลักสูตร ", s)


def fix_en(s: str) -> str:
    """แก้ตัวพิมพ์ที่ระบบสร้างผิดในหนังสือภาษาอังกฤษ (ตามไฟล์ตัวอย่าง (EN))"""
    s = fix_text(s)
    s = re.sub(r"\bDR\.", "Dr.", s)
    s = re.sub(r"\bOther\s+(?=(?:Dr|Mr|Mrs|Ms|Miss)\b)", "", s)          # คำนำหน้า "Other" จากระบบ
    # ตำแหน่งซ้ำจากระบบ: "Assistant Professor Asst.prof.dr. X" -> "Assistant Professor Dr. X"
    s = re.sub(r"(?i)\b((?:Assistant|Associate) Professor)\s+(?:Asst|Assoc)\.\s*Prof\.?\s*(Dr\.)?\s*",
               lambda m: m[1] + (" Dr. " if m[2] else " "), s)
    s = re.sub(r"\bDr\.(?:\s*Dr\.)+\s*", "Dr. ", s)                        # "Dr. Dr.Somchai" -> "Dr. Somchai"
    s = re.sub(r"\b([A-Z])\.([a-z])\.", lambda m: f"{m[1]}.{m[2].upper()}.", s)   # M.d. -> M.D.
    s = re.sub(r"\b[A-Z]{3,}(?:\s+[A-Z]{2,})+\b", lambda m: m[0].title(), s)     # FACULTY OF SCIENCE
    s = re.sub(rf"(?<=[A-Za-z)] )({SMALL_WORDS})(?= )", lambda m: m[1].lower(), s)  # Master Of Science
    s = re.sub(r"\(\s*international\s+program\s*\)", "(International Program)", s, flags=re.I)
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r",(?:\s*,)+", ",", s)
    s = re.sub(r"\b(M\.D\.|Ph\.D\.) to\b", r"\1, to", s)
    return s


# ---------- ชื่อวิชาภาษาอังกฤษ (เรียนรู้จากหนังสือเชิญ / PDF) ----------
def load_courses() -> dict:
    return COURSES.load({})


def save_courses(courses: dict):
    COURSES.save(courses)


def course_of(L: Letter):
    """คืน (index, code, name) ของแถววิชาในตาราง"""
    for i, (label, value) in enumerate(L.rows):
        m = COURSE_CODE.match(label)
        if m:
            return i, m.group(1).replace(" ", ""), CREDITS.sub("", value).strip()
        if label.upper() in COURSE_LABELS:
            vm = re.match(r"([A-Z]{2,6}\s?\d{3,4})\s*:?\s*(.*)", value)
            if vm:
                return i, vm.group(1).replace(" ", ""), CREDITS.sub("", vm.group(2)).strip()
    return None


def learn_course(L: Letter, courses: dict):
    c = course_of(L)
    if c and c[2] and not THAI.search(c[2]):
        courses[c[1]] = c[2]


# ---------- ชื่อเรียก / ชื่อไฟล์ ----------
def lang_label(lang: str) -> str:
    return {"th": "หนังสือภาษาไทย · บฑ.31", "en": "หนังสือภาษาอังกฤษ · GR.31"}.get(lang, "ไม่ทราบภาษา")


def kind_name(L: Letter) -> str:
    return KIND_NAMES[L.kind] + (" (EN)" if L.lang == "en" else "")


def short_label(kind: str) -> str:
    """ชื่อสั้นบนปุ่มเปิดไฟล์: 'หนังสือเชิญ' -> 'เชิญ'"""
    return {"หนังสือเชิญ": "เชิญ", "หนังสืออนุมัติ": "อนุมัติ"}.get(kind, kind.replace("หนังสือ", ""))


# คำนำหน้าบุคคล (ไม่ใช่ตำแหน่งทางวิชาการ) — ตัดออกจากชื่อไฟล์
PERSONAL_PREFIX = re.compile(r"(?<!\S)(?:นางสาว\s*|น\.ส\.\s*|นาย\s*|นาง\s+|(?:Mr|Mrs|Ms)\.\s+|Miss\s+)")


def lecturer_name(L: Letter) -> str:
    """ชื่ออาจารย์พิเศษพร้อมตำแหน่งทางวิชาการ (และ ดร./Dr.) สำหรับตั้งชื่อไฟล์
    เช่น 'ผู้ช่วยศาสตราจารย์ ดร. สมชาย ใจดี' — ตัดคำนำหน้าบุคคลและวุฒิท้ายชื่อ (M.D.) ออก"""
    text = " ".join(L.body)
    if L.kind == "approve":
        m = re.search(r"ขอเรียนเชิญ\s*(.+?)\s*จาก", text) or re.search(r"to allow (.+?),? to give", text) \
            or re.search(r"invitation to (.+?),", text)
        name = m.group(1) if m else ""
    else:
        name = re.sub(r"^(?:เรียน|Dear)\s*", "", L.header.get("to", ""))
    name = re.sub(r",?\s*(?:M\.D\.|Ph\.D\.|D\.V\.M\.|M\.Sc\.|Pharm\.D\.).*$", "", clean(name))
    return clean(PERSONAL_PREFIX.sub("", name))


def output_stem(L: Letter) -> str:
    """หนังสือเชิญ-บฑ.31 EGIT617 ผู้ช่วยศาสตราจารย์ ดร. สมชาย ใจดี
    หนังสือขออนุมัติ-GR.31 SCFS522 Associate Professor Dr. Somchai Jaidee"""
    kind = {"invite": "หนังสือเชิญ", "approve": "หนังสือขออนุมัติ"}.get(L.kind, "หนังสือ")
    c = course_of(L)
    return safe_stem(f"{kind}-{'GR.31' if L.lang == 'en' else 'บฑ.31'} {c[1] if c else ''} {lecturer_name(L)}")
