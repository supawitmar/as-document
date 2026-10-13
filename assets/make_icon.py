# สร้างไอคอนโปรแกรม (app_icon.png / app.ico): สี่เหลี่ยมมุมมนไล่สีม่วง-น้ำเงิน + เอกสารสีขาว + เครื่องหมายถูก
from pathlib import Path
from PIL import Image, ImageDraw

S = 1024
OUT = Path(__file__).resolve().parent


def gradient(size, c1, c2):
    g = Image.new("RGB", (size, size))
    px = g.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))
    return g


def main():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((32, 32, S - 32, S - 32), radius=220, fill=255)
    img.paste(gradient(S, (67, 56, 202), (37, 99, 235)), (0, 0), mask)

    d = ImageDraw.Draw(img)
    # เอกสาร (มุมพับขวาบน)
    x0, y0, x1, y1, fold = 300, 210, 724, 800, 130
    d.rounded_rectangle((x0, y0, x1, y1), radius=48, fill="white")
    d.polygon([(x1 - fold, y0 - 2), (x1 + 2, y0 - 2), (x1 + 2, y0 + fold)], fill=(52, 78, 218))
    d.polygon([(x1 - fold, y0), (x1 - fold, y0 + fold), (x1, y0 + fold)], fill=(199, 210, 254))
    for i, w in enumerate((300, 300, 220)):
        y = 400 + i * 85
        d.rounded_rectangle((x0 + 62, y, x0 + 62 + w, y + 34), radius=17, fill=(165, 180, 252))
    # วงกลมเครื่องหมายถูก
    cx, cy, r = 700, 740, 150
    d.ellipse((cx - r - 22, cy - r - 22, cx + r + 22, cy + r + 22), fill=(52, 78, 218))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(22, 163, 74))
    d.line([(cx - 70, cy + 5), (cx - 15, cy + 60), (cx + 78, cy - 52)], fill="white", width=44, joint="curve")

    icon = img.resize((256, 256), Image.LANCZOS)
    icon.save(OUT / "app_icon.png")
    icon.save(OUT / "app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
