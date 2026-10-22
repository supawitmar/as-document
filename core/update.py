# -*- coding: utf-8 -*-
"""
อัปเดตจาก GitHub — เครื่องที่ติดตั้งแล้วได้ประเภทเอกสารใหม่/แก้รูปแบบ โดยไม่ต้องติดตั้งใหม่
(หลักการเดียวกับระบบตรวจเล่ม e-thesis checker)

**ติดตั้งเฉพาะรุ่นที่ออกแล้ว:** ทุกรุ่นมีป้าย (git tag) `v<เลข>` ที่ tools/release.py ติดให้ — เครื่องผู้ใช้ดาวน์โหลด
ZIP ของป้ายนั้น ไม่ใช่ของ branch main ตรง ๆ งานที่ push ขึ้น main แต่ยังไม่ออกรุ่นจึงไม่ลงเครื่องที่ใช้งาน

ผู้พัฒนา: ออกรุ่นด้วย `python tools/release.py "หัวข้อ" -i "รายละเอียด" ...` (version.json + CHANGELOG.md + ป้าย v<เลข>
           + โฟลเดอร์ "อัปเดต version 1.x") แล้ว push เมื่อเจ้าของสั่ง: `python tools/release.py --push`
เครื่องผู้ใช้อัปเดตได้ 3 ทาง (ทุกทางติดตั้งด้วย apply_tree ของ "รุ่นใหม่" — ตัวติดตั้งรุ่นเก่าไม่ต้องรู้จักไฟล์ใหม่):
    1. ในโปรแกรม: เช็กตอนเปิด (จำผล 30 นาที) ถ้ามีรุ่นที่ออกแล้วใหม่กว่า แสดงแถบ "มีอัปเดตใหม่" → อัปเดตเลย
    2. ดับเบิลคลิก `อัปเดตระบบปรับเอกสาร.bat` ในโฟลเดอร์โปรแกรม (ไม่ต้องเปิดโปรแกรม)
    3. แบบ manual ไม่ต้องใช้อินเทอร์เน็ต: โฟลเดอร์ "อัปเดต version 1.x" (คลิกเพื่ออัปเดต…bat) หรือแตก ZIP ของรุ่นนั้น
       (เช่นจาก GitHub) แล้วดับเบิลคลิก `ติดตั้งอัปเดตจากโฟลเดอร์นี้.bat` — tools/package/update.ps1 หาโปรแกรมในเครื่องเอง
    (บรรทัดคำสั่ง: python -m core.update [--check] [--zip ไฟล์.zip] [--fetch โฟลเดอร์])
เลขเวอร์ชันที่ผู้ใช้เห็นคือ "version" (1.0, 1.1, 1.1.1 …) — โปรแกรมเทียบรุ่นด้วย "build" (เลขจำนวนเต็ม เพิ่มทีละ 1)
รุ่นที่ติดตั้งอยู่บันทึกใน .update/installed.json (รุ่น, ป้าย, ติดตั้งจากไหน, เวลา)

สิ่งที่ไม่ถูกเขียนทับ:
    - ไฟล์เฉพาะเครื่อง (LOCAL_ONLY): settings.json, converted.json, translations.json, samples/, ไอคอน .lnk
    - ไฟล์ข้อมูล doctypes/*/data/*.json: รวมแบบ 3 ทาง — เทียบกับฉบับที่ติดตั้งครั้งก่อน (.update/base/)
      ค่าที่เครื่องนี้แก้/เรียนรู้เองชนะ, ค่าที่ผู้พัฒนาแก้ในรุ่นใหม่ก็ได้มาด้วย
ไฟล์ที่รุ่นก่อนหน้าติดตั้งแต่รุ่นใหม่ไม่มีแล้ว จะถูกลบ (เฉพาะไฟล์ที่อยู่ในรายการติดตั้งของรุ่นก่อน)
เครื่องพัฒนา (มีโฟลเดอร์ .git) ไม่อัปเดตด้วยวิธีนี้ — ใช้ git pull
"""
import base64
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from core import BASE, NO_WINDOW

REPO = "supawitmar/as-document"
BRANCH = "main"
VERSION_FILE = BASE / "version.json"
STATE = BASE / ".update"                  # ฉบับที่ติดตั้งครั้งก่อน (base สำหรับรวมข้อมูล) + รายการไฟล์ + รุ่นที่ติดตั้ง
LOCAL_ONLY = ["settings.json", "converted.json", "translations.json", "*/translations.json", "*.migrated",
              "*.lnk", "doctypes/*/samples/*", ".update/*", ".git/*", "__pycache__/*", "*/__pycache__/*",
              "assets/example_*", "dist/*"]
DATA_FILES = ["doctypes/*/data/*.json"]
CHECK_TTL = 30 * 60                      # จำผลเช็กอัปเดต 30 นาที (ไม่ถาม GitHub ทุกครั้งที่เปิดหน้า)
_cache = {"at": 0.0, "result": None}


API = f"https://api.github.com/repos/{REPO}"


def raw_url(path: str, ref: str = BRANCH) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{ref}/{path}"


def tag_of(version: str) -> str:
    return f"v{version}"


def zip_url(version: str) -> str:
    """ZIP ของรุ่นที่ออกแล้ว (ป้าย v<เลข>)"""
    return f"https://github.com/{REPO}/archive/refs/tags/{tag_of(version)}.zip"


# ส่งชื่อโปรแกรมไปกับทุกคำขอ (แบบเดียวกับระบบตรวจเล่ม) — proxy/firewall ขององค์กรบางแห่งบล็อกชื่อเริ่มต้น
# "Python-urllib/3.x" ทำให้เช็กอัปเดตไม่ผ่านทั้งที่เครือข่ายเข้า GitHub ได้ (พบที่เครื่องที่ทำงาน 19 ต.ค. 2569)
HEADERS = {"User-Agent": "as-document-updater (+https://github.com/supawitmar/as-document)"}


def _is_cert_error(e: Exception) -> bool:
    """เครือข่ายองค์กรที่ตรวจการเชื่อมต่อเข้ารหัสด้วยใบรับรองขององค์กร — Python ไม่รู้จักใบรับรองนั้น แต่ Windows รู้จัก"""
    reason = getattr(e, "reason", e)
    return isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(e)


def _fetch_windows(url: str, timeout: float) -> bytes:
    """ดาวน์โหลดด้วยเครื่องมือของ Windows ที่ตรวจใบรับรองแบบเดียวกับเบราว์เซอร์ (curl.exe ของ Windows ใช้ Schannel,
    สำรองด้วย PowerShell) — ใช้เมื่อ Python ตรวจใบรับรองไม่ผ่าน (พบที่เครื่องที่ทำงาน 22 ต.ค. 2569:
    "CERTIFICATE_VERIFY_FAILED unable to get local issuer certificate" ทั้งที่เบราว์เซอร์ใช้เน็ตได้)
    ได้สถานะ 404 -> HTTPError 404 (ให้ latest_release รู้ว่ายังไม่มีป้าย)"""
    with tempfile.TemporaryDirectory(prefix="docfetch_") as t:
        out = Path(t) / "body"
        curl = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "curl.exe"
        if curl.exists():
            base = [str(curl), "-sL", "--max-time", str(int(timeout)), "-A", HEADERS["User-Agent"],
                    "-o", str(out), "-w", "%{http_code}"]
            for extra in (["--ssl-revoke-best-effort"], []):       # curl รุ่นเก่าของ Windows ไม่รู้จักตัวเลือกนี้
                r = subprocess.run(base + extra + [url], capture_output=True, text=True, timeout=timeout + 15, **NO_WINDOW)
                code = r.stdout.strip()[-3:]
                if r.returncode == 0 and code == "200":
                    return out.read_bytes()
                if r.returncode == 0 and code.isdigit():
                    raise urllib.error.HTTPError(url, int(code), f"HTTP {code}", {}, None)
                if r.returncode != 2:                                 # 2 = ไม่รู้จักตัวเลือก -> ลองแบบไม่มี
                    break
        ps = ("$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol = "
              "[Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12; "
              "try { Invoke-WebRequest -UseBasicParsing -Uri $env:DOC_URL -OutFile $env:DOC_OUT "
              "-UserAgent $env:DOC_UA -TimeoutSec $env:DOC_T; exit 0 } "
              "catch { $c = 0; if ($_.Exception.Response) { $c = [int]$_.Exception.Response.StatusCode }; "
              "Write-Output $c; exit 1 }")
        env = {**os.environ, "DOC_URL": url, "DOC_OUT": str(out), "DOC_UA": HEADERS["User-Agent"], "DOC_T": str(int(timeout))}
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                           text=True, env=env, timeout=timeout + 30, **NO_WINDOW)
        if r.returncode == 0 and out.exists():
            return out.read_bytes()
        code = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        if code.isdigit() and int(code) >= 400:
            raise urllib.error.HTTPError(url, int(code), f"HTTP {code}", {}, None)
        raise RuntimeError("ดาวน์โหลดไม่สำเร็จทั้งผ่าน Python และเครื่องมือของ Windows: " + (r.stderr or r.stdout).strip()[-200:])


def _fetch(url: str, timeout: float) -> bytes:
    """ดาวน์โหลด url — ใช้ Python ก่อน ถ้าใบรับรองขององค์กรทำให้ไม่ผ่าน ใช้เครื่องมือของ Windows แทน"""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout) as r:
            return r.read()
    except Exception as e:
        if not _is_cert_error(e):
            raise
        return _fetch_windows(url, timeout)


def _get_json(url: str, timeout: float):
    return json.loads(_fetch(url, timeout).decode("utf-8"))


def version_label(build: int, version: str = "") -> str:
    """เลขเวอร์ชันที่แสดง: ใช้ "version" ใน version.json ถ้ามี — รุ่นก่อนมีเลขเวอร์ชันนับ build 1 = 1.0"""
    return version or (f"1.{build - 1}" if build >= 1 else "ก่อน 1.0")


def read_version(path: Path = VERSION_FILE) -> dict:
    try:
        v = json.loads(Path(path).read_text(encoding="utf-8"))
        build = int(v.get("build", 0))
        return {"build": build, "version": version_label(build, v.get("version", "")), "date": v.get("date", ""),
                "changes": v.get("changes", [])}
    except (OSError, ValueError, TypeError):
        return {"build": 0, "version": version_label(0), "date": "", "changes": []}


def is_dev_checkout() -> bool:
    return (BASE / ".git").exists()


def _tag_key(name: str):
    m = re.match(r"^v(\d+(?:\.\d+)*)$", name)
    return tuple(int(x) for x in m.group(1).split(".")) + (0,) * 3 if m else None


def _latest_from_api(cur_build: int, timeout: float):
    """ถามรายการป้ายจาก GitHub API (api.github.com) แบบเดียวกับระบบตรวจเล่ม แล้วอ่าน version.json ของป้ายใหม่สุด"""
    data = _get_json(f"{API}/tags?per_page=100", timeout)
    tags = sorted((t["name"] for t in data if isinstance(t, dict) and _tag_key(str(t.get("name", "")))),
                  key=_tag_key, reverse=True)
    for tag in tags[:5]:
        try:
            got = _get_json(f"{API}/contents/version.json?ref={tag}", timeout)
        except urllib.error.HTTPError as e:
            if e.code == 404:                  # ป้ายก่อนมี version.json
                continue
            raise
        v = json.loads(base64.b64decode(got["content"]).decode("utf-8"))
        return v if int(v.get("build", 0)) > cur_build else None
    return None


def latest_release(cur_build: int, timeout: float = 6):
    """รุ่นล่าสุดที่ "ออกแล้ว" (มีป้าย v<เลข> บน GitHub) และใหม่กว่า cur_build — ไม่มี = None
    ถาม GitHub API ก่อน ไม่ได้ (เช่นเกินโควตา 60 ครั้ง/ชม.) ค่อยอ่าน raw.githubusercontent.com — เครือข่ายที่ทำงาน
    ตรวจ/บล็อก raw.githubusercontent.com (Python: ใบรับรองไม่ผ่าน, curl: HTTP 403 — 22 ต.ค. 2569)
    แต่ api.github.com และ github.com ผ่าน (ระบบตรวจเล่มที่ใช้ API จึงขึ้นแถบอัปเดตได้)"""
    try:
        return _latest_from_api(cur_build, timeout)
    except Exception as api_error:
        try:
            return _latest_from_raw(cur_build, timeout)
        except Exception as e:
            raise RuntimeError(f"{e} · GitHub API: {api_error}") from e


def _latest_from_raw(cur_build: int, timeout: float):
    """ดูรายการรุ่นจาก version.json ของ main แล้วยืนยันว่ามีป้ายจริงด้วย version.json ของป้ายนั้น
    (รุ่นที่ commit แล้วแต่ยังไม่ push ป้าย = ยังไม่ออก ข้ามไปดูรุ่นก่อนหน้า)"""
    head = _get_json(raw_url("version.json") + f"?t={int(time.time() // CHECK_TTL)}", timeout)
    cands = [c for c in head.get("changes", []) if int(c.get("build", 0)) > cur_build and c.get("version")]
    for c in sorted(cands, key=lambda c: -int(c["build"]))[:5]:
        try:
            tagged = _get_json(raw_url("version.json", tag_of(c["version"])), timeout)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        if int(tagged.get("build", 0)) > cur_build:
            return tagged
    return None


def check(timeout: float = 6, force: bool = False) -> dict:
    """{'available', 'current', 'latest', 'version', 'latest_version', 'changes': [รุ่นที่ใหม่กว่า], 'dev', 'error'}"""
    if not force and _cache["result"] and time.time() - _cache["at"] < CHECK_TTL:
        return _cache["result"]
    cur = read_version()
    out = {"available": False, "current": cur["build"], "latest": cur["build"], "version": cur["version"],
           "latest_version": cur["version"], "changes": [], "dev": is_dev_checkout(), "error": ""}
    try:
        rel = latest_release(cur["build"], timeout)
    except Exception as e:          # ไม่มีอินเทอร์เน็ต ฯลฯ — ใช้งานต่อได้ตามปกติ (ไม่จำผลที่ผิดพลาด)
        out["error"] = str(e)
        return out
    if rel:
        out["latest"] = int(rel.get("build", 0))
        out["latest_version"] = version_label(out["latest"], rel.get("version", ""))
        out["changes"] = [c for c in rel.get("changes", []) if int(c.get("build", 0)) > cur["build"]]
        out["available"] = not out["dev"]
    _cache.update(at=time.time(), result=out)
    return out


def _match(rel: str, patterns: list) -> bool:
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def merge_data(local, new, base):
    """รวมไฟล์ข้อมูล JSON แบบ 3 ทาง (dict): ค่าที่เครื่องนี้เปลี่ยนจาก base ชนะ ที่เหลือใช้ของรุ่นใหม่"""
    if not isinstance(local, dict) or not isinstance(new, dict):
        return new if local is None or local == base else local
    base = base if isinstance(base, dict) else {}
    merged = dict(new)
    for k, v in local.items():
        if k not in base or base[k] != v:            # เครื่องนี้เพิ่ม/แก้เอง
            merged[k] = v
    for k in base:
        if k not in local and k in merged and merged[k] == base[k]:   # เครื่องนี้ลบเอง (และรุ่นใหม่ไม่ได้แก้)
            del merged[k]
    return merged


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def apply_tree(src: Path, dest: Path = BASE, log=print, source: str = "") -> dict:
    """คัดลอกโปรแกรมจากโฟลเดอร์ src (ที่แตกจาก ZIP) ทับโฟลเดอร์ที่ติดตั้ง dest
    เขียนเฉพาะไฟล์ที่ต่าง · ไม่แตะไฟล์เฉพาะเครื่อง · รวม data/*.json แบบ 3 ทาง · ลบเฉพาะไฟล์ในรายการของรุ่นก่อน"""
    src, dest = Path(src), Path(dest)
    if (dest / ".git").exists():
        raise RuntimeError(f"{dest} เป็นเครื่องพัฒนา (มี .git) — อัปเดตด้วย git pull")
    if src.resolve() == dest.resolve():
        raise RuntimeError("โฟลเดอร์นี้คือโปรแกรมที่ติดตั้งอยู่แล้ว — ใช้ อัปเดตระบบปรับเอกสาร.bat แทน")
    state = dest / STATE.name
    old_manifest = set(_read_json(state / "manifest.json") or [])
    files = [p for p in src.rglob("*") if p.is_file()]
    rels = sorted(p.relative_to(src).as_posix() for p in files)
    installed, merged, changed, removed = [], [], [], []
    req = dest / "requirements.txt"
    req_before = _sha(req) if req.exists() else ""
    for rel in rels:
        if _match(rel, LOCAL_ONLY):
            continue
        s, d = src / rel, dest / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        if _match(rel, DATA_FILES) and d.exists():
            new, local, base = _read_json(s), _read_json(d), _read_json(state / "base" / rel)
            if new is not None and local is not None and local != new:
                result = merge_data(local, new, base)
                sort = isinstance(new, dict) and list(new) == sorted(new)        # คงรูปแบบไฟล์ของรุ่นใหม่
                d.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=sort), encoding="utf-8")
                merged.append(rel)
            elif new is not None and local is None:
                shutil.copy2(s, d)
        elif not d.exists() or _sha(s) != _sha(d):
            shutil.copy2(s, d)
            changed.append(rel)
        installed.append(rel)
        if _match(rel, DATA_FILES):           # เก็บฉบับของรุ่นใหม่ไว้เป็น base ของการรวมครั้งหน้า
            b = state / "base" / rel
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, b)
    for rel in sorted(old_manifest - set(installed)):      # ไฟล์ที่รุ่นใหม่เอาออกแล้ว
        p = dest / rel
        if p.is_file() and not _match(rel, LOCAL_ONLY + DATA_FILES):
            p.unlink()
            removed.append(rel)
            for parent in p.parents:                       # โฟลเดอร์ที่ว่างลงเพราะไฟล์ถูกเอาออก
                if parent == dest or not parent.is_relative_to(dest) or any(parent.iterdir()):
                    break
                parent.rmdir()
    state.mkdir(exist_ok=True)
    (state / "manifest.json").write_text(json.dumps(installed, ensure_ascii=False, indent=0), encoding="utf-8")
    v = read_version(dest / VERSION_FILE.name)
    (state / "installed.json").write_text(json.dumps(
        {"version": v["version"], "build": v["build"], "tag": tag_of(v["version"]), "source": source or str(src),
         "installed_at": dt.datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=2), encoding="utf-8")
    pip = ""
    if req.exists() and _sha(req) != req_before:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--upgrade", "--disable-pip-version-check",
                            "--no-warn-script-location",
                            "-q", "-r", str(req)], capture_output=True, text=True, **NO_WINDOW)
        pip = "" if r.returncode == 0 else (r.stderr or r.stdout).strip()[-300:]
    log(f"อัปเดต {len(changed)} ไฟล์, รวมข้อมูล {len(merged)} ไฟล์, ลบ {len(removed)} ไฟล์")
    return {"changed": changed, "merged": merged, "removed": removed, "pip_error": pip}


def fetch(workdir: Path, zip_path: Path = None, log=print) -> Path:
    """ดาวน์โหลดรุ่นล่าสุดที่ออกแล้ว (หรือใช้ zip_path) แตกไว้ใน workdir คืนโฟลเดอร์โปรแกรมรุ่นใหม่"""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    z = workdir / "src.zip"
    expect = ""
    if zip_path:
        shutil.copy(zip_path, z)
    else:
        rel = latest_release(read_version()["build"])
        if not rel:
            raise RuntimeError(f"เป็นรุ่นล่าสุดที่ออกแล้ว (version {read_version()['version']})")
        expect = version_label(int(rel.get("build", 0)), rel.get("version", ""))
        log(f"กำลังดาวน์โหลด version {expect}…")
        z.write_bytes(_fetch(zip_url(expect), 120))
    with zipfile.ZipFile(z) as zf:
        zf.extractall(workdir / "x")
    roots = [p for p in (workdir / "x").iterdir() if p.is_dir()]
    if len(roots) != 1 or not (roots[0] / "app.py").exists() or not (roots[0] / "core" / "update.py").exists():
        raise RuntimeError("ไฟล์อัปเดตไม่ถูกต้อง (ไม่พบ app.py / core/update.py)")
    got = read_version(roots[0] / VERSION_FILE.name)["version"]
    if expect and got != expect:
        raise RuntimeError(f"ไฟล์ที่ดาวน์โหลดเป็น version {got} ไม่ใช่ {expect}")
    return roots[0]


def install_with_new(tree: Path, dest: Path = BASE, source: str = "") -> dict:
    """ติดตั้งด้วยตัวอัปเดตของรุ่นใหม่ (python -m core.update --tree ในโฟลเดอร์รุ่นใหม่) — ตัวติดตั้งรุ่นเก่า
    ไม่ต้องรู้จักไฟล์/กฎใหม่ของรุ่นถัดไป"""
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "core.update", "--tree", str(tree), "--dest", str(dest),
                        "--source", source, "--json"], cwd=str(tree), capture_output=True, text=True, encoding="utf-8", **NO_WINDOW)
    line = next((ln for ln in reversed(r.stdout.splitlines()) if ln.startswith("{")), "")
    if r.returncode or not line:
        raise RuntimeError((r.stderr or r.stdout).strip()[-400:] or "ตัวอัปเดตของรุ่นใหม่ทำงานไม่สำเร็จ")
    return json.loads(line)


def apply(zip_path: Path = None, log=print) -> dict:
    """ดาวน์โหลดรุ่นล่าสุดที่ออกแล้ว (หรือใช้ zip_path) แล้วติดตั้งทับ — คืนผล apply_tree + รุ่นใหม่"""
    if is_dev_checkout():
        raise RuntimeError("เครื่องนี้เป็นเครื่องพัฒนา (มี .git) — อัปเดตด้วย git pull")
    with tempfile.TemporaryDirectory(prefix="docupdate_") as t:
        tree = fetch(Path(t), zip_path, log=log)
        tag = tag_of(read_version(tree / VERSION_FILE.name)["version"])
        res = install_with_new(tree, BASE, source=str(zip_path) if zip_path else f"GitHub {tag}")
    _cache.update(at=0.0, result=None)
    return res


def main(argv=None) -> int:
    import argparse
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="อัปเดตโปรแกรมจาก GitHub (เฉพาะรุ่นที่ออกแล้ว)")
    ap.add_argument("--zip", help="ใช้ไฟล์ ZIP ที่ดาวน์โหลดไว้แล้ว (แทนการดาวน์โหลด)")
    ap.add_argument("--tree", help="ใช้โฟลเดอร์ที่แตก ZIP ไว้แล้ว (update.ps1 / get.ps1 ใช้)")
    ap.add_argument("--dest", help="โฟลเดอร์ที่ติดตั้ง (ใช้กับ --tree; ค่าเริ่มต้น = โฟลเดอร์ของโปรแกรมนี้)")
    ap.add_argument("--check", action="store_true", help="เช็กอย่างเดียว")
    ap.add_argument("--fetch", metavar="DIR", help="ดาวน์โหลดรุ่นล่าสุดที่ออกแล้วแตกไว้ใน DIR แล้วพิมพ์ path (update.ps1 ใช้)")
    ap.add_argument("--source", default="", help="บันทึกว่าติดตั้งจากไหน (ลง .update/installed.json)")
    ap.add_argument("--json", action="store_true", help="พิมพ์ผลเป็น JSON บรรทัดสุดท้าย")
    args = ap.parse_args(argv)
    if args.check:
        print(json.dumps(check(force=True), ensure_ascii=False, indent=2))
        return 0
    if args.fetch:
        try:
            print(fetch(Path(args.fetch), Path(args.zip) if args.zip else None))
        except RuntimeError as e:
            print(f"!! {e}")
            return 3
        return 0
    if args.tree:
        dest = Path(args.dest) if args.dest else BASE
        r = apply_tree(Path(args.tree), dest, source=args.source)
        v = read_version(dest / VERSION_FILE.name)          # อ่านหลังติดตั้ง = รุ่นใหม่
        r.update(build=v["build"], version=v["version"])
    else:
        r = apply(Path(args.zip) if args.zip else None)
    if args.json:
        print(json.dumps(r, ensure_ascii=False))
        return 0
    print(f"version {r['version']} (build {r['build']}): อัปเดต {len(r['changed'])} ไฟล์, "
          f"รวมข้อมูล {len(r['merged'])}, ลบ {len(r['removed'])}")
    if r["pip_error"]:
        print("!! ติดตั้งไลบรารีไม่สำเร็จ:", r["pip_error"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
