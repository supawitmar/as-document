# -*- coding: utf-8 -*-
"""
อัปเดต (patch) จาก GitHub — เครื่องที่ติดตั้งแล้วได้ประเภทเอกสารใหม่/แก้รูปแบบ โดยไม่ต้องติดตั้งใหม่

ผู้พัฒนา: ปล่อยรุ่นใหม่ด้วย `python tools/release.py "หัวข้อ" -i "รายละเอียด" ...`
           (เพิ่ม version 1.x + build ใน version.json, commit, push และสร้างโฟลเดอร์ "อัปเดต version 1.x")
เครื่องผู้ใช้อัปเดตได้ 2 ทาง (ใช้ apply_tree ตัวเดียวกัน):
    1. ในโปรแกรม: เช็ก version.json บน GitHub ตอนเปิด ถ้า build ใหม่กว่า แสดงแถบ "มีอัปเดตใหม่" → อัปเดตเลย
    2. โฟลเดอร์ "อัปเดต version 1.x" (ไม่ต้องใช้อินเทอร์เน็ต): ดับเบิลคลิกไฟล์ "คลิกเพื่ออัปเดต…" (tools/package/update.ps1)
    (หรือบรรทัดคำสั่ง: python -m core.update [--zip ไฟล์.zip])
เลขเวอร์ชันที่ผู้ใช้เห็นคือ "version" (1.0, 1.1, …) — โปรแกรมเทียบรุ่นด้วย "build" (เลขจำนวนเต็ม เพิ่มทีละ 1)

สิ่งที่ไม่ถูกเขียนทับ:
    - ไฟล์เฉพาะเครื่อง (LOCAL_ONLY): settings.json, converted.json, translations.json, samples/, ไอคอน .lnk
    - ไฟล์ข้อมูล doctypes/*/data/*.json: รวมแบบ 3 ทาง — เทียบกับฉบับที่ติดตั้งครั้งก่อน (.update/base/)
      ค่าที่เครื่องนี้แก้/เรียนรู้เองชนะ, ค่าที่ผู้พัฒนาแก้ใน patch ก็ได้มาด้วย
ไฟล์ที่ patch ก่อนหน้าติดตั้งแต่ patch ใหม่ไม่มีแล้ว จะถูกลบ (เฉพาะไฟล์ที่อยู่ในรายการติดตั้งของ patch ก่อน)
เครื่องพัฒนา (มีโฟลเดอร์ .git) ไม่อัปเดตด้วยวิธีนี้ — ใช้ git pull
"""
import fnmatch
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from core import BASE

REPO = "supawitmar/as-document"
BRANCH = "main"
VERSION_FILE = BASE / "version.json"
STATE = BASE / ".update"                  # ฉบับที่ติดตั้งครั้งก่อน (base สำหรับรวมข้อมูล) + รายการไฟล์
LOCAL_ONLY = ["settings.json", "converted.json", "translations.json", "*/translations.json", "*.migrated",
              "*.lnk", "doctypes/*/samples/*", ".update/*", ".git/*", "__pycache__/*", "*/__pycache__/*",
              "assets/example_*"]
DATA_FILES = ["doctypes/*/data/*.json"]


def raw_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{path}"


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


def check(timeout: float = 6) -> dict:
    """{'available', 'current', 'latest', 'version', 'latest_version', 'changes': [รุ่นที่ใหม่กว่า], 'dev', 'error'}"""
    cur = read_version()
    out = {"available": False, "current": cur["build"], "latest": cur["build"], "version": cur["version"],
           "latest_version": cur["version"], "changes": [], "dev": is_dev_checkout(), "error": ""}
    try:
        with urllib.request.urlopen(raw_url("version.json") + f"?t={cur['build']}", timeout=timeout) as r:
            latest = json.loads(r.read().decode("utf-8"))
    except Exception as e:          # ไม่มีอินเทอร์เน็ต ฯลฯ — ใช้งานต่อได้ตามปกติ
        out["error"] = str(e)
        return out
    out["latest"] = int(latest.get("build", 0))
    out["latest_version"] = version_label(out["latest"], latest.get("version", ""))
    out["changes"] = [c for c in latest.get("changes", []) if int(c.get("build", 0)) > cur["build"]]
    out["available"] = out["latest"] > cur["build"] and not out["dev"]
    return out


def _match(rel: str, patterns: list) -> bool:
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def merge_data(local, new, base):
    """รวมไฟล์ข้อมูล JSON แบบ 3 ทาง (dict): ค่าที่เครื่องนี้เปลี่ยนจาก base ชนะ ที่เหลือใช้ของ patch ใหม่"""
    if not isinstance(local, dict) or not isinstance(new, dict):
        return new if local is None or local == base else local
    base = base if isinstance(base, dict) else {}
    merged = dict(new)
    for k, v in local.items():
        if k not in base or base[k] != v:            # เครื่องนี้เพิ่ม/แก้เอง
            merged[k] = v
    for k in base:
        if k not in local and k in merged and merged[k] == base[k]:   # เครื่องนี้ลบเอง (และ patch ไม่ได้แก้)
            del merged[k]
    return merged


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def apply_tree(src: Path, dest: Path = BASE, log=print) -> dict:
    """คัดลอกโปรแกรมจากโฟลเดอร์ src (ที่แตกจาก ZIP) ทับโฟลเดอร์ที่ติดตั้ง dest"""
    src, dest = Path(src), Path(dest)
    if (dest / ".git").exists():
        raise RuntimeError(f"{dest} เป็นเครื่องพัฒนา (มี .git) — อัปเดตด้วย git pull")
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
                sort = isinstance(new, dict) and list(new) == sorted(new)        # คงรูปแบบไฟล์ของ patch
                d.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=sort), encoding="utf-8")
                merged.append(rel)
            elif new is not None and local is None:
                shutil.copy2(s, d)
        elif not d.exists() or _sha(s) != _sha(d):
            shutil.copy2(s, d)
            changed.append(rel)
        installed.append(rel)
        if _match(rel, DATA_FILES):           # เก็บฉบับของ patch ไว้เป็น base ของการรวมครั้งหน้า
            b = state / "base" / rel
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, b)
    for rel in sorted(old_manifest - set(installed)):      # ไฟล์ที่ patch ใหม่เอาออกแล้ว
        p = dest / rel
        if p.is_file() and not _match(rel, LOCAL_ONLY + DATA_FILES):
            p.unlink()
            removed.append(rel)
    state.mkdir(exist_ok=True)
    (state / "manifest.json").write_text(json.dumps(installed, ensure_ascii=False, indent=0), encoding="utf-8")
    pip = ""
    if req.exists() and _sha(req) != req_before:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--upgrade", "--disable-pip-version-check",
                            "-q", "-r", str(req)], capture_output=True, text=True)
        pip = "" if r.returncode == 0 else (r.stderr or r.stdout).strip()[-300:]
    log(f"อัปเดต {len(changed)} ไฟล์, รวมข้อมูล {len(merged)} ไฟล์, ลบ {len(removed)} ไฟล์")
    return {"changed": changed, "merged": merged, "removed": removed, "pip_error": pip}


def apply(zip_path: Path = None, log=print) -> dict:
    """ดาวน์โหลด (หรือใช้ zip_path) แล้วติดตั้งทับ — คืนผล apply_tree + build ใหม่"""
    if is_dev_checkout():
        raise RuntimeError("เครื่องนี้เป็นเครื่องพัฒนา (มี .git) — อัปเดตด้วย git pull")
    with tempfile.TemporaryDirectory(prefix="docupdate_") as t:
        t = Path(t)
        z = t / "src.zip"
        if zip_path:
            shutil.copy(zip_path, z)
        else:
            log("กำลังดาวน์โหลด…")
            with urllib.request.urlopen(f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip", timeout=60) as r:
                z.write_bytes(r.read())
        with zipfile.ZipFile(z) as zf:
            zf.extractall(t / "x")
        roots = [p for p in (t / "x").iterdir() if p.is_dir()]
        if len(roots) != 1 or not (roots[0] / "app.py").exists() or not (roots[0] / "version.json").exists():
            raise RuntimeError("ไฟล์อัปเดตไม่ถูกต้อง (ไม่พบ app.py / version.json)")
        res = apply_tree(roots[0], log=log)
    v = read_version()
    res["build"], res["version"] = v["build"], v["version"]
    return res


def main(argv=None) -> int:
    import argparse
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="อัปเดตโปรแกรมจาก GitHub")
    ap.add_argument("--zip", help="ใช้ไฟล์ ZIP ที่ดาวน์โหลดไว้แล้ว (แทนการดาวน์โหลด)")
    ap.add_argument("--tree", help="ใช้โฟลเดอร์ที่แตก ZIP ไว้แล้ว (get.ps1 ใช้ตอนอัปเดตเครื่องที่ติดตั้งไว้)")
    ap.add_argument("--dest", help="โฟลเดอร์ที่ติดตั้ง (ใช้กับ --tree; ค่าเริ่มต้น = โฟลเดอร์ของโปรแกรมนี้)")
    ap.add_argument("--check", action="store_true", help="เช็กอย่างเดียว")
    args = ap.parse_args(argv)
    if args.check:
        print(json.dumps(check(), ensure_ascii=False, indent=2))
        return 0
    if args.tree:
        dest = Path(args.dest) if args.dest else BASE
        v = read_version(dest / VERSION_FILE.name)
        r = {**apply_tree(Path(args.tree), dest), "build": v["build"], "version": v["version"]}
    else:
        r = apply(Path(args.zip) if args.zip else None)
    print(f"version {r['version']} (build {r['build']}): อัปเดต {len(r['changed'])} ไฟล์, "
          f"รวมข้อมูล {len(r['merged'])}, ลบ {len(r['removed'])}")
    if r["pip_error"]:
        print("!! ติดตั้งไลบรารีไม่สำเร็จ:", r["pip_error"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
