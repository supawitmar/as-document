# -*- coding: utf-8 -*-
"""
แกนกลาง (hub) ของระบบปรับเอกสาร — ส่วนที่ใช้ร่วมกันทุกประเภทเอกสาร

    core.text      อ่านไฟล์/ตัดบรรทัด/ทำความสะอาดข้อความ
    core.wordhtml  ชิ้นส่วน Word HTML (ย่อหน้า, บล็อกลายมือชื่อ, ห่อเอกสาร)
    core.render    แปลง Word HTML -> .docx / .pdf ผ่าน Microsoft Word
    core.store     ไฟล์ข้อมูล JSON ของแต่ละประเภทเอกสาร (ย้ายจากที่เก็บเดิมให้อัตโนมัติ)
    core.doctype   คลาสฐาน DocType — สัญญาที่ประเภทเอกสารทุกตัวต้องทำตาม
    core.registry  ค้นหาประเภทเอกสารทั้งหมดในโฟลเดอร์ doctypes/
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ASSETS = BASE / "assets"
DOCTYPES_DIR = BASE / "doctypes"
