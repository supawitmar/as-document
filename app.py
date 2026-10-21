# -*- coding: utf-8 -*-
"""
หน้าโปรแกรม "ระบบปรับเอกสาร" (hub) แบบเว็บ — เปิดเป็นหน้าต่างแอปของ Microsoft Edge
ทำงานในเครื่องเท่านั้น: เซิร์ฟเวอร์ฟังที่ 127.0.0.1 และทุกคำขอต้องมี token

hub ไม่มีกฎของเอกสารใดเลย: รายชื่อประเภทเอกสารมาจาก doctypes/ (core.registry) หน้าจอสร้างจาก manifest
ของแต่ละประเภท และการอ่าน/แปลงไฟล์ส่งต่อให้ประเภทนั้น (core.doctype.DocType)
"""
import ctypes
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from core import ASSETS, BASE, registry, update
from core.doctype import Job
from core.render import save_file

WEB = BASE / "web"
DOWNLOADS = Path.home() / "Downloads"
SETTINGS_FILE = BASE / "settings.json"
HISTORY_FILE = BASE / "converted.json"
UPLOADS = Path(tempfile.gettempdir()) / "fixletters_uploads"
PREVIEWS = Path(tempfile.gettempdir()) / "fixletters_preview"
TOKEN = secrets.token_urlsafe(16)
APP_WINDOW_TITLE = "ระบบปรับเอกสาร"   # ต้องตรงกับ <title> ใน web/index.html
DEFAULT_SETTINGS = {"format": "docx", "dest": "same", "outdir": "", "doctype": "", "options": {},
                    "form_memory": {}}     # form_memory: ค่าช่องฟอร์มที่ติ๊ก remember {ประเภท: {key: ค่า}}
FORMATS = ("docx", "pdf", "both")     # รูปแบบไฟล์ที่ส่งออก: Word / PDF / Word + PDF

items = {}          # id -> {"path": Path, "origin": "path"|"upload", "doctype": id}
allowed = set()     # ไฟล์/โฟลเดอร์ที่อนุญาตให้เปิดจากหน้าเว็บ
dialog_lock = threading.Lock()
preview_lock = threading.Lock()
preview_files = {}  # รหัสลิงก์ -> (รหัสรายการ, ไฟล์ PDF ตัวอย่าง)
preview_cache = {}  # รหัสรายการ -> {"sig", "dir", "result"}: ผลจากปุ่มดูตัวอย่าง (มีทั้ง .docx และ .pdf) ใช้ซ้ำตอนบันทึก
last_ping = [0.0]
restart = threading.Event()   # อัปเดตแล้ว: เปิดโปรแกรมใหม่ แล้วปิดตัวนี้
jobs_running = [0]            # จำนวนงานแปลง/ดูตัวอย่างที่กำลังทำ — ห้ามอัปเดตระหว่างนี้
jobs_lock = threading.Lock()
INSTALLS_FILE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "as-document" / "installs.json"
FILES = [a for a in sys.argv[1:] if not a.startswith("--")]


# ---------- ตั้งค่า ----------
def load_settings() -> dict:
    try:
        raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    s = {**DEFAULT_SETTINGS, **{k: raw[k] for k in DEFAULT_SETTINGS if k in raw}}
    if s["format"] not in FORMATS:
        s["format"] = DEFAULT_SETTINGS["format"]
    opts = dict(raw.get("options") or {})
    if "want_approve" in raw or "mode" in raw:        # settings.json รุ่นก่อน hub (ตัวเลือกของ บฑ.31 อยู่ชั้นบนสุด)
        mode = {"bt31": "eform"}.get(raw.get("mode"), raw.get("mode"))
        opts.setdefault("bt31", {k: v for k, v in (("want_approve", raw.get("want_approve")), ("mode", mode))
                                 if v is not None})
    dts = registry.discover()
    s["options"] = {d.id: {**d.options, **opts.get(d.id, {})} for d in dts.values()}
    if s["doctype"] not in dts:
        s["doctype"] = next(iter(dts), "")
    return s


def save_settings(s: dict):
    clean = {k: s.get(k, v) for k, v in DEFAULT_SETTINGS.items()}
    SETTINGS_FILE.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_checks():
    """เปิดโปรแกรมใหม่: ช่องติ๊กทุกช่อง (ตัวเลือกแบบเปิด/ปิด) กลับเป็นค่าเริ่มต้นของประเภทเอกสาร (ไม่ติ๊ก)
    — รูปแบบไฟล์ ที่บันทึก และแท็บที่เปิด ยังจำไว้ตามเดิม"""
    s = load_settings()
    for d in registry.all_doctypes():
        o = s["options"].setdefault(d.id, {})
        o.update({k: v for k, v in d.options.items() if isinstance(v, bool)})
    save_settings(s)


def update_settings(patch: dict) -> dict:
    s = load_settings()
    for k, v in patch.items():
        if k == "options":        # รวมทีละประเภทเอกสาร
            for dt_id, o in (v or {}).items():
                s["options"][dt_id] = {**s["options"].get(dt_id, {}), **o}
        elif k in DEFAULT_SETTINGS:
            s[k] = v
    save_settings(s)
    return load_settings()


# ---------- รายการไฟล์ ----------
def register(path: Path, origin: str, doctype: str) -> dict:
    path = path.resolve()
    for iid, it in items.items():
        if it["path"] == path and it["doctype"] == doctype:
            return describe(iid)
    iid = uuid.uuid4().hex[:10]
    items[iid] = {"path": path, "origin": origin, "doctype": doctype}
    if origin == "path":
        allowed.add(path.parent)
    return describe(iid)


def describe(iid: str) -> dict:
    it = items[iid]
    dt = registry.get(it["doctype"])
    size_mb = it["path"].stat().st_size / 1048576 if it["path"].exists() else 0
    try:
        if dt.max_mb and size_mb > dt.max_mb:
            info = {"ok": False, "reason": f"ไฟล์ขนาด {size_mb:.1f} MB เกินกำหนด (ไม่เกิน {dt.max_mb} MB)"}
        else:
            info = dt.inspect(it["path"])
            # ช่องที่กำหนดขนาดเองได้ (เช่น ตารางสอน) — ตรวจหลังรู้ว่าไฟล์นี้เป็นของช่องไหน
            slot_max = next((s.get("max_mb") for s in dt.ui.get("slots", []) if s.get("id") == info.get("slot")), None)
            if slot_max and size_mb > slot_max:
                info = {**info, "ok": False, "reason": f"ไฟล์ขนาด {size_mb:.1f} MB เกินกำหนด (ไม่เกิน {slot_max} MB)"}
    except Exception as e:      # ประเภทเอกสารอ่านไฟล์ไม่ได้ — แสดงเป็นแถวที่ใช้ไม่ได้ แทนที่จะล้มทั้งหน้า
        info = {"ok": False, "reason": f"อ่านไฟล์ไม่ได้: {e}"}
    folder = str(it["path"].parent) if it["origin"] == "path" else ""
    return {**info, "subtitle": info.get("subtitle") or folder, "id": iid, "name": it["path"].name,
            "origin": it["origin"], "folder": folder, "doctype": it["doctype"]}


def collect(args: list, prefer: str) -> list:
    """ไฟล์/โฟลเดอร์จากบรรทัดคำสั่ง (หรือที่ลากมาวางบนไอคอน) -> [(path, doctype)]"""
    out = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            dt = registry.get(prefer) if prefer else None
            out += [(f, prefer) for f in (dt.collect_dir(p) if dt else [])]
        elif p.exists() and (dt := registry.for_path(p, prefer)):
            out.append((p, dt.id))
    return out


def converted_log() -> set:
    """ไฟล์ที่เคยแปลงแล้ว (path + เวลาแก้ไข) — ชื่อไฟล์ผลลัพธ์ไม่ได้อ้างชื่อต้นฉบับ จึงต้องจดไว้"""
    try:
        return set(json.loads(HISTORY_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        # ครั้งแรก: นับไฟล์ที่เคยแปลงด้วยชื่อแบบเดิม "Export (xx) - หนังสือ….docx" ว่าแปลงแล้ว
        old = {x.name.split(" - ")[0] for x in DOWNLOADS.glob("Export* - *.docx")}
        return {source_key(p) for p in DOWNLOADS.glob("Export*.doc") if p.stem in old}


def source_key(p: Path) -> str:
    return f"{p.resolve()}|{int(p.stat().st_mtime)}"


def remember_converted(paths: list):
    done = converted_log()
    done.update(source_key(p) for p in paths if p.exists())
    HISTORY_FILE.write_text(json.dumps(sorted(done)[-2000:], ensure_ascii=False, indent=0), encoding="utf-8")


def new_in_downloads(doctype: str, days: int = 3) -> list:
    """ไฟล์ใน Downloads ตามรูปแบบชื่อของประเภทเอกสาร ที่ดาวน์โหลดภายใน 3 วันและยังไม่เคยแปลง (ใหม่สุดก่อน)"""
    try:
        pattern = (registry.get(doctype).downloads or {}).get("glob")
    except ValueError:
        return []
    if not pattern:
        return []
    done = converted_log()
    since = time.time() - days * 86400
    new = [p for p in DOWNLOADS.glob(pattern) if p.stat().st_mtime >= since and source_key(p) not in done]
    return sorted(new, key=lambda p: p.stat().st_mtime, reverse=True)


def ask(kind: str, initial: str, picker: dict = None):
    """เปิดหน้าต่างเลือกไฟล์/โฟลเดอร์ของ Windows (ได้ path จริง)"""
    import tkinter as tk
    from tkinter import filedialog
    with dialog_lock:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            if kind == "files":
                return list(filedialog.askopenfilenames(
                    parent=root, title=picker.get("title", "เลือกไฟล์"), initialdir=initial,
                    filetypes=picker.get("filters") or [("ทุกไฟล์", "*.*")]))
            return filedialog.askdirectory(parent=root, title="เลือกโฟลเดอร์สำหรับบันทึกไฟล์", initialdir=initial)
        finally:
            root.destroy()


def preview_sig(doctype: str, iid: str, options: dict, extra: dict, companions: list) -> str:
    """ลายเซ็นของสิ่งที่ใช้สร้างเอกสาร — ถ้าเปลี่ยน (ตัวเลือก/ข้อมูลที่กรอก/ไฟล์แนบ/ไฟล์ต้นฉบับ) ต้องสร้างใหม่"""
    comp = sorted(source_key(items[c]["path"]) for c in companions if c in items and c != iid and items[c]["path"].exists())
    return json.dumps([doctype, source_key(items[iid]["path"]), options, extra or {}, comp], sort_keys=True, ensure_ascii=False)


def from_preview(doctype: str, job: Job, options: dict, extra: dict, companions: list, fmt: str):
    """ใช้ไฟล์ที่สร้างไว้ตอนดูตัวอย่าง (ถ้ายังตรงกับตัวเลือกปัจจุบัน) — คัดลอกไปปลายทาง ไม่ต้องเปิด Word ซ้ำ"""
    c = preview_cache.get(job.id)
    if not c or not c["result"].get("ok") or c["sig"] != preview_sig(doctype, job.id, options, extra, companions):
        return None
    return copy_cached(c["result"], job.outdir, fmt)


def copy_cached(result: dict, outdir: Path, fmt: str):
    """คัดลอกไฟล์ที่สร้างไว้ตอนดูตัวอย่างไปโฟลเดอร์ปลายทางตามรูปแบบที่เลือก — ไม่ครบ = None (ให้แปลงใหม่)"""
    exts = {"pdf": ["pdf"], "both": ["docx", "pdf"]}.get(fmt, ["docx"])
    outs = result.get("outputs", [])
    # ทุกฉบับต้องมีไฟล์ตามรูปแบบที่เลือกอย่างน้อยหนึ่งแบบ (ไฟล์ Word ที่จัดแล้วได้ PDF อย่างเดียว)
    if not outs or not all(any(o.get(e) and Path(o[e]).exists() for e in exts) for o in outs):
        return None
    outdir.mkdir(parents=True, exist_ok=True)
    copied, notes = [], list(result.get("notes", []))
    for o in outs:
        new = {**o, "docx": None, "pdf": None, "doc": None}
        for e in exts:
            if o.get(e) and Path(o[e]).exists():       # ชื่อซ้ำ = เขียนทับ (ฉบับปรับปรุง)
                new[e] = save_file(Path(o[e]), outdir / Path(o[e]).name, notes, move=False)
        copied.append(new)
    return {**result, "outputs": copied, "notes": notes}


def pack(r: dict) -> dict:
    """ผลของประเภทเอกสาร -> ผลที่ส่งให้หน้าจอ (path เป็นข้อความ) และอนุญาตให้เปิดไฟล์ที่ได้"""
    outputs = [{k: str(o.get(k) or "") for k in ("kind", "label", "docx", "pdf", "doc")} for o in r.get("outputs", [])]
    for o in outputs:
        for f in (o["docx"], o["pdf"], o["doc"]):
            if f:
                allowed.update({Path(f), Path(f).parent})
    return {"ok": bool(r.get("ok")), "error": r.get("error", ""), "notes": r.get("notes", []), "outputs": outputs,
            "docx": next((f for o in outputs for f in (o["docx"], o["pdf"]) if f), "")}


def convert(doctype: str, ids: list, settings: dict, extra: dict = None, companions=()) -> dict:
    dt = registry.get(doctype)
    chosen = Path(settings["outdir"]) if settings.get("dest") == "folder" and settings.get("outdir") else None
    jobs = [Job(i, items[i]["path"], chosen or (items[i]["path"].parent if items[i]["origin"] == "path" else DOWNLOADS))
            for i in ids if i in items and items[i]["doctype"] == doctype]
    opts, fmt, extra = settings["options"].get(doctype, {}), settings.get("format"), extra or {}
    comps = [c for c in companions if c in items]
    results, todo = {}, []
    for j in jobs:
        r = None if j.id in comps else from_preview(doctype, j, opts, extra.get(j.id), comps, fmt)
        if r:
            results[j.id] = r
        else:
            todo.append(j)
    if any(j.id not in comps for j in todo):        # มีหนังสือที่ยังไม่ได้ดูตัวอย่าง (หรือเปลี่ยนตัวเลือกหลังดู) -> แปลงด้วย Word
        results.update(dt.convert(todo, opts, "both" if fmt == "both" else fmt == "pdf", extra, log=lambda m: None))
    out = {jid: pack(r) for jid, r in results.items()}
    remember_converted([items[i]["path"] for i, r in out.items() if r["ok"] and items[i]["origin"] == "path"])
    return out


def preview(doctype: str, iid: str, options: dict, extra: dict, companions=()) -> dict:
    """ปุ่ม "ดูตัวอย่าง": สร้าง PDF ชั่วคราว (ไม่บันทึกลงโฟลเดอร์ผลลัพธ์) แล้วคืนลิงก์ให้หน้าจอแสดง"""
    if iid not in items or items[iid]["doctype"] != doctype:
        raise ValueError("ไม่พบไฟล์ในรายการ")
    dt = registry.get(doctype)
    opts = {**load_settings()["options"].get(doctype, {}), **(options or {})}
    with preview_lock:
        drop_preview(iid)                                  # ตัวอย่างเดิมของรายการนี้
        outdir = PREVIEWS / iid / uuid.uuid4().hex[:8]
        outdir.mkdir(parents=True, exist_ok=True)
        comp = [Job(c, items[c]["path"], outdir) for c in companions if c in items and c != iid]
        r = dt.preview(Job(iid, items[iid]["path"], outdir), opts, extra or {}, log=lambda m: None, companions=comp)
        preview_cache[iid] = {"sig": preview_sig(doctype, iid, opts, extra, list(companions)), "dir": outdir, "result": r}
        return preview_pages(iid, r)


def preview_pages(owner: str, r: dict) -> dict:
    """ลิงก์ PDF ตัวอย่างให้หน้าจอแสดง (เปิดได้ระหว่างที่ตัวอย่างยังอยู่ใน preview_cache)"""
    pages = []
    for o in r.get("outputs", []):
        if o.get("pdf") and Path(o["pdf"]).exists():
            key = uuid.uuid4().hex[:12]
            preview_files[key] = (owner, Path(o["pdf"]))
            pages.append({"kind": o.get("kind", ""), "label": o.get("label", ""), "url": f"/preview/{key}/{quote(Path(o['pdf']).name)}"})
    if pages:
        return {"ok": True, "error": "", "notes": r.get("notes", []), "pages": pages}
    return {"ok": False, "error": r.get("error") or "สร้างตัวอย่างไม่ได้ — ต้องใช้ Microsoft Word ในเครื่อง",
            "notes": r.get("notes", []), "pages": []}


# ---------- ทางเข้าแบบฟอร์มกรอกข้อมูล (ประเภทเอกสารที่มี ui["form"] เช่น ext_ebook) ----------
def form_fields(dt) -> list:
    return [f for sec in (dt.ui.get("form") or {}).get("sections", []) for f in sec.get("fields", [])]


def form_sig(doctype: str, values: dict, options: dict) -> str:
    return json.dumps([doctype, values or {}, options or {}], sort_keys=True, ensure_ascii=False)


def form_check(doctype: str, values: dict) -> dict:
    r = registry.get(doctype).check_form(values or {})
    return {"ok": bool(r.get("ok")), "errors": r.get("errors") or {}, "warnings": r.get("warnings") or [],
            "outputs_preview": [p if isinstance(p, dict) else {"name": str(p)} for p in r.get("outputs_preview") or []]}


def form_preview(doctype: str, values: dict, options: dict) -> dict:
    dt = registry.get(doctype)
    opts = {**load_settings()["options"].get(doctype, {}), **(options or {})}
    owner = f"form:{doctype}"
    with preview_lock:
        drop_preview(owner)
        outdir = PREVIEWS / f"form-{doctype}" / uuid.uuid4().hex[:8]
        outdir.mkdir(parents=True, exist_ok=True)
        r = dt.preview_form(values or {}, opts, outdir, log=lambda m: None)
        preview_cache[owner] = {"sig": form_sig(doctype, values, opts), "dir": outdir, "result": r}
        return preview_pages(owner, r)


def form_convert(doctype: str, values: dict, settings: dict) -> dict:
    """สร้างเอกสารจากฟอร์ม — ใช้ไฟล์ตอนดูตัวอย่างถ้าข้อมูล/ตัวเลือกยังเหมือนเดิม ไม่ต้องเปิด Word ซ้ำ"""
    dt = registry.get(doctype)
    values = values or {}
    chosen = Path(settings["outdir"]) if settings.get("dest") == "folder" and settings.get("outdir") else None
    outdir, fmt = chosen or DOWNLOADS, settings.get("format")
    opts = settings["options"].get(doctype, {})
    check = form_check(doctype, values)
    if check["errors"]:
        return {"ok": False, "error": "กรอกข้อมูลให้ครบ/ถูกต้องก่อน: " + ", ".join(
            f.get("label", k) for k in check["errors"] for f in form_fields(dt) if f["key"] == k),
            "notes": [], "outputs": [], "docx": ""}
    c = preview_cache.get(f"form:{doctype}")
    r = None
    if c and c["result"].get("ok") and c["sig"] == form_sig(doctype, values, opts):
        r = copy_cached(c["result"], outdir, fmt)
    if not r:
        outdir.mkdir(parents=True, exist_ok=True)
        r = dt.convert_form(values, opts, "both" if fmt == "both" else fmt == "pdf", outdir, log=lambda m: None)
    out = pack(r)
    if out["ok"]:
        remember_form(doctype, values)
    return out


def remember_form(doctype: str, values: dict):
    """จำค่าช่องที่ประเภทเอกสารกำหนด remember (เช่น ชื่อ/ตำแหน่งผู้เสนอ) ไว้เติมครั้งหน้า — เฉพาะเครื่องนี้"""
    keep = {f["key"]: values.get(f["key"], "") for f in form_fields(registry.get(doctype)) if f.get("remember")}
    if keep:
        s = load_settings()
        mem = dict(s.get("form_memory") or {})
        mem[doctype] = {**mem.get(doctype, {}), **keep}
        s["form_memory"] = mem
        save_settings(s)


def form_prefill(doctype: str, path: Path) -> dict:
    r = registry.get(doctype).prefill_form(Path(path))
    return {"values": r.get("values") or {}, "notes": r.get("notes") or [], "error": r.get("error") or ""}


def drop_preview(iid: str):
    c = preview_cache.pop(iid, None)
    if c:
        shutil.rmtree(c["dir"].parent, ignore_errors=True)
    for k in [k for k, (owner, _) in preview_files.items() if owner == iid]:
        del preview_files[k]


def is_allowed(p: Path) -> bool:
    return p in allowed or p.parent in allowed and p.suffix.lower() in (".docx", ".pdf", ".doc")


REQUIRED_LIBS = {"pymupdf": "pymupdf", "PIL": "pillow"}     # ชื่อที่ import -> ชื่อที่ pip


def missing_libs() -> list:
    import importlib.util
    return [pip for mod, pip in REQUIRED_LIBS.items() if importlib.util.find_spec(mod) is None]


def init_payload() -> dict:
    s = load_settings()
    initial = [register(p, "path", d) for p, d in collect(FILES, s["doctype"])]
    if initial and initial[0]["doctype"] != s["doctype"]:     # เปิดพร้อมไฟล์ -> ไปที่ประเภทเอกสารของไฟล์นั้น
        s = update_settings({"doctype": initial[0]["doctype"]})
    return {"settings": s, "doctypes": [d.manifest() for d in registry.all_doctypes()],
            "load_errors": {k: v.strip().splitlines()[-1] for k, v in registry.errors.items()},
            "missing_libs": missing_libs(), "version": update.read_version()["version"], "python": sys.executable.replace("pythonw.exe", "python.exe"),
            "items": initial, "downloads": str(DOWNLOADS),
            "downloads_new": {d.id: len(new_in_downloads(d.id)) for d in registry.all_doctypes() if d.downloads}}


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code=200, body=b"", ctype="application/json; charset=utf-8", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _authorized(self, query) -> bool:
        return secrets.compare_digest(self.headers.get("X-Token") or query.get("token", [""])[0], TOKEN)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            html = (WEB / "index.html").read_text(encoding="utf-8").replace("{{TOKEN}}", TOKEN)
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if url.path == "/icon.png":
            return self._send(200, (ASSETS / "app_icon.png").read_bytes(), "image/png")
        q = parse_qs(url.query)
        if not self._authorized(q):
            return self._json({"error": "forbidden"}, 403)
        last_ping[0] = time.time()
        if url.path == "/api/init":
            return self._json(init_payload())
        if url.path.startswith("/preview/"):
            f = preview_files.get(url.path.split("/")[2], ("", None))[1]      # /preview/<รหัส>/<ชื่อไฟล์>.pdf
            if not f or not f.exists():
                return self._json({"error": "not found"}, 404)
            return self._send(200, f.read_bytes(), "application/pdf",
                              {"Content-Disposition": f"inline; filename*=UTF-8''{quote(f.name)}"})
        if url.path == "/api/downloads_count":
            return self._json({"count": len(new_in_downloads(q.get("doctype", [""])[0]))})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if not self._authorized(q):
            return self._json({"error": "forbidden"}, 403)
        last_ping[0] = time.time()
        n = int(self.headers.get("Content-Length") or 0)
        if url.path in ("/api/upload_raw", "/api/form/prefill_raw"):   # ไฟล์ที่ลากมาวาง: รับเป็นไบต์ตรง ๆ (ไฟล์ใหญ่ไม่กินหน่วยความจำ)
            try:
                if url.path == "/api/form/prefill_raw":          # วางไฟล์บนฟอร์ม -> เติมช่องให้อัตโนมัติ (ไม่เพิ่มเป็นรายการ)
                    doctype = q.get("doctype", [""])[0]
                    return self._json(form_prefill(doctype, self.save_upload(q, n, doctype)))
                return self._json(self.upload_raw(q, n))
            except Exception as e:
                return self._json({"error": str(e)}, 500)
        try:
            data = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except ValueError:
            return self._json({"error": "bad json"}, 400)
        try:
            return self._json(self.route(url.path, data))
        except Exception as e:  # ส่งข้อผิดพลาดกลับไปแสดงบนหน้าจอ
            return self._json({"error": str(e)}, 500)

    def upload_raw(self, q, n: int) -> dict:
        doctype = q.get("doctype", [""])[0]
        return {"item": register(self.save_upload(q, n, doctype), "upload", doctype)}

    def save_upload(self, q, n: int, doctype: str) -> Path:
        registry.get(doctype)
        name = Path(q.get("name", ["file"])[0] or "file").name
        d = UPLOADS / uuid.uuid4().hex[:8]
        d.mkdir(parents=True, exist_ok=True)
        with open(d / name, "wb") as f:
            left = n
            while left > 0:
                chunk = self.rfile.read(min(left, 1 << 20))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        return d / name

    def route(self, path, data):
        doctype = data.get("doctype") or ""
        if path == "/api/ping":
            return {"ok": True}
        if path == "/api/update/check":
            return update.check()
        if path == "/api/update/apply":
            with jobs_lock:
                if jobs_running[0]:
                    raise ValueError("กำลังแปลงไฟล์อยู่ — รอให้เสร็จก่อนแล้วค่อยกดอัปเดต")
                jobs_running[0] += 1          # กันไม่ให้เริ่มแปลงไฟล์ระหว่างอัปเดต
            try:
                r = update.apply(log=lambda m: None)
            finally:
                with jobs_lock:
                    jobs_running[0] -= 1
            relaunch = "--serve" not in sys.argv
            if relaunch:
                threading.Timer(1.0, relaunch_app).start()
            return {**r, "relaunch": relaunch}
        if path == "/api/pick_files":
            picker = registry.get(doctype).pickers.get(data.get("pick"), {})
            return {"items": [register(Path(p), "path", doctype) for p in ask("files", str(DOWNLOADS), picker)]}
        if path == "/api/pick_folder":
            s = load_settings()
            return {"path": ask("folder", s.get("outdir") or str(DOWNLOADS)) or ""}
        if path == "/api/downloads":
            return {"items": [register(p, "path", doctype) for p in new_in_downloads(doctype)]}
        if path == "/api/remove":
            for i in data.get("ids", []):
                items.pop(i, None)
                with preview_lock:
                    drop_preview(i)
            return {"ok": True}
        if path == "/api/settings":
            return {"settings": update_settings(data)}
        if path == "/api/preview":
            with job():
                return preview(doctype, data.get("id") or "", data.get("options") or {}, data.get("extra") or {},
                               data.get("companions") or [])
        if path == "/api/convert":
            s = load_settings()
            patch = data.get("settings", {})
            s.update({k: v for k, v in patch.items() if k in DEFAULT_SETTINGS and k != "options"})
            for dt_id, o in (patch.get("options") or {}).items():
                s["options"][dt_id] = {**s["options"].get(dt_id, {}), **o}
            with job():
                return {"results": convert(doctype, data.get("ids", []), s, data.get("extra") or {},
                                           data.get("companions") or [])}
        if path == "/api/form/check":
            return form_check(doctype, data.get("values") or {})
        if path == "/api/form/preview":
            with job():
                return form_preview(doctype, data.get("values") or {}, data.get("options") or {})
        if path == "/api/form/convert":
            s = load_settings()
            patch = data.get("settings", {})
            s.update({k: v for k, v in patch.items() if k in ("format", "dest", "outdir")})
            for dt_id, o in (patch.get("options") or {}).items():
                s["options"][dt_id] = {**s["options"].get(dt_id, {}), **o}
            with job():
                return form_convert(doctype, data.get("values") or {}, s)
        if path == "/api/form/prefill_pick":
            pre = (registry.get(doctype).ui.get("form") or {}).get("prefill") or {}
            pats = " ".join("*" + e for e in pre.get("accept") or [".pdf"])
            picked = ask("files", str(DOWNLOADS), {"title": pre.get("label", "เลือกไฟล์"),
                                                   "filters": [(pre.get("label", "ไฟล์"), pats), ("ทุกไฟล์", "*.*")]})
            return form_prefill(doctype, picked[0]) if picked else {"values": {}, "notes": [], "error": ""}
        if path in ("/api/open", "/api/reveal"):
            p = Path(data.get("path") or "")
            if not p.exists() or not is_allowed(p):
                raise ValueError("ไม่อนุญาตให้เปิดไฟล์นี้")
            if path == "/api/open":
                os.startfile(p)
            elif p.is_dir():
                os.startfile(p)
            else:
                subprocess.Popen(f'explorer /select,"{p}"')
            return {"ok": True}
        raise ValueError("ไม่รู้จักคำสั่ง")


# ---------- เปิดหน้าต่าง ----------
def find_edge():
    for env in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base and (p := Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe").exists():
            return p
    return None


class job:
    """นับงานแปลง/ดูตัวอย่างที่กำลังทำ (with job(): ...) — ระหว่างอัปเดตจะไม่รับงานใหม่"""
    def __enter__(self):
        with jobs_lock:
            jobs_running[0] += 1

    def __exit__(self, *exc):
        with jobs_lock:
            jobs_running[0] -= 1


def remember_install():
    """จำตำแหน่งโปรแกรมนี้ (และ Python ที่ใช้) ให้ตัวอัปเดตแบบ manual หาเจอเสมอ — %LOCALAPPDATA%/as-document/installs.json"""
    try:
        known = json.loads(INSTALLS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        known = []
    me = {"dir": str(BASE), "python": sys.executable.replace("pythonw.exe", "python.exe"),
          "version": update.read_version()["version"], "seen": time.strftime("%Y-%m-%d %H:%M")}
    known = [me] + [k for k in known if isinstance(k, dict) and k.get("dir") != me["dir"] and Path(k.get("dir", "")).exists()]
    try:
        INSTALLS_FILE.parent.mkdir(parents=True, exist_ok=True)
        INSTALLS_FILE.write_text(json.dumps(known[:10], ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def relaunch_app():
    """หลังอัปเดต: เปิดโปรแกรมรุ่นใหม่ (หน้าต่างใหม่) แล้วให้ตัวนี้ปิดเอง"""
    pyw = Path(sys.executable).with_name("pythonw.exe")
    subprocess.Popen([str(pyw if pyw.exists() else sys.executable), str(BASE / "app.py")], cwd=str(BASE))
    restart.set()


def app_window_open() -> bool:
    return bool(ctypes.windll.user32.FindWindowW(None, APP_WINDOW_TITLE))


def main():
    shutil.rmtree(PREVIEWS, ignore_errors=True)       # ตัวอย่างที่ค้างจากครั้งก่อน
    reset_checks()
    remember_install()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    if "--serve" in sys.argv:   # สำหรับทดสอบ: เปิดเซิร์ฟเวอร์อย่างเดียว
        print(url, flush=True)
        threading.Event().wait()

    edge = find_edge()
    if edge:
        subprocess.Popen([str(edge), f"--app={url}", "--window-size=1180,900"])
    else:
        webbrowser.open(url)
    # อยู่จนกว่าหน้าต่างแอปจะปิด (ตรวจจากชื่อหน้าต่าง) หรือหน้าเว็บหยุดส่งสัญญาณนาน
    last_ping[0] = time.time()
    seen = False
    while not restart.wait(3):
        if app_window_open():
            seen = True
            continue
        idle = time.time() - last_ping[0]
        if (seen and idle > 10) or idle > 150:
            break
    server.shutdown()


if __name__ == "__main__":
    main()
