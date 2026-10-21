# -*- coding: utf-8 -*-
"""สร้างเอกสารจากไฟล์ค่าฟอร์ม (JSON) — ใช้ทดสอบ/เทียบกับตัวอย่าง ระหว่างที่หน้าโปรแกรมยังไม่มีฟอร์ม

    python -m doctypes.ext_ebook <ค่า.json> [-o โฟลเดอร์] [--format docx|pdf|both] [--html]

<ค่า.json> = {"prog_ref": "อว 78.102/1033", "prog_date": "2026-08-28", "student": "นางสาวสมหญิง รักเรียน", ...}
(คีย์ตาม form.FORM) · --html บันทึก Word HTML ไว้ดูด้วย ไม่เรียก Word
"""
import argparse
import json
import sys
from pathlib import Path

from core import render

from . import DOCTYPE, layout, load_data
from .letter import make_request, output_stems


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="สร้างหนังสือขยายเวลาส่งรูปเล่มอิเล็กทรอนิกส์ (A + B) จากค่าฟอร์ม")
    ap.add_argument("values")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("--format", choices=("docx", "pdf", "both"), default="both")
    ap.add_argument("--html", action="store_true")
    args = ap.parse_args(argv)
    values = json.loads(Path(args.values).read_text(encoding="utf-8"))
    chk = DOCTYPE.check_form(values)
    for w in chk["warnings"]:
        print("คำเตือน:", w)
    if not chk["ok"]:
        for k, msg in chk["errors"].items():
            print(f"!! {k}: {msg}")
        return 1
    out = Path(args.outdir)
    if args.html:
        r, (office, signer) = make_request(values), load_data()
        a, b = output_stems(r)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{a}.htm").write_text(layout.build_a(r, office, signer), encoding="utf-8")
        (out / f"{b}.htm").write_text(layout.build_b(r, office, signer, render.LOGO_FILE.as_uri()),
                                      encoding="utf-8")
        return 0
    fmt = {"docx": False, "pdf": True, "both": "both"}[args.format]
    res = DOCTYPE.convert_form(values, {}, fmt, out, log=print)
    if res["error"]:
        print("!!", res["error"])
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
