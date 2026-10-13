# -*- coding: utf-8 -*-
"""หน้าจอโปรแกรม "ระบบปรับเอกสาร บฑ.31" — ใช้งานร่วมกับ fix_letters.py"""
import ctypes
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import fix_letters as fx

APP_TITLE = "ระบบปรับเอกสาร บฑ.31 — บัณฑิตวิทยาลัย"
DOWNLOADS = Path.home() / "Downloads"
FONT = "Leelawadee UI"

NAVY = "#14336b"
NAVY_DARK = "#0d2550"
GOLD = "#c9a227"
BG = "#f4f6fa"
CARD = "#ffffff"
MUTED = "#6b7280"
OK_GREEN = "#15803d"
WARN = "#b45309"
ERR_RED = "#b91c1c"


# ---------- ลากไฟล์มาวาง (Windows API, ไม่ต้องติดตั้งเพิ่ม) ----------
def enable_file_drop(root: tk.Tk, callback):
    """callback ถูกเรียกจากภายใน window procedure — ห้ามเรียก tkinter ในนั้น (โปรแกรมจะล่ม)
    ให้ส่งงานผ่าน queue แทน"""
    if sys.platform != "win32":
        return False
    from ctypes import wintypes
    user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
    WM_DROPFILES, GWLP_WNDPROC = 0x0233, -4
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.CallWindowProcW.restype = LRESULT
    user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.GetParent.restype = wintypes.HWND
    shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_wchar_p, wintypes.UINT]
    shell32.DragFinish.argtypes = [ctypes.c_void_p]
    shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]

    root.update_idletasks()
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    old = None

    def proc(h, msg, wp, lp):
        if msg == WM_DROPFILES:
            files = []
            for i in range(shell32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)):
                n = shell32.DragQueryFileW(wp, i, None, 0)
                buf = ctypes.create_unicode_buffer(n + 1)
                shell32.DragQueryFileW(wp, i, buf, n + 1)
                files.append(buf.value)
            shell32.DragFinish(wp)
            callback(files)
            return 0
        return user32.CallWindowProcW(old, h, msg, wp, lp)

    root._drop_proc = WNDPROC(proc)  # เก็บ reference ไว้ไม่ให้ถูกเก็บกวาด
    old = user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ctypes.cast(root._drop_proc, ctypes.c_void_p))
    shell32.DragAcceptFiles(hwnd, True)
    return True


class App:
    def __init__(self, root: tk.Tk, initial: list):
        self.root = root
        self.files = {}          # iid -> {"path": Path, "result": dict|None}
        self.queue = queue.Queue()
        self.busy = False

        root.title(APP_TITLE)
        root.configure(bg=BG)
        self._styles()
        self._header()
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(14, 16))
        # แถวปุ่มและตัวเลือกยึดด้านล่างก่อน เพื่อให้หดเฉพาะรายการไฟล์เมื่อจอเล็ก
        self._action_bar(body)
        self._options_card(body)
        self._files_card(body)

        self.drop_ok = False
        try:
            self.drop_ok = enable_file_drop(root, lambda files: self.queue.put(("drop", files)))
        except Exception:
            pass
        self._fit_window()
        self.refresh_empty()
        if initial:
            self.add_files(initial)
        root.after(100, self._poll)

    # ---------- หน้าตา ----------
    def _fit_window(self):
        """ขนาดหน้าต่างตามการย่อ/ขยายหน้าจอ (DPI) และไม่เกินขนาดจอ"""
        r = self.root
        r.update_idletasks()
        scale = r.winfo_fpixels("1i") / 96
        w = min(max(int(920 * scale), r.winfo_reqwidth()), int(r.winfo_screenwidth() * 0.95))
        h = min(max(int(660 * scale), r.winfo_reqheight()), int(r.winfo_screenheight() * 0.82))
        r.geometry(f"{w}x{h}+{(r.winfo_screenwidth() - w) // 2}+{int(20 * scale)}")
        r.minsize(min(w, r.winfo_reqwidth()), min(h, r.winfo_reqheight()))

    def _styles(self):
        s = ttk.Style()
        if "vista" in s.theme_names():
            s.theme_use("vista")
        s.configure(".", font=(FONT, 10))
        s.configure("Treeview", rowheight=30, font=(FONT, 10))
        s.configure("Treeview.Heading", font=(FONT, 10, "bold"))
        s.configure("TCheckbutton", background=CARD, font=(FONT, 10))
        s.configure("TRadiobutton", background=CARD, font=(FONT, 10))
        s.configure("TButton", font=(FONT, 10), padding=(10, 4))

    def _header(self):
        h = tk.Frame(self.root, bg=NAVY)
        h.pack(fill="x")
        tk.Frame(h, bg=GOLD, height=4).pack(side="bottom", fill="x")
        inner = tk.Frame(h, bg=NAVY)
        inner.pack(fill="x", padx=20, pady=(14, 12))
        tk.Label(inner, text="ระบบปรับเอกสาร บฑ.31", bg=NAVY, fg="white",
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(inner, text="แปลงไฟล์หนังสือเชิญ / หนังสือขออนุมัติอาจารย์พิเศษจากระบบ ให้เป็นไฟล์ Word รูปแบบมาตรฐานพร้อมใช้",
                 bg=NAVY, fg="#c7d2e8", font=(FONT, 10)).pack(anchor="w", pady=(2, 0))

    def _card(self, parent, step, title, **pack):
        outer = tk.Frame(parent, bg="#dfe4ee")
        outer.pack(fill="x", **pack)
        card = tk.Frame(outer, bg=CARD)
        card.pack(fill="both", expand=True, padx=1, pady=1)
        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x", padx=14, pady=(10, 6))
        tk.Label(head, text=f" {step} ", bg=NAVY, fg="white", font=(FONT, 10, "bold")).pack(side="left")
        tk.Label(head, text=title, bg=CARD, fg="#111827", font=(FONT, 11, "bold")).pack(side="left", padx=8)
        return outer, card, head

    def _files_card(self, parent):
        outer, card, head = self._card(parent, "1", "เลือกไฟล์ Export")
        outer.pack_configure(fill="both", expand=True)

        bar = tk.Frame(card, bg=CARD)
        bar.pack(fill="x", padx=14)
        ttk.Button(bar, text="+ เพิ่มไฟล์…", command=self.pick_files).pack(side="left")
        ttk.Button(bar, text="ไฟล์ใหม่ใน Downloads", command=self.add_new_downloads).pack(side="left", padx=6)
        ttk.Button(bar, text="ล้างรายการ", command=self.clear).pack(side="right")
        ttk.Button(bar, text="ลบที่เลือก", command=self.remove_selected).pack(side="right", padx=6)

        wrap = tk.Frame(card, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=14, pady=(8, 12))
        cols = ("file", "kind", "to", "status")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="extended", height=6)
        for c, text, w, st in (("file", "ไฟล์", 170, False), ("kind", "ประเภท", 120, False),
                               ("to", "เรียน", 330, True), ("status", "สถานะ", 190, True)):
            self.tree.heading(c, text=text, anchor="w")
            self.tree.column(c, width=w, stretch=st, anchor="w")
        self.tree.tag_configure("done", foreground=OK_GREEN)
        self.tree.tag_configure("warn", foreground=WARN)
        self.tree.tag_configure("error", foreground=ERR_RED)
        self.tree.tag_configure("muted", foreground=MUTED)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self.open_selected())
        self.tree.bind("<Delete>", lambda e: self.remove_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_buttons())

        self.empty = tk.Label(self.tree, bg="white", fg=MUTED, font=(FONT, 11), justify="center",
                              text="ลากไฟล์ Export (.doc) มาวางที่นี่\nหรือกด “+ เพิ่มไฟล์…”")

    def _options_card(self, parent):
        _, card, _ = self._card(parent, "2", "ตัวเลือก", side="bottom", pady=(12, 0))
        grid = tk.Frame(card, bg=CARD)
        grid.pack(fill="x", padx=14, pady=(0, 12))

        self.var_pdf = tk.BooleanVar(value=True)
        ttk.Checkbutton(grid, text="สร้างไฟล์ PDF ด้วย", variable=self.var_pdf).grid(row=0, column=0, sticky="w")

        self.var_out = tk.StringVar(value="same")
        self.outdir = None
        tk.Label(grid, text="บันทึกไฟล์ที่:", bg=CARD, font=(FONT, 10)).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Radiobutton(grid, text="โฟลเดอร์เดียวกับไฟล์ต้นฉบับ", value="same", variable=self.var_out,
                        command=self.update_out_label).grid(row=2, column=0, sticky="w")
        other = tk.Frame(grid, bg=CARD)
        other.grid(row=2, column=1, sticky="w", padx=(28, 0))
        ttk.Radiobutton(other, text="โฟลเดอร์อื่น", value="other", variable=self.var_out,
                        command=self.choose_outdir).pack(side="left")
        self.out_label = tk.Label(other, text="", bg=CARD, fg=MUTED, font=(FONT, 9))
        self.out_label.pack(side="left", padx=6)

    def _action_bar(self, parent):
        bar = tk.Frame(parent, bg=BG)
        bar.pack(side="bottom", fill="x", pady=(14, 0))
        self.run_btn = tk.Button(bar, text="ปรับเอกสาร  ▶", command=self.run, bg=NAVY, fg="white",
                                 activebackground=NAVY_DARK, activeforeground="white", relief="flat",
                                 font=(FONT, 12, "bold"), padx=26, pady=8, cursor="hand2", bd=0)
        self.run_btn.pack(side="left")
        self.open_dir_btn = ttk.Button(bar, text="📂 เปิดโฟลเดอร์ผลลัพธ์", command=self.open_folder)
        self.open_dir_btn.pack(side="right")
        self.open_btn = ttk.Button(bar, text="📄 เปิดไฟล์ที่เลือก", command=self.open_selected)
        self.open_btn.pack(side="right", padx=6)

        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=140)
        self.status = tk.Label(bar, text="", bg=BG, fg=MUTED, font=(FONT, 10), anchor="w", justify="left")
        self.status.pack(side="left", fill="x", expand=True, padx=(14, 0))
        self.status.bind("<Configure>", lambda e: self.status.configure(wraplength=max(e.width - 4, 100)))
        self.update_buttons()

    # ---------- จัดการรายการไฟล์ ----------
    def add_files(self, paths):
        if self.busy:
            return
        added = 0
        for p in fx.collect([str(x) for x in paths]):
            p = p.resolve()
            iid = str(p).lower()
            if iid in self.files:
                continue
            info = fx.inspect(p)
            self.files[iid] = {"path": p, "result": None, "ok": info["ok"]}
            status = "พร้อมแปลง" if info["ok"] else f"✗ {info['reason']}"
            self.tree.insert("", "end", iid=iid, values=(p.name, info["kind"] or "-", info["to"], status),
                             tags=() if info["ok"] else ("error",))
            added += 1
        self.refresh_empty()
        self.update_buttons()
        if added:
            self.set_status(f"เพิ่ม {added} ไฟล์ — กด “ปรับเอกสาร” เพื่อเริ่ม")

    def pick_files(self):
        names = filedialog.askopenfilenames(
            parent=self.root, title="เลือกไฟล์ Export ที่ต้องการปรับ", initialdir=str(DOWNLOADS),
            filetypes=[("ไฟล์ Export", "*.doc *.htm *.html"), ("ทุกไฟล์", "*.*")])
        if names:
            self.add_files(names)

    def add_new_downloads(self):
        """ไฟล์ Export*.doc ใน Downloads ที่ยังไม่เคยแปลง"""
        new = [p for p in sorted(DOWNLOADS.glob("Export*.doc"))
               if not any(DOWNLOADS.glob(f"{glob_escape(p.stem)} - *.docx"))]
        if not new:
            messagebox.showinfo(APP_TITLE, "ไม่พบไฟล์ Export ใหม่ในโฟลเดอร์ Downloads", parent=self.root)
            return
        self.add_files(new)

    def remove_selected(self):
        if self.busy:
            return
        for iid in self.tree.selection():
            self.tree.delete(iid)
            self.files.pop(iid, None)
        self.refresh_empty()
        self.update_buttons()

    def clear(self):
        if self.busy:
            return
        self.tree.delete(*self.tree.get_children())
        self.files.clear()
        self.refresh_empty()
        self.update_buttons()
        self.set_status("")

    def refresh_empty(self):
        if self.files:
            self.empty.place_forget()
        else:
            self.empty.place(relx=0.5, rely=0.55, anchor="center")

    # ---------- ตัวเลือก ----------
    def choose_outdir(self):
        d = filedialog.askdirectory(parent=self.root, title="เลือกโฟลเดอร์สำหรับบันทึกไฟล์",
                                    initialdir=str(self.outdir or DOWNLOADS))
        if d:
            self.outdir = Path(d)
        elif not self.outdir:
            self.var_out.set("same")
        self.update_out_label()

    def update_out_label(self):
        show = self.var_out.get() == "other" and self.outdir
        self.out_label.configure(text=shorten(str(self.outdir)) if show else "")

    # ---------- แปลงไฟล์ ----------
    def run(self):
        todo = [iid for iid, f in self.files.items() if f["ok"] and not f["result"]]
        if not todo:
            msg = "ยังไม่มีไฟล์ให้แปลง — เพิ่มไฟล์ Export ก่อน" if not self.files else "แปลงไฟล์ในรายการครบแล้ว"
            messagebox.showinfo(APP_TITLE, msg, parent=self.root)
            return
        self.busy = True
        for iid in todo:
            self.tree.set(iid, "status", "⏳ กำลังแปลง…")
            self.tree.item(iid, tags=("muted",))
        self.update_buttons()
        self.progress.pack(side="left", padx=(14, 0), before=self.status)
        self.progress.start(12)
        self.set_status("กำลังแปลงด้วย Microsoft Word … (ครั้งแรกอาจใช้เวลาสักครู่)")
        paths = [self.files[i]["path"] for i in todo]
        outdir = self.outdir if self.var_out.get() == "other" else None
        opts = dict(outdir=outdir, pdf=self.var_pdf.get())
        threading.Thread(target=self._worker, args=(paths, opts), daemon=True).start()

    def _worker(self, paths, opts):
        try:
            results = fx.convert(paths, log=lambda m: None, **opts)
            self.queue.put(("done", results))
        except Exception as e:  # แสดงข้อผิดพลาดบนหน้าจอแทนการปิดโปรแกรม
            self.queue.put(("fail", str(e)))

    def _poll(self):
        try:
            while True:
                kind, data = self.queue.get_nowait()
                if kind == "drop":
                    self.add_files(data)
                else:
                    self._finish(kind, data)
        except queue.Empty:
            pass
        self.root.after(150, self._poll)

    def _finish(self, kind, data):
        self.busy = False
        self.progress.stop()
        self.progress.pack_forget()
        if kind == "fail":
            for iid, f in self.files.items():
                if f["ok"] and not f["result"]:
                    self.tree.set(iid, "status", "พร้อมแปลง")
                    self.tree.item(iid, tags=())
            self.set_status("เกิดข้อผิดพลาด", ERR_RED)
            messagebox.showerror(APP_TITLE, f"แปลงไฟล์ไม่สำเร็จ\n\n{data}", parent=self.root)
            self.update_buttons()
            return

        ok = warn = bad = 0
        notes = []
        for r in data:
            iid = str(Path(r["src"]).resolve()).lower()
            if iid not in self.files:
                continue
            self.files[iid]["result"] = r
            if r["docx"]:
                if r["notes"]:
                    warn += 1
                    notes += [f"• {r['src'].name}: {n}" for n in r["notes"]]
                    self.tree.set(iid, "status", "✓ เสร็จ (มีหมายเหตุ)")
                    self.tree.item(iid, tags=("warn",))
                else:
                    ok += 1
                    self.tree.set(iid, "status", "✓ เสร็จ" + (" (+PDF)" if r["pdf"] else ""))
                    self.tree.item(iid, tags=("done",))
            else:
                bad += 1
                self.tree.set(iid, "status", f"✗ {r['error']}")
                self.tree.item(iid, tags=("error",))

        total = ok + warn
        if bad:
            self.set_status(f"เสร็จ {total} ไฟล์, ไม่สำเร็จ {bad} ไฟล์", ERR_RED)
        else:
            self.set_status(f"✓ เสร็จเรียบร้อย {total} ไฟล์ — ดับเบิลคลิกที่รายการเพื่อเปิดไฟล์", OK_GREEN)
        if notes:
            messagebox.showwarning(APP_TITLE, "แปลงเสร็จแล้ว แต่มีหมายเหตุ:\n\n" + "\n".join(notes), parent=self.root)
        self.update_buttons()

    # ---------- เปิดไฟล์ ----------
    def _result_of(self, iid):
        f = self.files.get(iid)
        return f and f["result"]

    def open_selected(self):
        sel = self.tree.selection() or self.tree.get_children()[:1]
        for iid in sel:
            r = self._result_of(iid)
            target = r and (r["docx"] or r["doc"])
            if target and Path(target).exists():
                os.startfile(target)
            elif iid in self.files:
                os.startfile(self.files[iid]["path"].parent)

    def open_folder(self):
        done = [r for f in self.files.values() if (r := f["result"]) and (r["docx"] or r["doc"])]
        if done:
            path = Path(done[-1]["docx"] or done[-1]["doc"])
            if path.exists():  # เปิด Explorer พร้อมเลือกไฟล์ผลลัพธ์
                subprocess.Popen(f'explorer /select,"{path}"')
            else:
                os.startfile(path.parent)
        elif self.outdir and self.var_out.get() == "other":
            os.startfile(self.outdir)
        else:
            os.startfile(DOWNLOADS)

    # ---------- อื่นๆ ----------
    def update_buttons(self):
        has_result = any(f["result"] for f in self.files.values())
        self.run_btn.configure(state="disabled" if self.busy else "normal",
                               bg=MUTED if self.busy else NAVY)
        self.open_btn.configure(state="normal" if has_result and not self.busy else "disabled")

    def set_status(self, text, color=MUTED):
        self.status.configure(text=text, fg=color)


def glob_escape(s: str) -> str:
    return s.replace("[", "[[]")


def shorten(s: str, n: int = 50) -> str:
    return s if len(s) <= n else "…" + s[-(n - 1):]


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # ตัวอักษรคมชัดบนจอความละเอียดสูง
    except Exception:
        pass
    root = tk.Tk()
    try:
        root.iconbitmap(default=str(fx.ASSETS / "app.ico"))
    except tk.TclError:
        pass
    App(root, sys.argv[1:])
    root.mainloop()


if __name__ == "__main__":
    main()
