# -*- coding: utf-8 -*-
"""
ประเภทเอกสาร: ขอขยายเวลาการส่งรูปเล่มอิเล็กทรอนิกส์และคงสภาพผลสอบ

ไม่มีไฟล์ต้นฉบับ — ผู้ใช้กรอกข้อมูลครั้งเดียวในฟอร์ม (ui["form"]) แล้วได้ 2 ฉบับเสมอ:
    A หนังสือแจ้งผล บัณฑิตวิทยาลัย -> คณบดีคณะ + สำเนาเรียน (ประธานหลักสูตร, อาจารย์ที่ปรึกษาหลัก, นักศึกษา)
    B บันทึกข้อความ งานบริการการศึกษา -> รองคณบดีฝ่ายแผนฯ เพื่อขออนุมัติ (มีเหตุผล + ช่องอนุมัติ)

    form.py     ช่องกรอก + ตรวจค่า + วันที่ไทย
    profile.py  เติมฟอร์มจาก PDF หน้า Student Profile (ระบบฐานข้อมูลนักศึกษา)
    letter.py   แบบจำลองคำขอ + ข้อความของทั้ง 2 ฉบับ + ชื่อไฟล์
    layout.py   รูปแบบหน้ากระดาษ A / B ตามตัวอย่างที่เจ้าหน้าที่จัด
    data/       signers.json (ผู้ลงนาม A = ผู้อนุมัติ B), office.json (ที่อยู่, เลขที่หนังสือ, ส่วนราชการ, เรียน ของ B)
    assets/     โลโก้ขาวดำของหนังสือภายนอก

hub เรียก check_form / convert_form / preview_form / prefill_form (สเปกที่ส่งให้ hub: HUB_FORM_SPEC.md) — convert() รับแบบ job ได้ด้วย
(ค่าฟอร์มอยู่ใน extra[job.id]) เผื่อ hub ส่งฟอร์มมาเป็นรายการเดียว
ทดสอบจากบรรทัดคำสั่ง: python -m doctypes.ext_ebook <ค่า.json> [-o โฟลเดอร์] [--format docx|pdf|both]
"""
from pathlib import Path

from core import render
from core.doctype import DocType
from core.store import JsonFile

from . import form, layout, profile
from .letter import KIND_A, KIND_B, make_request, output_stems

DATA = Path(__file__).resolve().parent / "data"


def load_data() -> tuple:
    office = JsonFile(DATA / "office.json").load({})
    signer = JsonFile(DATA / "signers.json").load({}).get("th", [])
    return office, signer


class ExtEbook(DocType):
    id = "ext_ebook"
    name = "ขยายเวลาส่งรูปเล่มอิเล็กทรอนิกส์"
    description = "กรอกข้อมูลครั้งเดียว → หนังสือแจ้งผลถึงคณะ + บันทึกข้อความขออนุมัติขยายเวลาและคงสภาพผลสอบ"
    icon = "calendar"
    color = "amber"
    order = 30
    options = {}
    drop_hint = "ประเภทนี้ไม่ใช้ไฟล์ — กรอกข้อมูลในฟอร์ม"
    ui = {"modes": [], "slots": [], "form": {**form.FORM, "prefill": {
        "label": "เติมจากหน้า Student Profile (PDF)", "accept": [".pdf"],
        "hint": "เปิดหน้า Student Profile ในระบบฐานข้อมูลนักศึกษา → Ctrl+P บันทึกเป็น PDF → วางที่นี่ "
                "(เติมชื่อ รหัส หลักสูตร คณะ วันสอบผ่าน อาจารย์ที่ปรึกษาหลัก — ช่องอื่นกรอกเอง)"}}}

    def manifest(self) -> dict:
        m = super().manifest()
        m["form_defaults"] = form.defaults()
        return m

    # ---------- ฟอร์ม ----------
    def check_form(self, values: dict) -> dict:
        errors, warnings = form.check(values or {})
        out = {"ok": not errors, "errors": errors, "warnings": warnings, "outputs_preview": []}
        if not errors:
            a, b = output_stems(make_request(values))
            out["outputs_preview"] = [{"name": b, "kind": KIND_B}, {"name": a, "kind": KIND_A}]
        return out

    def prefill_form(self, path: Path) -> dict:
        return profile.prefill(path)

    def convert_form(self, values: dict, options: dict, pdf, outdir: Path, log=lambda m: None) -> dict:
        errors, warnings = form.check(values or {})
        if errors:
            bad = ", ".join(f"{form.FIELDS[k]['label']}: {msg}" for k, msg in errors.items())
            return {"ok": False, "error": f"ข้อมูลยังไม่ครบ/ไม่ถูกต้อง — {bad}", "notes": warnings, "outputs": []}
        r = make_request(values)
        office, signer = load_data()
        stem_a, stem_b = output_stems(r)
        # บันทึกข้อความ (B) มาก่อน — ลำดับแท็บดูตัวอย่าง/รายการผลลัพธ์ในหน้าโปรแกรม (ผู้ใช้ขอ 21 ต.ค. 2569)
        entries = [dict(src=Path(stem_b), outdir=outdir, stem=stem_b, kind=KIND_B, notes=list(warnings),
                        build=lambda logo: layout.build_b(r, office, signer, logo)),
                   dict(src=Path(stem_a), outdir=outdir, stem=stem_a, kind=KIND_A, notes=[],
                        build=lambda logo: layout.build_a(r, office, signer))]
        fmt = "both" if pdf == "both" else "pdf" if pdf else "docx"
        res = render.render(entries, log=log, fmt=fmt)
        outputs = [{"kind": x["kind"], "label": x["kind"], "docx": x["docx"], "pdf": x["pdf"], "doc": x["doc"]}
                   for x in res if x["docx"] or x["pdf"] or x["doc"]]
        ok = all(x["docx"] or x["pdf"] for x in res)
        return {"ok": ok, "error": "; ".join(f"{x['kind']}: {x['error']}" for x in res if x["error"]),
                "notes": [n for x in res for n in x["notes"]], "outputs": outputs}

    def preview_form(self, values: dict, options: dict, outdir: Path, log=lambda m: None) -> dict:
        return self.convert_form(values, options, "both", outdir, log=log)

    # ---------- สัญญาเดิม (ไฟล์) ----------
    def inspect(self, path: Path) -> dict:
        return {"ok": False, "reason": self.drop_hint}

    def convert(self, jobs: list, options: dict, pdf, extra: dict, log=lambda m: None) -> dict:
        return {j.id: self.convert_form(extra.get(j.id) or {}, options, pdf, j.outdir, log=log) for j in jobs}

    def preview(self, job, options: dict, extra: dict, log=lambda m: None, companions=()) -> dict:
        return self.preview_form(extra or {}, options, job.outdir, log=log)


DOCTYPE = ExtEbook()
