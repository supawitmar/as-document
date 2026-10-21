# สเปกที่ ext_ebook ต้องการจาก hub: "ฟอร์มกรอกข้อมูล" (ไม่มีไฟล์ต้นฉบับ)

ประเภทเอกสาร `doctypes/ext_ebook/` = ขอขยายเวลาการส่งรูปเล่มอิเล็กทรอนิกส์และคงสภาพผลสอบ
ผู้ใช้ยืนยันแล้ว (21 ต.ค. 2569): **กรอกข้อมูลเองในหน้าโปรแกรม** + เติมบางช่องจาก PDF หน้า Student Profile ได้ — กรอก 1 ครั้ง ได้ 2 ฉบับเสมอ
(A หนังสือแจ้งผลถึงคณบดี + B บันทึกข้อความขออนุมัติ) · ผู้เสนอใน B กรอกทุกครั้ง (ให้ hub จำค่าล่าสุดไว้เติมให้)

hub ตอนนี้รับแค่ "วางไฟล์" (slots + fields ต่อไฟล์) — ขอเพิ่มทางเข้าแบบฟอร์ม (ฝั่ง doctype ทำครบแล้ว ไม่ต้องรอ hub)

## 1. manifest: `ui["form"]`

```python
ui = {"modes": [], "slots": [], "form": {
    "title": "ข้อมูลการขอขยายเวลา",
    "submit_label": "สร้างเอกสาร",
    "sections": [
        {"title": "หนังสือของหลักสูตร", "fields": [ <field>, ... ]},
        ...
    ]}}
```

ถ้าประเภทมี `ui.form` → แสดงฟอร์มแทนช่องวางไฟล์ (ไม่มีรายการไฟล์ / ไม่มี inspect)

`<field>`:

| คีย์ | ความหมาย |
|---|---|
| `key` | ชื่อค่า (ส่งกลับใน values) |
| `label`, `placeholder`, `hint` | ข้อความ (hint = บรรทัดเล็กใต้ช่อง) |
| `type` | `text` · `textarea` · `date` · `select` |
| `required` | bool — ว่าง = ห้ามสร้าง |
| `options` | (select) รายการตัวเลือก [str] |
| `allow_other` | (select) พิมพ์ค่าอื่นได้ (datalist / combobox) |
| `pattern`, `pattern_msg` | regex (ใช้ได้ทั้ง JS/Python) ตรวจตอนพิมพ์ + ข้อความเมื่อไม่ตรง |
| `default` | ค่าเริ่มต้น; `"today"` = วันนี้ (ใช้กับ date) |
| `remember` | bool — hub จำค่าล่าสุดของเครื่องนี้ (เช่นใน settings.json `options.<id>.form_last`) แล้วเติมให้ครั้งถัดไป |
| `width` | `half` / `full` (ไม่ระบุ = full) |

ค่า `date`: hub ส่งเป็น ISO `YYYY-MM-DD` (ค.ศ. จาก `<input type=date>`) — doctype แปลงเป็นวันที่ไทย พ.ศ. เอง
(doctype รับข้อความไทย เช่น "11 พฤษภาคม 2569" / "11 พ.ค. 69" ได้ด้วย ถ้า hub อยากใช้ช่องข้อความแทน)

## 2. เมธอดใหม่ของ DocType (เฉพาะประเภทที่มี ui.form)

```python
def check_form(self, values: dict) -> dict:
    """เรียกตอนพิมพ์ (debounce) และก่อนสร้าง
    -> {"ok": bool, "errors": {key: ข้อความ}, "warnings": [ข้อความ], "outputs_preview": [{"name", "kind"}]}"""

def convert_form(self, values: dict, options: dict, pdf, outdir: Path, log=print) -> dict:
    """pdf ความหมายเดียวกับ convert (True / False / "both")
    -> {"ok", "error", "notes": [...], "outputs": [{"kind","label","docx","pdf","doc"}, ...]}  (ผลแบบ 1 job ของ convert)"""

def preview_form(self, values: dict, options: dict, outdir: Path, log=print) -> dict:
    """ค่าเริ่มต้น = convert_form(values, options, "both", outdir) — outputs มีหลายไฟล์ (A, B) ให้แสดงเป็นแท็บ/หน้าต่อกัน"""

def prefill_form(self, path: Path) -> dict:
    """ไฟล์ที่ผู้ใช้วาง/เลือกในช่อง ui.form.prefill -> {"values": {key: ค่า}, "notes": [...], "error": ""}
    values มีเฉพาะช่องที่อ่านได้ — hub เติมทับเฉพาะช่องเหล่านั้น (ช่องอื่นคงค่าที่ผู้ใช้กรอกไว้); วันที่เป็น ISO"""
```

ข้อเสนอ: ใส่ค่าเริ่มต้นใน core/doctype.py — `check_form` ตรวจ required/pattern จาก ui.form, `convert_form` raise NotImplementedError,
`preview_form` เรียก convert_form แบบ "both" · ext_ebook override ครบทุกตัวแล้ว (ตรวจวันที่ต่อเนื่อง/รหัส 7 หลัก ฯลฯ)

`ui["form"]["prefill"] = {"label", "accept": [".pdf"], "hint"}` → hub แสดงช่องวาง/เลือกไฟล์บนฟอร์ม แล้วเรียก prefill_form
(ไม่มีคีย์นี้ = ไม่แสดง) · error ไม่ว่าง = แสดงข้อความ ไม่เติมอะไร · notes = ช่องที่อ่านไม่ได้ (ให้ผู้ใช้กรอกเอง)

## 3. หน้าจอ

- ปุ่ม "ดูตัวอย่าง" → preview_form → แสดง PDF ทุกไฟล์ใน outputs (2 ไฟล์)
- ปุ่ม submit_label → convert_form ลงโฟลเดอร์ "บันทึกไฟล์ที่" ตามตัวเลือก (Word / PDF / Word+PDF) → แสดงผลแบบเดียวกับรายการไฟล์ (เปิดไฟล์/โฟลเดอร์)
- errors แสดงใต้ช่องนั้น; warnings แสดงเหนือปุ่ม (ไม่บล็อก); outputs_preview แสดงชื่อไฟล์ที่จะได้
- ปุ่ม "ล้างฟอร์ม" (ค่าที่ remember ยังคงอยู่); จำค่าที่กรอกค้างไว้ถ้าปิดโปรแกรมกลางคันได้ยิ่งดี (ไม่บังคับ)

## 4. ช่องของ ext_ebook

`doctypes/ext_ebook/form.py` → `FORM` (+ `prefill` ใน `__init__.py`); manifest มี `form_defaults` (ค่าเริ่มต้น เช่น วันที่บันทึก = วันนี้)
ตรวจด้วย `python -c "from doctypes.ext_ebook import DOCTYPE; import json; print(json.dumps(DOCTYPE.manifest()['form'], ensure_ascii=False, indent=1))"`
