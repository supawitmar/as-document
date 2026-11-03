# -*- coding: utf-8 -*-
"""
ยกเว้น/ลดหย่อนค่าปรับส่งรูปเล่มล่าช้า: รูปแบบหน้ากระดาษ (Request -> Word HTML) ของทั้ง 2 ฉบับ

ค่าทั้งหมดวัดจากฉบับที่เจ้าหน้าที่จัด (tools/learn.py inspect + ตำแหน่งคำใน PDF, samples/ ต.ค. 2569)
ระยะ x ในหน่วย pt จากขอบซ้ายของพื้นที่พิมพ์; บรรทัดปกติ = single (TH Sarabun New 16pt -> 21.3pt)

บันทึกข้อความ (memo_reduce)
  ขอบ บน 2 / ซ้าย 3 / ขวา 2 / ล่าง 0 ซม. — โลโก้สีชิดซ้าย 75.95pt, "บันทึกข้อความ" 20pt หนา กึ่งกลาง
  ป้ายหัวบันทึกหนา + เส้นประใต้ค่าถึงตำแหน่งท้ายเส้นของแต่ละบรรทัด (MEMO_HEAD_TABS), "เรียน" ไม่หนา
  เนื้อความ exactly 18pt ไม่เว้นบรรทัดระหว่างย่อหน้า, ส่วนท้ายและลายมือชื่อ exactly 18pt:
  รองคณบดี (ซ้าย) คู่กับผู้เสนอ (ขวา) ในบรรทัดเดียวกันด้วยแท็บกึ่งกลาง, ช่องอนุมัติและคณบดีอยู่บนแกนซ้ายเดียวกัน
  (ตัวอย่างจัดด้วยการเคาะเว้นวรรค — แกนซ้ายเป็นค่ากลางของบรรทัดฝั่งซ้ายทั้งหมด คลาดจากตัวอย่างไม่เกิน ~5pt)
หนังสือแจ้งผล (letter_waive) — หนังสือภายนอกแบบเดียวกับ ext_ebook ฉบับ A
  ขอบ บน 2.7 / ซ้าย 2.75 / ขวา 2.0 / ล่าง 0 ซม. — โลโก้ขาวดำ 69.8pt กึ่งกลางเหนือขอบบน
  ที่อยู่ชิดขวา 3 บรรทัด, แท็บ เรื่อง/เรียน 34pt, ทุกย่อหน้าเยื้อง 2 ซม., กระจายแบบไทย
  ย่อหน้าผลการพิจารณา exactly 18pt (ตามตัวอย่าง), ลายมือชื่อแกนกึ่งกลาง ~69% ของบรรทัด, สำเนาเรียน 12pt แท็บ 2 ซม.
"""
import re
from pathlib import Path

from core.text import NB
from core.wordhtml import esc, font_css, lines_html, text_width_pt, wrap_document

from .letter import APPROVE_BOXES, CLOSING_LETTER, CLOSING_MEMO, FORWARD_MEMO, Request

HERE = Path(__file__).resolve().parent
LOGO_BW = HERE / "assets" / "logo_mu_bw.png"     # โลโก้ขาวดำจากตัวอย่างหนังสือแจ้งผล (หนังสือภายนอก)
FAMILY = "TH Sarabun New"
F16, F12, F20 = (font_css(FAMILY, s) for s in (16, 12, 20))
TIGHT = F16 + ";letter-spacing:-.3pt"            # ลายมือชื่อในหนังสือแจ้งผล (ตัวอย่างบีบ -0.3pt)
PAGE_W = 595.3
PAGE_MARGIN = "margin:72.0pt 72.0pt 0cm 72.0pt;"      # ค่าใน assets/word_head.html (แทนด้วยขอบของแต่ละฉบับ)
EXACT16 = "line-height:16.0pt;mso-line-height-rule:exactly;"
EXACT18 = "line-height:18.0pt;mso-line-height-rule:exactly;"
JUSTIFY = "text-align:justify;text-justify:inter-cluster;"
TAB = "<span style='mso-tab-count:1'>&nbsp;&nbsp;&nbsp; </span>"
INDENT = 56.7                     # ย่อหน้า 2 ซม. (ทั้ง 2 ฉบับ)
NB_HYPHEN = "‑"              # Word แปลงเป็นขีดไม่ตัดบรรทัด (nonbreaking hyphen) ตอนเปิด HTML

# ---------- หนังสือแจ้งผล ----------
L_MARGIN = dict(top=31.1, right=56.7, bottom=0.0, left=77.95)    # บน = ขอบบนของโลโก้ (ขอบกระดาษจริง 76.55pt)
L_WIDTH = PAGE_W - L_MARGIN["left"] - L_MARGIN["right"]
L_LOGO = 93                       # px = 69.8pt
L_ADDRESS_TOP = 6.9               # ระยะเหนือที่อยู่ (pt) ให้ baseline บรรทัดแรกอยู่ที่ 122.5pt จากขอบกระดาษ
L_LABEL_TAB = 34.0                # เรื่อง / เรียน -> ข้อความ
L_SIGN_AXIS = 316.8               # แกนกึ่งกลางลายมือชื่อ (pt จากขอบซ้าย) — ตัวอย่าง 394.7pt จากขอบกระดาษ
L_GAP_BEFORE_SIGN = 4
L_CC_TAB = 56.7

# ---------- บันทึกข้อความ ----------
M_MARGIN = dict(top=56.7, right=56.7, bottom=0.0, left=85.05)
M_WIDTH = PAGE_W - M_MARGIN["left"] - M_MARGIN["right"]
M_LOGO = 101                      # px = 75.95pt
M_LOGO_LEFT = 8.65
M_LOGO_ROW = 74.5                 # ความสูงแถวโลโก้ (pt)
M_TITLE_TOP = 21.4                # ระยะเหนือ "บันทึกข้อความ" ในแถวโลโก้
M_HEAD_TOP = 13.4                # ระยะเหนือหัวบันทึก ให้ baseline "ส่วนราชการ" อยู่ที่ 158.5pt ตามตัวอย่าง
M_HEAD_TABS = {"unit": (136.4, 358.6), "date": (52.6, 322.5), "subject": (33.9, 351.0)}   # (ต้นค่า, ท้ายเส้นประ)
M_TO_GAP = NB * 2                 # "เรียน  รองคณบดี…" เคาะ 2 ครั้ง
M_FORWARD_INDENT = 25.4           # "- เพื่อโปรดพิจารณา"
M_LEFT_AXIS = 98.0               # แกนฝั่งซ้าย: รองคณบดี / ช่องอนุมัติ / คณบดี (ตัวอย่าง ≈ 183–189pt จากขอบกระดาษ)
M_RIGHT_AXIS = 356.6              # แกนผู้เสนอ (ตัวอย่าง 441.7pt จากขอบกระดาษ)
M_BOX_GAP = NB * 16               # ระหว่าง "[ ] อนุมัติ" กับ "[ ] ไม่อนุมัติ"
M_DEAN_STYLE = EXACT18 + "margin-top:2.0pt;"   # ตัวอย่างใช้สไตล์ Heading 3 (เว้นก่อนย่อหน้า 2pt) กับส่วนคณบดี


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


def body(text: str, style: str = "") -> str:
    """ย่อหน้าเนื้อความ — ขีดในคำภาษาอังกฤษ (E-thesis) เป็นขีดไม่ตัดบรรทัด: Word เคยตัดเป็น "E-" / "thesis" """
    text = re.sub(r"(?<=[A-Za-z])-(?=[A-Za-z])", NB_HYPHEN, text)
    return para(esc(text), style=f"text-indent:{INDENT:.1f}pt;{JUSTIFY}" + style)


def block_at(lines: list, axis: float, width: float, style: str = "", font: str = F16) -> str:
    """บรรทัดจัดกึ่งกลางบนแกน axis (pt จากขอบซ้าย) — บรรทัดยาวสุดต้องไม่ล้นขอบ จึงเลื่อนแกนให้พอ"""
    half = (max(text_width_pt(x, FAMILY) for x in lines if x) + 2) / 2
    axis = min(max(axis, half), width - half)
    side = f"margin-left:{2 * axis - width:.1f}pt;" if axis > width / 2 else f"margin-right:{width - 2 * axis:.1f}pt;"
    return para("<br>\n".join(esc(x) if x else "&nbsp;" for x in lines), align="center", style=side + style, font=font)


def columns(cells: list, axes: tuple, style: str = "") -> str:
    """บรรทัดเดียวที่มีข้อความหลายช่อง แต่ละช่องกึ่งกลางบนแกนของตัวเอง (แท็บกึ่งกลาง) — ช่องว่าง "" = ข้าม
    ข้อความที่กว้างเกินครึ่งหนึ่งของระยะถึงแกนแรก Word เริ่มที่ขอบซ้าย (ไม่ล้นออกนอกพื้นที่พิมพ์)"""
    stops = " ".join(f"center {a:.1f}pt" for a in axes)
    return para("".join(TAB + esc(c) for c in cells), style=f"tab-stops:{stops};" + style)


def with_margins(html: str, m: dict) -> str:
    assert PAGE_MARGIN in html, "assets/word_head.html เปลี่ยนขอบกระดาษ — แก้ PAGE_MARGIN ใน layout.py"
    return html.replace(PAGE_MARGIN, f"margin:{m['top']}pt {m['right']}pt {m['bottom']}pt {m['left']}pt;", 1)


# ---------- หนังสือแจ้งผล ----------
def build_letter(r: Request, office: dict, signer: list, logo_src: str = None) -> str:
    out = [para(f'<img width={L_LOGO} height={L_LOGO} src="{logo_src or str(LOGO_BW)}">', align="center")]
    address = [x.replace("  ", NB + " ") for x in office["address"]]
    out.append(para(lines_html(address), align="right", style=f"margin-top:{L_ADDRESS_TOP}pt;"))
    out += blank(style=EXACT16)
    out.append(para("ที่" + "&nbsp;" * 3 + esc(office["ref"])))
    out.append(para("วันที่"))
    out.append(hanging("เรื่อง", esc(r.subject_letter), L_LABEL_TAB))
    out += blank()
    out.append(hanging("เรียน", esc(r.to), L_LABEL_TAB))
    first, result = r.body_letter()
    out += blank()
    out.append(body(first))
    out += blank()
    out.append(body(result, EXACT18))
    out += blank()
    out.append(body(CLOSING_LETTER))
    out += blank(L_GAP_BEFORE_SIGN)
    out.append(block_at(signer, L_SIGN_AXIS, L_WIDTH, font=TIGHT))
    out += blank(3)
    # สำเนาเรียน: ย่อหน้าละรายการ 12pt — ตัวอย่างเคาะเว้นวรรค 1 ครั้งหน้า "สำเนาเรียน" (เว้นวรรค 16pt แบบ
    # no-break ทำให้บรรทัดสูงขึ้น ~3pt จึงใช้ขนาด 12pt ตามข้อความ)
    cc = f"margin-left:{L_CC_TAB:.1f}pt;text-indent:-{L_CC_TAB:.1f}pt;tab-stops:{L_CC_TAB:.1f}pt;"
    for n, x in enumerate(r.cc_letter(), 1):
        label = "&nbsp;สำเนาเรียน" if n == 1 else ""
        out.append(para(f"{label}{TAB}{esc(f'{n}. {x}')}", font=F12, style=cc))
    return with_margins(wrap_document(out), L_MARGIN)


# ---------- บันทึกข้อความ ----------
def memo_head(logo_src: str) -> str:
    """โลโก้ชิดซ้าย + "บันทึกข้อความ" กึ่งกลางหน้า (ตารางไม่มีเส้น 3 ช่อง 25/50/25%)"""
    cell = "valign=top style='padding:0cm 0cm 0cm 0cm'"
    logo = para(f'<img width={M_LOGO} height={M_LOGO} src="{logo_src}">', style=f"margin-left:{M_LOGO_LEFT}pt;")
    title = para("<b>บันทึกข้อความ</b>", align="center", font=F20, style=f"margin-top:{M_TITLE_TOP}pt;")
    return ("<table class=MsoNormalTable border=0 cellspacing=0 cellpadding=0 width=\"100%\" "
            "style='width:100.0%;border-collapse:collapse;mso-padding-alt:0cm 0cm 0cm 0cm'>\n"
            f"<tr style='height:{M_LOGO_ROW}pt;mso-height-rule:exactly'>\n"
            f"<td width=\"25%\" {cell}>{logo}</td>\n<td width=\"50%\" {cell}>{title}</td>\n"
            f"<td width=\"25%\" {cell}>{para('&nbsp;')}</td>\n</tr>\n</table>\n\n")


def head_line(label: str, value: str, tabs: tuple, style: str = "") -> str:
    """ป้ายหนา + ค่าบนเส้นประ (เส้นประเริ่มหลังป้าย ไปจนถึงแท็บขวา)"""
    start, end = tabs
    dotted = f"<u style='text-underline:dotted'>{TAB}{esc(value)}{TAB}</u>"
    return para(f"<b>{esc(label)}</b>{dotted}", style=f"tab-stops:{start:.1f}pt right {end:.1f}pt;" + style)


def build_memo(r: Request, office: dict, signers: dict, logo_src: str) -> str:
    out = [memo_head(logo_src)]
    out.append(head_line("ส่วนราชการ/ หน่วยงาน", office["memo_unit"], M_HEAD_TABS["unit"],
                         f"margin-top:{M_HEAD_TOP}pt;"))
    out.append(head_line("วันที่", r.memo_date, M_HEAD_TABS["date"]))
    out.append(head_line("เรื่อง", r.subject_memo, M_HEAD_TABS["subject"]))
    out += blank(style=EXACT18)
    out.append(para(f"เรียน{M_TO_GAP}{esc(office['memo_to'])}", style=EXACT18))
    out += blank(style=EXACT18)
    out += [body(p, EXACT18) for p in r.body_memo()]
    out += blank(style=EXACT18)
    out.append(body(CLOSING_MEMO, EXACT18))      # ตัวอย่างบรรทัดนี้เป็น TH SarabunPSK (เตี้ยกว่า) = ระยะเท่า exactly 18pt
    out.append(para(esc(FORWARD_MEMO[0]), style=EXACT18))
    out.append(para(esc(FORWARD_MEMO[1]), style=f"margin-left:{M_FORWARD_INDENT}pt;" + EXACT18))
    out += blank(3, style=EXACT18)
    left, right = signers["memo_left"], [f"({r.proposer})", r.proposer_title]
    axes = (M_LEFT_AXIS, M_RIGHT_AXIS)
    for n in range(max(len(left), len(right))):
        out.append(columns([left[n] if n < len(left) else "", right[n] if n < len(right) else ""], axes, EXACT18))
    out += blank(2, style=EXACT18)
    approve, reject = (f"[{NB * 3}]{NB * 2}{x}" for x in APPROVE_BOXES)
    out.append(columns([approve + M_BOX_GAP + reject], axes[:1], EXACT18))
    out += blank(3, style=M_DEAN_STYLE)
    out += [columns([x], axes[:1], M_DEAN_STYLE) for x in signers["memo_approver"]]
    return with_margins(wrap_document(out), M_MARGIN)
