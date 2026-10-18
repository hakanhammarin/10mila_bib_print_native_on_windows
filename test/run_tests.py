#!/usr/bin/env python3
"""
Testprogram för native nummerlappsutskrift på Windows (utan Acrobat).
Kör testerna T0-T5 och TC i PLAN.md och loggar resultaten i test/out/results.md.

    python run_tests.py              # meny
    python run_tests.py t3           # ett test direkt
    python run_tests.py t4 --orient cw
    python run_tests.py t3 --dry-run # skapa bara filerna i test/out, skicka inget

Bara Pythons standardbibliotek behövs.
"""
import argparse
import datetime
import glob
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REPO_DIR = TEST_DIR.parent
sys.path.insert(0, str(REPO_DIR))
from print_backend import (  # noqa: E402
    ORIENTS, PAPER_H_PT, PAPER_W_PT, convert, ghostscript, pdftops, pdf_job,
    send_raw9100, send_spooler_raw, wrap_job,
)

OUT_DIR = TEST_DIR / "out"
RESULTS = OUT_DIR / "results.md"
CALIBRATION_PDF = TEST_DIR / "calibration_225x160.pdf"
PLAIN_CALIBRATION = {"A4": TEST_DIR / "calibration_A4.pdf", "A5": TEST_DIR / "calibration_A5.pdf"}
SAMPLE_BIB_PDF = TEST_DIR / "sample_bib.pdf"
A5_PORTRAIT_PT = (419.528, 595.276)  # A5-papper stående i facket


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


def tc(args):
    """TC: kalibrering på vanligt papper: A4 stående, A5 liggande som en nummerlapp (--size A4 eller A5)."""
    size = args.size or "A4"
    print(f"\nTC {size}: lägg vanligt {size}-papper i facket (kortsidan in) och ställ in facket på {size} på panelen.")
    if not args.dry_run:
        input("Tryck Enter när papperet ligger i ... ")
    if size == "A4":
        # A4 stående på A4 stående: ingen rotation, bara 100 % och marginaler
        variants, paper = ["gs_land"], None
    else:
        # A5 liggande på A5 stående papper: samma rotation som nummerlappen, alla varianter som i T3
        variants, paper = ([args.orient] if args.orient else list(ORIENTS)), A5_PORTRAIT_PT
    for v in variants:
        ps = OUT_DIR / f"tc_{size}_{v}.ps"
        try:
            secs = convert(PLAIN_CALIBRATION[size], v, ps, **({"paper": paper} if paper else {}))
        except Exception as e:
            print(f"  ❌ {e}")
            log("tc", f"{size} {v}", f"KONVERTERINGSFEL: {e}", args)
            continue
        what = "ingen rotation" if size == "A4" else ORIENTS[v]
        deliver(wrap_job(ps.read_bytes(), f"TC {size} {v}", args.tray, not args.no_pjl), f"TC {size}", args,
                "tc", f"{size}_{v}", f"calibration_{size}.pdf på vanligt papper, {what}, konvertering {secs:.1f} s")


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


TESTS = {"info": t_info, "t0": t0, "t1": t1, "tc": tc, "t2": t2, "t3": t3, "t4": t4, "t5": t5}


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
    p.add_argument("--size", choices=list(PLAIN_CALIBRATION), help="papper för tc (A4 eller A5)")
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
