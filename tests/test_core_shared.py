# -*- coding: utf-8 -*-
"""ทดสอบส่วนกลางที่ประเภทเอกสารแบบฟอร์มใช้ร่วมกัน (core.thaidate, core.student_profile) — ชื่อทั้งหมดเป็นชื่อสมมติ"""
import datetime as dt
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import student_profile as sp  # noqa: E402
from core.thaidate import baht_text, money, parse_date, parse_money, thai_date  # noqa: E402


class ThaiDateMoney(unittest.TestCase):
    def test_dates(self):
        d = dt.date(2026, 5, 11)
        for s in ("2026-05-11", "2569-05-11", "11 พฤษภาคม 2569", "11 พ.ค. 69", "11/5/2569", d):
            self.assertEqual(parse_date(s), d, s)
        self.assertIsNone(parse_date("31 กุมภาพันธ์ 2569"))
        self.assertEqual(thai_date(d), "11 พฤษภาคม 2569")

    def test_baht_text(self):
        cases = {18520: "หนึ่งหมื่นแปดพันห้าร้อยยี่สิบบาทถ้วน", 30000: "สามหมื่นบาทถ้วน",   # ตามตัวอย่างหนังสือจริง
                 145400: "หนึ่งแสนสี่หมื่นห้าพันสี่ร้อยบาทถ้วน", 11: "สิบเอ็ดบาทถ้วน", 21: "ยี่สิบเอ็ดบาทถ้วน",
                 101: "หนึ่งร้อยเอ็ดบาทถ้วน", 1: "หนึ่งบาทถ้วน", 0: "ศูนย์บาทถ้วน",
                 1000001: "หนึ่งล้านเอ็ดบาทถ้วน", 20000000: "ยี่สิบล้านบาทถ้วน",
                 Decimal("21.50"): "ยี่สิบเอ็ดบาทห้าสิบสตางค์", Decimal("0.25"): "ยี่สิบห้าสตางค์"}
        for amount, words in cases.items():
            self.assertEqual(baht_text(amount), words, amount)

    def test_money(self):
        self.assertEqual(parse_money("18,520 บาท"), Decimal("18520"))
        self.assertEqual(parse_money(" 92600 "), Decimal("92600"))
        for bad in ("", "abc", "-5", "1.234"):
            self.assertIsNone(parse_money(bad), bad)
        self.assertEqual((money(145400), money(Decimal("21.5"))), ("145,400", "21.50"))


class StudentProfile(unittest.TestCase):
    ROWS = ["Student Profile",
            "รหัสนักศึกษา : 6512345 EGCH/M   สถานภาพ : กำลังศึกษา",
            "ชื่อ - นามสกุล : น.ส. สมหญิง รักเรียน",
            "หลักสูตร (TH) : วิศวกรรมศาสตรมหาบัณฑิต สาขาวิชาวิศวกรรมเคมี (หลักสูตรนานาชาติ)",
            "คณะ : คณะวิศวกรรมศาสตร์",
            "วันที่สอบวิทยานิพนธ์ ผ่าน : 11 พ.ค. 2569",
            "อาจารย์ที่ปรึกษาหลัก : ผศ.ดร.สมชาย ใจดี"]

    def test_parse(self):
        self.assertTrue(sp.is_profile(self.ROWS))
        self.assertEqual(sp.parse(self.ROWS), {
            "student_id": "6512345", "program_code": "EGCH/M", "student": "นางสาวสมหญิง รักเรียน",
            "degree": "วิศวกรรมศาสตรมหาบัณฑิต", "major": "วิศวกรรมเคมี", "program_type": "หลักสูตรนานาชาติ",
            "faculty": "คณะวิศวกรรมศาสตร์", "pass_date": "2026-05-11",
            "advisor": "ผู้ช่วยศาสตราจารย์ ดร. สมชาย ใจดี"})

    def test_names(self):
        self.assertEqual(sp.faculty_name("วิศวกรรมศาสตร์"), "คณะวิศวกรรมศาสตร์")
        self.assertEqual(sp.head_of("สถาบันโภชนาการ"), "ผู้อำนวยการสถาบันโภชนาการ")
        self.assertEqual(sp.head_of("สังคมศาสตร์และมนุษยศาสตร์"), "คณบดีคณะสังคมศาสตร์และมนุษยศาสตร์")
        self.assertEqual(sp.head_of(""), "")
        self.assertEqual(sp.prefill(Path("x.docx"))["error"], "รองรับเฉพาะไฟล์ PDF หน้า Student Profile")


if __name__ == "__main__":
    unittest.main()
