# -*- coding: utf-8 -*-
"""
วันที่ไทยและจำนวนเงิน — ใช้ร่วมกันทุกประเภทเอกสารที่กรอกฟอร์ม (ย้ายจาก doctypes/ext_ebook/form.py 3 พ.ย. 2569)

    parse_date("11 พ.ค. 69") -> date(2026, 5, 11)      thai_date(date) -> "11 พฤษภาคม 2569"
    parse_money("18,520")    -> Decimal("18520")       money(18520)    -> "18,520"
    baht_text(18520)         -> "หนึ่งหมื่นแปดพันห้าร้อยยี่สิบบาทถ้วน"
"""
import datetime as dt
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from core.text import clean

MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
          "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
MONTHS_SHORT = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
DIGITS = ["ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
PLACES = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]


def parse_date(s) -> "dt.date | None":
    """ค่าวันที่จากฟอร์ม -> date (ปี ค.ศ.)
    รับ ISO "2026-05-11" (ปี > 2400 ถือเป็น พ.ศ.), "11 พฤษภาคม 2569", "11 พ.ค. 69", "11/5/2569" — อ่านไม่ได้ = None"""
    if isinstance(s, dt.date):
        return s
    s = clean(str(s or ""))
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
    else:
        m = re.fullmatch(r"(\d{1,2})\s*(?:[/.\-]\s*(\d{1,2})\s*[/.\-]|\s+([ก-๙.\s]+?)\s*)\s*(\d{2,4})", s)
        if not m:
            return None
        d, y = int(m[1]), int(m[4])
        if m[2]:
            mo = int(m[2])
        else:
            name = m[3].replace(" ", "")
            mo = next((i + 1 for i, (full, short) in enumerate(zip(MONTHS, MONTHS_SHORT))
                       if name in (full, short, short.replace(".", ""))), 0)
        if y < 100:
            y += 2500                      # "69" = พ.ศ. 2569
    if y > 2400:
        y -= 543
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def thai_date(d: dt.date) -> str:
    """11 พฤษภาคม 2569"""
    return f"{d.day} {MONTHS[d.month - 1]} {d.year + 543}"


def parse_money(s) -> "Decimal | None":
    """"18,520" / "18520.50" / "18,520 บาท" -> Decimal — อ่านไม่ได้หรือติดลบ = None"""
    s = re.sub(r"[,\s]|บาท$", "", clean(str(s or "")))
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", s):
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def money(amount) -> str:
    """18520 -> "18,520" · 18520.5 -> "18,520.50" (ทศนิยมแสดงเมื่อมีสตางค์)"""
    a = Decimal(str(amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return f"{a:,.2f}" if a % 1 else f"{int(a):,}"


def _read_int(n: int, after: bool = False) -> str:
    """อ่านจำนวนเต็มเป็นคำไทย (ล้านซ้อนได้) — 0 = "" · after = มีหลักล้านนำหน้า (1 ตัวท้ายอ่าน "เอ็ด")"""
    if n >= 1_000_000:
        return _read_int(n // 1_000_000, after) + "ล้าน" + _read_int(n % 1_000_000, True)
    out = ""
    s = str(n)
    for i, ch in enumerate(s):
        d, place = int(ch), len(s) - i - 1
        if d == 0:
            continue
        if place == 1 and d == 1:
            word = ""                       # สิบ
        elif place == 1 and d == 2:
            word = "ยี่"
        elif place == 0 and d == 1 and (len(s) > 1 or after):
            word = "เอ็ด"
        else:
            word = DIGITS[d]
        out += word + PLACES[place]
    return out


def baht_text(amount) -> str:
    """18520 -> "หนึ่งหมื่นแปดพันห้าร้อยยี่สิบบาทถ้วน" · 21.50 -> "ยี่สิบเอ็ดบาทห้าสิบสตางค์" · 0 -> "ศูนย์บาทถ้วน" """
    a = Decimal(str(amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    baht, satang = int(a), int((a - int(a)) * 100)
    words = (_read_int(baht) or ("" if satang else DIGITS[0])) + ("บาท" if baht or not satang else "")
    return words + (_read_int(satang) + "สตางค์" if satang else "ถ้วน")
