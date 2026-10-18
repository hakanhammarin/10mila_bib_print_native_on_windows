#!/usr/bin/env python3
"""
Testprogram för native nummerlappsutskrift på Windows (utan Acrobat).
Kör testerna T0-T5 i PLAN.md och loggar resultaten i test/out/results.md.

    python run_tests.py              # meny
    python run_tests.py t3           # ett test direkt
    python run_tests.py t4 --orient cw
    python run_tests.py t3 --dry-run # skapa bara filerna i test/out, skicka inget

Bara Pythons standardbibliotek behövs.
"""
import argparse
import ctypes
import datetime
import glob
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REPO_DIR = TEST_DIR.parent
OUT_DIR = TEST_DIR / "out"
RESULTS = OUT_DIR / "results.md"
CALIBRATION_PDF = TEST_DIR / "calibration_225x160.pdf"
SAMPLE_BIB_PDF = TEST_DIR / "sample_bib.pdf"

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


def convert(pdf, variant, out_ps, reverse=True):
    """Konverterar pdf till PostScript enligt variant. Returnerar sekunder det tog.
    reverse=True skriver sidorna i omvänd ordning (10 -> 1), bara med Ghostscript."""
    out_ps = str(out_ps)
    if variant.startswith("gs_"):
        gs = ghostscript()
        if not gs:
            raise RuntimeError("Hittar inte Ghostscript (tools/gs/bin/gswin64c.exe)")
        cmd = [gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", f"--permit-file-read={Path(pdf).resolve()}",
               "-sDEVICE=ps2write", f"-sOutputFile={out_ps}"]
        setup = ""
        if variant == "gs_cw":
            setup = f"<< /BeginPage {{ pop 0 {PAPER_H_PT} translate -90 rotate }} >> setpagedevice "
        elif variant == "gs_ccw":
            setup = f"<< /BeginPage {{ pop {PAPER_W_PT} 0 translate 90 rotate }} >> setpagedevice "
        if setup:
            cmd += ["-dFIXEDMEDIA", f"-dDEVICEWIDTHPOINTS={PAPER_W_PT}", f"-dDEVICEHEIGHTPOINTS={PAPER_H_PT}"]
        order = "pdfpagecount -1 1" if reverse else "1 1 pdfpagecount"
        pages = (f"{ps_string(pdf)} (r) file runpdfbegin {order} {{ pdfgetpage pdfshowpage }} for runpdfend")
        return run(cmd + ["-c", setup + pages])
    if variant.startswith("pp_"):
        pp = pdftops()
        if not pp:
            raise RuntimeError("Hittar inte pdftops (tools/poppler/pdftops.exe)")
        if variant == "pp_land":
            return run([pp, "-level3", "-origpagesizes", str(pdf), out_ps])
        return run([pp, "-level3", "-paperw", "454", "-paperh", "638", "-nocenter", str(pdf), out_ps])
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


# ==================== Logg ====================

def log(test, variant, details, args):
    OUT_DIR.mkdir(exist_ok=True)
    if args.dry_run:
        answer = "(dry-run, inget skickat)"
    else:
        print("\nTitta på utskriften: rätt fack? rättvänd? 100 % (linjalen 100 mm)? hur många mm klipps vid kanterna?")
        print("Felmeddelande på skrivarens display?")
        answer = input("Beskriv kort vad som kom ut (Enter = inget kom ut): ").strip() or "INGET KOM UT"
    with open(RESULTS, "a", encoding="utf-8") as f:
        f.write(f"- {datetime.datetime.now():%Y-%m-%d %H:%M} **{test}** `{variant}` {details} -> {answer}\n")


def deliver(data, name, args, test, variant, details, via=None):
    via = via or args.via
    path = OUT_DIR / f"{test}_{variant}.prn"
    OUT_DIR.mkdir(exist_ok=True)
    path.write_bytes(data)
    if args.dry_run:
        print(f"  skapade {path.name} ({len(data) // 1024} kB)")
        log(test, variant, details, args)
        return
    print(f"  skickar {path.name} ({len(data) // 1024} kB) via {via} ...")
    try:
        if via == "spooler":
            secs = send_spooler_raw(data, args.printer, name)
        else:
            secs = send_raw9100(data, args.host, args.port)
        details += f" (skickat på {secs:.1f} s)"
    except Exception as e:
        print(f"  ❌ kunde inte skicka: {e}")
        details += f" SKICKFEL: {e}"
    log(test, variant, details, args)


# ==================== Testerna ====================

def t_info(args):
    """Systeminfo, verktyg, skrivare och PPD-filen för OKI-drivrutinen."""
    OUT_DIR.mkdir(exist_ok=True)
    lines = [f"Python {sys.version.split()[0]}, {platform.platform()}",
             f"Ghostscript: {ghostscript()}", f"pdftops: {pdftops()}"]
    # Startar verktygen en gång; misslyckas det saknas oftast Visual C++ runtime
    for tool, flag in ((ghostscript(), "--version"), (pdftops(), "-v")):
        if tool:
            try:
                r = subprocess.run([tool, flag], capture_output=True, text=True, timeout=20)
                lines.append(f"  {Path(tool).name} {flag}: {(r.stdout + r.stderr).strip().splitlines()[0]}")
            except Exception as e:
                lines.append(f"  {Path(tool).name} startar inte: {e}")
    if os.name == "nt":
        sysdir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
        ok = all((sysdir / d).exists() for d in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"))
        lines.append(f"Visual C++ runtime: {'finns' if ok else 'SAKNAS - kör tools\\vcredist_x64.exe en gång'}")
        ps = ("Get-Printer | Format-List Name,DriverName,PortName,Type; "
              "Get-PrinterPort | Format-List Name,PrinterHostAddress,PortNumber,Protocol")
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        lines.append(res.stdout.strip())
        ppds = glob.glob(str(sysdir / "spool" / "drivers" / "x64" / "3" / "*.ppd")) + \
            glob.glob(str(sysdir / "spool" / "drivers" / "x64" / "3" / "*.PPD"))
        for ppd in ppds:
            text = Path(ppd).read_text("latin-1", errors="replace")
            if "C542" not in text and "OKI" not in text.upper():
                continue
            shutil.copy(ppd, OUT_DIR / Path(ppd).name)
            lines.append(f"PPD: {ppd} (kopierad till test/out)")
            for l in text.splitlines():
                if l.startswith(("*ModelName", "*InputSlot", "*DefaultInputSlot", "*CustomPageSize",
                                 "*ParamCustomPageSize", "*LanguageLevel", "*Product", "*PSVersion")):
                    lines.append("    " + l[:160])
    report = "\n".join(lines)
    print(report)
    (OUT_DIR / "info.txt").write_text(report, encoding="utf-8")
    print(f"\nSparat i {OUT_DIR / 'info.txt'}")


def t0(args):
    """T0: vilka portar svarar på skrivaren."""
    out = []
    for port, what in ((9100, "raw"), (515, "LPR"), (631, "IPP"), (80, "webb")):
        try:
            with socket.create_connection((args.host, port), timeout=3):
                state = "öppen"
        except OSError as e:
            state = f"stängd ({e.__class__.__name__})"
        print(f"  {args.host}:{port} {what}: {state}")
        out.append(f"{port}={state}")
    with open(RESULTS, "a", encoding="utf-8") as f:
        f.write(f"- {datetime.datetime.now():%Y-%m-%d %H:%M} **t0** {args.host}: {', '.join(out)}\n")


def t1(args):
    """T1: en minimal handskriven PostScript-sida 160x225 mm."""
    ps = f"""%!PS-Adobe-3.0
<< /PageSize [{PAPER_W_PT} {PAPER_H_PT}] >> setpagedevice
/Helvetica-Bold findfont 24 scalefont setfont
40 500 moveto (T1 raw PostScript OK) show
/Helvetica findfont 12 scalefont setfont
40 470 moveto (160 x 225 mm, staende) show
14.17 14.17 425.2 609.45 rectstroke
showpage
""".encode()
    deliver(wrap_job(ps, "T1", args.tray, not args.no_pjl), "T1", args, "t1", "handwritten", "minimal PS-sida")


def t2(args):
    """T2: skicka PDF direkt (om skrivaren kan PDF själv)."""
    deliver(pdf_job(CALIBRATION_PDF.read_bytes(), "T2"), "T2", args, "t2", "pdf_direct",
            "kalibreringssidan som PDF med @PJL ENTER LANGUAGE=PDF", via="raw9100")


def t3(args):
    """T3: kalibreringssidan i alla orienteringsvarianter."""
    variants = [args.orient] if args.orient else list(ORIENTS)
    for v in variants:
        print(f"\nT3 {v}: {ORIENTS[v]}")
        ps = OUT_DIR / f"t3_{v}.ps"
        try:
            secs = convert(CALIBRATION_PDF, v, ps)
        except Exception as e:
            print(f"  ❌ {e}")
            log("t3", v, f"KONVERTERINGSFEL: {e}", args)
            continue
        deliver(wrap_job(ps.read_bytes(), f"T3 {v}", args.tray, not args.no_pjl), f"T3 {v}", args,
                "t3", v, f"{ORIENTS[v]}, konvertering {secs:.1f} s")


def t4(args):
    """T4: riktig nummerlapp (10 sidor) med Ghostscript och pdftops, vald orientering."""
    orient = args.orient or "gs_cw"
    side = orient.split("_", 1)[1]  # cw / ccw / land / rot
    pairs = {"cw": ["gs_cw"], "ccw": ["gs_ccw", "pp_rot"], "rot": ["gs_ccw", "pp_rot"], "land": ["gs_land", "pp_land"]}[side]
    for v in pairs:
        print(f"\nT4 {v}")
        ps = OUT_DIR / f"t4_{v}.ps"
        try:
            secs = convert(SAMPLE_BIB_PDF, v, ps)
        except Exception as e:
            print(f"  ❌ {e}")
            log("t4", v, f"KONVERTERINGSFEL: {e}", args)
            continue
        deliver(wrap_job(ps.read_bytes(), f"T4 {v}", args.tray, not args.no_pjl), f"T4 {v}", args,
                "t4", v, f"sample_bib.pdf 10 sidor, konvertering {secs:.1f} s")
    if side == "cw":
        print("\n(pdftops kan bara rotera moturs; för pdftops-jämförelse kör: t4 --orient gs_ccw)")


def t5(args):
    """T5: samma som T4 men via Windows utskriftskö (RAW)."""
    v = args.orient or "gs_cw"
    ps = OUT_DIR / f"t5_{v}.ps"
    secs = convert(SAMPLE_BIB_PDF, v, ps)
    deliver(wrap_job(ps.read_bytes(), f"T5 {v}", args.tray, not args.no_pjl), f"T5 {v}", args,
            "t5", v, f"sample_bib.pdf via kön '{args.printer}', konvertering {secs:.1f} s", via="spooler")


TESTS = {"info": t_info, "t0": t0, "t1": t1, "t2": t2, "t3": t3, "t4": t4, "t5": t5}


def menu(args):
    while True:
        print("\n=== Test: native nummerlappsutskrift ===")
        for k, fn in TESTS.items():
            print(f"  {k:5} {fn.__doc__.strip().splitlines()[0]}")
        choice = input("Välj test (exit avslutar): ").strip().lower()
        if choice == "exit":
            break
        if choice in TESTS:
            TESTS[choice](args)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("test", nargs="?", choices=list(TESTS) + ["menu"], default="menu")
    p.add_argument("--host", default="OKIC542PS", help="skrivarens namn/IP för port 9100")
    p.add_argument("--port", type=int, default=9100)
    p.add_argument("--printer", default="OKIC542PS", help="namnet på utskriftskön i Windows (T5)")
    p.add_argument("--via", choices=["raw9100", "spooler"], default="raw9100")
    p.add_argument("--orient", choices=list(ORIENTS) + ["pp_land"], help="bara en variant")
    p.add_argument("--tray", type=int, help="tvinga fack med PostScript /MediaPosition N")
    p.add_argument("--no-pjl", action="store_true", help="skicka utan PJL-huvud")
    p.add_argument("--dry-run", action="store_true", help="skapa filer i test/out men skicka inget")
    args = p.parse_args()
    OUT_DIR.mkdir(exist_ok=True)
    if args.test == "menu":
        menu(args)
    else:
        TESTS[args.test](args)


if __name__ == "__main__":
    main()
