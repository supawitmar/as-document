# -*- coding: utf-8 -*-
"""
ชิ้นส่วน Word HTML ที่ใช้ร่วมกันทุกประเภทเอกสาร

ทุกประเภทเอกสารสร้าง "Word HTML" (HTML แบบที่ Word บันทึกเอง) แล้วให้ Word แปลงเป็น .docx/.pdf (core.render)
ได้ผลตรงกับไฟล์ตัวอย่างที่เจ้าหน้าที่จัดใน Word มากที่สุด — รูปแบบเฉพาะของแต่ละเอกสาร (ระยะ/ตำแหน่ง)
อยู่ในโมดูล layout ของประเภทนั้น ส่วนนี้มีแค่ชิ้นส่วนกลาง
"""
import html
import os
import re
from pathlib import Path

from core import ASSETS
from core.text import NB

PAGE_HEAD = ASSETS / "word_head.html"   # <head> มาตรฐาน: A4, ขอบ 2.54 ซม. (ล่าง 0), สไตล์ MsoNormal
TEXT_WIDTH = 595.3 - 72 - 72            # ความกว้างพื้นที่พิมพ์ A4 (pt) ตามขอบใน word_head.html
FONT_FILES = {"TH Sarabun New": "THSarabunNew.ttf", "TH SarabunPSK": "THSarabun.ttf"}
THAI_MARKS = re.compile(r"[ัิ-ฺ็-๎]")   # สระบน/ล่าง วรรณยุกต์ ไม่กินที่ในบรรทัด


def font_css(family: str = "TH Sarabun New", size: float = 16) -> str:
    return f'font-size:{size:.1f}pt;font-family:"{family}",sans-serif;mso-fareast-font-family:"Times New Roman"'


def esc(s: str) -> str:
    return html.escape(s, quote=False).replace(NB, "&nbsp;")


def lines_html(lines: list) -> str:
    return "<br>\n".join(esc(x) for x in lines)


def paragraph(content: str, style: str = "", align: str = "", font: str = None, thai: bool = True) -> str:
    """ย่อหน้าแบบ Word (class=MsoNormal) — content เป็น HTML แล้ว (ใช้ esc()/lines_html() กับข้อความ)"""
    attr = f" align={align}" if align else ""
    if align:
        style = f"text-align:{align};" + style
    style_attr = f" style='{style.rstrip(';')}'" if style else ""
    lang = " lang=TH" if thai else ""
    return (f"<p class=MsoNormal{attr}{style_attr}><span{lang} style='{font or font_css()}'>"
            f"{content}<o:p></o:p></span></p>\n\n")


def label_table(rows: list, cell, label_width: int = 20, cellspacing: str = " cellspacing=3") -> str:
    """ตาราง 2 คอลัมน์ไม่มีเส้น "ป้าย : ค่า" — cell(content, align) คืน HTML ย่อหน้าในช่อง"""
    out = [f"<table class=MsoNormalTable border=0{cellspacing} cellpadding=0 width=\"100%\" "
           "style='width:100.0%;mso-cellspacing:1.5pt'>\n"]
    for label, value in rows:
        out.append(
            f" <tr>\n  <td width=\"{label_width}%\" valign=top style='width:{label_width}.0%;padding:.75pt .75pt .75pt .75pt'>\n  "
            + cell(esc(label) + " : ", "right").strip()
            + "\n  </td>\n  <td style='padding:.75pt .75pt .75pt .75pt'>\n  "
            + cell(esc(value), "").strip()
            + "\n  </td>\n </tr>\n")
    out.append("</table>\n\n")
    return "".join(out)


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


def signature_block(lines: list, family: str, thai: bool, center: float = 0.75, extra_style: str = "",
                    width: float = TEXT_WIDTH) -> str:
    """บล็อกคำลงท้าย + ชื่อ + ตำแหน่ง จัดกึ่งกลางทุกบรรทัดบนแกนเดียวกัน
    แกนอยู่ที่ center (สัดส่วนจากขอบซ้ายของพื้นที่พิมพ์) แต่ขยับซ้ายให้บรรทัดที่ยาวที่สุดไม่เกินขอบขวา
    วัดความยาวด้วยฟอนต์จริง ไม่ใช้การเติมช่องว่าง — บรรทัดว่าง ("") = ที่ลงนาม"""
    longest = max(text_width_pt(x, family) for x in lines if x) + 6
    axis = min(width * center, width - longest / 2)
    indent = max(0.0, 2 * axis - width)      # ย่อหน้าจัดกึ่งกลางที่เยื้องซ้าย indent -> กึ่งกลางอยู่ที่ axis
    style = f"margin-left:{indent:.1f}pt;text-align:center;" + extra_style
    body = "<br>\n".join(esc(x) if x else "&nbsp;" for x in lines)
    lang = " lang=TH" if thai else ""
    return (f"<p class=MsoNormal align=center style='{style}'><span{lang} style='{font_css(family)}'>"
            f"{body}<o:p></o:p></span></p>\n\n")


def wrap_document(paragraphs_html: list, head: Path = PAGE_HEAD) -> str:
    """ห่อย่อหน้าเป็นเอกสาร Word HTML ทั้งไฟล์ — ประเภทเอกสารที่ใช้กระดาษ/ขอบต่างไปส่ง head ของตัวเองได้"""
    return (Path(head).read_text(encoding="utf-8") + "\n<body lang=EN-US style='tab-interval:36.0pt;word-wrap:break-word'>\n\n"
            "<div class=WordSection1>\n\n" + "".join(paragraphs_html) + "</div>\n\n</body>\n\n</html>\n")
