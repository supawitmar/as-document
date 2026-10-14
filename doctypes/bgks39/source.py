# -*- coding: utf-8 -*-
"""
บฑกศ.39: อ่านไฟล์ .docx ที่ระบบสร้าง — "(บฑกศ.39 หนังสือเชิญ) <นักศึกษา>.docx" / "(บฑกศ.39 หนังสือขออนุมัติ) <นักศึกษา>.docx"

ลักษณะไฟล์ดิบ (จากไฟล์ตัวอย่างใน samples/, ต.ค. 2569):
  - ไฟล์เดียวมีหลายฉบับต่อกัน (หนังสือเชิญ 1 ฉบับต่อผู้ทำหน้าที่ 1 คน) โดยไม่มีตัวแบ่งหน้า
  - แต่ละฉบับขึ้นต้นด้วยที่อยู่ชิดขวา 4 บรรทัด แล้ว "ที่ อว 78.02 /", "วันที่", "เรื่อง", "เรียน"
  - ย่อหน้าใหม่ = มีย่อหน้าว่างคั่น หรือขึ้นต้นด้วยช่องว่าง/แท็บ (บางฉบับระบบตัดย่อหน้าเดียวเป็น 2 ย่อหน้า Word)
  - ลายมือชื่อ = ย่อหน้าจัดกึ่งกลางที่ขึ้นต้นด้วย "(" ต่อด้วยตำแหน่ง, ท้ายฉบับเป็น "หมายเหตุ:" และข้อมูลติดต่อ
"""
import html
import re
import zipfile
from pathlib import Path

from core.text import clean

REF = re.compile(r"^ที่\s")
SIGN_OFF = "ขอแสดงความนับถือ"
NOTE_HEAD = re.compile(r"^หมายเหตุ\s*:?")


def read_paragraphs(path: Path) -> list:
    """[(ข้อความดิบ (มี \\t), การจัดแนว)] ของทุกย่อหน้าใน word/document.xml"""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    out = []
    for m in re.finditer(r"<w:p[ >].*?</w:p>|<w:p/>", xml, re.S):
        p = m.group(0)
        jc = re.search(r'<w:jc w:val="(\w+)"', p)
        text = ""
        for r in re.finditer(r"<w:t(?: [^>]*)?>(.*?)</w:t>|<w:tab/>|<w:br/>", p):
            text += html.unescape(r.group(1)) if r.group(1) is not None else "\t"
        out.append((text, jc.group(1) if jc else ""))
    return out


def split_letters(paras: list) -> list:
    """แบ่งย่อหน้าทั้งไฟล์เป็นรายฉบับ: ฉบับเริ่มที่ที่อยู่ชิดขวาก่อนบรรทัด "ที่ ..." """
    starts = []
    for i, (t, _) in enumerate(paras):
        if REF.match(clean(t)):
            s = i
            while s > 0 and (not clean(paras[s - 1][0]) or paras[s - 1][1] == "right"):
                s -= 1
            while s < i and not clean(paras[s][0]):       # ข้ามย่อหน้าว่างหัวฉบับ
                s += 1
            starts.append(s)
    return [paras[a:b] for a, b in zip(starts, starts[1:] + [len(paras)])]


def label_value(text: str, label: str) -> str:
    return clean(re.sub(rf"^\s*{label}", "", text.replace("\t", " ")))


def parse_letter(paras: list) -> dict:
    """ย่อหน้าดิบของหนึ่งฉบับ -> ส่วนต่าง ๆ (ข้อความยังไม่ปรับ)"""
    d = {"address": [], "ref": "", "date": "", "subject": "", "to": "", "body": [], "closing": "",
         "sign_off": False, "signature": [], "notes": []}
    i, n = 0, len(paras)
    while i < n and not REF.match(clean(paras[i][0])):
        if clean(paras[i][0]):
            d["address"].append(clean(paras[i][0]))
        i += 1
    # ส่วนหัว: ที่ / วันที่ / เรื่อง / เรียน
    while i < n:
        t = clean(paras[i][0].replace("\t", " "))
        if REF.match(t):
            d["ref"] = t
        elif t.startswith("วันที่"):
            d["date"] = label_value(paras[i][0], "วันที่")
        elif t.startswith("เรื่อง"):
            d["subject"] = label_value(paras[i][0], "เรื่อง")
        elif t.startswith("เรียน"):
            d["to"] = label_value(paras[i][0], "เรียน")
            i += 1
            break
        i += 1
    # เนื้อความจนถึงลายมือชื่อ
    paras_out, cur = [], ""
    while i < n:
        raw, jc = paras[i]
        t = clean(raw.replace("\t", " "))
        if t == SIGN_OFF:
            d["sign_off"] = True
        elif t.startswith("(") and jc == "center":
            break
        elif not t:
            if cur:
                paras_out.append(cur)
            cur = ""
        elif cur and not raw[:1].isspace():
            cur += " " + t                                 # ย่อหน้าที่ระบบตัดกลางประโยค
        else:
            if cur:
                paras_out.append(cur)
            cur = t
        i += 1
    if cur:
        paras_out.append(cur)
    if paras_out and re.search(r"ขอขอบพระคุณ|จึงเรียนมา|จักขอบพระคุณ", paras_out[-1]):
        d["closing"] = paras_out.pop()
    d["body"] = paras_out
    # ลายมือชื่อ: ย่อหน้ากึ่งกลางต่อเนื่อง
    while i < n and clean(paras[i][0]) and paras[i][1] == "center":
        d["signature"].append(clean(paras[i][0]))
        i += 1
    # หมายเหตุ / ข้อมูลติดต่อ: ทุกย่อหน้าที่เหลือ
    d["notes"] = [clean(t.replace("\t", " ")) for t, _ in paras[i:] if clean(t)]
    return d


def read_letters(path: Path) -> list:
    return [parse_letter(p) for p in split_letters(read_paragraphs(path))]
