# -*- coding: utf-8 -*-
"""
ปรับหนังสือ (หนังสือเชิญ / หนังสือขออนุมัติอาจารย์พิเศษ) ที่ export จากระบบบัณฑิตวิทยาลัย
ให้เป็นรูปแบบมาตรฐานตามไฟล์ตัวอย่าง แล้วบันทึกเป็น .docx ผ่าน Microsoft Word

วิธีใช้:
    python fix_letters.py                      -> เปิดหน้าต่างให้เลือกไฟล์
    python fix_letters.py "Export (90).doc" "Export (91).doc"
    python fix_letters.py C:\\Users\\...\\Downloads   (ทุกไฟล์ Export*.doc ในโฟลเดอร์)
ตัวเลือก:
    -o DIR      โฟลเดอร์ปลายทาง (ค่าเริ่มต้น: โฟลเดอร์เดียวกับไฟล์ต้นฉบับ)
    --pdf       สร้างไฟล์ PDF เพิ่ม
    --doc       เก็บไฟล์ .doc (Word HTML แบบเดียวกับไฟล์ตัวอย่าง) เพิ่ม
    --no-supervisor  ไม่ต้องขออนุมัติผู้บังคับบัญชา (ตัดประโยคแจ้งผู้บังคับบัญชาในหนังสือเชิญ)
ชื่อไฟล์ผลลัพธ์: หนังสือเชิญ-บฑ.31 <รหัสวิชา> <ชื่ออาจารย์>  /  หนังสือขออนุมัติ-GR.31 <รหัสวิชา> <ชื่ออาจารย์> (ภาษาอังกฤษ)
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
COURSES_FILE = BASE / "courses.json"
LOGO_URL = "https://graduate.mahidol.ac.th/prof/admin/pic/logo_mu1.jpg"
LOGO_FILE = ASSETS / "logo_mu1.jpg"

NB = "\u00a0"
THAI = re.compile(r"[\u0e00-\u0e7f]")
COURSE_CODE = re.compile(r"^(?:วิชา\s*)?([A-Z]{2,6}\s?\d{3,4})\s*:?$")
CREDITS = re.compile(r"\s*\d+(?:\s*\([\d\s\-]+\))?\s*(?:หน่วยกิต|credits?)\s*$", re.I)
COURSE_LABELS = {"วิชา", "COURSE", "SUBJECT"}
EN_LABELS = {"วิชา": "COURSE", "หัวข้อ": "TOPIC", "วันที่": "DATE", "เวลา": "TIME", "สถานที่": "PLACE"}
SMALL_WORDS = r"Of|In|And|For|The|At|On|To|With|From|By"
SIGN_OFF = r"ขอแสดงความนับถือ|Sincerely|Yours|Best regards|Kind regards"
NO_TITLE_TH = re.compile(r"(?<!\S)อื่น\s?ๆ\s+")   # ระบบใส่ "อื่นๆ" แทนตำแหน่งทางวิชาการที่ไม่ได้ระบุ
SUPERVISOR_INFORMED = re.compile(r"\s*ทั้งนี้\s*ได้แจ้งให้ผู้บังคับบัญชาของท่าน\s*ทราบแล้ว")
TIME_RANGE = re.compile(r"(\d{1,2}[.:]\d{2})\s*-\s*(\d{1,2}[.:]\d{2})")
DEGREE_AND = re.compile(r"หลักสูตร (?:(ปริญญา(?:ตรี|โท|เอก)) )?และ (?:(ปริญญา(?:ตรี|โท|เอก)) )?")

# ---------- รูปแบบตามไฟล์ตัวอย่าง ----------
FONT = 'font-size:16.0pt;font-family:"TH Sarabun New",sans-serif;mso-fareast-font-family:"Times New Roman"'
LH = "line-height:18.0pt;mso-line-height-rule:exactly;"
TAB = "tab-stops:2.0cm"
INDENT = ("<span style='mso-spacerun:yes'> </span>"
          "<span style='mso-tab-count:1'>               </span>")

DOC_TYPES = {
    # ชื่อเรียก, บรรทัดว่างก่อนข้อมูลติดต่อ, ย่อหน้าว่างหลังคำลงท้าย, ย่อหน้าว่างท้ายเอกสาร,
    # ระยะห่างตัวอักษรของย่อหน้าแรกหลังตาราง
    "approve": dict(name="หนังสืออนุมัติ", contact_gap=2, blank_after_closing=True, tail_blank=True,
                    first_closing_spacing=""),
    "invite": dict(name="หนังสือเชิญ", contact_gap=1, blank_after_closing=False, tail_blank=False,
                   first_closing_spacing=".3pt"),
    "generic": dict(name="หนังสือ", contact_gap=1, blank_after_closing=False, tail_blank=False,
                    first_closing_spacing=""),
}

# หนังสือภาษาอังกฤษ (ตามไฟล์ตัวอย่าง (EN)): บรรทัดว่างก่อนย่อหน้าท้าย, เยื้องด้วย tab หรือ &nbsp;,
# ย่อหน้าว่างท้ายเอกสาร (ระยะ margin-bottom)
EN_TYPES = {
    "approve": dict(closing_breaks=2, closing_indent="nbsp", tail=(12, 14)),
    "invite": dict(closing_breaks=1, closing_indent="tab", tail=(12,)),
    "generic": dict(closing_breaks=1, closing_indent="tab", tail=(12,)),
}


@dataclass
class Letter:
    kind: str = "generic"
    lang: str = "th"                             # "th" | "en"
    address: list = field(default_factory=list)  # ที่อยู่ (TH) / ชื่อสถาบันกึ่งกลาง (EN)
    header: dict = field(default_factory=dict)   # ref, date, subject, to
    body: list = field(default_factory=list)     # ย่อหน้าก่อนตาราง
    rows: list = field(default_factory=list)     # [(label, value)]
    closing: list = field(default_factory=list)  # ย่อหน้าหลังตาราง
    signature: list = field(default_factory=list)
    contact: list = field(default_factory=list)


# ---------- อ่านไฟล์ ----------
def read_source(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp874"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def to_lines(frag: str) -> list:
    """HTML -> รายการบรรทัด (ตัดตาม <br>/<div>), เก็บ &nbsp; ไว้เป็น \\xa0"""
    frag = re.sub(r"(?i)<br\s*/?>", "\n", frag)
    frag = re.sub(r"(?i)</?(?:div|p|tr)\b[^>]*>", "\n", frag)
    frag = re.sub(r"<[^>]+>", "", frag)
    frag = html.unescape(frag)
    return [re.sub(r"[ \t]+", " ", ln) for ln in frag.split("\n")]


def clean(s: str) -> str:
    """ตัดช่องว่าง/&nbsp; หัวท้าย และยุบช่องว่างซ้ำเหลือช่องเดียว"""
    return re.sub(r"[ \u00a0]+", " ", s).strip()


def join_sentences(parts: list) -> str:
    """ภาษาอังกฤษ: บรรทัดที่ระบบตัดด้วย <br> กลางย่อหน้า ถ้าไม่มีเครื่องหมายปิดประโยค ให้เติมจุด"""
    out = parts[0]
    for p in parts[1:]:
        if re.search(r"[A-Za-z0-9)]$", out) and p[:1].isupper():
            out += "."
        out += " " + p
    return out


def paragraphs(lines: list, en=False) -> list:
    """รวมบรรทัดเป็นย่อหน้า โดยใช้บรรทัดว่างเป็นตัวแบ่ง"""
    join = join_sentences if en else " ".join
    out, cur = [], []
    for ln in lines:
        if clean(ln):
            cur.append(clean(ln))
        elif cur:
            out.append(join(cur))
            cur = []
    if cur:
        out.append(join(cur))
    return out


LANG_SIGNALS = {
    "th": ("เรียน", "เรื่อง", "ขอแสดงความนับถือ", "ที่ อว", "จึงเรียน", "จึงขอเรียนเชิญ", "บัณฑิตวิทยาลัย มหาวิทยาลัยมหิดล"),
    "en": ("Dear ", "Sincerely", "Ref.No", "COURSE :", "would like to invite", "request your approval",
           "Faculty of Graduate Studies, Mahidol University"),
}


def detect_lang(text: str) -> str:
    """ภาษาของหนังสือจากถ้อยคำในเอกสาร: 'th' / 'en' / '' (ตัดสินไม่ได้)"""
    score = {lang: sum(k in text for k in keys) for lang, keys in LANG_SIGNALS.items()}
    if score["th"] == score["en"]:
        return ""
    return max(score, key=score.get)


def lang_label(lang: str) -> str:
    return {"th": "หนังสือภาษาไทย · บฑ.31", "en": "หนังสือภาษาอังกฤษ · GR.31"}.get(lang, "ไม่ทราบภาษา")


def parse(src: str) -> Letter:
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    src = re.sub(r"(?is)<style.*?</style>|<link[^>]*>|<img[^>]*>", "", src)
    src = re.sub(r"\s*[\r\n]+\s*", " ", src)
    i = src.lower().find("<body")
    body = src[i:] if i >= 0 else src

    L = Letter()
    m = re.search(r"(?is)<table.*?</table>", body)
    pre, table, post = (body[:m.start()], m.group(0), body[m.end():]) if m else (body, "", "")
    L.lang = detect_lang(" ".join(clean(x) for x in to_lines(body)))

    if L.lang == "en":
        parse_header_en(L, to_lines(pre))
    else:
        # ที่อยู่ส่วนราชการ (div ชิดขวาก่อน "ที่")
        am = re.search(r'(?is)<div[^>]*align="?right"?[^>]*>(.*?)</div>', pre)
        if am:
            L.address = [clean(x) for x in to_lines(am.group(1)) if clean(x)]
            pre = pre[am.end():]

        # หัวหนังสือ + เนื้อความก่อนตาราง
        lines = to_lines(pre)
        keys = [("ref", "ที่ "), ("date", "วันที่"), ("subject", "เรื่อง"), ("to", "เรียน")]
        rest_at = 0
        for idx, ln in enumerate(lines):
            c = clean(ln)
            for k, prefix in keys:
                if k not in L.header and c.startswith(prefix):
                    L.header[k] = c
                    rest_at = idx + 1
                    break
            if "to" in L.header:
                break
        L.body = paragraphs(lines[rest_at:])

    # ตาราง
    for tr in re.findall(r"(?is)<tr\b.*?</tr>", table):
        cells = [clean(" ".join(to_lines(td))) for td in re.findall(r"(?is)<td\b[^>]*>(.*?)</td>", tr)]
        if len(cells) >= 2:
            L.rows.append((cells[0].rstrip(": ").strip(), cells[1]))

    # คำลงท้าย / ลายมือชื่อ / ข้อมูลติดต่อ
    sm = re.search(rf'(?is)<div[^>]*align="?right"?[^>]*>\s*(?={SIGN_OFF})', post)
    if sm:
        closing_html, after = post[:sm.start()], post[sm.end():]
        end = after.lower().find("</div>")
        sig_html, contact_html = (after[:end], after[end + 6:]) if end >= 0 else (after, "")
    else:
        closing_html, sig_html, contact_html = post, "", ""
    L.closing = paragraphs(to_lines(closing_html), en=L.lang == "en")
    L.signature = [ln.strip(" ") for ln in to_lines(sig_html) if clean(ln)]
    L.contact = [clean(x) for x in to_lines(contact_html) if clean(x)]

    if L.lang == "en":
        text = " ".join(L.body).lower()
        L.kind = "approve" if "approv" in text else "invite" if "invit" in text else "generic"
    else:
        subj = L.header.get("subject", "")
        L.kind = "approve" if "อนุมัติ" in subj else "invite" if "เชิญ" in subj else "generic"
    return L


def parse_header_en(L: Letter, lines: list):
    """ภาษาอังกฤษ: [ชื่อสถาบัน] / Ref.No... / เดือน , ปี / Dear ... / เนื้อความ"""
    cl = [clean(x) for x in lines]
    ref = next((i for i, c in enumerate(cl) if re.match(r"(?i)ref\b", c)), None)
    dear = next((i for i, c in enumerate(cl) if c.startswith("Dear")), len(cl))
    top = ref if ref is not None else dear
    L.address = [c for c in cl[:top] if c]
    if ref is not None:
        L.header["ref"] = cl[ref]
        date = [c for c in cl[ref + 1:dear] if c]
        if date:
            L.header["date"] = " ".join(date)
    if dear < len(cl):
        L.header["to"] = cl[dear]
    L.body = paragraphs(lines[dear + 1:], en=True)


# ---------- ปรับเนื้อหา ----------
def fix_text(s: str) -> str:
    s = TIME_RANGE.sub(r"\1 - \2", clean(s))
    return re.sub(r"(\d[.:]\d{2})\s*น\.", r"\1 น.", s)     # "12.00น." -> "12.00 น."


def fix_degree(s: str) -> str:
    """'หลักสูตร และ ปริญญาเอก ปรัชญาดุษฎีบัณฑิต' -> 'หลักสูตร ปรัชญาดุษฎีบัณฑิต'"""
    def repl(m):
        return m.group(0) if m.group(1) and m.group(2) else "หลักสูตร "
    return DEGREE_AND.sub(repl, s)


def load_courses() -> dict:
    try:
        return json.loads(COURSES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_courses(courses: dict):
    COURSES_FILE.write_text(json.dumps(courses, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


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


def normalize_en(L: Letter, courses: dict) -> list:
    if "to" in L.header:
        L.header["to"] = fix_en(L.header["to"])
    if "date" in L.header:
        d = clean(L.header["date"])
        m = re.fullmatch(r"([A-Za-z]+)\s*,\s*(\d{4})", d)       # "April , 2026" -> เว้นที่ให้เติมวัน
        L.header["date"] = f"{m[1]}{NB * 5}, {m[2]}" if m else d
    L.address = L.address or ["Mahidol University"]
    L.body = [fix_en(p) for p in L.body]
    L.body = [p + "." if re.search(r"[A-Za-z0-9)]$", p) else p for p in L.body]
    L.closing = [fix_en(p) for p in L.closing]

    rows = []
    c = course_of(L)
    for i, (label, value) in enumerate(L.rows):
        if c and i == c[0]:
            name = c[2]
            if THAI.search(name) and c[1] in courses:
                name = courses[c[1]]
            rows.append(("COURSE", f"{c[1]} {name}".strip()))
            continue
        label = EN_LABELS.get(label, label.upper())
        value = fix_text(value)
        if label == "TIME":
            value = re.sub(r"\s*น\.$", "", value)
        elif label != "DATE":
            value = fix_en(value)
        rows.append((label, value))
    L.rows = rows
    return []


def kind_name(L: Letter) -> str:
    return DOC_TYPES[L.kind]["name"] + (" (EN)" if L.lang == "en" else "")


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
    stem = f"{kind}-{'GR.31' if L.lang == 'en' else 'บฑ.31'} {c[1] if c else ''} {lecturer_name(L)}"
    return clean(re.sub(r'[<>:"/\\|?*]', "", stem)).rstrip(". ")


def normalize(L: Letter, courses: dict, inform_supervisor: bool = True) -> list:
    """inform_supervisor=False: ไม่ต้องขออนุมัติผู้บังคับบัญชา -> ตัดประโยค "ทั้งนี้ได้แจ้งให้ผู้บังคับบัญชาของท่านทราบแล้ว" """
    if L.lang == "en":
        return normalize_en(L, courses)
    notes = []
    L.header = {k: NO_TITLE_TH.sub("", fix_text(v)) for k, v in L.header.items()}
    if "date" in L.header:
        L.header["date"] = "วันที่ " + NB * 4 + " " + L.header["date"][len("วันที่"):].strip()
    L.body = [NO_TITLE_TH.sub("", fix_degree(fix_text(p))) for p in L.body]
    L.closing = [fix_degree(fix_text(p)) for p in L.closing]
    if not inform_supervisor:
        L.closing = [SUPERVISOR_INFORMED.sub("", p) for p in L.closing]

    c = course_of(L)
    if c:
        i, code, name = c
        if THAI.search(name):     # ใช้ชื่อวิชาภาษาอังกฤษเสมอ
            if code in courses:
                name = courses[code]
            else:
                notes.append(f"ไม่พบชื่อวิชาภาษาอังกฤษของ {code} (ใช้ชื่อภาษาไทย) — "
                             f"แปลงหนังสือเชิญของวิชานี้ก่อน หรือเพิ่มใน courses.json")
        L.rows[i] = ("วิชา", f"{code} {name}".strip())
        # ข้อความ "...ในการสอนวิชา" ซ้ำกับหัวตาราง "วิชา :" จึงตัดออก
        if L.body and L.body[-1].endswith("วิชา"):
            L.body[-1] = L.body[-1][:-len("วิชา")].rstrip()
    L.rows = [(label, fix_text(v)) for label, v in L.rows]
    return notes


# ---------- สร้าง Word HTML ----------
def esc(s: str) -> str:
    return html.escape(s, quote=False).replace(NB, "&nbsp;")


def para(content: str, align: str = "", line_height=True, justify="", space_after=False) -> str:
    """justify: "" | "thai" (กระจายแบบ inter-cluster) | "plain" """
    style = ""
    attr = ""
    if align:
        attr = f" align={align}"
        style += f"text-align:{align};"
    if space_after:
        style = "margin-bottom:14.0pt;" + style
    if justify:
        style += "text-align:justify;" + ("text-justify:inter-cluster;" if justify == "thai" else "")
    if line_height:
        style += LH
    style += TAB
    return f"<p class=MsoNormal{attr} style='{style}'><span lang=TH style='{FONT}'>{content}<o:p></o:p></span></p>\n\n"


def lines_html(lines: list) -> str:
    return "<br>\n".join(esc(x) for x in lines)


TEXT_WIDTH = 595.3 - 72 - 72      # ความกว้างพื้นที่พิมพ์ A4 (pt) ตามขอบใน word_head.html
SIGN_CENTER = 0.75                # แกนกลางของบล็อกลายมือชื่อ (สัดส่วนจากขอบซ้ายของพื้นที่พิมพ์) ตามไฟล์ตัวอย่าง
FONT_FILES = {"TH Sarabun New": "THSarabunNew.ttf", "TH SarabunPSK": "THSarabun.ttf"}
THAI_MARKS = re.compile(r"[ัิ-ฺ็-๎]")   # สระบน/ล่าง วรรณยุกต์ ไม่กินที่ในบรรทัด


def text_width_pt(text: str, family: str, size: float = 16) -> float:
    """วัดความกว้างข้อความด้วยฟอนต์จริงในเครื่อง (ถ้าวัดไม่ได้ ใช้ค่าประมาณ)"""
    dirs = [Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",   # ฟอนต์ที่ติดตั้งเฉพาะผู้ใช้
            Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
    try:
        from PIL import ImageFont
        path = next((d / FONT_FILES[family] for d in dirs if (d / FONT_FILES[family]).exists()), None)
        if path is None:      # เครื่องอื่นอาจตั้งชื่อไฟล์ฟอนต์ต่างไป: หาไฟล์ตัวปกติ (ไม่ใช่ Bold/Italic) ที่ชื่อตรงกัน
            key = family.replace(" ", "").lower().replace("thsarabunpsk", "thsarabun")
            path = next(f for d in dirs if d.exists() for f in d.glob("*.tt[fc]")
                        if f.stem.replace(" ", "").replace("-", "").lower() in (key, key + "regular"))
        return ImageFont.truetype(str(path), 100).getlength(text) * size / 100
    except Exception:
        return len(THAI_MARKS.sub("", text)) * size * 0.30


def signature_block(lines: list, family: str, thai: bool) -> str:
    """บล็อกคำลงท้าย + ชื่อ + ตำแหน่ง จัดกึ่งกลางทุกบรรทัดบนแกนเดียวกัน
    แกนอยู่ที่ราว 3/4 ของบรรทัด แต่ขยับซ้ายให้บรรทัดที่ยาวที่สุดไม่เกินขอบขวา"""
    longest = max(text_width_pt(x, family) for x in lines if x) + 6
    center = min(TEXT_WIDTH * SIGN_CENTER, TEXT_WIDTH - longest / 2)
    indent = max(0.0, 2 * center - TEXT_WIDTH)      # ย่อหน้าจัดกึ่งกลางที่เยื้องซ้าย indent -> กึ่งกลางอยู่ที่ center
    font = f'font-size:16.0pt;font-family:"{family}",sans-serif;mso-fareast-font-family:"Times New Roman"'
    style = f"margin-left:{indent:.1f}pt;text-align:center;" + (LH + TAB if thai else "")
    body = "<br>\n".join(esc(x) if x else "&nbsp;" for x in lines)
    lang = " lang=TH" if thai else ""
    return f"<p class=MsoNormal align=center style='{style}'><span{lang} style='{font}'>{body}<o:p></o:p></span></p>\n\n"


def wrap_document(paragraphs_html: list) -> str:
    head = (ASSETS / "word_head.html").read_text(encoding="utf-8")
    return (head + "\n<body lang=EN-US style='tab-interval:36.0pt;word-wrap:break-word'>\n\n"
            "<div class=WordSection1>\n\n" + "".join(paragraphs_html) + "</div>\n\n</body>\n\n</html>\n")


def para_en(content: str, align="", justify=False, margin_bottom=0, tab_stop="", font=FONT) -> str:
    """ย่อหน้าภาษาอังกฤษ: ระยะบรรทัดปกติ (single) ตามไฟล์ตัวอย่าง (EN)"""
    style = f"margin-bottom:{margin_bottom}.0pt;" if margin_bottom else ""
    attr = f" align={align}" if align else ""
    if align:
        style += f"text-align:{align};"
    if justify:
        style += "text-align:justify;"
    if tab_stop:
        style += f"tab-stops:{tab_stop};"
    style_attr = f" style='{style.rstrip(';')}'" if style else ""
    return f"<p class=MsoNormal{attr}{style_attr}><span style='{font}'>{content}<o:p></o:p></span></p>\n\n"


def build_html_en(L: Letter, logo_src: str) -> str:
    prof = EN_TYPES[L.kind]
    h = L.header
    indent13 = "&nbsp;" * 13
    out = [para_en(f'<img width=90 height=90 src="{logo_src}">', align="center"),
           para_en(lines_html(L.address), align="center"),
           para_en(lines_html([x for x in (h.get("ref"), h.get("date")) if x]))]
    if h.get("to"):
        out.append(para_en("<br>\n" + esc(h["to"])))
    for p in L.body:
        out.append(para_en("<br>\n" + indent13 + esc(p), justify=True))

    if L.rows:
        out.append("<table class=MsoNormalTable border=0 cellpadding=0 width=\"100%\" "
                   "style='width:100.0%;mso-cellspacing:1.5pt'>\n")
        for label, value in L.rows:
            out.append(
                " <tr>\n  <td width=\"20%\" valign=top style='width:20.0%;padding:.75pt .75pt .75pt .75pt'>\n  "
                + para_en(esc(label) + " : ", align="right").strip()
                + "\n  </td>\n  <td style='padding:.75pt .75pt .75pt .75pt'>\n  "
                + para_en(esc(value)).strip()
                + "\n  </td>\n </tr>\n")
        out.append("</table>\n\n")

    if L.closing:
        indent = INDENT if prof["closing_indent"] == "tab" else indent13
        content = "<br>\n" * prof["closing_breaks"] + "<br>\n<br>\n".join(indent + esc(p) for p in L.closing)
        out.append(para_en(content, justify=True, margin_bottom=12,
                           tab_stop="42.55pt" if prof["closing_indent"] == "tab" else ""))

    if L.signature:
        # ฟอนต์ TH SarabunPSK และบรรทัดว่าง 3 บรรทัดสำหรับลงนาม ตามไฟล์ตัวอย่าง (EN)
        first, *others = [clean(x) for x in L.signature]
        out.append(signature_block([first, "", "", ""] + others, "TH SarabunPSK", thai=False))
    if L.contact:
        out.append(para_en(lines_html([""] + L.contact)))
    for mb in prof["tail"]:
        out.append(para_en("&nbsp;", margin_bottom=mb))
    return wrap_document(out)


def build_html(L: Letter, logo_src: str) -> str:
    if L.lang == "en":
        return build_html_en(L, logo_src)
    prof = DOC_TYPES[L.kind]
    h = L.header
    out = [para(f'<img width=90 height=90 src="{logo_src}">', align="center", line_height=False)]
    if L.address:
        out.append(para(lines_html(L.address), align="right", line_height=False))
    out.append(para(lines_html(["", h.get("ref", ""), h.get("date", ""), h.get("subject", ""), "", h.get("to", "")])))
    for p in L.body:
        out.append(para("<br>\n" + INDENT + esc(p), justify="thai"))

    if L.rows:
        out.append("<table class=MsoNormalTable border=0 cellspacing=3 cellpadding=0 width=\"100%\" "
                   "style='width:100.0%;mso-cellspacing:1.5pt'>\n")
        for label, value in L.rows:
            out.append(
                " <tr>\n  <td width=\"20%\" valign=top style='width:20.0%;padding:.75pt .75pt .75pt .75pt'>\n  "
                + para(esc(label) + " : ", align="right").strip()
                + "\n  </td>\n  <td style='padding:.75pt .75pt .75pt .75pt'>\n  "
                + para(esc(value)).strip()
                + "\n  </td>\n </tr>\n")
        out.append("</table>\n\n")

    if L.closing:
        parts = [esc(p) for p in L.closing]
        if prof["first_closing_spacing"]:
            parts[0] = f"<span style='letter-spacing:{prof['first_closing_spacing']}'>{parts[0]}</span>"
        content = "<br>\n" + "<br>\n<br>\n".join(INDENT + p for p in parts)
        out.append(para(content, justify="plain", space_after=True))
    if prof["blank_after_closing"]:
        out.append(para("&nbsp;", space_after=True))

    if L.signature:
        first, *others = [clean(x) for x in L.signature]
        out.append(signature_block([first, "", "", ""] + others, "TH Sarabun New", thai=True))
    if L.contact:
        out.append(para(lines_html([""] * prof["contact_gap"] + L.contact), line_height=False))
    if prof["tail_blank"]:
        out.append(para("&nbsp;", align="right"))
    return wrap_document(out)


# ---------- โลโก้ / Word ----------
def logo_source(tmp: Path) -> str:
    """คัดลอกโลโก้ไว้ข้างไฟล์ HTML ชั่วคราว ให้ Word ฝังรูปลงเอกสารได้แม้ไม่มีอินเทอร์เน็ต"""
    if not LOGO_FILE.exists():
        try:
            with urllib.request.urlopen(LOGO_URL, timeout=15) as r:
                LOGO_FILE.write_bytes(r.read())
        except OSError:
            return LOGO_URL
    shutil.copy(LOGO_FILE, tmp / "logo.jpg")
    return "logo.jpg"


def word_convert(jobs: list) -> dict:
    """jobs: [{'in':..., 'docx':..., 'pdf':...}] (path ภาษาอังกฤษใน temp) -> {in: error or ''}"""
    jf = Path(jobs[0]["in"]).parent / "jobs.json"
    jf.write_text(json.dumps(jobs), encoding="utf-8")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(ASSETS / "to_docx.ps1"), "-Jobs", str(jf)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    results = {}
    for ln in r.stdout.splitlines():
        if ln.startswith(("OK\t", "ERR\t")):
            status, path, *msg = ln.split("\t")
            results[path] = "" if status == "OK" else (msg[0] if msg else "error")
    if not results:
        raise RuntimeError((r.stderr or r.stdout or "ไม่สามารถเรียก Microsoft Word").strip())
    return results


def unique(path: Path) -> Path:
    if not path.exists():
        return path
    n = 2
    while (p := path.with_name(f"{path.stem} ({n}){path.suffix}")).exists():
        n += 1
    return p


def collect(args_files: list) -> list:
    files = []
    for a in args_files:
        p = Path(a)
        if p.is_dir():
            files += sorted(x for x in p.glob("Export*.doc"))
        elif p.exists():
            files.append(p)
        else:
            print(f"!! ไม่พบไฟล์: {a}")
    return files


def pick_files() -> list:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    names = filedialog.askopenfilenames(
        title="เลือกไฟล์ Export ที่ต้องการปรับ",
        initialdir=str(Path.home() / "Downloads"),
        filetypes=[("Word export", "*.doc *.htm *.html"), ("All files", "*.*")])
    root.destroy()
    return [Path(n) for n in names]


def inspect(path: Path) -> dict:
    """อ่านไฟล์แบบเร็วเพื่อแสดงในหน้าจอ: ประเภทหนังสือ และผู้รับ"""
    try:
        src = read_source(path)
    except OSError as e:
        return {"ok": False, "kind": "", "kind_code": "", "lang": "", "to": "", "reason": str(e)}
    if "ProgId content=Word.Document" in src:
        return {"ok": False, "kind": "", "kind_code": "", "lang": "", "to": "",
                "reason": "ไม่ใช่ไฟล์ export (เป็นไฟล์ Word แล้ว)"}
    L = parse(src)
    if not L.header:
        return {"ok": False, "kind": "", "kind_code": "", "lang": "", "to": "",
                "reason": "ไม่พบหัวหนังสือ (ที่/วันที่/เรื่อง/เรียน หรือ Dear)"}
    if not L.lang:
        return {"ok": False, "kind": "", "kind_code": L.kind, "lang": "", "to": "",
                "reason": "ระบุไม่ได้ว่าเป็นหนังสือภาษาไทยหรือภาษาอังกฤษ — ตรวจไฟล์ต้นฉบับ"}
    to = L.header.get("to", "").removeprefix("เรียน").removeprefix("Dear")
    to = clean(fix_en(to) if L.lang == "en" else NO_TITLE_TH.sub("", to))
    normalize(L, load_courses())          # เพื่อแสดงชื่อไฟล์ที่จะได้ก่อนแปลง
    return {"ok": True, "kind": kind_name(L), "kind_code": L.kind, "lang": L.lang, "lang_label": lang_label(L.lang),
            "lang_source": "ตามถ้อยคำในไฟล์ Export", "to": to, "outputs_preview": [output_stem(L)], "reason": ""}


def convert(files: list, outdir=None, pdf=False, keep_doc=False, log=print, inform_supervisor=True) -> list:
    """แปลงไฟล์ทั้งหมด คืนรายการผลลัพธ์
    [{'src': Path, 'kind': str, 'docx': Path|None, 'pdf': Path|None, 'doc': Path|None, 'notes': [...], 'error': str}]"""
    courses = load_courses()
    results, letters = [], []
    for f in files:
        f = Path(f)
        try:
            src = read_source(f)
        except OSError as e:
            results.append(dict(src=f, kind="", docx=None, pdf=None, doc=None, notes=[], error=str(e)))
            continue
        if "ProgId content=Word.Document" in src:
            msg = "ข้าม: เป็นไฟล์ที่บันทึกจาก Word แล้ว (ไม่ใช่ไฟล์ export จากระบบ)"
            log(f"-- {f.name}: {msg}")
            results.append(dict(src=f, kind="", docx=None, pdf=None, doc=None, notes=[], error=msg))
            continue
        L = parse(src)
        if not L.lang:
            msg = "ระบุไม่ได้ว่าเป็นหนังสือภาษาไทยหรือภาษาอังกฤษ"
            log(f"!! {f.name}: {msg}")
            results.append(dict(src=f, kind="", docx=None, pdf=None, doc=None, notes=[], error=msg))
            continue
        learn_course(L, courses)
        letters.append((f, L))
    save_courses(courses)
    # หนังสือเชิญก่อน เพื่อให้หนังสืออนุมัติใช้ชื่อวิชาภาษาอังกฤษจากหนังสือเชิญได้
    letters.sort(key=lambda x: x[1].kind != "invite")
    if not letters:
        return results

    entries = []
    for f, L in letters:
        notes = normalize(L, courses, inform_supervisor)
        if clean(re.sub(r"^(?:เรียน|Dear)", "", L.header.get("to", ""))) in ("", "-"):
            notes.append("ไฟล์ต้นฉบับไม่มีชื่อผู้รับ (บรรทัด เรียน/Dear ว่าง) — กรอกในระบบแล้ว export ใหม่ หรือแก้ในไฟล์ Word")
        od = Path(outdir) if outdir else f.parent
        entries.append(dict(src=f, letter=L, outdir=od, stem=output_stem(L), notes=notes))
    return results + render_letters(entries, pdf=pdf, keep_doc=keep_doc, log=log)


def render_letters(entries: list, pdf=False, keep_doc=False, log=print) -> list:
    """สร้างไฟล์จาก Letter ที่จัดรูปแบบแล้ว
    entries: [{'src': Path, 'letter': Letter, 'outdir': Path, 'stem': str, 'notes': [...]}]"""
    if not entries:
        return []
    tmp = Path(tempfile.mkdtemp(prefix="fixletters_"))
    logo = logo_source(tmp)
    jobs = []
    for n, e in enumerate(entries):
        L, od, stem = e["letter"], Path(e["outdir"]), e["stem"]
        od.mkdir(parents=True, exist_ok=True)
        tmp_html = tmp / f"doc{n}.htm"
        tmp_html.write_text(build_html(L, logo), encoding="utf-8")
        job = {"in": str(tmp_html), "docx": str(tmp / f"doc{n}.docx")}
        if pdf:
            job["pdf"] = str(tmp / f"doc{n}.pdf")
        res = dict(src=e["src"], kind=kind_name(L), docx=None, pdf=None, doc=None, notes=e["notes"], error="")
        if keep_doc:
            res["doc"] = unique(od / f"{stem}.doc")
            res["doc"].write_text(build_html(L, LOGO_URL), encoding="utf-8")
            log(f"   .doc  -> {res['doc']}")
        jobs.append((job, od, stem, res))

    log("กำลังแปลงด้วย Microsoft Word ...")
    try:
        status = word_convert([j for j, *_ in jobs])
    except RuntimeError as e:
        log(f"!! แปลงเป็น .docx ไม่สำเร็จ ({e}) — บันทึกเป็น .doc แทน")
        status = None

    results = []
    for job, od, stem, res in jobs:
        name = Path(res["src"]).name
        err = "Word ไม่ทำงาน" if status is None else status.get(job["in"], "ไม่ทราบสาเหตุ")
        if err:
            fallback = unique(od / f"{stem}.doc")
            fallback.write_text(Path(job["in"]).read_text(encoding="utf-8")
                                .replace(f'src="{logo}"', f'src="{LOGO_URL}"'), encoding="utf-8")
            res.update(error=err, doc=fallback)
            log(f"!! {name}: {err} -> บันทึกเป็น {fallback}")
        else:
            res["docx"] = unique(od / f"{stem}.docx")
            shutil.move(job["docx"], res["docx"])
            log(f"OK {name} -> {res['docx']}")
            if job.get("pdf") and Path(job["pdf"]).exists():
                res["pdf"] = unique(od / f"{stem}.pdf")
                shutil.move(job["pdf"], res["pdf"])
                log(f"   pdf   -> {res['pdf']}")
            for note in res["notes"]:
                log(f"   หมายเหตุ: {note}")
        results.append(res)
    shutil.rmtree(tmp, ignore_errors=True)
    return results


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="ปรับไฟล์ Export จากระบบบัณฑิตวิทยาลัยให้เป็นรูปแบบมาตรฐาน")
    ap.add_argument("files", nargs="*")
    ap.add_argument("-o", "--outdir")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--doc", action="store_true")
    ap.add_argument("--no-supervisor", action="store_true",
                    help="ไม่ต้องขออนุมัติผู้บังคับบัญชา: ตัดประโยค 'ทั้งนี้ได้แจ้งให้ผู้บังคับบัญชาของท่านทราบแล้ว'")
    args = ap.parse_args(argv)

    files = collect(args.files) if args.files else pick_files()
    if not files:
        print("ไม่มีไฟล์ให้ปรับ")
        return 1
    # PDF หน้า บฑ.31 -> สร้างหนังสือจากข้อมูลแบบฟอร์ม (หนังสือขออนุมัติด้วย ถ้าแบบฟอร์มระบุ)
    pdfs = [f for f in files if f.suffix.lower() == ".pdf"]
    files = [f for f in files if f.suffix.lower() != ".pdf"]
    total = ok = 0
    if pdfs:
        import bt31
        for f in pdfs:
            r = bt31.convert(f, args.outdir, args.pdf, want_approve=not args.no_supervisor)
            for n in r["notes"]:
                print(f"   หมายเหตุ: {n}")
            if r["error"]:
                print(f"!! {f.name}: {r['error']}")
            total += 1
            ok += r["ok"]
    if files:
        results = convert(files, args.outdir, args.pdf, args.doc, inform_supervisor=not args.no_supervisor)
        total += len(results)
        ok += sum(1 for r in results if r["docx"])
    print(f"\nเสร็จ {ok}/{total} ไฟล์")
    return 0 if total and ok == total else 2


if __name__ == "__main__":
    sys.exit(main())
