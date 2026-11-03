# -*- coding: utf-8 -*-
"""ทดสอบประเภทเอกสาร late_fine (ยกเว้น/ลดหย่อนค่าปรับส่งรูปเล่มล่าช้า) — ไม่เรียก Word, ชื่อทั้งหมดเป็นชื่อสมมติ"""
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from doctypes.late_fine import DOCTYPE, form, layout, load_data  # noqa: E402
from doctypes.late_fine.letter import kinds, make_request, output_stems  # noqa: E402

VALUES = {
    "mode": "ลดหย่อน",
    "prog_ref": "บฑ. 999/2569", "prog_date": "2026-10-22",
    "prog_subject": "ขอลดหย่อนค่าปรับการส่ง Thesis Submission ล่าช้า",
    "student": "นางสาวสมหญิง รักเรียน", "student_id": "6512345", "program_code": "egch/m",
    "degree": "หลักสูตรวิศวกรรมศาสตรมหาบัณฑิต", "major": "สาขาวิชาวิศวกรรมเคมี", "program_type": "หลักสูตรนานาชาติ",
    "faculty": "วิศวกรรมศาสตร์", "to": "", "advisor": "ผศ.ดร.สมชาย ใจดี",
    "pass_date": "17 ก.พ. 2568", "submit_date": "2026-04-24", "late_days": "259",
    "fine": "92,600", "pay": "18520 บาท",
    "reason": "เนื่องจากนักศึกษาประสบปัญหาสุขภาพอย่างต่อเนื่อง",
    "memo_date": "2026-11-03", "proposer": "นายสมชาย ใจดี", "proposer_title": "นักวิชาการศึกษา",
}
WAIVE = {**VALUES, "mode": "ยกเว้น", "pay": ""}


class Check(unittest.TestCase):
    def test_ok(self):
        for v in (VALUES, WAIVE):
            self.assertEqual(form.check(v), ({}, []))

    def test_required_and_patterns(self):
        errors, _ = form.check({**VALUES, "mode": "", "student": "", "student_id": "65123",
                                "program_code": "EGCH", "pass_date": "พรุ่งนี้", "late_days": "สองวัน", "fine": "abc"})
        self.assertEqual(set(errors),
                         {"mode", "student", "student_id", "program_code", "pass_date", "late_days", "fine"})
        self.assertNotIn("program_type", form.check({**VALUES, "program_type": ""})[0])   # ไม่บังคับ
        self.assertIn("mode", form.check({**VALUES, "mode": "ยกเลิก"})[0])

    def test_pay_only_for_reduce(self):
        self.assertIn("pay", form.check({**VALUES, "pay": ""})[0])               # ลดหย่อนต้องมียอด
        self.assertIn("pay", form.check({**VALUES, "pay": "92,600"})[0])         # ต้องน้อยกว่าค่าปรับเต็ม
        self.assertIn("pay", form.check({**VALUES, "pay": "100,000"})[0])
        self.assertIn("pay", form.check({**VALUES, "pay": "0"})[0])              # 0 บาท = ยกเว้น
        self.assertNotIn("pay", form.check({**VALUES, "pay": "92,599.50"})[0])
        errors, warnings = form.check({**WAIVE, "pay": "18,520"})                # ยกเว้น: ไม่บังคับ แต่เตือนว่าไม่ใช้
        self.assertNotIn("pay", errors)
        self.assertTrue(any("ไม่ใช้ยอด" in w for w in warnings))

    def test_date_order(self):
        _, warnings = form.check({**VALUES, "submit_date": "2024-01-01"})
        self.assertTrue(any("ก่อนวันสอบผ่าน" in w for w in warnings))

    def test_prefix_warning(self):
        _, warnings = form.check({**VALUES, "student": "สมหญิง รักเรียน"})
        self.assertTrue(any("คำนำหน้า" in w for w in warnings))

    def test_today_default(self):
        self.assertEqual(form.defaults(dt.date(2026, 11, 3))["memo_date"], "2026-11-03")
        self.assertEqual(form.defaults()["mode"], "")                         # ต้องเลือกเอง ไม่มีค่าเริ่มต้น

    def test_check_form_names(self):
        r = DOCTYPE.check_form(VALUES)
        self.assertTrue(r["ok"])
        self.assertEqual([o["name"] for o in r["outputs_preview"]],                   # บันทึกข้อความมาก่อน
                         ["บันทึกขออนุมัติลดหย่อนค่าปรับ 6512345 EGCH-M นางสาวสมหญิง รักเรียน",
                          "ลดหย่อนค่าปรับ 6512345 EGCH-M นางสาวสมหญิง รักเรียน"])
        self.assertEqual(DOCTYPE.check_form(WAIVE)["outputs_preview"][1]["name"],
                         "ยกเว้นค่าปรับ 6512345 EGCH-M นางสาวสมหญิง รักเรียน")
        self.assertFalse(DOCTYPE.check_form({})["ok"])


class Text(unittest.TestCase):
    def setUp(self):
        self.r, self.w = make_request(VALUES), make_request(WAIVE)

    def test_normalized(self):
        r = self.r
        self.assertEqual(r.program_code, "EGCH/M")
        self.assertEqual(r.program, "วิศวกรรมศาสตรมหาบัณฑิต สาขาวิชาวิศวกรรมเคมี (หลักสูตรนานาชาติ)")
        self.assertEqual(r.faculty, "คณะวิศวกรรมศาสตร์")
        self.assertEqual(r.to, "คณบดีคณะวิศวกรรมศาสตร์")
        self.assertEqual(r.advisor, "ผู้ช่วยศาสตราจารย์ ดร. สมชาย ใจดี")
        self.assertEqual(r.proposer, "สมชาย ใจดี")
        self.assertEqual((r.prog_date, r.pass_date, r.submit_date, r.memo_date),
                         ("22 ตุลาคม 2569", "17 กุมภาพันธ์ 2568", "24 เมษายน 2569", "3 พฤศจิกายน 2569"))
        self.assertEqual((r.fine, r.pay, r.pay_text), ("92,600", "18,520", "หนึ่งหมื่นแปดพันห้าร้อยยี่สิบบาทถ้วน"))
        self.assertEqual((self.w.pay, self.w.pay_text), ("", ""))

    def test_money_and_days_formats(self):
        r = make_request({**VALUES, "fine": "145400", "pay": "30,000.50", "late_days": "1020 วัน"})
        self.assertEqual((r.fine, r.pay, r.late_days), ("145,400", "30,000.50", "1,020"))
        self.assertEqual(r.pay_text, "สามหมื่นบาทห้าสิบสตางค์")

    def test_student_line(self):
        line = self.r.student_line
        self.assertTrue(line.startswith("ตามที่ หลักสูตรฯ มีหนังสือที่ บฑ. 999/2569 ลงวันที่ 22 ตุลาคม 2569 เรื่อง "
                                        "ขอลดหย่อนค่าปรับการส่ง Thesis Submission ล่าช้าของ นางสาวสมหญิง รักเรียน "
                                        "รหัสประจำตัว 6512345 EGCH/M นักศึกษาหลักสูตรวิศวกรรมศาสตรมหาบัณฑิต"))
        self.assertNotIn("หลักสูตรหลักสูตร", line)                          # จุดผิดในตัวอย่างจริง
        self.assertIn("ซึ่งสอบวิทยานิพนธ์ “ผ่าน” ตั้งแต่วันที่ 17 กุมภาพันธ์ 2568 และได้ดำเนินการส่งไฟล์ E-thesis "
                      "เข้าสู่ระบบเมื่อวันที่ 24 เมษายน 2569 ทำให้มีค่าปรับในการส่งเล่มล่าช้า จำนวน 259 วัน "
                      "เป็นเงิน 92,600 บาท", line)

    def test_subject_of_program_letter(self):
        for s in ("เรื่อง ขอยกเว้นค่าปรับ", "ขอยกเว้นค่าปรับของ", "ขอยกเว้นค่าปรับของ นางสาวสมหญิง รักเรียน"):
            self.assertEqual(make_request({**VALUES, "prog_subject": s}).prog_subject, "ขอยกเว้นค่าปรับ", s)

    def test_memo(self):
        self.assertEqual(self.r.subject_memo, "เสนอพิจารณาขออนุมัติขอลดหย่อนค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้า")
        self.assertEqual(self.w.subject_memo, "เสนอพิจารณาขออนุมัติขอยกเว้นค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้า")
        first, ask = self.r.body_memo()
        self.assertTrue(first.endswith("เป็นเงิน 92,600 บาท เนื่องจากนักศึกษาประสบปัญหาสุขภาพอย่างต่อเนื่อง "
                                       "จึงทำให้นักศึกษาส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้าและทำให้มีค่าปรับในการส่งล่าช้า "
                                       "(รายละเอียดตามเอกสารแนบ)"))
        self.assertEqual(ask, "ทั้งนี้ หลักสูตรฯ ขอความอนุเคราะห์ลดหย่อนค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้า "
                              "โดยคงชำระทั้งหมดจำนวน 18,520 บาท (หนึ่งหมื่นแปดพันห้าร้อยยี่สิบบาทถ้วน)")
        self.assertEqual(self.w.body_memo()[1],             # ยกเว้น = ไม่ต้องชำระ จึงไม่มียอดเงิน (เจ้าของแก้)
                         "ทั้งนี้ หลักสูตรฯ ขอความอนุเคราะห์ยกเว้นค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้าทั้งหมด")

    def test_reason_tail_not_doubled(self):
        r = make_request({**VALUES, "reason": "ป่วย จึงทำให้มีค่าปรับในการส่งล่าช้า (รายละเอียดตามเอกสารแนบ)."})
        self.assertEqual(r.reason_text(), "เนื่องจากป่วย จึงทำให้มีค่าปรับในการส่งล่าช้า (รายละเอียดตามเอกสารแนบ)")

    def test_letter(self):
        self.assertEqual(self.r.subject_letter, "อนุมัติลดหย่อนค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้า")
        first, result = self.r.body_letter()
        self.assertTrue(first.endswith("เป็นเงิน 92,600 บาท ตามรายละเอียดที่แจ้งมาแล้วนั้น"))
        self.assertNotIn("เนื่องจาก", first)
        self.assertEqual(result, "บัณฑิตวิทยาลัยพิจารณาแล้ว เห็นสมควรอนุมัติลดหย่อนค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์"
                                 "ล่าช้า ตามที่หลักสูตรฯ เสนอมา โดยให้นักศึกษาชำระค่าปรับจำนวน 18,520 บาท "
                                 "(หนึ่งหมื่นแปดพันห้าร้อยยี่สิบบาทถ้วน)")
        self.assertEqual(self.w.body_letter()[1], "บัณฑิตวิทยาลัยพิจารณาแล้ว เห็นสมควรอนุมัติยกเว้นค่าปรับการส่ง"
                                                  "รูปเล่มอิเล็กทรอนิกส์ล่าช้า ตามที่หลักสูตรฯ เสนอมา")
        self.assertEqual(self.r.cc_letter(), [
            "ประธานหลักสูตรวิศวกรรมศาสตรมหาบัณฑิต สาขาวิชาวิศวกรรมเคมี (หลักสูตรนานาชาติ)",
            "ผู้ช่วยศาสตราจารย์ ดร. สมชาย ใจดี อาจารย์ที่ปรึกษาวิทยานิพนธ์หลัก"])

    def test_one_name_for_the_work(self):
        """คำเรียกตัวงาน = "รูปเล่มอิเล็กทรอนิกส์" ทุกที่ — ยกเว้นชื่อเรื่องของหนังสือหลักสูตรที่ยกมาอ้าง"""
        for r in (self.r, self.w):
            text = " ".join([r.subject_memo, r.subject_letter, *r.body_memo(), *r.body_letter()])
            text = text.replace(r.prog_subject, "")
            for bad in ("Thesis Submission", "ดิจิทัล", "ไฟล์รูปเล่มวิทยานิพนธ์"):
                self.assertNotIn(bad, text)

    def test_stems_safe(self):
        r = make_request({**VALUES, "student": 'นางสาวสมหญิง "รักเรียน"'})
        for s in output_stems(r):
            self.assertNotIn('"', s)
            self.assertNotIn("/", s)
        self.assertEqual(kinds(r), ("บันทึกข้อความขออนุมัติลดหย่อนค่าปรับ", "หนังสือแจ้งผลลดหย่อนค่าปรับ"))


class Html(unittest.TestCase):
    def test_build(self):
        office, signers = load_data()
        self.assertEqual(office["memo_to"], "รองคณบดีฝ่ายแผนและพัฒนาคุณภาพ")         # ไม่มี "ผ่านหัวหน้างาน"
        self.assertEqual(set(signers), {"letter", "memo_left", "memo_approver"})
        for values in (VALUES, WAIVE):
            r = make_request(values)
            memo = layout.build_memo(r, office, signers, "logo.jpg")
            letter = layout.build_letter(r, office, signers["letter"])
            for html in (memo, letter):
                self.assertNotIn(layout.PAGE_MARGIN, html)
                self.assertNotIn("E-thesis", html)                                     # ขีดไม่ตัดบรรทัด
                self.assertIn("E‑thesis", html)
                self.assertNotIn("หัวงาน", html)
            self.assertIn("margin:31.1pt 56.7pt 0.0pt 77.95pt", letter)
            self.assertIn("margin:56.7pt 56.7pt 0.0pt 85.05pt", memo)
            self.assertIn("คณบดีคณะวิศวกรรมศาสตร์", letter)
            self.assertIn("สำเนาเรียน", letter)
            self.assertIn(signers["letter"][2], letter)
            self.assertIn("text-underline:dotted", memo)
            self.assertIn("(สมชาย ใจดี)", memo)
            self.assertIn("ไม่อนุมัติ", memo)
            self.assertIn("เรียน คณบดีบัณฑิตวิทยาลัย", memo)
            for line in signers["memo_left"] + signers["memo_approver"]:
                self.assertIn(line, memo)
            self.assertNotIn("หัวหน้างาน", memo)
        self.assertTrue(layout.LOGO_BW.exists())


class Registry(unittest.TestCase):
    def test_discover(self):
        from core import registry
        dts = registry.discover()
        self.assertIn("late_fine", dts)
        self.assertNotIn("late_fine", registry.errors)
        m = dts["late_fine"].manifest()
        self.assertEqual(m["slots"], [])
        self.assertIn("prefill", m["form"])
        fields = [f for s in m["form"]["sections"] for f in s["fields"]]
        self.assertEqual(fields[0]["key"], "mode")                                    # ตัวเลือกบนสุด
        self.assertEqual(fields[0]["options"], ["ยกเว้น", "ลดหย่อน"])
        keys = {f["key"] for f in fields}
        # ช่องนักศึกษาชื่อเดียวกับที่ core.student_profile เติมให้
        self.assertTrue({"student", "student_id", "program_code", "degree", "major", "program_type", "faculty",
                         "pass_date", "advisor"} <= keys)
        self.assertEqual({f["key"] for f in fields if f.get("remember")}, {"proposer", "proposer_title"})
        self.assertTrue(DOCTYPE.prefill_form(Path("x.docx"))["error"])


if __name__ == "__main__":
    unittest.main()
