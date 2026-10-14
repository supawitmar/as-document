# -*- coding: utf-8 -*-
"""
บฑ.31: รูปแบบหน้ากระดาษของหนังสือ (Letter -> Word HTML) — "format" ที่เรียนรู้จากไฟล์ตัวอย่างที่เจ้าหน้าที่จัดแล้ว

ทุกค่าในไฟล์นี้มาจากการเทียบไฟล์ Export ดิบกับไฟล์ที่เจ้าหน้าที่แก้แล้ว — ถ้ารูปแบบที่ต้องการเปลี่ยน
ให้ขอไฟล์ตัวอย่างใหม่ แล้วเทียบด้วย tools/learn.py (ดู doctypes/README.md)
"""
from core import render
from core.text import clean
from core.wordhtml import esc, font_css, label_table, lines_html, signature_block, wrap_document

from .letter import Letter, kind_name

# ---------- รูปแบบตามไฟล์ตัวอย่าง ----------
FONT = font_css("TH Sarabun New", 16)
LH = "line-height:18.0pt;mso-line-height-rule:exactly;"
TAB = "tab-stops:2.0cm"
INDENT = ("<span style='mso-spacerun:yes'> </span>"
          "<span style='mso-tab-count:1'>               </span>")
SIGN_CENTER = 0.75     # แกนกลางของบล็อกลายมือชื่อ (สัดส่วนจากขอบซ้ายของพื้นที่พิมพ์) ตามไฟล์ตัวอย่าง

DOC_TYPES = {
    # ย่อหน้าว่างหลังคำลงท้าย, ย่อหน้าว่างท้ายเอกสาร, ระยะห่างตัวอักษรของย่อหน้าแรกหลังตาราง
    # (หนังสือภาษาไทยไม่พิมพ์ข้อมูลติดต่ออาจารย์ผู้รับผิดชอบวิชาท้ายหนังสือ — เจ้าหน้าที่ตัดออก 14 ต.ค. 2569)
    "approve": dict(blank_after_closing=True, tail_blank=True, first_closing_spacing=""),
    "invite": dict(blank_after_closing=False, tail_blank=False, first_closing_spacing=".3pt"),
    "generic": dict(blank_after_closing=False, tail_blank=False, first_closing_spacing=""),
}

# หนังสือภาษาอังกฤษ (ตามไฟล์ตัวอย่าง (EN)): บรรทัดว่างก่อนย่อหน้าท้าย, เยื้องด้วย tab หรือ &nbsp;,
# ย่อหน้าว่างท้ายเอกสาร (ระยะ margin-bottom)
EN_TYPES = {
    "approve": dict(closing_breaks=2, closing_indent="nbsp", tail=(12, 14)),
    "invite": dict(closing_breaks=1, closing_indent="tab", tail=(12,)),
    "generic": dict(closing_breaks=1, closing_indent="tab", tail=(12,)),
}


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
           para_en(lines_html([x for x in (h.get("ref"), h.get("date"), h.get("subject")) if x]))]
    if h.get("to"):
        out.append(para_en("<br>\n" + esc(h["to"])))
    for p in L.body:
        out.append(para_en("<br>\n" + indent13 + esc(p), justify=True))

    if L.rows:
        out.append(label_table(L.rows, lambda c, a: para_en(c, align=a), cellspacing=""))

    if L.closing:
        indent = INDENT if prof["closing_indent"] == "tab" else indent13
        content = "<br>\n" * prof["closing_breaks"] + "<br>\n<br>\n".join(indent + esc(p) for p in L.closing)
        out.append(para_en(content, justify=True, margin_bottom=12,
                           tab_stop="42.55pt" if prof["closing_indent"] == "tab" else ""))

    if L.signature:
        # ฟอนต์ TH SarabunPSK และบรรทัดว่าง 3 บรรทัดสำหรับลงนาม ตามไฟล์ตัวอย่าง (EN)
        first, *others = [clean(x) for x in L.signature]
        out.append(signature_block([first, "", "", ""] + others, "TH SarabunPSK", thai=False, center=SIGN_CENTER))
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
        out.append(label_table(L.rows, lambda c, a: para(c, align=a)))

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
        out.append(signature_block([first, "", "", ""] + others, "TH Sarabun New", thai=True,
                                   center=SIGN_CENTER, extra_style=LH + TAB))
    if prof["tail_blank"]:
        out.append(para("&nbsp;", align="right"))
    return wrap_document(out)


def render_letters(entries: list, pdf=False, keep_doc=False, log=print, fmt=None) -> list:
    """สร้างไฟล์จาก Letter ที่จัดรูปแบบแล้ว
    entries: [{'src': Path, 'letter': Letter, 'outdir': Path, 'stem': str, 'notes': [...]}]"""
    jobs = [dict(src=e["src"], outdir=e["outdir"], stem=e["stem"], notes=e["notes"], kind=kind_name(e["letter"]),
                 attach=e.get("attach") or [], build=lambda logo, L=e["letter"]: build_html(L, logo)) for e in entries]
    return render.render(jobs, pdf=pdf, keep_doc=keep_doc, log=log, fmt=fmt)
