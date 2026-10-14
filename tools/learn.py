# -*- coding: utf-8 -*-
"""
เครื่องมือ "เรียนรู้รูปแบบ" เอกสาร — ใช้ตอนเพิ่มประเภทเอกสารใหม่ หรือเมื่อเจ้าหน้าที่ปรับรูปแบบเอกสารเดิม

    python tools/learn.py inspect <ตัวอย่าง.pdf|.docx|.doc|.htm>
        อ่านไฟล์ตัวอย่างที่เจ้าหน้าที่จัดแล้ว แสดงทุกบรรทัดพร้อม ฟอนต์ / ขนาด / ระยะจากขอบซ้าย / ระยะบรรทัด
        และสรุปค่าที่ใช้บ่อย (ฟอนต์หลัก, ตำแหน่งย่อหน้า, ระยะบรรทัด, ขอบกระดาษ) — เอาไปตั้งค่าใน layout.py

    python tools/learn.py compare <ของเรา> <ตัวอย่าง> [-o โฟลเดอร์]
        แปลงทั้งสองไฟล์เป็นภาพทีละหน้า วัดเปอร์เซ็นต์พิกเซลที่ต่างกัน และบันทึกภาพ
        <หน้า>-side.png (วางคู่ ซ้าย=ของเรา ขวา=ตัวอย่าง) และ <หน้า>-diff.png (แดง=ต่าง) ไว้ตรวจด้วยตา
        ต่างกันราว 1% = ระยะคำ/การตัดบรรทัด, มากกว่านั้น = ระยะหรือตำแหน่งยังไม่ตรง

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
            print(f"หน้า {i + 1}: ต่างกัน {pct:.1f}% ของพื้นที่ตัวอักษร  -> {outdir / f'{i + 1}-side.png'}")
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
