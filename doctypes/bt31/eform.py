# -*- coding: utf-8 -*-
"""
บฑ.31 ทางเข้าที่ 2: PDF หน้า "บฑ.31 คำร้องขอเชิญอาจารย์พิเศษ" (e-Form)
(สั่งพิมพ์หน้าเว็บระบบฐานข้อมูลวิทยานิพนธ์/สารนิพนธ์เป็น PDF) -> Letter -> รูปแบบเดียวกับไฟล์ Export

    python bt31.py "ระบบฐานข้อมูลวิทยานิพนธ์_สารนิพนธ์.pdf" [--pdf] [--approve] [-o DIR] [--show]
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

from core import BASE
from core.store import JsonFile
from core.text import NB, THAI, clean

from .layout import render_letters
from .letter import DATA, Letter, fix_text, subject_of, use_attachment, lang_label, load_courses, output_stem, save_courses

SIGNERS = JsonFile(DATA / "signers.json", legacy=BASE / "signers.json")               # ผู้ลงนาม {"th": [...], "en": [...]}
TRANSLATIONS = JsonFile(DATA / "translations.json", legacy=BASE / "translations.json", sort_keys=True)
SIGNERS_FILE = SIGNERS.path
TRANSLATIONS_FILE = TRANSLATIONS.path   # คำแปลที่ผู้ใช้กรอก {ข้อความไทย: English} ใช้ซ้ำครั้งต่อไป (เฉพาะเครื่อง)
DEFAULT_SIGNERS = {
    "th": ["(รองศาสตราจารย์ ดร. กภ.วรินทร์ กฤตยาเกียรณ)",
           "รองคณบดีฝ่ายแผนและพัฒนาคุณภาพ",
           "ปฏิบัติหน้าที่แทนคณบดีบัณฑิตวิทยาลัย"],
    "en": ["(Associate Professor Dr. Warin Krityakiarana)",
           "Deputy Dean for Planning and Quality Assurance",
           "Acting as Dean of the Faculty of Graduate Studies, Mahidol University"],
}
MONTHS_EN = ["January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]
# ชื่อส่วนงานมหาวิทยาลัยมหิดลภาษาอังกฤษ (แก้/เพิ่มได้ใน translations.json)
FACULTY_EN = {
    "บัณฑิตวิทยาลัย": "Faculty of Graduate Studies",
    "คณะวิทยาศาสตร์": "Faculty of Science",
    "คณะวิศวกรรมศาสตร์": "Faculty of Engineering",
    "คณะแพทยศาสตร์ศิริราชพยาบาล": "Faculty of Medicine Siriraj Hospital",
    "คณะแพทยศาสตร์โรงพยาบาลรามาธิบดี": "Faculty of Medicine Ramathibodi Hospital",
    "คณะเวชศาสตร์เขตร้อน": "Faculty of Tropical Medicine",
    "คณะสาธารณสุขศาสตร์": "Faculty of Public Health",
    "คณะทันตแพทยศาสตร์": "Faculty of Dentistry",
    "คณะเภสัชศาสตร์": "Faculty of Pharmacy",
    "คณะเทคนิคการแพทย์": "Faculty of Medical Technology",
    "คณะพยาบาลศาสตร์": "Faculty of Nursing",
    "คณะสัตวแพทยศาสตร์": "Faculty of Veterinary Science",
    "คณะสังคมศาสตร์และมนุษยศาสตร์": "Faculty of Social Sciences and Humanities",
    "คณะศิลปศาสตร์": "Faculty of Liberal Arts",
    "คณะสิ่งแวดล้อมและทรัพยากรศาสตร์": "Faculty of Environment and Resource Studies",
    "คณะกายภาพบำบัด": "Faculty of Physical Therapy",
    "คณะเทคโนโลยีสารสนเทศและการสื่อสาร": "Faculty of Information and Communication Technology",
    "วิทยาลัยวิทยาศาสตร์และเทคโนโลยีการกีฬา": "College of Sports Science and Technology",
    "วิทยาลัยการจัดการ": "College of Management",
    "วิทยาลัยดุริยางคศิลป์": "College of Music",
    "วิทยาลัยศาสนศึกษา": "College of Religious Studies",
    "วิทยาลัยราชสุดา": "Ratchasuda College",
    "วิทยาลัยนานาชาติ": "Mahidol University International College",
    "สถาบันโภชนาการ": "Institute of Nutrition",
    "สถาบันวิจัยภาษาและวัฒนธรรมเอเชีย": "Research Institute for Languages and Cultures of Asia",
    "สถาบันวิจัยประชากรและสังคม": "Institute for Population and Social Research",
    "สถาบันชีววิทยาศาสตร์โมเลกุล": "Institute of Molecular Biosciences",
    "สถาบันพัฒนาสุขภาพอาเซียน": "ASEAN Institute for Health Development",
    "สถาบันสิทธิมนุษยชนและสันติศึกษา": "Institute of Human Rights and Peace Studies",
    "สถาบันนวัตกรรมการเรียนรู้": "Institute for Innovative Learning",
    "สถาบันแห่งชาติเพื่อการพัฒนาเด็กและครอบครัว": "National Institute for Child and Family Development",
}
TITLE_EN = {"ศาสตราจารย์": "Professor", "รองศาสตราจารย์": "Associate Professor",
            "ผู้ช่วยศาสตราจารย์": "Assistant Professor", "อาจารย์": "Lecturer",
            "ศาสตราจารย์เกียรติคุณ": "Professor Emeritus"}
PREFIX_EN = [("นางสาว", "Ms."), ("น.ส.", "Ms."), ("นาง", "Mrs."), ("นาย", "Mr."), ("ดร.", "Dr."), ("ดร", "Dr.")]
DEGREE_EN = {
    "ปรัชญาดุษฎีบัณฑิต": "Doctor of Philosophy", "วิทยาศาสตรมหาบัณฑิต": "Master of Science",
    "ศิลปศาสตรมหาบัณฑิต": "Master of Arts", "วิศวกรรมศาสตรมหาบัณฑิต": "Master of Engineering",
    "สาธารณสุขศาสตรมหาบัณฑิต": "Master of Public Health", "พยาบาลศาสตรมหาบัณฑิต": "Master of Nursing Science",
    "การศึกษามหาบัณฑิต": "Master of Education", "บริหารธุรกิจมหาบัณฑิต": "Master of Business Administration",
    "ประกาศนียบัตรบัณฑิตชั้นสูง": "Higher Graduate Diploma", "ประกาศนียบัตรบัณฑิต": "Graduate Diploma",
}
EN_FIELD_LABELS = {"person": "ชื่ออาจารย์พิเศษ", "workplace": "สถานที่ทำงาน", "program": "หลักสูตร",
                   "faculty": "คณะ/สถาบัน", "contact": "อาจารย์ผู้รับผิดชอบวิชา", "approver": "ผู้บังคับบัญชาที่ขออนุมัติ"}
ADDRESS_TH = ["บัณฑิตวิทยาลัย งานบริการการศึกษา", "25/25 ถ.พุทธมณฑลสาย 4 ต.ศาลายา", "อ.พุทธมณฑล จ.นครปฐม 73170"]
MONTHS_TH = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
             "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
VALUE_X = 318          # ในหน้าเว็บที่พิมพ์ออกมา ป้ายชื่อช่องอยู่ซ้าย ค่าอยู่ขวาของตำแหน่งนี้ (pt)
ROW_TOLERANCE = 18     # ค่าที่อยู่ห่างจากป้ายในแนวตั้งไม่เกินนี้ ถือเป็นค่าของป้ายนั้น
TYPO = {"มหาวิทยลัย": "มหาวิทยาลัย"}
OPTION_GROUPS = {      # ตัวเลือกแบบติ๊ก/วงกลม เรียงซ้ายไปขวาตามหน้าเว็บ
    "degree": (["ป.บัณฑิต", "ป.โท", "ป.บัณฑิตชั้นสูง", "ป.เอก"], "ป.โท"),
    "track": (["ภาคปกติ", "ภาคพิเศษ", "นานาชาติ"], "นานาชาติ"),
    "teach": (["บรรยาย", "สัมนา", "ปฏิบัติการ"], "บรรยาย"),
}
TRACK_TEXT = {"ภาคปกติ": "(ภาคปกติ)", "ภาคพิเศษ": "(ภาคพิเศษ)", "นานาชาติ": "(หลักสูตรนานาชาติ)"}


# ---------- อ่าน PDF ----------
def join_wrapped(parts: list) -> str:
    """ต่อบรรทัดที่ถูกตัดในหน้าเว็บ: ไทยต่อไทยไม่เว้นวรรค นอกนั้นเว้นวรรค"""
    out = ""
    for p in (clean(x) for x in parts):
        if not p:
            continue
        if out and not (THAI.search(out[-1]) and THAI.search(p[0])):
            out += " "
        out += p
    for a, b in TYPO.items():
        out = out.replace(a, b)
    return out


def request_lang(value: str) -> str:
    """ภาษาของหนังสือตามช่อง "ภาษาที่ขอหนังสือเชิญ" ในแบบฟอร์ม: 'th' / 'en' / '' (ไม่ได้ระบุ)"""
    if re.search(r"(?i)english|อังกฤษ", value):
        return "en"
    if re.search(r"(?i)thai|ไทย", value):
        return "th"
    return ""


def checked_options(page, lines) -> dict:
    """หาตัวเลือกที่ติ๊กไว้: กล่องที่ถูกเลือกจะมีรูปเล็ก (เครื่องหมายถูก/จุด) วาดอยู่ข้างใน"""
    boxes, marks = [], []
    for d in page.get_drawings():
        r = d["rect"]
        if 8 <= r.width <= 12 and 8 <= r.height <= 12:
            if not any(abs(r.x0 - b.x0) < 2 and abs(r.y0 - b.y0) < 2 for b in boxes):
                boxes.append(r)
        elif 3 <= r.width < 8 and 3 <= r.height < 8:
            marks.append(r)
    result = {}
    for key, (options, anchor) in OPTION_GROUPS.items():
        anchor_line = next((ln for ln in lines if clean(ln["text"]) == anchor), None)
        if not anchor_line:
            continue
        row = sorted((b for b in boxes if abs(b.y0 - anchor_line["y"]) < 22 and b.x0 >= VALUE_X), key=lambda b: b.x0)
        if len(row) != len(options):
            continue
        result[key] = [opt for opt, b in zip(options, row) if any(b.contains(m) for m in marks)]
    return result


def read_pdf(path: Path) -> dict:
    import pymupdf
    doc = pymupdf.open(str(path))
    fields, extra, options = {}, [], {}
    full_text = []
    for page in doc:
        lines = []
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                t = "".join(s["text"] for s in ln["spans"])
                if t.strip():
                    lines.append({"x": ln["bbox"][0], "y": ln["bbox"][1], "text": t})
        full_text += [clean(ln["text"]) for ln in lines]
        for k, v in checked_options(page, lines).items():
            options.setdefault(k, v)
        labels = [ln for ln in lines if ln["x"] < VALUE_X]
        values = [ln for ln in lines if ln["x"] >= VALUE_X]
        groups = {}
        for v in values:
            near = min(labels, key=lambda lb: abs(lb["y"] - v["y"]), default=None)
            if near and abs(near["y"] - v["y"]) <= ROW_TOLERANCE:
                groups.setdefault(id(near), (near, []))[1].append(v)
            else:
                extra.append(v)
        for lb, vs in sorted(groups.values(), key=lambda g: g[0]["y"]):
            fields.setdefault(clean(lb["text"]), []).append(join_wrapped(x["text"] for x in sorted(vs, key=lambda x: x["y"])))
    doc.close()

    def get(*keys, all_=False):
        for label, vals in fields.items():
            if any(k in label for k in keys):
                return vals if all_ else vals[0]
        return [] if all_ else ""

    option_words = {"ป.บัณฑิต", "ป.โท", "ป.บัณฑิตชั้น", "สูง", "ป.เอก", "ภาค", "ปกติ", "พิเศษ", "นานาชาติ",
                    "บรรยาย", "สัมนา", "ปฏิบัติการ", "Preview", "ใช้สำหรับการเบิกเงิน"}
    # ชื่อหลักสูตรไม่มีป้ายชื่อช่อง (อยู่ใต้ตัวเลือก) และอาจถูกตัดเป็นหลายบรรทัด
    start = next((i for i, v in enumerate(extra) if clean(v["text"]) not in option_words
                  and THAI.search(v["text"]) and ("บัณฑิต" in v["text"] or "สาขา" in v["text"])), None)
    program_lines = []
    if start is not None:
        program_lines = [extra[start]]
        for v in extra[start + 1:]:
            if 0 < v["y"] - program_lines[-1]["y"] <= ROW_TOLERANCE and clean(v["text"]) not in option_words:
                program_lines.append(v)
            else:
                break
    program = join_wrapped(v["text"] for v in program_lines)
    text = " ".join(full_text)
    year = re.search(r"ปีการศึกษา\s*([0-9/]+)", text)
    work_pos = get("ตำแหน่งที่ปฏิบัติงาน")
    m = re.search(r"(.*?)ต้องขออนุมัติผู้บังคับบัญชา.*?ที่ต้อง\s*ขออนุมัติ\s*(.*)", work_pos)
    return {
        "lang": request_lang(get("ภาษาที่ขอ")),
        "program": program,
        "faculty": get("คณะ/สถาบัน"),
        "year": year.group(1) if year else "",
        "name": get("ชื่อ-สกุล"),
        "title": get("ตำแหน่งทางวิชาการ"),
        "workplace": get("สถานที่ทำงาน"),
        "position": clean(m.group(1)) if m else work_pos,
        "approver": clean(m.group(2)) if m else "",
        "course_code": get("รายวิชาที่สอน").replace(" ", ""),
        "course_th": get("ชื่อวิชาภาษาไทย"),
        "course_en": get("ชื่อวิชาภาษาอังกฤษ"),
        "credits": get("หน่วยกิต"),
        "students": get("จำนวนนักศึกษา"),
        "sessions": [dict(topic=t, date=d, time=tm, place=p) for t, d, tm, p in zip(
            get("สอนหัวข้อเรื่อง", all_=True), get("สอนวันที่", all_=True),
            get("สอนเวลา", all_=True), get("สถานที่สอน", all_=True))],
        "hours": get("กำหนดการสอน"),
        "contact": get("ผู้รับผิดชอบวิชา", "รายละเอียดการขอเชิญ"),
        "phone": get("โทรศัพท์"),
        "email": get("อีเมล"),
        "options": options,
    }


# ---------- จัดข้อความ ----------
def thai_date(s: str) -> str:
    """'2569/11/22' -> '22 พฤศจิกายน 2569' (หลายวันคั่นด้วย , ได้)"""
    def one(m):
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        y = y + 543 if y < 2400 else y
        return f"{d} {MONTHS_TH[mo - 1]} {y}" if 1 <= mo <= 12 else m[0]
    return re.sub(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", one, s)


def clean_place(s: str) -> str:
    """ลบชื่อช่องที่ระบบใส่ไว้แต่ไม่มีค่า เช่น 'ห้อง 314 ชั้น 3 อาคาร/ตึก ชั้น คณะ /สถาบัน / วิทยาลัย'"""
    s = re.sub(r"อาคาร\s*/\s*ตึก", "อาคาร", s)
    s = re.sub(r"คณะ\s*/\s*สถาบัน\s*/\s*วิทยาลัย", "|FAC|", s)
    for _ in range(3):
        s = re.sub(r"(อาคาร|ชั้น)\s*(?=(?:อาคาร|ชั้น|\|FAC\||$))", "", s)
    return clean(s.replace("|FAC|", " "))


def load_signers() -> dict:
    data = SIGNERS.load()
    if not isinstance(data, dict):
        SIGNERS.save(DEFAULT_SIGNERS)
        return dict(DEFAULT_SIGNERS)
    return {**DEFAULT_SIGNERS, **data}


def person(d: dict) -> str:
    title = d["title"] if d["title"] not in ("", "-", "อื่นๆ", "อื่น ๆ") else ""
    return clean(f"{title} {d['name']}")


def is_international(d: dict) -> bool:
    """ติ๊ก 'นานาชาติ' (อาจติ๊กคู่กับภาคปกติ/พิเศษ) หรือชื่อหลักสูตรระบุว่าเป็นหลักสูตรนานาชาติ"""
    return "นานาชาติ" in d["options"].get("track", []) or "นานาชาติ" in d["program"]


def track_text_th(d: dict) -> str:
    """ข้อความต่อท้ายชื่อหลักสูตรในหนังสือเชิญภาษาไทย เช่น '(ภาคปกติ)' — ไม่ซ้ำกับที่มีในชื่อหลักสูตรแล้ว"""
    if is_international(d):
        return "" if "นานาชาติ" in d["program"] else TRACK_TEXT["นานาชาติ"]
    return TRACK_TEXT.get(next(iter(d["options"].get("track", [])), ""), "")


def needs_unit(place: str) -> bool:
    """สถานที่สอนที่มีแค่ห้อง/ชั้น/อาคาร (ไม่มีชื่อหน่วยงาน) — ให้เติมชื่อส่วนงาน"""
    return bool(re.search(r"ห้อง|ชั้น|อาคาร|(?i:room|floor|building)", place)) and \
        not re.search(r"มหาวิทยาลัย|บริษัท|(?i:university|ltd|co\.|company|hospital|โรงพยาบาล)", place)


def build_letters_th(d: dict, kinds: list, today=None, inform_supervisor=True) -> tuple:
    """คืน ([(kind, Letter)], notes)"""
    today = today or dt.date.today()
    notes = []
    course_name = d["course_en"] or d["course_th"]      # ใช้ชื่อวิชาภาษาอังกฤษเสมอ
    rows = [("วิชา", clean(f"{d['course_code']} {course_name}"))]
    for s in d["sessions"]:
        place = clean_place(s["place"])
        if needs_unit(place):
            place = clean(f"{place} {d['faculty']} มหาวิทยาลัยมหิดล")
            notes.append(f"สถานที่สอนเติมชื่อส่วนงานให้เป็น “{place}” — โปรดตรวจสอบ")
        rows += [("หัวข้อ", s["topic"]), ("วันที่", thai_date(s["date"])),
                 ("เวลา", fix_text(s["time"])), ("สถานที่", place)]
    header_common = {"ref": "ที่ อว 78.02 /",
                     "date": f"วันที่{NB * 4} {MONTHS_TH[today.month - 1]} {today.year + 543}"}
    signers = load_signers()["th"]
    contact = []
    if d["contact"]:
        contact.append(f"ติดต่ออาจารย์ผู้รับผิดชอบวิชา {d['contact']}")
    if d["phone"]:
        contact.append(f"โทรศัพท์ {d['phone']}")
    who = person(d)
    letters = []
    if "invite" in kinds:
        L = Letter(kind="invite", lang="th", address=list(ADDRESS_TH), rows=list(rows),
                      signature=["ขอแสดงความนับถือ"] + signers, contact=list(contact))
        L.header = {**header_common, "subject": subject_of(L), "to": f"เรียน {who}"}
        L.body = [clean(f"บัณฑิตวิทยาลัย มหาวิทยาลัยมหิดล และคณะกรรมการบริหารหลักสูตร {d['program']} "
                           f"{track_text_th(d)} {d['faculty']} "
                           f"ได้พิจารณาเห็นว่าท่านเป็นผู้ทรงความรู้และมีประสบการณ์ในการสอน")]
        # แจ้งผู้บังคับบัญชาเฉพาะเมื่อแบบฟอร์มระบุว่าต้องขออนุมัติ และผู้ใช้ติ๊กให้ทำหนังสือขออนุมัติ
        informed = " ทั้งนี้ได้แจ้งให้ผู้บังคับบัญชาของท่านทราบแล้ว" if d["approver"] and inform_supervisor else ""
        L.closing = [clean(f"จึงขอเรียนเชิญท่านบรรยายวิชาดังกล่าวแก่นักศึกษาบัณฑิตวิทยาลัยหลักสูตร {d['program']} "
                              f"{d['faculty']} จำนวน {d['students']}{informed}"),
                     "บัณฑิตวิทยาลัย ขอขอบพระคุณอย่างยิ่งมา ณ โอกาสนี้"]
        letters.append(("invite", L))
    if "approve" in kinds:
        if not d["approver"]:
            notes.append("แบบฟอร์มไม่ได้ระบุผู้บังคับบัญชาที่ต้องขออนุมัติ — ไม่ได้สร้างหนังสือขออนุมัติ")
        else:
            L = Letter(kind="approve", lang="th", address=list(ADDRESS_TH), rows=list(rows),
                          signature=["ขอแสดงความนับถือ"] + signers, contact=list(contact))
            L.header = {**header_common, "subject": subject_of(L), "to": f"เรียน {d['approver']}"}
            L.body = [clean(f"บัณฑิตวิทยาลัย มหาวิทยาลัยมหิดล และคณะกรรมการบริหารหลักสูตร {d['program']} "
                               f"{d['faculty']} มีความประสงค์ขอเรียนเชิญ {who} จาก{d['workplace']} "
                               f"เป็นอาจารย์พิเศษสอนนักศึกษาบัณฑิตวิทยาลัย หลักสูตร {d['program']} จำนวน {d['students']}")]
            L.closing = ["จึงเรียนมาเพื่อขอท่านโปรดพิจารณาอนุมัติด้วย จักขอบพระคุณยิ่ง"]
            letters.append(("approve", L))
    return letters, notes


# ---------- หนังสือภาษาอังกฤษ ----------
def load_translations() -> dict:
    return TRANSLATIONS.load({})


def save_translations(new: dict):
    t = load_translations()
    t.update({k: v for k, v in new.items() if k and v and THAI.search(k) and not THAI.search(v)})
    TRANSLATIONS.save(t)


def en_date(s: str) -> str:
    """'2026/11/12' หรือ '2569/11/12' -> 'November 12, 2026'"""
    def one(m):
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        y = y - 543 if y > 2400 else y
        return f"{MONTHS_EN[mo - 1]} {d}, {y}" if 1 <= mo <= 12 else m[0]
    return re.sub(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", one, s)


def en_time(s: str) -> str:
    """'09.30 am - 12.00 pm' -> '09.30 - 12.00' (แบบ 24 ชั่วโมงตามไฟล์ตัวอย่าง (EN)), ตัด 'น.'"""
    def one(m):
        h, mi, ap = int(m[1]), m[2], m[3].lower().replace(".", "")
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        return f"{h:02d}.{mi}"
    s = re.sub(r"(\d{1,2})[.:](\d{2})\s*(a\.?m\.?|p\.?m\.?)", one, s, flags=re.I)
    s = re.sub(r"\s*น\.", "", s).replace("และ", "and")
    return fix_text(s)


def core_th(name: str) -> str:
    """ชื่อ-สกุลภาษาไทยไม่รวมคำนำหน้า: 'ดร สมหญิง รักเรียน' -> 'สมหญิง รักเรียน'"""
    return clean(re.sub(r"^(?:(?:นางสาว|น\.ส\.|นาง|นาย|ดร\.?)\s*)+", "", clean(name)))


def core_en(name: str) -> str:
    """'Lecturer Dr. Somying Rakrian' -> 'Somying Rakrian'"""
    titles = r"Professor Emeritus|Associate Professor|Assistant Professor|Professor|Lecturer|Ms\.|Mrs\.|Mr\.|Dr\."
    return clean(re.sub(rf"^(?:(?:{titles})\s+)+", "", clean(name)))


def name_en(title: str, name: str, tr: dict) -> str:
    """แปลงคำนำหน้า/ตำแหน่งเป็นภาษาอังกฤษ ชื่อที่ยังเป็นภาษาไทยใช้คำแปลที่เคยกรอก (ถ้าไม่มี คืนค่าที่ยังมีภาษาไทย)"""
    parts = [TITLE_EN.get(title, "")] if title not in ("", "-", "อื่นๆ", "อื่น ๆ") else []
    rest = clean(name)
    for th, eng in PREFIX_EN:
        if rest.startswith(th):
            parts.append(eng)
            rest = rest[len(th):].strip()
            break
    if rest.startswith(("ดร.", "ดร ")):
        parts.append("Dr.")
        rest = rest[3:].strip()
    if THAI.search(rest):
        rest = tr.get(rest, rest)
    return clean(" ".join(p for p in parts + [rest] if p))


def split_title(full: str) -> tuple:
    """'อาจารย์ ดร สมหญิง รักเรียน' -> ('อาจารย์', 'ดร สมหญิง รักเรียน')"""
    for t in sorted(TITLE_EN, key=len, reverse=True):
        if full.startswith(t + " "):
            return t, full[len(t):].strip()
    return "", full


def en_fields(d: dict) -> list:
    """ช่องข้อมูลภาษาอังกฤษที่หนังสือต้องใช้: ค่าที่แปลได้เอง + ช่องที่ต้องให้ผู้ใช้กรอก"""
    tr = {**FACULTY_EN, **load_translations()}
    program_en = tr.get(d["program"], "")
    if not program_en:
        deg = next((v for k, v in DEGREE_EN.items() if d["program"].startswith(k)), "")
        program_en = f"{deg} Program in " if deg else ""
    ct, cn = split_title(d["contact"])
    fields = [
        ("person", d["name"], name_en(d["title"], d["name"], tr)),
        ("workplace", d["workplace"], tr.get(d["workplace"], d["workplace"])),
        ("program", d["program"], program_en),
        ("faculty", d["faculty"], tr.get(d["faculty"], d["faculty"])),
        ("contact", d["contact"], name_en(ct, cn, tr) if d["contact"] else ""),
    ]
    if d["approver"]:
        fields.append(("approver", d["approver"], tr.get(d["approver"], d["approver"])))
    return [{"key": k, "label": EN_FIELD_LABELS[k], "th": th, "value": v,
             "ok": bool(v) and not THAI.search(v) and not v.rstrip().endswith(" in")}
            for k, th, v in fields if th]


def build_letters_en(d: dict, kinds: list, en: dict, today=None) -> tuple:
    today = today or dt.date.today()
    notes = []
    program = en["program"] + (" (International Program)" if is_international(d) and "International" not in en["program"] else "")
    faculty = en["faculty"]
    rows = [("COURSE", clean(f"{d['course_code']} {d['course_en'] or d['course_th']}"))]
    for s in d["sessions"]:
        place = clean_place(s["place"])
        if needs_unit(place):
            place = clean(f"{place}, {faculty}, Mahidol University")
            notes.append(f"PLACE เติมชื่อส่วนงานให้เป็น “{place}” — โปรดตรวจสอบ")
        rows += [("TOPIC", s["topic"]), ("DATE", en_date(s["date"])), ("TIME", en_time(s["time"])), ("PLACE", place)]
    header = {"ref": "Ref.No.78.02 /", "date": f"{MONTHS_EN[today.month - 1]}{NB * 5}, {today.year}"}
    signature = ["Sincerely yours"] + load_signers()["en"]
    who = en["person"]
    letters = []
    if "invite" in kinds:
        L = Letter(kind="invite", lang="en", address=["Mahidol University"], rows=list(rows), signature=signature)
        L.header = {**header, "subject": subject_of(L), "to": f"Dear {who}"}
        L.body = [f"The Faculty of Graduate Studies, Mahidol University would like to invite you to give lecture "
                  f"for our graduate students in {program} at the {faculty}."]
        contact = f" If you have any questions do not hesitate to contact {en['contact']} in {program} at the " \
                  f"{faculty}, Mahidol University." if en.get("contact") else ""
        email = f" e-mail {d['email']}" if d["email"] and contact else ""
        L.closing = ["Thank you for your kind consideration in this matter. We hope you will accept this invitation."
                     + contact + email]
        letters.append(("invite", L))
    if "approve" in kinds:
        if not d["approver"]:
            notes.append("แบบฟอร์มระบุว่าไม่ต้องขออนุมัติผู้บังคับบัญชา — ไม่ได้สร้างหนังสือขออนุมัติ")
        else:
            L = Letter(kind="approve", lang="en", address=["Mahidol University"], rows=list(rows), signature=signature)
            L.header = {**header, "subject": subject_of(L), "to": f"Dear {en['approver']}"}
            L.body = [f"According to our invitation to {who}, {en['workplace']}, to give a lecture for our graduate "
                      f"students in {program} at the {faculty}. We would like to request your approval to allow "
                      f"{who} to give lecture as outlined below."]
            L.closing = ["We would appreciate your approval. Thank you for your assistance."]
            letters.append(("approve", L))
    return letters, notes


# ---------- ใช้จากโปรแกรม ----------
def inspect(path: Path) -> dict:
    try:
        d = read_pdf(Path(path))
    except Exception as e:
        return {"ok": False, "kind": "บฑ.31", "kind_code": "bt31", "lang": "", "to": "", "reason": f"อ่าน PDF ไม่ได้: {e}"}
    if not d["name"] or not d["course_code"]:
        return {"ok": False, "kind": "บฑ.31", "kind_code": "bt31", "lang": "", "to": "",
                "reason": "ไม่ใช่ PDF หน้า บฑ.31 คำร้องขอเชิญอาจารย์พิเศษ"}
    if not d["lang"]:
        return {"ok": False, "kind": "บฑ.31", "kind_code": "bt31", "lang": "", "to": person(d),
                "reason": "แบบฟอร์มไม่ได้ระบุ “ภาษาที่ขอหนังสือเชิญ” — ระบุในระบบแล้วพิมพ์ PDF ใหม่"}
    first = d["sessions"][0] if d["sessions"] else {}
    if d["lang"] == "en":
        summary = " · ".join(x for x in (d["course_code"], en_date(first.get("date", "")), en_time(first.get("time", ""))) if x)
    else:
        summary = " · ".join(x for x in (d["course_code"], thai_date(first.get("date", "")), first.get("time", "")) if x)
    info = {"ok": True, "kind": "บฑ.31", "kind_code": "bt31", "lang": d["lang"], "to": person(d),
            "lang_label": lang_label(d["lang"]), "lang_source": "ตามที่ขอในแบบฟอร์ม บฑ.31",
            "summary": summary, "approver": d["approver"], "reason": ""}
    kinds = ["invite", "approve"] if d["approver"] else ["invite"]
    if d["lang"] == "en":
        info["en_fields"] = en_fields(d)
        values = {k: "" for k in EN_FIELD_LABELS} | {f["key"]: f["value"] for f in info["en_fields"]}
        letters, _ = build_letters_en(d, kinds, values)
    else:
        letters, _ = build_letters_th(d, kinds)
    info["outputs_preview"] = [output_stem(L) for _, L in letters]   # ชื่อไฟล์ที่จะได้ (แสดงก่อนแปลง)
    return info


def is_form(path: Path) -> bool:
    """เป็น PDF หน้า บฑ.31 หรือไม่ (PDF อื่นในหน้าจอถือเป็นตารางสอนที่แนบ)"""
    try:
        d = read_pdf(Path(path))
    except Exception:
        return False
    return bool(d["name"] and d["course_code"])


def convert(path: Path, outdir=None, pdf=False, want_approve=False, en=None, log=print, fmt=None,
            attachment=False, attach_files=()) -> dict:
    """en: ข้อมูลภาษาอังกฤษที่ผู้ใช้กรอก/แก้ {key: value} (เฉพาะคำร้องขอหนังสือภาษาอังกฤษ)
    คืน {'src', 'ok', 'outputs': [{'kind','docx','pdf'}], 'notes', 'error'}"""
    path = Path(path)
    res = {"src": path, "ok": False, "outputs": [], "notes": [], "error": ""}
    info = inspect(path)
    if not info["ok"]:
        res["error"] = info["reason"]
        return res
    d = read_pdf(path)
    kinds = ["invite"] + (["approve"] if want_approve else [])
    if d["lang"] == "en":
        fields = {f["key"]: f for f in info["en_fields"]}
        values = {k: clean((en or {}).get(k) or f["value"]) for k, f in fields.items()}
        missing = [fields[k]["label"] for k, v in values.items()
                   if (k != "approver" or want_approve) and (not v or THAI.search(v) or v.endswith(" in"))]
        if missing:
            res["error"] = "กรอกข้อมูลภาษาอังกฤษให้ครบ: " + ", ".join(missing)
            return res
        # จำคำแปลไว้ใช้ครั้งต่อไป (ชื่อคนเก็บเฉพาะชื่อ-สกุล ไม่รวมตำแหน่ง/คำนำหน้า)
        learned = {fields[k]["th"]: v for k, v in values.items() if k in ("workplace", "program", "faculty", "approver")}
        learned[core_th(d["name"])] = core_en(values["person"])
        if "contact" in values:
            learned[core_th(split_title(d["contact"])[1])] = core_en(values["contact"])
        save_translations(learned)
        letters, notes = build_letters_en(d, kinds, values)
    else:
        letters, notes = build_letters_th(d, kinds, inform_supervisor=want_approve)
    if d["approver"] and not want_approve:
        notes.append(f"แบบฟอร์มระบุว่าต้องขออนุมัติจาก {d['approver']} — ติ๊ก “ต้องการหนังสือขออนุมัติ” เพื่อสร้างด้วย")
    courses = load_courses()
    if d["course_en"] and d["course_code"]:
        courses[d["course_code"]] = d["course_en"]
        save_courses(courses)
    if attachment:
        for _, L in letters:
            use_attachment(L)
        notes = [n for n in notes if not n.startswith(("สถานที่สอน", "PLACE"))]     # แถวสถานที่เป็น "ตามเอกสารแนบ" แล้ว
    od = Path(outdir) if outdir else path.parent
    entries = [dict(src=path, letter=L, outdir=od, stem=output_stem(L), notes=[], attach=list(attach_files))
               for _, L in letters]
    for r in render_letters(entries, pdf=pdf, log=log, fmt=fmt):
        res["outputs"].append({"kind": r["kind"], "docx": r["docx"], "pdf": r["pdf"], "doc": r["doc"], "error": r["error"]})
    res["notes"] = notes
    res["ok"] = bool(res["outputs"]) and all(o["docx"] or o["pdf"] for o in res["outputs"])
    if not res["ok"]:
        res["error"] = next((o["error"] for o in res["outputs"] if o["error"]), "สร้างไฟล์ไม่สำเร็จ")
    return res


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="สร้างหนังสือเชิญ/ขออนุมัติจาก PDF หน้า บฑ.31")
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--outdir")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--approve", action="store_true", help="สร้างหนังสือขออนุมัติด้วย")
    ap.add_argument("--show", action="store_true", help="แสดงข้อมูลที่อ่านได้จาก PDF")
    ap.add_argument("--en", action="append", default=[], metavar="KEY=VALUE",
                    help="ข้อมูลภาษาอังกฤษ (คำร้องภาษาอังกฤษ): person, workplace, program, faculty, contact, approver")
    args = ap.parse_args(argv)
    ok = True
    for f in args.files:
        if args.show:
            print(json.dumps({**read_pdf(Path(f)), "en_fields": inspect(Path(f)).get("en_fields")}, ensure_ascii=False, indent=2))
            continue
        en = dict(x.split("=", 1) for x in args.en if "=" in x)
        r = convert(Path(f), args.outdir, args.pdf, args.approve, en=en)
        for n in r["notes"]:
            print(f"   หมายเหตุ: {n}")
        if r["error"]:
            print(f"!! {Path(f).name}: {r['error']}")
        ok &= r["ok"]
    return 0 if ok else 2
