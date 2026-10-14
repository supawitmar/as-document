# -*- coding: utf-8 -*-
"""
บฑกศ.39: รูปแบบหน้ากระดาษ (Letter -> Word HTML)

ค่าทั้งหมดวัดจากไฟล์ที่ระบบสร้าง (tools/learn.py inspect, ไฟล์ตัวอย่างใน samples/ ต.ค. 2569)
ยังไม่มีฉบับที่เจ้าหน้าที่จัดแล้วมาเทียบ — ถ้าได้มา ให้วัดใหม่แล้วแก้ค่าในไฟล์นี้ (ดู doctypes/README.md)

  กระดาษ A4 ขอบซ้าย/ขวา 2.5 ซม. (1418 twips), โลโก้กึ่งกลาง 2.5 ซม. คู่กับที่อยู่ชิดขวา 4 บรรทัด
  TH Sarabun New 16pt ระยะบรรทัด 18pt, แท็บป้าย ที่/วันที่/เรื่อง/เรียน 2 ซม. (1134 twips)
  ลายมือชื่อจัดกึ่งกลางหน้า, หมายเหตุท้ายหนังสือชิดซ้าย
  ไฟล์หนึ่งมีหลายฉบับ: ทุกฉบับขึ้นหน้าใหม่ (ไฟล์ดิบไม่มีตัวแบ่งหน้า ฉบับที่ 2 เป็นต้นไปจึงเริ่มกลางหน้า)

หนังสือเชิญกับหนังสือขออนุมัติจัดต่างกัน (PROFILES) ตามไฟล์ดิบของแต่ละแบบ
"""
from core.text import NB
from core.wordhtml import esc, font_css, lines_html, signature_block, wrap_document

from .letter import Letter

FONT = font_css("TH Sarabun New", 16)
LH = "line-height:18.0pt;mso-line-height-rule:exactly;"
TAB = "tab-stops:2.0cm;"
TAB_SPAN = "<span style='mso-tab-count:1'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; </span>"
DAY_BLANK = "&nbsp;" * 10                 # ที่ว่างให้ลงวันที่ ระหว่าง "วันที่" กับเดือน
JUSTIFY = "text-align:justify;text-justify:inter-cluster;"
PAGE_MARGIN = ("margin:72.0pt 72.0pt 0cm 72.0pt;",          # ค่าใน assets/word_head.html
               "margin:1.25cm 2.5cm 0.5cm 2.5cm;")           # ไฟล์ดิบ: บน (หัวกระดาษ) 1.25, ซ้าย/ขวา 2.5, ล่าง 0.5 ซม.
LOGO = (95, 93)                           # px (= 2.51 x 2.46 ซม. ตามโลโก้ในหัวกระดาษไฟล์ดิบ)
SIGN_CENTER = 0.5                         # แกนลายมือชื่อ (สัดส่วนจากขอบซ้ายพื้นที่พิมพ์) — ไฟล์ดิบจัดกึ่งกลาง

PROFILES = {
    # body_indent        ย่อหน้าบรรทัดแรกของเนื้อความ
    # gap_before_closing บรรทัดว่างก่อนย่อหน้าท้าย ("ขอขอบพระคุณ..." / "จึงเรียนมา...")
    # sign_off           มี "ขอแสดงความนับถือ" (บรรทัดว่างก่อน, บรรทัดว่างหลังสำหรับลงนาม)
    # gap_before_sign    บรรทัดว่างระหว่างย่อหน้าท้ายกับชื่อผู้ลงนาม (กรณีไม่มีคำลงท้าย)
    # gap_before_notes   บรรทัดว่างก่อน "หมายเหตุ:"
    "invite": dict(body_indent="2.0cm", gap_before_closing=1, sign_off=False, gap_before_sign=3, gap_before_notes=3),
    "approve": dict(body_indent="3.0cm", gap_before_closing=0, sign_off=True, gap_before_sign=3, gap_before_notes=2),
}


def para(content: str, style: str = "", align: str = "", line_height=True) -> str:
    attr = f" align={align}" if align else ""
    if align:
        style = f"text-align:{align};" + style
    return (f"<p class=MsoNormal{attr} style='{style}{LH if line_height else ''}{TAB}'><span lang=TH style='{FONT}'>"
            f"{content}<o:p></o:p></span></p>\n\n")


def blank(n: int = 1) -> list:
    return [para("&nbsp;") for _ in range(n)]


def labeled(label: str, value: str) -> str:
    """'เรื่อง<tab>ข้อความ' — บรรทัดที่ล้นเยื้องตรงแท็บ"""
    return para(esc(label) + TAB_SPAN + value, style="margin-left:2.0cm;text-indent:-2.0cm;")


def page_break() -> str:
    return ("<p class=MsoNormal style='page-break-before:always;line-height:1.0pt;mso-line-height-rule:exactly'>"
            "<span style='font-size:1.0pt'>&nbsp;</span></p>\n\n")


def head_block(L: Letter, logo_src: str) -> str:
    """โลโก้กึ่งกลางหน้า + ที่อยู่ชิดขวาในแถวเดียวกัน (ตารางไม่มีเส้น 3 ช่อง 35/30/35%)"""
    cell = "valign=top style='padding:0cm 0cm 0cm 0cm'"
    w, h = LOGO
    return ("<table class=MsoNormalTable border=0 cellspacing=0 cellpadding=0 width=\"100%\" "
            "style='width:100.0%;border-collapse:collapse;mso-padding-alt:0cm 0cm 0cm 0cm'>\n<tr>\n"
            f"<td width=\"35%\" {cell}>{para('&nbsp;')}</td>\n"
            f"<td width=\"30%\" {cell}>{para(f'<img width={w} height={h} src=\"{logo_src}\">', align='center', line_height=False)}</td>\n"
            f"<td width=\"35%\" {cell}>{para(lines_html(L.address), align='right')}</td>\n"
            "</tr>\n</table>\n\n")


def letter_html(L: Letter, logo_src: str) -> list:
    prof = PROFILES[L.kind]
    out = [head_block(L, logo_src)]
    out += blank()
    out.append(para(esc(L.ref)))
    out.append(para("วันที่" + TAB_SPAN + DAY_BLANK + esc(L.date.replace(NB, " "))))
    out.append(labeled("เรื่อง", esc(L.subject)))
    out += blank()
    out.append(labeled("เรียน", esc(L.to)))
    for p in L.body:
        out += blank()
        out.append(para(esc(p), style=f"text-indent:{prof['body_indent']};{JUSTIFY}"))
    if L.closing:
        out += blank(prof["gap_before_closing"])
        if not prof["gap_before_closing"]:
            out[-1] = out[-1].replace("style='", "style='margin-bottom:10.0pt;", 1)   # ระยะหลังย่อหน้าตามไฟล์ดิบ
        out.append(para(esc(L.closing), style="text-indent:2.0cm;"))
    if prof["sign_off"]:
        out += blank(2)
        lines = ["ขอแสดงความนับถือ"] + [""] * prof["gap_before_sign"] + L.signature
    else:
        out += blank(prof["gap_before_sign"])
        lines = L.signature
    if lines:
        out.append(signature_block(lines, "TH Sarabun New", thai=True, center=SIGN_CENTER, extra_style=LH + TAB))
    if L.notes:
        out += blank(prof["gap_before_notes"])
        out += [para(esc(x), style=JUSTIFY) for x in L.notes]
    return out


def build_html(letters: list, logo_src: str) -> str:
    out = []
    for n, L in enumerate(letters):
        if n:
            out.append(page_break())
        out += letter_html(L, logo_src)
    html = wrap_document(out)
    assert PAGE_MARGIN[0] in html, "assets/word_head.html เปลี่ยนขอบกระดาษ — แก้ PAGE_MARGIN ใน layout.py"
    return html.replace(PAGE_MARGIN[0], PAGE_MARGIN[1], 1)
