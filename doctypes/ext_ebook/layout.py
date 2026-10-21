# -*- coding: utf-8 -*-
"""
ขยายเวลาส่งรูปเล่มอิเล็กทรอนิกส์: รูปแบบหน้ากระดาษ (Request -> Word HTML) ของทั้ง 2 ฉบับ

ค่าทั้งหมดวัดจากฉบับที่เจ้าหน้าที่จัด (tools/learn.py inspect + ตำแหน่งคำใน PDF, samples/ ต.ค. 2569)
ระยะ x ในหน่วย pt จากขอบซ้ายของพื้นที่พิมพ์; บรรทัดปกติ = single (TH Sarabun New 16pt -> 21.3pt)

A หนังสือแจ้งผล (หนังสือภายนอก)
  ขอบ บน 2.7 / ซ้าย 2.75 / ขวา 2.0 / ล่าง 0 ซม. — โลโก้ขาวดำ 69.8pt กึ่งกลางเหนือขอบบน (ในตัวอย่างเป็นรูปลอย)
  ที่อยู่ชิดขวา 3 บรรทัด, แท็บ เรื่อง/เรียน 34pt, ย่อหน้าแรก 1.25 ซม. ย่อหน้าถัดไป 2 ซม., กระจายแบบไทย
  ลายมือชื่อไม่มี "ขอแสดงความนับถือ" (ตามตัวอย่าง) แกนกึ่งกลาง ~72% ของบรรทัด, สำเนาเรียน 14pt แท็บ 2 ซม.
B บันทึกข้อความ
  ขอบ บน 2 / ซ้าย 3 / ขวา 2 / ล่าง 0.25 ซม. — โลโก้สีชิดซ้าย 75.95pt, "บันทึกข้อความ" 20pt หนา กึ่งกลาง
  ป้ายหัวบันทึกหนา + เส้นประใต้ค่าถึงตำแหน่งท้ายเส้นของแต่ละบรรทัด (HEAD_TABS), เว้นบรรทัด 8pt ระหว่างย่อหน้า
  ลายมือชื่อผู้เสนอ/ผู้อนุมัติ จัดกึ่งกลางบนแกนด้านซ้าย ระยะบรรทัด exactly 18pt
"""
from pathlib import Path

from core.text import NB
from core.wordhtml import esc, font_css, lines_html, text_width_pt, wrap_document

from .letter import APPROVE, CLOSING_A, CLOSING_B, SUBJECT_A, SUBJECT_B, Request

HERE = Path(__file__).resolve().parent
LOGO_BW = HERE / "assets" / "logo_mu_bw.png"     # โลโก้ขาวดำจากตัวอย่าง A (หนังสือภายนอก)
FAMILY = "TH Sarabun New"
F16, F14, F8, F20 = (font_css(FAMILY, s) for s in (16, 14, 8, 20))
# ตัวอย่าง A บีบตัวอักษรเป็นช่วง ๆ (-0.3pt): เนื้อความเฉลี่ย -0.2pt (ตัดบรรทัดตรงกับตัวอย่าง), เรียน/ลายมือชื่อ/สำเนาเรียน -0.3pt
CONDENSED = F16 + ";letter-spacing:-.2pt"
TIGHT, CC_FONT = F16 + ";letter-spacing:-.3pt", F14 + ";letter-spacing:-.3pt"
PAGE_W = 595.3
PAGE_MARGIN = "margin:72.0pt 72.0pt 0cm 72.0pt;"      # ค่าใน assets/word_head.html (แทนด้วยขอบของแต่ละฉบับ)
EXACT16 = "line-height:16.0pt;mso-line-height-rule:exactly;"
EXACT18 = "line-height:18.0pt;mso-line-height-rule:exactly;"
JUSTIFY = "text-align:justify;text-justify:inter-cluster;"
TAB = "<span style='mso-tab-count:1'>&nbsp;&nbsp;&nbsp; </span>"

# ---------- A ----------
A_MARGIN = dict(top=31.1, right=56.7, bottom=0.0, left=77.95)    # บน = ขอบบนของโลโก้ (ขอบกระดาษจริง 76.55pt)
A_WIDTH = PAGE_W - A_MARGIN["left"] - A_MARGIN["right"]
A_LOGO = 93                       # px = 69.8pt
A_ADDRESS_TOP = 6.9               # ระยะเหนือที่อยู่ (pt) ให้ baseline บรรทัดแรกอยู่ที่ 122.5pt จากขอบกระดาษ
A_LABEL_TAB = 34.0                # เรื่อง / เรียน -> ข้อความ
A_INDENT_FIRST = 35.4             # ย่อหน้า "ตามที่ ..." (1.25 ซม.)
A_INDENT = 56.7                   # ย่อหน้าถัดไปและ "จึงเรียนมา..." (2 ซม.)
A_SIGN_AXIS = 0.72                # แกนกึ่งกลางลายมือชื่อ (สัดส่วนของความกว้างบรรทัด)
A_GAP_BEFORE_SIGN = 4
A_CC_TAB = 56.7

# ---------- B ----------
B_MARGIN = dict(top=56.7, right=56.7, bottom=7.1, left=85.05)
B_WIDTH = PAGE_W - B_MARGIN["left"] - B_MARGIN["right"]
B_LOGO = 101                      # px = 75.95pt
B_LOGO_LEFT = 8.65
B_LOGO_ROW = 74.5                 # ความสูงแถวโลโก้ (pt) ให้หัวบันทึกเริ่มที่ขอบล่างโลโก้ตามตัวอย่าง
B_TITLE_TOP = 21.4                # ระยะเหนือ "บันทึกข้อความ" ในแถวโลโก้
B_HEAD_TABS = {"unit": (136.4, 430.6), "date": (73.4, 394.6), "subject": (60.3, 432.1)}   # (ต้นค่า, ท้ายเส้นประ)
B_INDENT = 56.7
B_PROPOSER_AXIS = 70.2            # แกนกึ่งกลางชื่อผู้เสนอ (pt จากขอบซ้าย)
B_APPROVE_AXIS = 102.5            # แกนกึ่งกลาง "อนุมัติ" + ผู้อนุมัติ


def para(content: str, style: str = "", align: str = "", font: str = F16) -> str:
    attr = f" align={align}" if align else ""
    if align:
        style = f"text-align:{align};" + style
    style_attr = f" style='{style.rstrip(';')}'" if style else ""
    return (f"<p class=MsoNormal{attr}{style_attr}><span lang=TH style='{font}'>"
            f"{content}<o:p></o:p></span></p>\n\n")


def blank(n: int = 1, style: str = "", font: str = F16) -> list:
    return [para("&nbsp;", style=style, font=font) for _ in range(n)]


def hanging(label: str, html_text: str, tab: float, font: str = F16, style: str = "") -> str:
    """'เรื่อง<tab>ข้อความ' — บรรทัดที่ล้น/ขึ้นบรรทัดใหม่เยื้องตรงแท็บ"""
    return para(esc(label) + TAB + html_text, font=font,
                style=f"margin-left:{tab:.1f}pt;text-indent:-{tab:.1f}pt;tab-stops:{tab:.1f}pt;" + style)


def body(text: str, indent: float, font: str = F16) -> str:
    return para(esc(text), style=f"text-indent:{indent:.1f}pt;{JUSTIFY}", font=font)


def block_at(lines: list, axis: float, width: float, style: str = "", font: str = F16) -> str:
    """บรรทัดจัดกึ่งกลางบนแกน axis (pt จากขอบซ้าย) — บรรทัดยาวสุดต้องไม่ล้นขอบ จึงเลื่อนแกนให้พอ
    (core.wordhtml.signature_block รองรับเฉพาะแกนครึ่งขวา; บันทึกข้อความมีแกนครึ่งซ้าย)"""
    half = (max(text_width_pt(x, FAMILY) for x in lines if x) + 2) / 2
    axis = min(max(axis, half), width - half)
    side = f"margin-left:{2 * axis - width:.1f}pt;" if axis > width / 2 else f"margin-right:{width - 2 * axis:.1f}pt;"
    return para("<br>\n".join(esc(x) if x else "&nbsp;" for x in lines), align="center", style=side + style, font=font)


def with_margins(html: str, m: dict) -> str:
    assert PAGE_MARGIN in html, "assets/word_head.html เปลี่ยนขอบกระดาษ — แก้ PAGE_MARGIN ใน layout.py"
    return html.replace(PAGE_MARGIN, f"margin:{m['top']}pt {m['right']}pt {m['bottom']}pt {m['left']}pt;", 1)


def logo_bw_src() -> str:
    """โลโก้ขาวดำ (หนังสือภายนอก) — Word อ่านจาก path เต็มแล้วฝังลงเอกสาร (assets/to_docx.ps1)"""
    return str(LOGO_BW)


# ---------- A: หนังสือแจ้งผล ----------
def build_a(r: Request, office: dict, signer: list, logo_src: str = None) -> str:
    out = [para(f'<img width={A_LOGO} height={A_LOGO} src="{logo_src or logo_bw_src()}">', align="center")]
    address = [x.replace("  ", NB + " ") for x in office["address"]]
    out.append(para(lines_html(address), align="right", style=f"margin-top:{A_ADDRESS_TOP}pt;"))
    out += blank(style=EXACT16)
    out.append(para("ที่" + "&nbsp;" * 3 + esc(office["ref"])))
    out.append(para("วันที่"))
    out.append(hanging("เรื่อง", esc(SUBJECT_A) + "<br>\n" + esc(f"ของ {r.student}"), A_LABEL_TAB))
    out += blank()
    out.append(hanging("เรียน", esc(r.to), A_LABEL_TAB, font=TIGHT, style="margin-top:1.0pt;"))   # ตัวอย่างเว้นเหนือ "เรียน" มากกว่าบรรทัดปกติ 1pt
    first, *rest = r.body_a()
    out += blank()
    out.append(body(first, A_INDENT_FIRST, CONDENSED))
    for p in rest:
        out += blank()
        out.append(body(p, A_INDENT, CONDENSED))
    out += blank()
    out.append(body(CLOSING_A, A_INDENT, CONDENSED))
    out += blank(A_GAP_BEFORE_SIGN)
    out.append(block_at(signer, A_WIDTH * A_SIGN_AXIS, A_WIDTH, font=TIGHT))
    out += blank(2)
    items = "<br>\n".join(esc(f"{n}. {x}") for n, x in enumerate(r.cc_a(), 1))
    out.append(hanging(NB + "สำเนาเรียน", items, A_CC_TAB, font=CC_FONT))
    return with_margins(wrap_document(out), A_MARGIN)


# ---------- B: บันทึกข้อความ ----------
def memo_head(logo_src: str) -> str:
    """โลโก้ชิดซ้าย + "บันทึกข้อความ" กึ่งกลางหน้า (ตารางไม่มีเส้น 3 ช่อง 25/50/25%)"""
    cell = "valign=top style='padding:0cm 0cm 0cm 0cm'"
    logo = para(f'<img width={B_LOGO} height={B_LOGO} src="{logo_src}">', style=f"margin-left:{B_LOGO_LEFT}pt;")
    title = para("<b>บันทึกข้อความ</b>", align="center", font=F20, style=f"margin-top:{B_TITLE_TOP}pt;")
    return ("<table class=MsoNormalTable border=0 cellspacing=0 cellpadding=0 width=\"100%\" "
            "style='width:100.0%;border-collapse:collapse;mso-padding-alt:0cm 0cm 0cm 0cm'>\n"
            f"<tr style='height:{B_LOGO_ROW}pt;mso-height-rule:exactly'>\n"
            f"<td width=\"25%\" {cell}>{logo}</td>\n<td width=\"50%\" {cell}>{title}</td>\n"
            f"<td width=\"25%\" {cell}>{para('&nbsp;')}</td>\n</tr>\n</table>\n\n")


def head_line(label: str, value: str, tabs: tuple) -> str:
    """ป้ายหนา + ค่าบนเส้นประ (เส้นประเริ่มหลังป้าย ไปจนถึงแท็บขวา)"""
    start, end = tabs
    dotted = f"<u style='text-underline:dotted'>{TAB}{esc(value)}{TAB}</u>"
    return para(f"<b>{esc(label)}</b>{dotted}", style=f"tab-stops:{start:.1f}pt right {end:.1f}pt;")


def build_b(r: Request, office: dict, signer: list, logo_src: str) -> str:
    out = [memo_head(logo_src)]
    out.append(head_line("ส่วนราชการ/ หน่วยงาน", office["memo_unit"], B_HEAD_TABS["unit"]))
    out.append(head_line("วันที่", r.memo_date, B_HEAD_TABS["date"]))
    out.append(head_line("เรื่อง", SUBJECT_B, B_HEAD_TABS["subject"]))
    out.append(para(f"<b>เรียน</b> {esc(office['memo_to'])}"))
    for p in r.body_b():
        out += blank(font=F8)
        out.append(body(p, B_INDENT))
    out += blank(font=F8)
    out.append(body(CLOSING_B, B_INDENT))
    out += blank(3)
    out += blank(style=EXACT18)
    out.append(block_at([f"({r.proposer})", r.proposer_title], B_PROPOSER_AXIS, B_WIDTH, EXACT18))
    out += blank(2, style=EXACT18)
    out.append(block_at([APPROVE, "", "", "", *signer], B_APPROVE_AXIS, B_WIDTH, EXACT18))
    return with_margins(wrap_document(out), B_MARGIN)
