# -*- coding: utf-8 -*-
"""
ไฟล์ข้อมูล JSON ของแต่ละประเภทเอกสาร (เช่น รายชื่อวิชา, ผู้ลงนาม, คำแปลที่ผู้ใช้กรอก)

ข้อมูลของแต่ละประเภทเก็บใน doctypes/<ประเภท>/data/ — ถ้าเครื่องนี้ยังมีไฟล์ชื่อเดียวกันในที่เก็บรุ่นเดิม (legacy)
จะรวมเข้ามาให้ครั้งแรกที่อ่าน (ค่าจากไฟล์เดิมชนะ เพราะเป็นค่าที่ผู้ใช้แก้/เรียนรู้ไว้) แล้วเปลี่ยนชื่อไฟล์เดิมเป็น .migrated
"""
import json
from pathlib import Path


class JsonFile:
    def __init__(self, path: Path, legacy: Path = None, sort_keys: bool = False):
        self.path = Path(path)
        self.legacy = Path(legacy) if legacy else None
        self.sort_keys = sort_keys

    def _read(self, p: Path):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _migrate(self):
        if not self.legacy or not self.legacy.exists():
            return
        old = self._read(self.legacy)
        if isinstance(old, dict):
            cur = self._read(self.path)
            self.save({**(cur if isinstance(cur, dict) else {}), **old})
        try:
            self.legacy.replace(self.legacy.with_name(self.legacy.name + ".migrated"))
        except OSError:
            pass

    def exists(self) -> bool:
        self._migrate()
        return self.path.exists()

    def load(self, default=None):
        """อ่านไฟล์ (ไม่มี/อ่านไม่ได้ -> default)"""
        self._migrate()
        data = self._read(self.path)
        return default if data is None else data

    def save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=self.sort_keys), encoding="utf-8")
