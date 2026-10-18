#!/usr/bin/env python3
"""
Skapar kalibreringssidor för att kontrollera rotation, 100 % skalning och
skrivarens marginaler:

    test/calibration_A4.pdf        210 x 297 mm stående (vanligt A4-papper)
    test/calibration_A5.pdf        210 x 148 mm liggande (vanligt A5-papper, simulerar nummerlappen)
    test/calibration_225x160.pdf   225 x 160 mm liggande (samma som nummerlapparna)

Varje sida har gränslinjer 5 mm och 10 mm från papperskanten, mm-streck 1-10 mm
in från varje kant och linjaler på 100 mm i båda riktningarna.
"""
from pathlib import Path
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

TEST_DIR = Path(__file__).parent

SIZES = {
    "A4": (210, 297),
    "A5": (210, 148),  # liggande som nummerlappen
    "225x160": (225, 160),
}


def boundary_lines(c, W, H):
    """Gränslinjer där marginalerna förväntas ligga: heldragen 5 mm, streckad 10 mm."""
    c.setLineWidth(0.6)
    c.rect(5 * mm, 5 * mm, W - 10 * mm, H - 10 * mm)
    c.setDash(3, 2)
    c.rect(10 * mm, 10 * mm, W - 20 * mm, H - 20 * mm)
    c.setDash()
    c.setFont("Helvetica", 5)
    c.drawString(5 * mm + 1, H - 5 * mm - 6, "5 mm")
    c.drawString(10 * mm + 1, H - 10 * mm - 6, "10 mm")


def edge_ticks(c, W, H):
    """Streck 1-10 mm in från varje kant. Det första synliga strecket visar hur mycket som klipps."""
    c.setLineWidth(0.3)
    c.setFont("Helvetica", 5)
    xm, ym = W * 0.62, H * 0.62  # var strecken sitter längs kanterna
    for d in range(1, 11):
        x = d * mm
        c.line(x, ym - 4 * mm, x, ym + 4 * mm)
        c.line(W - x, ym - 4 * mm, W - x, ym + 4 * mm)
        c.line(xm - 4 * mm, x, xm + 4 * mm, x)
        c.line(xm - 4 * mm, H - x, xm + 4 * mm, H - x)
        if d % 2 == 0:
            c.drawCentredString(x, ym + 5 * mm, str(d))
            c.drawCentredString(W - x, ym + 5 * mm, str(d))
            c.drawString(xm + 5 * mm, x - 1.5, str(d))
            c.drawString(xm + 5 * mm, H - x - 1.5, str(d))


def ruler(c, x0, y0, length_mm, vertical=False):
    """Linjal med mm-streck. 100 mm på papperet = 100 % skalning."""
    c.setLineWidth(0.4)
    if vertical:
        c.line(x0, y0, x0, y0 + length_mm * mm)
    else:
        c.line(x0, y0, x0 + length_mm * mm, y0)
    c.setFont("Helvetica", 6)
    for i in range(length_mm + 1):
        t = 4 * mm if i % 10 == 0 else (2.5 * mm if i % 5 == 0 else 1.5 * mm)
        if vertical:
            c.line(x0, y0 + i * mm, x0 + t, y0 + i * mm)
            if i % 10 == 0:
                c.drawString(x0 + 5 * mm, y0 + i * mm - 2, str(i))
        else:
            c.line(x0 + i * mm, y0, x0 + i * mm, y0 + t)
            if i % 10 == 0:
                c.drawCentredString(x0 + i * mm, y0 + 5 * mm, str(i))


def arrow_up(c, cx, top, label):
    c.setLineWidth(2)
    c.line(cx, top - 35 * mm, cx, top)
    p = c.beginPath()
    p.moveTo(cx - 5 * mm, top - 8 * mm)
    p.lineTo(cx, top)
    p.lineTo(cx + 5 * mm, top - 8 * mm)
    c.drawPath(p, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(cx, top - 41 * mm, label)


def make_page(name, w_mm, h_mm):
    W, H = w_mm * mm, h_mm * mm
    out = TEST_DIR / f"calibration_{name}.pdf"
    c = canvas.Canvas(str(out), pagesize=(W, H))
    c.setTitle(f"Kalibrering {name}")

    boundary_lines(c, W, H)
    edge_ticks(c, W, H)

    # Hörnmarkeringar innanför 10 mm-linjen
    c.setFont("Helvetica-Bold", 9)
    c.drawString(12 * mm, H - 16 * mm, "UV")
    c.drawRightString(W - 12 * mm, H - 16 * mm, "UH")
    c.drawString(12 * mm, 13 * mm, "NV")
    c.drawRightString(W - 12 * mm, 13 * mm, "NH")

    # Linjaler 100 mm vågrätt och lodrätt, från 20 mm in
    ruler(c, 20 * mm, 20 * mm, 100)
    ruler(c, 20 * mm, 20 * mm, 100, vertical=True)

    arrow_up(c, W * 0.75, H - 16 * mm, "UPP / TOP")

    c.setFont("Helvetica-Bold", 24)
    title = name if name.startswith("A") else "Nummerlapp"
    c.drawCentredString(W * 0.5, H * 0.5 + 4 * mm, f"{title}  {w_mm} x {h_mm} mm")
    c.setFont("Helvetica", 8)
    tx = W * 0.5
    ty = H * 0.5 - 4 * mm
    for line in ("Linjalerna ska mäta exakt 100 mm (0 till 100) = 100 % skalning.",
                 "Heldragen ram = 5 mm från kanten, streckad ram = 10 mm.",
                 "Första synliga strecket vid kanten = hur många mm skrivaren klipper."):
        c.drawCentredString(tx, ty, line)
        ty -= 4 * mm

    # Färgrutor CMYK
    for i, col in enumerate([(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)]):
        c.setFillColorCMYK(*col)
        c.rect(W - 50 * mm + i * 9 * mm, 30 * mm, 8 * mm, 8 * mm, stroke=0, fill=1)

    c.showPage()
    c.save()
    print(f"Skrev {out}")


def main():
    for name, (w, h) in SIZES.items():
        make_page(name, w, h)


if __name__ == "__main__":
    main()
