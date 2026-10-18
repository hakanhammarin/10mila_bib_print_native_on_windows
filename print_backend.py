#!/usr/bin/env python3
"""
Utskrift av nummerlappar utan Acrobat: PDF -> PostScript (Ghostscript eller pdftops)
-> rått till skrivaren (port 9100) eller via Windows utskriftskö med datatyp RAW.
Används av bib_print.py och test/run_tests.py. Bara Pythons standardbibliotek.
"""
import ctypes
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent

# Papperet i facket: 160 x 225 mm stående (kortsidan först)
PAPER_W_PT = 453.543
PAPER_H_PT = 637.795

UEL = b"\x1b%-12345X"

# Orienteringar som testas i T3. cw/ccw = vi roterar själva, land = skrivaren väljer.
ORIENTS = {
    "gs_cw": "Ghostscript, stående sida, roterad medurs",
    "gs_ccw": "Ghostscript, stående sida, roterad moturs",
    "gs_land": "Ghostscript, liggande sida 225x160, skrivaren matchar facket",
    "pp_rot": "pdftops, stående sida, pdftops roterar själv (sidorna i normal ordning)",
}


# ==================== Verktyg ====================

def find_tool(names, bundled):
    for p in bundled:
        if os.name == "nt" and p.exists():  # medföljande .exe bara på Windows
            return str(p)
    for n in names:
        found = shutil.which(n)
        if found:
            return found
    return None


def ghostscript():
    return find_tool(["gswin64c", "gs"], [REPO_DIR / "tools" / "gs" / "bin" / "gswin64c.exe"])


def pdftops():
    return find_tool(["pdftops"], [REPO_DIR / "tools" / "poppler" / "pdftops.exe"])


def run(cmd):
    t = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"{Path(cmd[0]).name} misslyckades ({res.returncode}): {res.stderr.strip() or res.stdout.strip()}")
    return time.time() - t


# ==================== Konvertering PDF -> PS ====================

def ps_string(path):
    """Filnamn som PostScript-sträng. Ghostscript klarar / även på Windows."""
    return "(" + str(Path(path).resolve()).replace("\\", "/").replace("(", "\\(").replace(")", "\\)") + ")"


def convert(pdf, variant, out_ps, reverse=True, paper=(PAPER_W_PT, PAPER_H_PT)):
    """Konverterar pdf till PostScript enligt variant. Returnerar sekunder det tog.
    paper = papperet i facket (bredd, höjd) i punkter, stående. Liggande sidor roteras dit.
    reverse=True skriver sidorna i omvänd ordning (10 -> 1), bara med Ghostscript."""
    pw, ph = paper
    out_ps = str(out_ps)
    if variant.startswith("gs_"):
        gs = ghostscript()
        if not gs:
            raise RuntimeError("Hittar inte Ghostscript (tools/gs/bin/gswin64c.exe)")
        cmd = [gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", f"--permit-file-read={Path(pdf).resolve()}",
               "-sDEVICE=ps2write", f"-sOutputFile={out_ps}"]
        setup = ""
        if variant == "gs_cw":
            setup = f"<< /BeginPage {{ pop 0 {ph} translate -90 rotate }} >> setpagedevice "
        elif variant == "gs_ccw":
            setup = f"<< /BeginPage {{ pop {pw} 0 translate 90 rotate }} >> setpagedevice "
        if setup:
            cmd += ["-dFIXEDMEDIA", f"-dDEVICEWIDTHPOINTS={pw}", f"-dDEVICEHEIGHTPOINTS={ph}"]
        order = "pdfpagecount -1 1" if reverse else "1 1 pdfpagecount"
        pages = (f"{ps_string(pdf)} (r) file runpdfbegin {order} {{ pdfgetpage pdfshowpage }} for runpdfend")
        return run(cmd + ["-c", setup + pages])
    if variant.startswith("pp_"):
        pp = pdftops()
        if not pp:
            raise RuntimeError("Hittar inte pdftops (tools/poppler/pdftops.exe)")
        if variant == "pp_land":
            return run([pp, "-level3", "-origpagesizes", str(pdf), out_ps])
        return run([pp, "-level3", "-paperw", str(round(pw)), "-paperh", str(round(ph)), "-nocenter", str(pdf), out_ps])
    raise ValueError(variant)


def wrap_job(ps_bytes, name, tray=None, pjl=True):
    """Lägger PJL-huvud och ev. facksval runt PostScript-jobbet."""
    prefix = b""
    if tray is not None:
        prefix = f"%!PS-Adobe-3.0\n<< /MediaPosition {int(tray)} >> setpagedevice\n".encode()
    body = prefix + ps_bytes
    if not pjl:
        return body
    head = (UEL + b"@PJL JOB NAME=\"" + name.encode("ascii", "replace") + b"\"\r\n"
            b"@PJL ENTER LANGUAGE=POSTSCRIPT\r\n")
    tail = b"\r\n\x04" + UEL + b"@PJL EOJ\r\n" + UEL
    return head + body + tail


def pdf_job(pdf_bytes, name):
    return (UEL + b"@PJL JOB NAME=\"" + name.encode("ascii", "replace") + b"\"\r\n"
            b"@PJL ENTER LANGUAGE=PDF\r\n" + pdf_bytes + UEL + b"@PJL EOJ\r\n" + UEL)


# ==================== Skicka ====================

def send_raw9100(data, host, port=9100):
    t = time.time()
    with socket.create_connection((host, port), timeout=15) as s:
        s.sendall(data)
        s.shutdown(socket.SHUT_WR)
        s.settimeout(5)
        try:
            while s.recv(4096):
                pass
        except (socket.timeout, ConnectionResetError):
            pass
    return time.time() - t


def send_spooler_raw(data, printer, doc_name):
    """Skickar färdigt PostScript via Windows utskriftskö med datatyp RAW (drivrutinen renderar inget)."""
    if os.name != "nt":
        raise RuntimeError("Utskriftskön finns bara på Windows")
    from ctypes import wintypes

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", wintypes.LPWSTR), ("pOutputFile", wintypes.LPWSTR), ("pDatatype", wintypes.LPWSTR)]

    ws = ctypes.WinDLL("winspool.drv", use_last_error=True)
    t = time.time()
    h = wintypes.HANDLE()
    if not ws.OpenPrinterW(printer, ctypes.byref(h), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        di = DOC_INFO_1(doc_name, None, "RAW")
        if not ws.StartDocPrinterW(h, 1, ctypes.byref(di)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            ws.StartPagePrinter(h)
            written = wintypes.DWORD()
            chunk = 1 << 20
            for i in range(0, len(data), chunk):
                part = data[i:i + chunk]
                if not ws.WritePrinter(h, part, len(part), ctypes.byref(written)) or written.value != len(part):
                    raise ctypes.WinError(ctypes.get_last_error())
            ws.EndPagePrinter(h)
        finally:
            ws.EndDocPrinter(h)
    finally:
        ws.ClosePrinter(h)
    return time.time() - t



# ==================== Hela kedjan ====================

def print_pdf(pdf, ps_path, variant, via, host, port, printer, tray=None, pjl=True, reverse=True):
    """Konverterar och skickar en PDF. Returnerar (konverteringstid, sändtid) i sekunder.
    Kastar undantag om något går fel, så att anroparen vet att filen inte skickades."""
    conv = convert(pdf, variant, ps_path, reverse=reverse)
    data = wrap_job(Path(ps_path).read_bytes(), Path(pdf).stem, tray, pjl)
    if via == "spooler":
        sent = send_spooler_raw(data, printer, Path(pdf).name)
    else:
        sent = send_raw9100(data, host, port)
    return conv, sent
