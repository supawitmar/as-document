# -*- coding: utf-8 -*-
"""บฑ.31: ระยะเยื้องบรรทัดต่อของ เรียน/Dear (ไทย 24.6pt / อังกฤษ 27.7pt) — ชื่อทั้งหมดเป็นชื่อสมมติ"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.wordhtml import text_width_pt  # noqa: E402
from doctypes.bt31.layout import build_html  # noqa: E402
from doctypes.bt31.letter import Letter  # noqa: E402

TH_TO = "เรียน  ผู้อำนวยการโรงเรียนแพทย์ตัวอย่าง สถาบันการแพทย์สมมติ คณะแพทยศาสตร์โรงพยาบาลตัวอย่าง มหาวิทยาลัยสมมติ"
EN_TO = "Dear Director of Example School of Medicine, Sample Medical Institute, Faculty of Medicine Example Hospital"


def to_paragraph(html: str, word: str) -> str:
    return next(p for p in re.findall(r"(?s)<p class=MsoNormal[^>]*>.*?</p>", html) if f">{word}" in p)


def hang(p: str) -> tuple:
    m = re.search(r"margin-left:([\d.]+)pt;text-indent:-([\d.]+)pt", p)
    return (float(m[1]), float(m[2])) if m else None


class ToLineIndent(unittest.TestCase):
    def test_thai_hangs_under_text_after_rian(self):
        p = to_paragraph(build_html(Letter(kind="approve", lang="th", header={"to": TH_TO}), "logo.jpg"), "เรียน")
        self.assertEqual(hang(p), (24.6, 24.6))
        self.assertIn(">เรียน ผู้อำนวยการ", p)            # ช่องว่างซ้ำถูกยุบ: ระยะคงที่ใช้ได้
        self.assertAlmostEqual(text_width_pt("เรียน ", "TH Sarabun New"), 24.6, delta=0.5)

    def test_english_keeps_sample_indent(self):
        p = to_paragraph(build_html(Letter(kind="approve", lang="en", header={"to": EN_TO}), "logo.jpg"), "Dear")
        self.assertEqual(hang(p), (27.7, 27.7))


if __name__ == "__main__":
    unittest.main()
