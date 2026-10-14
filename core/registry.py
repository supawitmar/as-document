# -*- coding: utf-8 -*-
"""
ทะเบียนประเภทเอกสาร: ค้นทุกโฟลเดอร์ใน doctypes/ (ยกเว้นที่ขึ้นต้นด้วย _) ที่มีตัวแปร DOCTYPE
ประเภทที่โหลดไม่ได้จะถูกข้าม (จดข้อผิดพลาดไว้ใน errors) โดยไม่ทำให้ประเภทอื่นใช้ไม่ได้
"""
import importlib
import traceback
from pathlib import Path

from core import DOCTYPES_DIR

_doctypes = {}
errors = {}


def discover() -> dict:
    if _doctypes or errors:
        return _doctypes
    found = []
    for d in sorted(DOCTYPES_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith(("_", ".")) or not (d / "__init__.py").exists():
            continue
        try:
            mod = importlib.import_module(f"doctypes.{d.name}")
            found.append(mod.DOCTYPE)
        except Exception:
            errors[d.name] = traceback.format_exc()
    for dt in sorted(found, key=lambda x: (x.order, x.name)):
        _doctypes[dt.id] = dt
    return _doctypes


def all_doctypes() -> list:
    return list(discover().values())


def get(doctype_id: str):
    dts = discover()
    if doctype_id not in dts:
        raise ValueError(f"ไม่รู้จักประเภทเอกสาร: {doctype_id}")
    return dts[doctype_id]


def for_path(path: Path, prefer: str = ""):
    """ประเภทเอกสารที่รับไฟล์นี้ (ให้ประเภทที่เปิดอยู่ก่อน)"""
    dts = all_doctypes()
    dts.sort(key=lambda d: d.id != prefer)
    return next((d for d in dts if d.accepts(path)), None)
