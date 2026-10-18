#!/usr/bin/env python3
"""
Skapar test/calibration_225x160.pdf: en kalibreringssida i samma format som
nummerlapparna (225 x 160 mm liggande) för att se rotation, skalning och
hur mycket av kanterna skrivaren klipper bort.
"""
from pathlib import Path
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

W, H = 225 * mm, 160 * mm
OUT = Path(__file__).parent / "calibration_225x160.pdf"


def edge_ticks(c):
    """Streck 1-10 mm in från varje kant. Det första synliga strecket visar hur mycket som klipps."""
    c.setLineWidth(0.3)
    c.setFont("Helvetica", 5)
    for d in range(1, 11):
        x = d * mm
        # vänster och höger kant
        c.line(x, H / 2 - 4 * mm, x, H / 2 + 4 * mm)
        c.line(W - x, H / 2 - 4 * mm, W - x, H / 2 + 4 * mm)
        # nederkant och överkant
        c.line(W / 3 - 4 * mm, x, W / 3 + 4 * mm, x)
        c.line(W / 3 - 4 * mm, H - x, W / 3 + 4 * mm, H - x)
        if d % 2 == 0:
            c.drawString(x - 1, H / 2 + 5 * mm, str(d))
            c.drawRightString(W - x + 1, H / 2 + 5 * mm, str(d))
            c.drawString(W / 3 + 5 * mm, x - 1.5, str(d))
            c.drawString(W / 3 + 5 * mm, H - x - 1.5, str(d))


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


def main():
    c = canvas.Canvas(str(OUT), pagesize=(W, H))
    c.setTitle("Kalibrering 225x160")

    # Ram 5 mm in från kanten
    c.setLineWidth(0.8)
    c.rect(5 * mm, 5 * mm, W - 10 * mm, H - 10 * mm)
    edge_ticks(c)

    # Hörnmarkeringar
    c.setFont("Helvetica-Bold", 10)
    c.drawString(7 * mm, H - 11 * mm, "UV")
    c.drawRightString(W - 7 * mm, H - 11 * mm, "UH")
    c.drawString(7 * mm, 7 * mm, "NV")
    c.drawRightString(W - 7 * mm, 7 * mm, "NH")

    # Pil mot överkanten
    cx = W * 0.7
    c.setLineWidth(2)
    c.line(cx, H - 60 * mm, cx, H - 20 * mm)
    p = c.beginPath()
    p.moveTo(cx - 6 * mm, H - 28 * mm)
    p.lineTo(cx, H - 18 * mm)
    p.lineTo(cx + 6 * mm, H - 28 * mm)
    c.drawPath(p, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(cx, H - 66 * mm, "UPP / TOP")

    # Linjaler: 200 mm vågrätt, 140 mm lodrätt
    ruler(c, 12.5 * mm, 20 * mm, 200)
    ruler(c, 20 * mm, 12.5 * mm, 140, vertical=True)

    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(W * 0.45, H * 0.52, "225 x 160 mm")
    c.setFont("Helvetica", 9)
    c.drawCentredString(W * 0.45, H * 0.52 - 8 * mm,
                        "Linjalen ska mäta exakt 100 mm mellan 0 och 100. Ramen ligger 5 mm in.")
    c.drawCentredString(W * 0.45, H * 0.52 - 13 * mm,
                        "Första synliga strecket vid kanten = hur många mm skrivaren klipper.")

    # Färgrutor CMYK
    for i, col in enumerate([(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)]):
        c.setFillColorCMYK(*col)
        c.rect(W - 50 * mm + i * 9 * mm, 30 * mm, 8 * mm, 8 * mm, stroke=0, fill=1)

    c.showPage()
    c.save()
    print(f"Skrev {OUT}")


if __name__ == "__main__":
    main()
