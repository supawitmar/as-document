# -*- coding: utf-8 -*-
"""ทดสอบประเภทเอกสาร ext_ebook (ขยายเวลาส่งรูปเล่มอิเล็กทรอนิกส์) — ไม่เรียก Word, ชื่อทั้งหมดเป็นชื่อสมมติ"""
import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from doctypes.ext_ebook import DOCTYPE, form, layout, load_data, profile  # noqa: E402
from doctypes.ext_ebook.letter import make_request, output_stems  # noqa: E402

VALUES = {
    "prog_ref": "อว78.102/999", "prog_date": "2026-08-28",
    "student": "นางสาวสมหญิง รักเรียน", "student_id": "6512345", "program_code": "egch/m",
    "degree": "วิศวกรรมศาสตรมหาบัณฑิต", "major": "สาขาวิชาวิศวกรรมเคมี", "program_type": "หลักสูตรนานาชาติ",
    "faculty": "คณะวิศวกรรมศาสตร์", "to": "", "advisor": "ผศ.ดร.สมชาย ใจดี",
    "pass_date": "11 พ.ค. 2569", "old_deadline": "2026-08-29", "new_deadline": "28 กันยายน 2569",
    "reason": "เนื่องจากคอมพิวเตอร์ของนักศึกษาเสีย",
    "memo_date": "2026-09-01", "proposer": "สมชาย ใจดี", "proposer_title": "นักวิชาการศึกษา",
}


class ThaiDate(unittest.TestCase):
    def test_parse(self):
        d = dt.date(2026, 5, 11)
        for s in ("2026-05-11", "2569-05-11", "11 พฤษภาคม 2569", "11 พ.ค. 2569", "11 พ.ค. 69", "11/5/2569",
                  "11 พค 2569"):
            self.assertEqual(form.parse_date(s), d, s)
        for s in ("", "abc", "31 กุมภาพันธ์ 2569", "2026-13-01"):
            self.assertIsNone(form.parse_date(s), s)

    def test_format(self):
        self.assertEqual(form.thai_date(dt.date(2026, 9, 1)), "1 กันยายน 2569")

    def test_today_default(self):
        self.assertEqual(form.defaults(dt.date(2026, 10, 21))["memo_date"], "2026-10-21")
        self.assertEqual(form.defaults()["proposer_title"], "นักวิชาการศึกษา")


class Check(unittest.TestCase):
    def test_ok(self):
        errors, warnings = form.check(VALUES)
        self.assertEqual(errors, {})
        self.assertEqual(warnings, [])

    def test_required_and_patterns(self):
        errors, _ = form.check({**VALUES, "student": "", "student_id": "65123", "program_code": "EGCH",
                                "prog_ref": "78.102/1", "pass_date": "พรุ่งนี้"})
        self.assertEqual(set(errors), {"student", "student_id", "program_code", "prog_ref", "pass_date"})
        self.assertNotIn("program_type", form.check({**VALUES, "program_type": ""})[0])   # ไม่บังคับ

    def test_date_order(self):
        _, warnings = form.check({**VALUES, "new_deadline": "2026-08-01"})
        self.assertTrue(any("ขยายถึง" in w for w in warnings))

    def test_prefix_warning(self):
        _, warnings = form.check({**VALUES, "student": "สมหญิง รักเรียน"})
        self.assertTrue(any("คำนำหน้า" in w for w in warnings))

    def test_check_form_preview_names(self):
        r = DOCTYPE.check_form(VALUES)
        self.assertTrue(r["ok"])
        self.assertEqual([o["name"] for o in r["outputs_preview"]],
                         ["ขยายส่งเล่ม 6512345 EGCHM นางสาวสมหญิง รักเรียน",
                          "บันทึกขออนุมัติขยายส่งเล่ม 6512345 EGCHM นางสาวสมหญิง รักเรียน"])
        self.assertFalse(DOCTYPE.check_form({})["ok"])


class Text(unittest.TestCase):
    def setUp(self):
        self.r = make_request(VALUES)

    def test_normalized(self):
        r = self.r
        self.assertEqual(r.prog_ref, "อว 78.102/999")
        self.assertEqual(r.program_code, "EGCH/M")
        self.assertEqual(r.major, "วิศวกรรมเคมี")
        self.assertEqual(r.advisor, "ผู้ช่วยศาสตราจารย์ ดร. สมชาย ใจดี")
        self.assertEqual(r.to, "คณบดีคณะวิศวกรรมศาสตร์")
        self.assertEqual(r.program, "วิศวกรรมศาสตรมหาบัณฑิต สาขาวิชาวิศวกรรมเคมี (หลักสูตรนานาชาติ)")
        self.assertEqual((r.pass_date, r.new_deadline, r.memo_date),
                         ("11 พฤษภาคม 2569", "28 กันยายน 2569", "1 กันยายน 2569"))

    def test_head_of_unit(self):
        self.assertEqual(make_request({**VALUES, "faculty": "สถาบันวิจัยตัวอย่าง"}).to, "ผู้อำนวยการสถาบันวิจัยตัวอย่าง")
        self.assertEqual(make_request({**VALUES, "faculty": "วิทยาศาสตร์"}).to, "คณบดีคณะวิทยาศาสตร์")
        self.assertEqual(make_request({**VALUES, "to": "คณบดีคณะทดสอบ"}).to, "คณบดีคณะทดสอบ")

    def test_no_program_type(self):
        self.assertTrue(make_request({**VALUES, "program_type": ""}).program.endswith("สาขาวิชาวิศวกรรมเคมี"))

    def test_same_dates_everywhere(self):
        """ตัวอย่างจริงเคยพิมพ์วันคงสภาพผลสอบใน B ไม่ตรงกับย่อหน้าแรก — ต้องมาจากช่องเดียว"""
        a, b = self.r.body_a(), self.r.body_b()
        for p in a + b:
            self.assertNotIn("7 กรกฎาคม", p)
        self.assertEqual(sum(p.count("11 พฤษภาคม 2569") for p in a), 2)
        self.assertEqual(sum(p.count("11 พฤษภาคม 2569") for p in b), 2)
        self.assertEqual(sum(p.count("28 กันยายน 2569") for p in b), 2)

    def test_fine_always_in_a(self):
        self.assertIn("นักศึกษาต้องชำระค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้า", self.r.body_a()[1])
        self.assertNotIn("ค่าปรับ", " ".join(self.r.body_b()))

    def test_reason(self):
        t = self.r.reason_text()
        self.assertEqual(t, "เนื่องจากคอมพิวเตอร์ของนักศึกษาเสีย ทำให้ไม่สามารถดำเนินการจัดทำรูปเล่มอิเล็กทรอนิกส์"
                            "ได้ทันในระยะเวลาที่กำหนด ภายในวันที่ 29 สิงหาคม 2569")
        self.assertTrue(self.r.body_b()[0].endswith(t))

    def test_proposer_without_prefix(self):
        for name in ("นายสมชาย ใจดี", "(สมชาย ใจดี)", "น.ส. สมชาย ใจดี"):
            self.assertEqual(make_request({**VALUES, "proposer": name}).proposer, "สมชาย ใจดี")

    def test_cc(self):
        self.assertEqual(self.r.cc_a(), [
            "ประธานหลักสูตรวิศวกรรมศาสตรมหาบัณฑิต สาขาวิชาวิศวกรรมเคมี (หลักสูตรนานาชาติ)",
            "ผู้ช่วยศาสตราจารย์ ดร. สมชาย ใจดี อาจารย์ที่ปรึกษาวิทยานิพนธ์หลัก",
            "นางสาวสมหญิง รักเรียน"])

    def test_stems_safe(self):
        a, b = output_stems(make_request({**VALUES, "student": 'นางสาวสมหญิง "รักเรียน"'}))
        self.assertNotIn('"', a + b)
        self.assertNotIn("/", a + b)


class Html(unittest.TestCase):
    def test_build(self):
        r, (office, signer) = make_request(VALUES), load_data()
        self.assertEqual(len(signer), 3)
        a = layout.build_a(r, office, signer, "logo.png")
        b = layout.build_b(r, office, signer, "logo.jpg")
        for html in (a, b):
            self.assertNotIn(layout.PAGE_MARGIN, html)
            self.assertIn(signer[0].replace("(", "("), html)
        self.assertIn("margin:31.1pt 56.7pt 0.0pt 77.95pt", a)
        self.assertIn("คณบดีคณะวิศวกรรมศาสตร์", a)
        self.assertIn("สำเนาเรียน", a)
        self.assertIn("text-underline:dotted", b)
        self.assertIn("(สมชาย ใจดี)", b)
        self.assertIn("อนุมัติ", b)
        self.assertTrue(layout.LOGO_BW.exists())


class Profile(unittest.TestCase):
    ROWS = ["Student Profile",
            "รหัสนักศึกษา :6512345 EGCH/M   สถานภาพ :กำลังศึกษา",
            "ชื่อ - นามสกุล :น.ส. สมหญิง รักเรียน",
            "ระดับปริญญา :ปริญญาโท",
            "หลักสูตร(TH) :วิศวกรรมศาสตรมหาบัณฑิต สาขาวิชาวิศวกรรมเคมี (หลักสูตรนานาชาติ)",
            "คณะ :คณะวิศวกรรมศาสตร์",
            "อาจารย์ที่ปรึกษาโครงร่าง :ผศ.ดร.สมชาย ใจดี",
            "อาจารย์ที่ปรึกษาหลัก :ผู้ช่วยศาสตราจารย์ ดร. สมชาย ใจดี",
            "วันที่สอบวิทยานิพนธ์ ผ่าน :11 พฤษภาคม 2569"]

    def test_parse(self):
        self.assertTrue(profile.is_profile(self.ROWS))
        self.assertEqual(profile.parse(self.ROWS), {
            "student_id": "6512345", "program_code": "EGCH/M", "student": "นางสาวสมหญิง รักเรียน",
            "degree": "วิศวกรรมศาสตรมหาบัณฑิต", "major": "วิศวกรรมเคมี", "program_type": "หลักสูตรนานาชาติ",
            "faculty": "คณะวิศวกรรมศาสตร์", "pass_date": "2026-05-11",
            "advisor": "ผู้ช่วยศาสตราจารย์ ดร. สมชาย ใจดี"})

    def test_prefix(self):
        self.assertEqual(profile.full_name("นาย สมชาย ใจดี"), "นายสมชาย ใจดี")
        self.assertEqual(profile.full_name("นาง สมหญิง รักเรียน"), "นางสมหญิง รักเรียน")
        self.assertEqual(profile.full_name("นางสาว สมหญิง รักเรียน"), "นางสาวสมหญิง รักเรียน")

    def test_missing_fields_untouched(self):
        v = profile.parse(["รหัสนักศึกษา :6512345", "หลักสูตร(TH) :พยาบาลศาสตรมหาบัณฑิต"])
        self.assertEqual(v, {"student_id": "6512345", "degree": "พยาบาลศาสตรมหาบัณฑิต"})

    def test_not_profile(self):
        self.assertFalse(profile.is_profile(["บันทึกข้อความ", "เรื่อง ทดสอบ"]))
        self.assertTrue(DOCTYPE.prefill_form(Path("x.docx"))["error"])

    def test_pdf_roundtrip(self):
        font = next((p for p in (Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "THSarabunNew.ttf",
                                 Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts/THSarabunNew.ttf")
                     if p.exists()), None)
        if not font:
            self.skipTest("ไม่มีฟอนต์ TH Sarabun New")
        import pymupdf
        with tempfile.TemporaryDirectory() as t:
            pdf = Path(t) / "profile.pdf"
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_font(fontname="sarabun", fontfile=str(font))
            for n, row in enumerate(self.ROWS):
                label, _, value = row.partition(":")
                page.insert_text((40, 60 + n * 20), label + (":" if value else ""), fontname="sarabun", fontsize=12)
                if value:
                    page.insert_text((200, 60 + n * 20), value.split("   ")[0], fontname="sarabun", fontsize=12)
            doc.save(str(pdf))
            doc.close()
            r = DOCTYPE.prefill_form(pdf)
        self.assertEqual(r["error"], "")
        self.assertEqual(r["values"]["student"], "นางสาวสมหญิง รักเรียน")
        self.assertEqual(r["values"]["pass_date"], "2026-05-11")
        self.assertEqual(r["values"]["program_code"], "EGCH/M")


class Registry(unittest.TestCase):
    def test_discover(self):
        from core import registry
        dts = registry.discover()
        self.assertIn("ext_ebook", dts)
        self.assertNotIn("ext_ebook", registry.errors)
        m = dts["ext_ebook"].manifest()
        self.assertEqual(m["slots"], [])
        self.assertIn("prefill", m["form"])
        keys = {f["key"] for s in m["form"]["sections"] for f in s["fields"]}
        self.assertTrue({"prog_ref", "student", "pass_date", "reason", "proposer"} <= keys)


if __name__ == "__main__":
    unittest.main()
