# -*- coding: utf-8 -*-
"""ทดสอบระบบอัปเดต/ออกรุ่น (ไม่ใช้อินเทอร์เน็ต) — python -m unittest discover -s tests"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from core import update  # noqa: E402
import release  # noqa: E402


def jsave(p: Path, d, sort=False):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2, sort_keys=sort), encoding="utf-8")


def jload(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def make_tree(d: Path, version: str, build: int, courses: dict, signers: dict, extra=()):
    (d / "core").mkdir(parents=True, exist_ok=True)
    (d / "app.py").write_text("# app\n", encoding="utf-8")
    (d / "core" / "update.py").write_text("# updater\n", encoding="utf-8")
    jsave(d / "version.json", {"version": version, "build": build, "changes": [{"build": build, "version": version}]})
    jsave(d / "doctypes/bt31/data/courses.json", courses, sort=True)
    jsave(d / "doctypes/bt31/data/signers.json", signers)
    for f in extra:
        (d / f).parent.mkdir(parents=True, exist_ok=True)
        (d / f).write_text("x", encoding="utf-8")


class MergeDataTests(unittest.TestCase):
    def test_local_edits_win_and_new_values_arrive(self):
        base = {"A": 1, "B": 1, "C": 1}
        local = {"A": 1, "B": 2, "D": 4}           # แก้ B, เพิ่ม D, ลบ C
        new = {"A": 9, "B": 1, "C": 1, "E": 5}     # รุ่นใหม่แก้ A, เพิ่ม E
        self.assertEqual(update.merge_data(local, new, base), {"A": 9, "B": 2, "D": 4, "E": 5})

    def test_first_update_without_base_keeps_everything_local(self):
        self.assertEqual(update.merge_data({"A": "local"}, {"A": "repo", "B": 1}, None), {"A": "local", "B": 1})


class ApplyTreeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="upd_"))
        self.inst, self.new = self.tmp / "inst", self.tmp / "new"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_two_updates_keep_local_data(self):
        make_tree(self.inst, "1.0", 1, {"A101": "OLD"}, {"th": ["เดิม"], "en": ["old"]}, extra=["gone.py", "old_dir/x.py"])
        first = self.tmp / "v1"
        make_tree(first, "1.0", 1, {"A101": "OLD"}, {"th": ["เดิม"], "en": ["old"]}, extra=["gone.py", "old_dir/x.py"])
        update.apply_tree(first, self.inst, log=lambda m: None)            # ติดตั้งครั้งแรก = มี base
        c = jload(self.inst / "doctypes/bt31/data/courses.json"); c["LOCAL1"] = "เรียนรู้เอง"
        jsave(self.inst / "doctypes/bt31/data/courses.json", c, sort=True)
        s = jload(self.inst / "doctypes/bt31/data/signers.json"); s["th"] = ["แก้เอง"]
        jsave(self.inst / "doctypes/bt31/data/signers.json", s)
        (self.inst / "settings.json").write_text('{"x": 1}', encoding="utf-8")
        jsave(self.inst / "doctypes/bt31/data/translations.json", {"ก": "local"})

        make_tree(self.new, "1.1", 2, {"A101": "OLD", "B202": "NEW"}, {"th": ["เดิม"], "en": ["new dean"]})
        r = update.apply_tree(self.new, self.inst, log=lambda m: None, source="ทดสอบ")

        c = jload(self.inst / "doctypes/bt31/data/courses.json")
        s = jload(self.inst / "doctypes/bt31/data/signers.json")
        self.assertEqual(c["LOCAL1"], "เรียนรู้เอง")
        self.assertEqual(c["B202"], "NEW")
        self.assertEqual(list(c), sorted(c))
        self.assertEqual(s, {"th": ["แก้เอง"], "en": ["new dean"]})
        self.assertEqual((self.inst / "settings.json").read_text(encoding="utf-8"), '{"x": 1}')
        self.assertEqual(jload(self.inst / "doctypes/bt31/data/translations.json"), {"ก": "local"})
        self.assertFalse((self.inst / "gone.py").exists())
        self.assertIn("gone.py", r["removed"])
        self.assertFalse((self.inst / "old_dir").exists())                 # โฟลเดอร์ที่ว่างลงถูกลบด้วย
        inst = jload(self.inst / ".update/installed.json")
        self.assertEqual((inst["version"], inst["tag"], inst["source"]), ("1.1", "v1.1", "ทดสอบ"))

    def test_refuses_dev_checkout_and_self_install(self):
        make_tree(self.inst, "1.0", 1, {}, {})
        make_tree(self.new, "1.1", 2, {}, {})
        with self.assertRaises(RuntimeError):
            update.apply_tree(self.inst, self.inst, log=lambda m: None)
        (self.inst / ".git").mkdir()
        with self.assertRaises(RuntimeError):
            update.apply_tree(self.new, self.inst, log=lambda m: None)


class ReleasedOnlyTests(unittest.TestCase):
    """ติดตั้งเฉพาะรุ่นที่ออกแล้ว (มีป้าย v<เลข>) — รุ่นบน main ที่ยังไม่มีป้ายต้องถูกข้าม"""

    def fake_github(self, head, tagged):
        def get(url, timeout):
            if "/main/version.json" in url:
                return head
            for ver, data in tagged.items():
                if f"/v{ver}/version.json" in url:
                    return data
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return mock.patch.object(update, "_get_json", side_effect=get)

    def test_skips_untagged_release(self):
        head = {"changes": [{"build": 7, "version": "1.4"}, {"build": 6, "version": "1.3"}, {"build": 5, "version": "1.2.2"}]}
        tagged = {"1.3": {"version": "1.3", "build": 6, "changes": [{"build": 6, "version": "1.3", "text": "ใหม่"}]}}
        with self.fake_github(head, tagged):
            self.assertEqual(update.latest_release(5)["version"], "1.3")
            self.assertIsNone(update.latest_release(6))

    def test_check_reports_and_caches(self):
        head = {"changes": [{"build": 6, "version": "1.3"}]}
        tagged = {"1.3": {"version": "1.3", "build": 6, "changes": [{"build": 6, "version": "1.3", "text": "ใหม่"}]}}
        with self.fake_github(head, tagged) as g, \
                mock.patch.object(update, "read_version", return_value={"build": 5, "version": "1.2.2"}), \
                mock.patch.object(update, "is_dev_checkout", return_value=False):
            update._cache.update(at=0.0, result=None)
            r = update.check()
            self.assertTrue(r["available"])
            self.assertEqual((r["latest_version"], len(r["changes"])), ("1.3", 1))
            calls = g.call_count
            update.check()                                   # จำผล 30 นาที
            self.assertEqual(g.call_count, calls)
        update._cache.update(at=0.0, result=None)

    def test_dev_checkout_never_offers_update(self):
        head = {"changes": [{"build": 6, "version": "1.3"}]}
        with self.fake_github(head, {"1.3": {"version": "1.3", "build": 6}}), \
                mock.patch.object(update, "read_version", return_value={"build": 5, "version": "1.2.2"}), \
                mock.patch.object(update, "is_dev_checkout", return_value=True):
            self.assertFalse(update.check(force=True)["available"])
        update._cache.update(at=0.0, result=None)


class UserAgentTests(unittest.TestCase):
    """คำขอถึง GitHub ต้องมีชื่อโปรแกรม (proxy ที่ทำงานบล็อก Python-urllib)"""

    def test_requests_carry_user_agent(self):
        seen = []

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b"{}"

        def fake(req, timeout):
            seen.append(req.get_header("User-agent"))
            return Resp()
        with mock.patch.object(update.urllib.request, "urlopen", side_effect=fake):
            update._get_json("https://example.invalid/x", 1)
        self.assertTrue(seen and seen[0].startswith("as-document-updater"))


class CorporateCertTests(unittest.TestCase):
    """เครือข่ายที่ทำงานตรวจ SSL ด้วยใบรับรององค์กร: Python ไม่ผ่าน -> ใช้เครื่องมือของ Windows (curl.exe / PowerShell)"""

    @staticmethod
    def cert_fail(*a, **k):
        import ssl
        raise urllib.error.URLError(ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate"))

    def test_cert_error_uses_windows_download(self):
        with mock.patch.object(update.urllib.request, "urlopen", side_effect=self.cert_fail), \
                mock.patch.object(update, "_fetch_windows", return_value=b'{"build": 9}') as win:
            self.assertEqual(update._get_json("https://example.invalid/v.json", 5), {"build": 9})
            win.assert_called_once()

    def test_other_errors_do_not_fall_back(self):
        boom = urllib.error.URLError(OSError("network unreachable"))
        with mock.patch.object(update.urllib.request, "urlopen", side_effect=boom), \
                mock.patch.object(update, "_fetch_windows") as win:
            with self.assertRaises(urllib.error.URLError):
                update._fetch("https://example.invalid/x", 5)
            win.assert_not_called()

    def test_curl_404_becomes_http_error(self):
        done = subprocess.CompletedProcess([], 0, stdout="404", stderr="")
        with mock.patch.object(update.subprocess, "run", return_value=done), \
                mock.patch.object(update.Path, "exists", return_value=True):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                update._fetch_windows("https://example.invalid/v9.9.9/version.json", 5)
        self.assertEqual(cm.exception.code, 404)


class NoConsoleWindowTests(unittest.TestCase):
    """โปรแกรมย่อยที่หน้าโปรแกรมเรียก (Word ผ่าน PowerShell, curl) ต้องไม่เปิดจอดำขึ้นแว้บ (ผู้ใช้แจ้ง 22 ต.ค. 2569)"""

    def test_word_convert_and_windows_fetch_hide_console(self):
        import os
        from core import render
        if os.name != "nt":
            self.skipTest("Windows only")
        flags = []
        def fake(*a, **k):
            flags.append(k.get("creationflags"))
            return subprocess.CompletedProcess(a[0], 0, stdout="404", stderr="")
        with mock.patch.object(render.subprocess, "run", side_effect=fake):
            with self.assertRaises(RuntimeError):           # ไม่มีบรรทัด OK/ERR -> ถือว่าเรียก Word ไม่ได้
                render.word_convert([{"in": str(Path(tempfile.gettempdir()) / "x.htm")}])
        with mock.patch.object(update.subprocess, "run", side_effect=fake), \
                mock.patch.object(update.Path, "exists", return_value=True):
            with self.assertRaises(urllib.error.HTTPError):
                update._fetch_windows("https://example.invalid/x", 5)
        self.assertTrue(flags)
        self.assertTrue(all(f == subprocess.CREATE_NO_WINDOW for f in flags), flags)


class InstallWithNewUpdaterTests(unittest.TestCase):
    """ติดตั้งด้วยตัวอัปเดตของรุ่นใหม่จริง (โฟลเดอร์ที่คัดลอกจาก repo นี้)"""

    def test_new_updater_installs_repo_tree(self):
        tmp = Path(tempfile.mkdtemp(prefix="upd_"))
        try:
            files = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-co", "--exclude-standard"],
                                   cwd=ROOT, capture_output=True).stdout.decode("utf-8").splitlines()
            new, inst = tmp / "new", tmp / "inst"
            for f in files:
                if (ROOT / f).is_file():
                    (new / f).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(ROOT / f, new / f)
            make_tree(inst, "1.0", 1, {"LOCAL1": "x"}, {"th": ["เดิม"]})
            r = update.install_with_new(new, inst, source="ทดสอบ")
            self.assertEqual(r["version"], update.read_version(new / "version.json")["version"])
            self.assertEqual(jload(inst / "doctypes/bt31/data/courses.json")["LOCAL1"], "x")
            self.assertTrue((inst / "อัปเดตระบบปรับเอกสาร.bat").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ReleaseToolTests(unittest.TestCase):
    def test_version_numbers(self):
        self.assertEqual(release.next_version({"version": "1.2.2", "build": 5}), "1.3")
        self.assertEqual(release.next_version({"version": "1.2", "build": 3}, fix=True), "1.2.1")
        self.assertEqual(release.next_version({"version": "1.2.1", "build": 4}, fix=True), "1.2.2")

    def test_changelog_for_staff(self):
        text = release.changelog({"changes": [{"version": "1.3", "date": "2026-10-19", "text": "หัวข้อ", "items": ["ข้อ 1"]}]})
        self.assertIn("## อัปเดต 1.3 — 19 ตุลาคม 2569", text)
        self.assertIn("- ข้อ 1", text)
        self.assertIn("อัปเดตระบบปรับเอกสาร.bat", text)

    def test_private_files_and_names_detected(self):
        self.assertTrue(release.PRIVATE.search("doctypes/bgks39/samples/a.docx"))
        self.assertTrue(release.PRIVATE.search("doctypes/bt31/data/translations.json"))
        self.assertFalse(release.PRIVATE.search("doctypes/bt31/data/courses.json"))
        names = [m[0] for m in release.PERSON.finditer("ตัวอย่าง นายเอบีซี ดีอีเอฟ")  # allow-name: ชื่อทดสอบ
                 if not ({m[1], m[2]} & release.FICTIONAL) and not m[1].startswith(release.NOT_NAME)]
        self.assertEqual(names, ["นายเอบีซี ดีอีเอฟ"])  # allow-name


if __name__ == "__main__":
    unittest.main()
