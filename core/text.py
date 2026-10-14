# -*- coding: utf-8 -*-
"""ข้อความ: อ่านไฟล์ที่ระบบ export (HTML นามสกุล .doc), ตัดเป็นบรรทัด/ย่อหน้า, ทำความสะอาดช่องว่าง"""
import html
import re
from pathlib import Path

NB = " "
THAI = re.compile(r"[฀-๿]")


def read_source(path: Path) -> str:
    raw = Path(path).read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp874"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def is_word_saved(src: str) -> bool:
    """ไฟล์ที่บันทึกจาก Word แล้ว (ไม่ใช่ไฟล์ export ดิบจากระบบ)"""
    return "ProgId content=Word.Document" in src


def to_lines(frag: str) -> list:
    """HTML -> รายการบรรทัด (ตัดตาม <br>/<div>), เก็บ &nbsp; ไว้เป็น \\xa0"""
    frag = re.sub(r"(?i)<br\s*/?>", "\n", frag)
    frag = re.sub(r"(?i)</?(?:div|p|tr)\b[^>]*>", "\n", frag)
    frag = re.sub(r"<[^>]+>", "", frag)
    frag = html.unescape(frag)
    return [re.sub(r"[ \t]+", " ", ln) for ln in frag.split("\n")]


def clean(s: str) -> str:
    """ตัดช่องว่าง/&nbsp; หัวท้าย และยุบช่องว่างซ้ำเหลือช่องเดียว"""
    return re.sub(r"[  ]+", " ", s).strip()


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


def safe_stem(stem: str) -> str:
    """ชื่อไฟล์ที่ใช้ได้บน Windows"""
    return clean(re.sub(r'[<>:"/\\|?*]', "", stem)).rstrip(". ")
