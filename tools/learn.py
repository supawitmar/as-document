# -*- coding: utf-8 -*-
"""
เครื่องมือ "เรียนรู้รูปแบบ" เอกสาร — ใช้ตอนเพิ่มประเภทเอกสารใหม่ หรือเมื่อเจ้าหน้าที่ปรับรูปแบบเอกสารเดิม

    python tools/learn.py inspect <ตัวอย่าง.pdf|.docx|.doc|.htm>
        อ่านไฟล์ตัวอย่างที่เจ้าหน้าที่จัดแล้ว แสดงทุกบรรทัดพร้อม ฟอนต์ / ขนาด / ระยะจากขอบซ้าย / ระยะบรรทัด
        และสรุปค่าที่ใช้บ่อย (ฟอนต์หลัก, ตำแหน่งย่อหน้า, ระยะบรรทัด, ขอบกระดาษ) — เอาไปตั้งค่าใน layout.py

    python tools/learn.py compare <ของเรา> <ตัวอย่าง> [-o โฟลเดอร์]
        เทียบ 2 แบบต่อหน้า:
        1. ตำแหน่งบรรทัด (ตัววัดหลัก): จับคู่บรรทัดที่ข้อความตรงกัน แล้ววัดว่าตำแหน่งต่างกันกี่ pt
           + รายการบรรทัดที่ข้อความต่าง — ใช้ได้แม้ระยะห่างตัวอักษรในบรรทัดต่างกันเล็กน้อย
           เกณฑ์ผ่าน: บรรทัดตรงเกือบทั้งหมด และคลาดเคลื่อนไม่เกิน ~1 pt (ข้อความต่างต้องอธิบายได้ทุกบรรทัด)
        2. พิกเซล: เปอร์เซ็นต์พื้นที่ตัวอักษรที่ต่าง + ภาพ <หน้า>-side.png (ซ้าย=ของเรา ขวา=ตัวอย่าง)
           และ <หน้า>-diff.png (แดง=ต่าง) ไว้ตรวจด้วยตา — ตัวเลขนี้สูงได้มาก (30–70%) แม้หน้าตาเหมือนกัน
           ถ้าการกระจายตัวอักษรแบบไทยต่างกันเล็กน้อย ใช้ได้ตรงเฉพาะไฟล์ที่ Word สร้างจากต้นทางเดียวกัน (~1% = ระยะคำ)

ไฟล์ .docx / .doc / .htm จะถูกแปลงเป็น PDF ด้วย Microsoft Word ก่อน (ต้องมี Word)
ไฟล์ตัวอย่างจริงมีข้อมูลบุคคล — เก็บไว้ที่ doctypes/<ประเภท>/samples/ (ไม่อยู่ใน git)
"""
import argparse
import shutil
import statistics
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.render import word_convert  # noqa: E402

PT_PER_CM = 72 / 2.54


def as_pdf(path: Path, tmp: Path) -> Path:
    """ไฟล์ Word/Word HTML -> PDF (ผ่าน Word) เพื่ออ่านตำแหน่งจริงบนหน้ากระดาษ"""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        return path
    src = tmp / f"in{len(list(tmp.iterdir()))}{path.suffix.lower()}"      # path ASCII สำหรับ PowerShell/COM
    shutil.copy(path, src)
    job = {"in": str(src), "docx": str(src.with_suffix(".out.docx")), "pdf": str(src.with_suffix(".pdf"))}
    err = word_convert([job]).get(job["in"], "ไม่ทราบสาเหตุ")
    if err:
        raise RuntimeError(f"Word แปลง {path.name} ไม่ได้: {err}")
    return Path(job["pdf"])


def cmd_inspect(path: Path):
    import pymupdf
    with tempfile.TemporaryDirectory(prefix="learn_") as t:
        doc = pymupdf.open(str(as_pdf(path, Path(t))))
        fonts, sizes, lefts, gaps = Counter(), Counter(), Counter(), Counter()
        x0s, x1s, tops, bottoms = [], [], [], []
        for pno, page in enumerate(doc, 1):
            w, h = page.rect.width, page.rect.height
            print(f"\n=== หน้า {pno}  ({w:.1f} x {h:.1f} pt = {w / PT_PER_CM:.2f} x {h / PT_PER_CM:.2f} ซม.) ===")
            print(f"{'y':>6} {'x':>6} {'ห่าง':>5}  {'ฟอนต์':<24} {'ขนาด':>5}  ข้อความ")
            prev_y = None
            for b in page.get_text("dict")["blocks"]:
                for ln in b.get("lines", []):
                    spans = [s for s in ln["spans"] if s["text"].strip()]
                    if not spans:
                        continue
                    text = "".join(s["text"] for s in ln["spans"]).strip()
                    s0 = max(spans, key=lambda s: len(s["text"]))
                    x, y = ln["bbox"][0], s0["origin"][1]
                    gap = y - prev_y if prev_y is not None and y > prev_y else 0
                    prev_y = y
                    font = s0["font"] + (" B" if s0["flags"] & 16 else "")
                    print(f"{y:6.1f} {x:6.1f} {gap:5.1f}  {font[:24]:<24} {s0['size']:5.1f}  {text[:70]}")
                    fonts[s0["font"]] += len(text)
                    sizes[round(s0["size"], 1)] += len(text)
                    lefts[round(x)] += 1
                    if 0 < gap < 40:
                        gaps[round(gap, 1)] += 1
                    x0s.append(x)
                    x1s.append(ln["bbox"][2])
                    tops.append(ln["bbox"][1])
                    bottoms.append(ln["bbox"][3])
        doc.close()
    if not x0s:
        print("ไม่พบข้อความ (ไฟล์สแกน?)")
        return
    print("\n=== สรุป ===")
    print("ฟอนต์ (ตามจำนวนตัวอักษร):", ", ".join(f"{f} {n}" for f, n in fonts.most_common(4)))
    print("ขนาดตัวอักษร:", ", ".join(f"{s}pt ×{n}" for s, n in sizes.most_common(4)))
    print("ระยะบรรทัดที่พบบ่อย (baseline ถึง baseline):", ", ".join(f"{g}pt ×{n}" for g, n in gaps.most_common(4)))
    print("ตำแหน่งต้นบรรทัดที่พบบ่อย (จากขอบกระดาษซ้าย):",
          ", ".join(f"{x}pt ({x / PT_PER_CM:.2f} ซม.) ×{n}" for x, n in lefts.most_common(6)))
    print(f"ขอบซ้ายน้อยสุด ≈ {min(x0s) / PT_PER_CM:.2f} ซม. · ขอบขวาของข้อความไกลสุด ≈ {max(x1s) / PT_PER_CM:.2f} ซม. "
          f"· บรรทัดแรก ≈ {min(tops) / PT_PER_CM:.2f} ซม. · บรรทัดสุดท้าย ≈ {max(bottoms) / PT_PER_CM:.2f} ซม.")
    if gaps:
        print(f"ระยะบรรทัดมัธยฐาน ≈ {statistics.median(g for g, n in gaps.items() for _ in range(n)):.1f}pt")


def page_lines(page) -> list:
    """[(y บน, x ของคำแรก, ข้อความ)] ของทุกบรรทัดที่มองเห็นในหน้า เรียงจากบนลงล่าง
    รวมคำที่อยู่แนวเดียวกัน (ป้าย + ค่าที่อยู่คนละย่อหน้า/คนละ tab) เป็นบรรทัดเดียว และวัดตำแหน่งจากคำแรกจริง
    (ไม่นับช่องว่างที่เคาะนำหน้า — ไฟล์ตัวอย่างหลายฉบับจัดลายมือชื่อด้วยการเคาะเว้นวรรค)"""
    rows = []
    for x0, y0, x1, y1, word, *_ in sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        mid = (y0 + y1) / 2
        if rows and abs(rows[-1]["mid"] - mid) < 3:
            rows[-1]["words"].append((x0, word))
            rows[-1]["y"] = min(rows[-1]["y"], y0)
        else:
            rows.append({"mid": mid, "y": y0, "words": [(x0, word)]})
    return [(r["y"], min(x for x, _ in r["words"]), " ".join(w for _, w in sorted(r["words"]))) for r in rows]


def compare_lines(a: list, b: list) -> dict:
    """จับคู่บรรทัดตามลำดับข้อความ (difflib) แล้ววัดระยะต่างของบรรทัดที่ข้อความตรงกัน"""
    import difflib
    sm = difflib.SequenceMatcher(a=[t for *_, t in a], b=[t for *_, t in b], autojunk=False)
    pairs, only_ours, only_sample = [], [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            pairs += [(a[i], b[j]) for i, j in zip(range(i1, i2), range(j1, j2))]
        else:
            only_ours += [t for *_, t in a[i1:i2]]
            only_sample += [t for *_, t in b[j1:j2]]
    dy = [abs(x[0] - y[0]) for x, y in pairs]
    dx = [abs(x[1] - y[1]) for x, y in pairs]
    return {"matched": len(pairs), "ours": len(a), "sample": len(b), "max_dy": max(dy, default=0), "max_dx": max(dx, default=0),
            "only_ours": only_ours, "only_sample": only_sample}


def cmd_compare(ours: Path, sample: Path, outdir: Path):
    import pymupdf
    from PIL import Image, ImageChops
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="learn_") as t:
        a, b = pymupdf.open(str(as_pdf(ours, Path(t)))), pymupdf.open(str(as_pdf(sample, Path(t))))
        if len(a) != len(b):
            print(f"!! จำนวนหน้าไม่เท่ากัน: ของเรา {len(a)} หน้า / ตัวอย่าง {len(b)} หน้า")
        for i in range(min(len(a), len(b))):
            ia, ib = [Image.frombytes("RGB", (p.width, p.height), p.samples)
                      for p in (a[i].get_pixmap(dpi=110), b[i].get_pixmap(dpi=110))]
            ib = ib.resize(ia.size)
            diff = ImageChops.difference(ia.convert("L"), ib.convert("L")).point(lambda v: 255 if v > 60 else 0)
            ink = ImageChops.lighter(ia.convert("L").point(lambda v: 255 if v < 200 else 0),
                                     ib.convert("L").point(lambda v: 255 if v < 200 else 0)).histogram()[255]
            changed = diff.histogram()[255]
            pct = 100 * changed / max(ink, 1)
            side = Image.new("RGB", (ia.width * 2 + 10, ia.height), "white")
            side.paste(ia, (0, 0))
            side.paste(ib, (ia.width + 10, 0))
            side.save(outdir / f"{i + 1}-side.png")
            red = Image.new("RGB", ia.size, (230, 40, 40))
            Image.composite(red, ia.convert("L").convert("RGB"), diff).save(outdir / f"{i + 1}-diff.png")
            r = compare_lines(page_lines(a[i]), page_lines(b[i]))
            print(f"หน้า {i + 1}: บรรทัดข้อความตรงกัน {r['matched']}/{max(r['ours'], r['sample'])} · "
                  f"ตำแหน่งคลาดเคลื่อนสูงสุด แนวตั้ง {r['max_dy']:.1f} pt / แนวนอน {r['max_dx']:.1f} pt")
            for t in r["only_ours"][:8]:
                print(f"     มีเฉพาะของเรา : {t[:90]}")
            for t in r["only_sample"][:8]:
                print(f"     มีเฉพาะตัวอย่าง: {t[:90]}")
            print(f"     พิกเซลต่างกัน {pct:.1f}% ของพื้นที่ตัวอักษร (ดูภาพ) -> {outdir / f'{i + 1}-side.png'}")
        a.close()
        b.close()


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="เรียนรู้/ตรวจรูปแบบเอกสารจากไฟล์ตัวอย่าง")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect", help="แสดงฟอนต์/ขนาด/ตำแหน่ง/ระยะบรรทัดของไฟล์ตัวอย่าง")
    p.add_argument("file")
    p = sub.add_parser("compare", help="เทียบผลลัพธ์ของเรากับไฟล์ตัวอย่างเป็นภาพ")
    p.add_argument("ours")
    p.add_argument("sample")
    p.add_argument("-o", "--outdir", default=str(Path(tempfile.gettempdir()) / "learn_compare"))
    args = ap.parse_args(argv)
    if args.cmd == "inspect":
        cmd_inspect(Path(args.file))
    else:
        cmd_compare(Path(args.ours), Path(args.sample), Path(args.outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
