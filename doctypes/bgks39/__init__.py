# -*- coding: utf-8 -*-
"""
ประเภทเอกสาร: บฑกศ.39 — หนังสือเชิญ / หนังสือขออนุมัติ ผู้ทำหน้าที่เพื่อให้ได้มาซึ่งหัวข้อวิทยานิพนธ์หรือการค้นคว้าอิสระ

    source.py   อ่านไฟล์ .docx ที่ระบบสร้าง แยกเป็นรายฉบับ
    letter.py   แบบจำลองหนังสือ + กฎข้อความ + กฎช่อง "เรียน" + ชื่อไฟล์
    layout.py   รูปแบบหน้ากระดาษ (แยกหนังสือเชิญ / หนังสือขออนุมัติ)

ผู้ใช้เลือกแท็บ "หนังสือเชิญ" หรือ "หนังสือขออนุมัติ" ก่อนเสมอ — สองแบบจัดหน้าไม่เหมือนกัน
ประเภทที่ใช้จัดจึงมาจากแท็บ (options["mode"]) ไม่ใช่การเดาจากเนื้อหา
"""
import zipfile
from pathlib import Path

from core import render
from core.doctype import DocType

from . import layout, source
from .letter import FORM, GROUPS, check_to, detect, make_letter, output_stem, set_to, student

ACCEPT = [".docx"]
MODES = ("invite", "approve")


def field_key(kind: str, index: int) -> str:
    return f"to_{kind}_{index}"


def load(path: Path, kind: str) -> list:
    return [make_letter(d, kind, str(path), i) for i, d in enumerate(source.read_letters(path))]


def detect_file(path: Path) -> str:
    kinds = [detect(d) for d in source.read_letters(path)]
    return max(MODES, key=kinds.count) if any(kinds) else ""


def references(paths: list, sid: str) -> list:
    """หนังสือของนักศึกษาคนเดียวกันในโฟลเดอร์เดียวกัน (เช่น ไฟล์ขออนุมัติคู่กับไฟล์เชิญ)
    ใช้หาชื่ออาจารย์/ผู้บังคับบัญชาเมื่อ "เรียน" ผิด — ประเภทของไฟล์อ้างอิงดูจากเนื้อหา"""
    seen, out = {Path(p).resolve() for p in paths}, []
    for folder in {Path(p).parent for p in paths}:
        for f in folder.glob(f"*{FORM}*.docx"):
            if f.resolve() in seen or f.name.startswith(tuple(g[1] for g in GROUPS.values())):
                continue
            seen.add(f.resolve())
            try:
                kind = detect_file(f)
                letters = load(f, kind) if kind else []
            except (OSError, KeyError, zipfile.BadZipFile):
                continue
            out += [L for L in letters if student(L)[1] == sid]
    return out


def prepare(path: Path, kind: str, others: list = ()) -> list:
    """อ่านไฟล์ตามประเภทที่เลือก แล้วตรวจ/แก้ "เรียน" (จับคู่กับหนังสือของนักศึกษาคนเดียวกัน)"""
    letters = load(path, kind)
    sid = next((student(L)[1] for L in letters if student(L)[1]), "")
    pool = letters + [L for L in others if student(L)[1] == sid] + references([path, *(L.src for L in others)], sid)
    check_to(pool)
    return letters


class Bgks39(DocType):
    id = "bgks39"
    name = "บฑกศ.39 ผู้ทำหน้าที่หัวข้อวิทยานิพนธ์"
    description = "หนังสือเชิญ / หนังสือขออนุมัติ ผู้ทำหน้าที่เพื่อให้ได้มาซึ่งหัวข้อวิทยานิพนธ์หรือการค้นคว้าอิสระ → Word รูปแบบมาตรฐาน"
    icon = "users"
    color = "teal"
    order = 20
    options = {"mode": "invite"}
    pickers = {"docx": {"title": f"เลือกไฟล์ {FORM} จากระบบ", "filters": [(f"ไฟล์ {FORM}", "*.docx"), ("ทุกไฟล์", "*.*")]}}
    drop_hint = f"รองรับไฟล์ .docx {FORM} ที่ดาวน์โหลดจากระบบ"
    ui = {
        "modes": [
            {"id": "invite", "label": "กลุ่มที่ 1 · หนังสือเชิญ", "icon": "invite", "color": "blue",
             "summary": [{"slot": "invite"}]},
            {"id": "approve", "label": "กลุ่มที่ 2 · หนังสือขออนุมัติ", "icon": "approve", "color": "violet",
             "summary": [{"slot": "approve"}]},
        ],
        "slots": [
            {"id": "invite", "mode": "invite", "num": 1, "title": "หนังสือเชิญอาจารย์ผู้ทำหน้าที่",
             "desc": "เรียน ชื่ออาจารย์ผู้ทำหน้าที่ · มี “ทั้งนี้ได้แจ้งให้ผู้บังคับบัญชาของท่านทราบแล้ว”",
             "icon": "invite", "color": "blue", "accept": ACCEPT, "pick": "docx", "pick_label": "เลือกไฟล์",
             "zone_title": "ลากไฟล์หนังสือเชิญมาวางที่นี่",
             "zone_desc": f"ไฟล์ “({FORM} หนังสือเชิญ) ….docx” — ทุกฉบับในไฟล์จะขึ้นหน้าใหม่"},
            {"id": "approve", "mode": "approve", "num": 2, "title": "หนังสือขออนุมัติส่งถึงผู้บังคับบัญชา",
             "desc": "เรียน ตำแหน่งผู้บังคับบัญชา (คณบดี / ผู้อำนวยการ / หัวหน้าภาควิชา) · ชื่ออาจารย์อยู่ในเนื้อหา",
             "icon": "approve", "color": "violet", "accept": ACCEPT, "pick": "docx", "pick_label": "เลือกไฟล์",
             "zone_title": "ลากไฟล์หนังสือขออนุมัติมาวางที่นี่",
             "zone_desc": f"ไฟล์ “({FORM} หนังสือขออนุมัติ) ….docx”"},
        ],
    }

    def inspect(self, path: Path) -> dict:
        path = Path(path)
        if path.name.startswith(tuple(f"{g[1]}-{FORM}" for g in GROUPS.values())):
            return {"ok": False, "reason": "เป็นไฟล์ที่ปรับแล้ว"}
        try:
            kind = detect_file(path)
            letters = prepare(path, kind or "invite")
        except (OSError, KeyError, zipfile.BadZipFile):
            return {"ok": False, "reason": "อ่านไฟล์ไม่ได้ (ไม่ใช่ไฟล์ .docx จากระบบ)"}
        if not letters:
            return {"ok": False, "reason": f"ไม่พบหนังสือ {FORM} ในไฟล์"}
        kind = kind or "invite"
        name, sid = student(letters[0])
        out = {"ok": True, "slot": kind, "kind": GROUPS[kind][1],
               "subtitle": f"{GROUPS[kind][1]} {len(letters)} ฉบับ · {name} {sid}".strip(),
               "subtitle2": "เรียน " + " / ".join(L.to for L in letters),
               "outputs_preview": [{"name": output_stem(kind, name)}]}
        ask = [L for L in letters if L.to_status != "ok"]
        if ask:
            out["fields_title"] = "ช่อง “เรียน” ที่ระบบใส่ไม่ตรงกับประเภทหนังสือ — ตรวจ/แก้ก่อนแปลง"
            out["fields_status"] = "ตรวจช่องเรียน"
            out["fields"] = [{"key": field_key(kind, L.index), "label": f"เรียน · ฉบับที่ {L.index + 1}",
                              "hint": f"ระบบใส่: {L.to_raw}", "value": L.to if L.to_status == "fixed" else "",
                              "check": "required",
                              "placeholder": "ชื่ออาจารย์ผู้ทำหน้าที่" if kind == "invite" else "ตำแหน่งผู้บังคับบัญชา"}
                             for L in ask]
        return out

    def convert(self, jobs: list, options: dict, pdf: bool, extra: dict, log=lambda m: None) -> dict:
        kind = options.get("mode") if options.get("mode") in MODES else "invite"
        everyone = [L for j in jobs for L in load(j.path, kind)]
        entries, ids = [], []
        for j in jobs:
            letters = prepare(j.path, kind, [L for L in everyone if L.src != str(j.path)])
            for L in letters:
                set_to(L, (extra.get(j.id) or {}).get(field_key(kind, L.index), ""))
            notes = [f"ฉบับที่ {L.index + 1} ({L.to}): {f}" if len(letters) > 1 else f
                     for L in letters for f in L.fixes]
            notes += [f"ฉบับที่ {L.index + 1}: ยังไม่มีช่อง “เรียน” ที่ถูกต้อง" for L in letters if L.to_status == "missing"]
            entries.append(dict(src=j.path, outdir=j.outdir, stem=output_stem(kind, student(letters[0])[0]),
                                kind=GROUPS[kind][1], notes=notes,
                                build=lambda logo, ls=letters: layout.build_html(ls, logo)))
            ids.append(j.id)
        out = {}
        for jid, r in zip(ids, render.render(entries, pdf=pdf, log=log)):
            out[jid] = {"ok": bool(r["docx"]), "error": r["error"], "notes": r["notes"],
                        "outputs": [{"kind": r["kind"], "label": "", "docx": r["docx"], "pdf": r["pdf"],
                                     "doc": r["doc"]}] if r["docx"] else []}
        return out


DOCTYPE = Bgks39()
