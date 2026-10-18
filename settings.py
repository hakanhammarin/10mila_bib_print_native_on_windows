#!/usr/bin/env python3
"""
Inställningar för nummerlappsutskrift på Windows utan Acrobat.
"""

# ==================== Windows Printing Settings ====================
WIN_PRINTER_NAME = "OKIC542PS"        # utskriftskön i Windows (används med WIN_PRINT_BACKEND = "spooler")
WIN_SOURCE_DIR = r"C:\bibs\out_bibs"  # här ligger 1.pdf, 2.pdf ...; utskrivna flyttas till printed

# Hur jobbet skickas: "raw9100" = direkt till skrivaren, "spooler" = via Windows utskriftskö (RAW)
WIN_PRINT_BACKEND = "raw9100"
WIN_PRINTER_HOST = "OKIC542PS"        # namn i hosts-filen eller IP-adress
WIN_PRINTER_PORT = 9100

# Konvertering och rotation, välj efter test T3:
#   gs_cw   = Ghostscript, roterad medurs till 160x225 stående
#   gs_ccw  = Ghostscript, roterad moturs
#   gs_land = Ghostscript, liggande 225x160, skrivaren matchar facket
#   pp_rot / pp_land = pdftops (kan inte skriva i omvänd ordning)
WIN_PRINT_VARIANT = "gs_cw"

WIN_REVERSE_PAGES = True  # sida 10 först, sida 1 sist
WIN_TRAY = None           # None = skrivaren väljer fack efter storlek, annars PostScript /MediaPosition
WIN_USE_PJL = True        # PJL-huvud runt jobbet
