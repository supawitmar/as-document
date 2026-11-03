# -*- coding: utf-8 -*-
"""
ประเภทเอกสาร: ขออนุมัติยกเว้น/ลดหย่อนค่าปรับการส่งรูปเล่มอิเล็กทรอนิกส์ล่าช้า (สเปกเจ้าของยืนยัน 3 พ.ย. 2569)

ไม่มีไฟล์ต้นฉบับ — ผู้ใช้กรอกข้อมูลครั้งเดียวในฟอร์ม (ui["form"]) เลือก "ยกเว้น" หรือ "ลดหย่อน" แล้วได้ 2 ฉบับเสมอ:
    บันทึกข้อความ งานบริการการศึกษา -> รองคณบดีฝ่ายแผนฯ เสนอคณบดีบัณฑิตวิทยาลัย (มีเหตุผล + ช่องอนุมัติ) — ขึ้นก่อน
    หนังสือแจ้งผล บัณฑิตวิทยาลัย -> คณบดีของส่วนงาน + สำเนาเรียน (ประธานหลักสูตร, อาจารย์ที่ปรึกษาหลัก)

    form.py     ช่องกรอก + ตรวจค่า (ยอดที่ต้องชำระบังคับเฉพาะลดหย่อน และต้องน้อยกว่าค่าปรับเต็ม)
    letter.py   แบบจำลองคำขอ + ข้อความของทั้ง 2 ฉบับ + ชื่อไฟล์
    layout.py   รูปแบบหน้ากระดาษตามตัวอย่างที่เจ้าหน้าที่จัด
    data/       signers.json (ผู้ลงนามหนังสือแจ้งผล, รองคณบดีและคณบดีในบันทึก), office.json (ที่อยู่, เลขที่หนังสือ,
                ส่วนราชการ, เรียน ของบันทึก)
    assets/     โลโก้ขาวดำของหนังสือภายนอก
วันที่/จำนวนเงิน: core.thaidate · เติมจาก Student Profile และตัวจัดชื่อ: core.student_profile
ทดสอบจากบรรทัดคำสั่ง: python -m doctypes.late_fine <ค่า.json> [-o โฟลเดอร์] [--format docx|pdf|both]
"""
from pathlib import Path

from core import render, student_profile
from core.doctype import DocType
from core.store import JsonFile

from . import form, layout
from .letter import kinds, make_request, output_stems

DATA = Path(__file__).resolve().parent / "data"


def load_data() -> tuple:
    return JsonFile(DATA / "office.json").load({}), JsonFile(DATA / "signers.json").load({})


class LateFine(DocType):
    id = "late_fine"
    name = "ยกเว้น/ลดหย่อนค่าปรับส่งรูปเล่มล่าช้า"
    description = "กรอกข้อมูลครั้งเดียว → บันทึกข้อความขออนุมัติ + หนังสือแจ้งผลถึงคณะ (ยกเว้น หรือ ลดหย่อนค่าปรับ)"
    icon = "approve"
    color = "rose"
    order = 40
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
            r = make_request(values)
            out["outputs_preview"] = [{"name": n, "kind": k} for n, k in zip(output_stems(r), kinds(r))]
        return out

    def prefill_form(self, path: Path) -> dict:
        return student_profile.prefill(path)

    def convert_form(self, values: dict, options: dict, pdf, outdir: Path, log=lambda m: None) -> dict:
        errors, warnings = form.check(values or {})
        if errors:
            bad = ", ".join(f"{form.FIELDS[k]['label']}: {msg}" for k, msg in errors.items())
            return {"ok": False, "error": f"ข้อมูลยังไม่ครบ/ไม่ถูกต้อง — {bad}", "notes": warnings, "outputs": []}
        r = make_request(values)
        office, signers = load_data()
        (stem_m, stem_l), (kind_m, kind_l) = output_stems(r), kinds(r)
        # บันทึกข้อความมาก่อน (ลำดับแท็บดูตัวอย่าง/รายการผลลัพธ์ในหน้าโปรแกรม เหมือน ext_ebook)
        # tighten: คำเดียวตกบรรทัดท้ายย่อหน้า (เช่น "ถ้วน)" ของจำนวนเงิน) → Word บีบบรรทัดก่อนหน้าให้ขึ้นไปอยู่ด้วย
        entries = [dict(src=Path(stem_m), outdir=outdir, stem=stem_m, kind=kind_m, notes=list(warnings), tighten=True,
                        build=lambda logo: layout.build_memo(r, office, signers, logo)),
                   dict(src=Path(stem_l), outdir=outdir, stem=stem_l, kind=kind_l, notes=[], tighten=True,
                        build=lambda logo: layout.build_letter(r, office, signers["letter"]))]
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


DOCTYPE = LateFine()
