# -*- coding: utf-8 -*-
"""ทดสอบทางเข้าแบบฟอร์มของ hub (ui["form"]) ด้วยประเภทเอกสารจำลอง — ไม่เปิด Word ไม่แตะ settings.json จริง"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app  # noqa: E402
from core import registry  # noqa: E402
from core.doctype import DocType  # noqa: E402


class FakeForm(DocType):
    id = "zz_form_test"
    name = "ฟอร์มทดสอบ"
    ui = {"form": {"title": "ทดสอบ", "prefill": {"label": "เติมจากไฟล์", "accept": [".pdf"]},
                   "sections": [{"title": "ข้อมูล", "fields": [
                       {"key": "name", "label": "ชื่อ", "type": "text", "required": True},
                       {"key": "when", "label": "วันที่", "type": "date", "default": "today"},
                       {"key": "staff", "label": "ผู้เสนอ", "type": "text", "remember": True}]}]}}

    def __init__(self):
        self.calls = []

    def check_form(self, values):
        r = super().check_form(values)
        r["outputs_preview"] = [{"name": f"เอกสาร {values.get('name', '')}"}] if values.get("name") else []
        return r

    def convert_form(self, values, options, pdf, outdir, log=print):
        self.calls.append(pdf)
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        out = {"kind": "ทดสอบ", "label": "", "docx": None, "pdf": None, "doc": None}
        for ext in (["docx", "pdf"] if pdf == "both" else ["pdf"] if pdf else ["docx"]):
            f = outdir / f"เอกสาร {values['name']}.{ext}"
            f.write_text("x", encoding="utf-8")
            out[ext] = f
        return {"ok": True, "error": "", "notes": [], "outputs": [out]}

    def prefill_form(self, path):
        return {"values": {"name": "สมชาย ใจดี"}, "notes": ["เติมจากไฟล์ทดสอบ"], "error": ""}


class HubFormTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hubform_"))
        registry.discover()
        self.dt = FakeForm()
        registry._doctypes[self.dt.id] = self.dt
        self.patches = [mock.patch.object(app, "SETTINGS_FILE", self.tmp / "settings.json"),
                        mock.patch.object(app, "DOWNLOADS", self.tmp / "Downloads"),
                        mock.patch.object(app, "PREVIEWS", self.tmp / "preview")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        registry._doctypes.pop(self.dt.id, None)
        app.preview_cache.pop(f"form:{self.dt.id}", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def settings(self, **kw):
        s = app.load_settings()
        s.update(kw)
        return s

    def test_manifest_has_form_and_empty_slots(self):
        m = self.dt.manifest()
        self.assertEqual((m["slots"], m["modes"], m["accept"]), ([], [], []))
        self.assertEqual(m["form"]["title"], "ทดสอบ")

    def test_check_reports_missing_required(self):
        r = app.form_check(self.dt.id, {"name": ""})
        self.assertFalse(r["ok"])
        self.assertIn("name", r["errors"])
        r = app.form_check(self.dt.id, {"name": "สมชาย ใจดี"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["outputs_preview"][0]["name"], "เอกสาร สมชาย ใจดี")

    def test_convert_refuses_incomplete_form(self):
        r = app.form_convert(self.dt.id, {"name": ""}, self.settings())
        self.assertFalse(r["ok"])
        self.assertIn("ชื่อ", r["error"])
        self.assertEqual(self.dt.calls, [])

    def test_convert_saves_to_downloads_and_remembers(self):
        r = app.form_convert(self.dt.id, {"name": "สมชาย ใจดี", "staff": "นายสมชาย ใจดี"}, self.settings(format="pdf"))
        self.assertTrue(r["ok"], r)
        self.assertEqual(Path(r["outputs"][0]["pdf"]).parent, self.tmp / "Downloads")
        self.assertEqual(self.dt.calls, [True])
        self.assertEqual(app.load_settings()["form_memory"][self.dt.id], {"staff": "นายสมชาย ใจดี"})

    def test_preview_is_reused_when_nothing_changed(self):
        values = {"name": "สมชาย ใจดี"}
        with mock.patch.object(app, "preview_pages", return_value={"ok": True}):
            app.form_preview(self.dt.id, values, {})
        self.assertEqual(self.dt.calls, ["both"])
        r = app.form_convert(self.dt.id, values, self.settings(format="both"))
        self.assertTrue(r["ok"])
        self.assertEqual(self.dt.calls, ["both"])                         # ไม่สร้างซ้ำ — คัดลอกจากตัวอย่าง
        self.assertTrue(r["outputs"][0]["docx"] and r["outputs"][0]["pdf"])
        app.form_convert(self.dt.id, {"name": "สมหญิง รักเรียน"}, self.settings(format="docx"))
        self.assertEqual(self.dt.calls, ["both", False])                  # ข้อมูลเปลี่ยน = สร้างใหม่

    def test_prefill_returns_values(self):
        r = app.form_prefill(self.dt.id, self.tmp / "x.pdf")
        self.assertEqual(r["values"], {"name": "สมชาย ใจดี"})

    def test_slot_doctypes_unchanged(self):
        for d in registry.all_doctypes():
            if d.id in ("bt31", "bgks39"):
                self.assertIsNone(d.manifest().get("form"))
                self.assertTrue(d.manifest()["slots"])


if __name__ == "__main__":
    unittest.main()
