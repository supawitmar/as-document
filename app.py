# -*- coding: utf-8 -*-
"""
หน้าโปรแกรม "ระบบปรับเอกสาร บฑ.31" แบบเว็บ (เปิดเป็นหน้าต่างแอปของ Microsoft Edge)
ทำงานในเครื่องเท่านั้น: เซิร์ฟเวอร์ฟังที่ 127.0.0.1 และทุกคำขอต้องมี token
"""
import base64
import ctypes
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import bt31
import fix_letters as fx

WEB = fx.BASE / "web"
DOWNLOADS = Path.home() / "Downloads"
SETTINGS_FILE = fx.BASE / "settings.json"
HISTORY_FILE = fx.BASE / "converted.json"
UPLOADS = Path(tempfile.gettempdir()) / "fixletters_uploads"
TOKEN = secrets.token_urlsafe(16)
APP_WINDOW_TITLE = "ระบบปรับเอกสาร บฑ.31"   # ต้องตรงกับ <title> ใน web/index.html
DEFAULT_SETTINGS = {"pdf": True, "dest": "same", "outdir": "", "want_approve": False, "mode": "export"}

items = {}          # id -> {"path": Path, "origin": "path"|"upload"}
allowed = set()     # ไฟล์/โฟลเดอร์ที่อนุญาตให้เปิดจากหน้าเว็บ
dialog_lock = threading.Lock()
last_ping = [0.0]
FILES = [a for a in sys.argv[1:] if not a.startswith("--")]


# ---------- ข้อมูล ----------
def load_settings() -> dict:
    try:
        return {**DEFAULT_SETTINGS, **json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return dict(DEFAULT_SETTINGS)


def save_settings(s: dict):
    clean = {k: s.get(k, v) for k, v in DEFAULT_SETTINGS.items()}
    SETTINGS_FILE.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def register(path: Path, origin: str) -> dict:
    path = path.resolve()
    for iid, it in items.items():
        if it["path"] == path:
            return describe(iid)
    iid = uuid.uuid4().hex[:10]
    items[iid] = {"path": path, "origin": origin}
    if origin == "path":
        allowed.add(path.parent)
    return describe(iid)


def describe(iid: str) -> dict:
    it = items[iid]
    info = bt31.inspect(it["path"]) if is_pdf(it["path"]) else fx.inspect(it["path"])
    folder = str(it["path"].parent) if it["origin"] == "path" else ""
    return {"id": iid, "name": it["path"].name, "origin": it["origin"], "folder": folder, **info}


def is_pdf(p: Path) -> bool:
    return p.suffix.lower() == ".pdf"


def converted_log() -> set:
    """ไฟล์ Export ที่เคยแปลงแล้ว (path + เวลาแก้ไข) — ชื่อไฟล์ผลลัพธ์ไม่ได้อ้างชื่อต้นฉบับ จึงต้องจดไว้"""
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


def new_in_downloads(days: int = 3) -> list:
    """ไฟล์ Export*.doc ใน Downloads ที่ดาวน์โหลดภายใน 3 วันและยังไม่เคยแปลง (ใหม่สุดก่อน)"""
    done = converted_log()
    since = time.time() - days * 86400
    new = [p for p in DOWNLOADS.glob("Export*.doc") if p.stat().st_mtime >= since and source_key(p) not in done]
    return sorted(new, key=lambda p: p.stat().st_mtime, reverse=True)


def ask(kind: str, initial: str):
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
                    parent=root, title="เลือกไฟล์ Export", initialdir=initial,
                    filetypes=[("ไฟล์ Export", "*.doc *.htm *.html"), ("ทุกไฟล์", "*.*")]))
            if kind == "pdf":
                return list(filedialog.askopenfilenames(
                    parent=root, title="เลือกไฟล์ PDF หน้า บฑ.31", initialdir=initial,
                    filetypes=[("PDF หน้า บฑ.31", "*.pdf"), ("ทุกไฟล์", "*.*")]))
            return filedialog.askdirectory(parent=root, title="เลือกโฟลเดอร์สำหรับบันทึกไฟล์", initialdir=initial)
        finally:
            root.destroy()


def convert(ids: list, settings: dict, extra: dict = None) -> dict:
    chosen = Path(settings["outdir"]) if settings.get("dest") == "folder" and settings.get("outdir") else None
    sel = [(i, items[i]) for i in ids if i in items]
    out = {}
    # PDF หน้า บฑ.31: สร้างหนังสือจากข้อมูลในแบบฟอร์ม
    for i, it in [(i, it) for i, it in sel if is_pdf(it["path"])]:
        dest = chosen or (it["path"].parent if it["origin"] == "path" else DOWNLOADS)
        r = bt31.convert(it["path"], outdir=dest, pdf=settings.get("pdf"), want_approve=settings.get("want_approve"),
                         en=(extra or {}).get(i), log=lambda m: None)
        outputs = [{k: str(o[k]) if o[k] else "" for k in ("kind", "docx", "pdf")} for o in r["outputs"]]
        for o in outputs:
            for f in (o["docx"], o["pdf"]):
                if f:
                    allowed.update({Path(f), Path(f).parent})
        out[i] = {"ok": r["ok"], "error": r["error"], "notes": r["notes"], "outputs": outputs,
                  "docx": next((o["docx"] for o in outputs if o["docx"]), ""), "pdf": "", "doc": ""}
    sel = [(i, it) for i, it in sel if not is_pdf(it["path"])]
    # เรียนรู้ชื่อวิชาภาษาอังกฤษจากทุกไฟล์ก่อน เผื่อแยกแปลงหลายกลุ่ม
    courses = fx.load_courses()
    for _, it in sel:
        try:
            fx.learn_course(fx.parse(fx.read_source(it["path"])), courses)
        except OSError:
            pass
    fx.save_courses(courses)

    groups = {}
    for i, it in sel:
        dest = chosen or (it["path"].parent if it["origin"] == "path" else DOWNLOADS)
        groups.setdefault(dest, []).append(i)
    for dest, gids in groups.items():
        by_path = {items[i]["path"]: i for i in gids}
        # ไม่ติ๊ก "ต้องการหนังสือขออนุมัติ" = ไม่ต้องขออนุมัติผู้บังคับบัญชา -> ตัดประโยคแจ้งผู้บังคับบัญชาในหนังสือเชิญ
        results = fx.convert(list(by_path), outdir=dest, pdf=settings.get("pdf"),
                             log=lambda m: None, inform_supervisor=bool(settings.get("want_approve")))
        for r in results:
            iid = by_path.get(Path(r["src"]).resolve())
            if not iid:
                continue
            files = {k: str(r[k]) if r[k] else "" for k in ("docx", "pdf", "doc")}
            for f in files.values():
                if f:
                    allowed.add(Path(f))
                    allowed.add(Path(f).parent)
            out[iid] = {"ok": bool(r["docx"]), "error": r["error"], "notes": r["notes"], **files}
    remember_converted([items[i]["path"] for i, r in out.items() if r["ok"] and items[i]["origin"] == "path"])
    return out


def is_allowed(p: Path) -> bool:
    return p in allowed or p.parent in allowed and p.suffix.lower() in (".docx", ".pdf", ".doc")


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code=200, body=b"", ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
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
            return self._send(200, (fx.ASSETS / "app_icon.png").read_bytes(), "image/png")
        q = parse_qs(url.query)
        if not self._authorized(q):
            return self._json({"error": "forbidden"}, 403)
        last_ping[0] = time.time()
        if url.path == "/api/init":
            initial = [register(p, "path") for p in fx.collect(FILES)]
            return self._json({"settings": load_settings(), "items": initial,
                               "downloads_new": len(new_in_downloads()), "downloads": str(DOWNLOADS)})
        if url.path == "/api/downloads_count":
            return self._json({"count": len(new_in_downloads())})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if not self._authorized(q):
            return self._json({"error": "forbidden"}, 403)
        last_ping[0] = time.time()
        n = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except ValueError:
            return self._json({"error": "bad json"}, 400)
        try:
            return self._json(self.route(url.path, data))
        except Exception as e:  # ส่งข้อผิดพลาดกลับไปแสดงบนหน้าจอ
            return self._json({"error": str(e)}, 500)

    def route(self, path, data):
        if path == "/api/ping":
            return {"ok": True}
        if path == "/api/pick_files":
            kind = "pdf" if data.get("type") == "pdf" else "files"
            return {"items": [register(Path(p), "path") for p in ask(kind, str(DOWNLOADS))]}
        if path == "/api/pick_folder":
            s = load_settings()
            return {"path": ask("folder", s.get("outdir") or str(DOWNLOADS)) or ""}
        if path == "/api/downloads":
            return {"items": [register(p, "path") for p in new_in_downloads()]}
        if path == "/api/upload":
            name = Path(data.get("name") or "file.doc").name
            d = UPLOADS / uuid.uuid4().hex[:8]
            d.mkdir(parents=True, exist_ok=True)
            (d / name).write_bytes(base64.b64decode(data.get("data") or ""))
            return {"item": register(d / name, "upload")}
        if path == "/api/remove":
            for i in data.get("ids", []):
                items.pop(i, None)
            return {"ok": True}
        if path == "/api/settings":
            s = {**load_settings(), **data}
            save_settings(s)
            return {"settings": load_settings()}
        if path == "/api/convert":
            s = {**load_settings(), **data.get("settings", {})}
            return {"results": convert(data.get("ids", []), s, data.get("extra") or {})}
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


def app_window_open() -> bool:
    return bool(ctypes.windll.user32.FindWindowW(None, APP_WINDOW_TITLE))


def main():
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
        subprocess.Popen([str(edge), f"--app={url}", "--window-size=1180,860"])
    else:
        webbrowser.open(url)
    # อยู่จนกว่าหน้าต่างแอปจะปิด (ตรวจจากชื่อหน้าต่าง) หรือหน้าเว็บหยุดส่งสัญญาณนาน
    last_ping[0] = time.time()
    seen = False
    while True:
        time.sleep(3)
        if app_window_open():
            seen = True
            continue
        idle = time.time() - last_ping[0]
        if (seen and idle > 10) or idle > 150:
            break
    server.shutdown()


if __name__ == "__main__":
    main()
