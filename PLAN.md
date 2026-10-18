# Plan: native BIB printing on Windows (no Acrobat)

Goal: replace `Acrobat.exe /t` in
[10mila_bib_print_via_acrobat_reader_on_windows](https://github.com/hakanhammarin/10mila_bib_print_via_acrobat_reader_on_windows)
with a path that needs no PDF viewer, while keeping the operator process exactly the same.

## 1. What stays the same (the process)

Taken from `acrobat_print_2.py`, `nummerlappar.cmd`, `settings.py` and
"Skrivarinställningar för Nummerlappsutskrift 10MILA 2026.pdf":

- Program and bibs live in `C:\bibs`, bibs in `C:\bibs\out_bibs\<nr>.pdf`.
- Operator starts `nummerlappar.cmd` from the desktop.
- Prompt `Startnummer:` then `Antal:`, `exit` quits. Same Swedish messages
  (`✅ Skickat`, `⚠️ Saknas`, `❌ Misslyckades`).
- Each printed file is moved to `C:\bibs\out_bibs\printed`.
- Settings stay in `settings.py` (`WIN_PRINTER_NAME = "OKIC542PS"`,
  `WIN_SOURCE_DIR = r"C:\bibs\out_bibs"`), plus a few new keys (section 4).
- Printer: OKI C542 with PostScript, reached by the hosts entry
  `192.168.1.27 OKIC542PS`, Tray 1 set on the panel to Custom 160 x 225 mm,
  paper loaded short edge first.

What changes: a file is "sent" when the printer (or spooler) has accepted the
whole job, not after a blind `sleep(5)` + `taskkill`. That makes it faster and
means "✅ Skickat" is actually true.

## 2. Facts about the PDFs

Checked on `out_bibs/1.pdf`:

- 10 pages per file, every page 637.795 x 453.543 pt = **225 x 160 mm landscape**, `/Rotate 0`.
- PDF 1.4 from pypdf, embedded TrueType/Type1C subsets, CMYK images at 300 dpi,
  one image with a soft mask (transparency). Helvetica is referenced but not embedded.
- The paper in the tray is 160 x 225 mm portrait (short edge feed), so every
  page needs a 90° rotation somewhere. Acrobat did it via "Auto" orientation;
  on macOS CUPS did it via `orientation-requested=4` + `media=Custom.160x225mm`.

The rotation plus the custom size is, in my reading, why earlier Windows attempts
failed: the Windows GDI path (driver + DEVMODE) tends to pick the wrong form,
scale to fit, or add margins. The macOS path worked because it never went
through GDI: it handed PostScript straight to the printer. So the plan copies
the macOS path.

## 3. Approach

### Primary: PDF → PostScript → raw to the printer (the macOS path, on Windows)

```
N.pdf ──(Ghostscript ps2write, or poppler pdftops)──► N.ps
      ──(prepend PJL + setpagedevice for 160x225, tray, rotation)──►
      ──(raw TCP 9100  or  Windows spooler, datatype RAW)──► OKI C542 PS
```

- Conversion: bundle a portable `gswin64c.exe` (Ghostscript) as the first choice
  (`-sDEVICE=ps2write`, it handles the soft-mask transparency by flattening),
  with poppler `pdftops.exe -level3 -origpagesizes` as the alternative. Both are
  free command-line tools, no viewer, no GUI, nothing to `taskkill`.
- Page setup goes into the PostScript itself, so the Windows driver cannot
  change it: `<< /PageSize [453.54 637.80] /ImagingBBox null >> setpagedevice`
  plus a 90° rotate of each page, or `PageSize [637.80 453.54]` and let the
  printer match the tray. Which one the OKI picks correctly is test T3.
- Tray: either the printer picks Tray 1 by matching the size (how CUPS did it)
  or we force it with PJL `@PJL SET MEDIASOURCE=TRAY1` / PS `/MediaPosition`.
- Sending, two options, both tested:
  - **A. Raw TCP port 9100** to `OKIC542PS`. Simplest, does not depend on the
    Windows driver at all. Python standard library only.
  - **B. Windows spooler with datatype RAW** to the existing queue `OKIC542PS`
    (`win32print.OpenPrinter / StartDocPrinter(..., "RAW") / WritePrinter`).
    Jobs show in the normal print queue, the driver is bypassed for rendering.
- Speed: convert all files of the batch first (or the next file while the
  current one is sending), then send. The OKI renders PS natively, which the
  settings guide already notes is the fast path.

### Fallback 1: printer-native PDF

Some OKI C5xx models accept PDF directly over 9100 (`@PJL ENTER LANGUAGE=PDF`).
If the C542 does, we skip conversion and send the PDF with a PJL header. Cheap to
test (T2), but not counted on.

### Fallback 2: render ourselves and print through GDI

PyMuPDF (or pdfium) renders each page at 600 dpi, rotated, and we draw it on
a printer DC with a DEVMODE we fill ourselves (`dmPaperSize=DMPAPER_USER`,
`dmPaperWidth=1600`, `dmPaperLength=2250`, tray, no scaling). This is the path
that probably failed before, so it is only the last resort. It is also the slowest.

Not planned: SumatraPDF or another viewer. It would just swap one viewer for another.

## 4. Proposed structure of the new repo

```
bib_print.py          # same interactive loop as acrobat_print_2.py
print_backend.py      # convert + send, one function per backend
settings.py           # existing settings + the new keys below
nummerlappar.cmd      # unchanged idea: cd c:\bibs, run bib_print.py
tools/                # gswin64c.exe (+ dll) or pdftops.exe, bundled
test/                 # test pages and the test script for section 5
README.md             # install steps (Python 3.1x, pip install, copy to C:\bibs)
```

New keys in `settings.py`:

```python
WIN_PRINT_BACKEND = "raw9100"   # raw9100 | spooler_raw | pdf_direct | gdi
WIN_PRINTER_HOST = "OKIC542PS"  # resolved through the hosts file
WIN_PRINTER_PORT = 9100
WIN_CONVERTER = "ghostscript"   # ghostscript | pdftops
WIN_ROTATE = "ps_rotate"        # ps_rotate | printer_match (decided by test T3)
WIN_TRAY_PJL = "TRAY1"
```

Optionally later: package as one `bib_print.exe` with PyInstaller so the
Windows machine does not need Python.

## 5. What to test on the Windows machine and the PS printer

Prepare:

- Windows machine with Python 3.1x and the OKI C542 PS driver installed as
  `OKIC542PS` (as in the settings guide), hosts entry in place.
- Printer: Tray 1 = Custom 160 x 225 mm, paper loaded short edge first.
- Plenty of plain A4 for the early tests plus a stack of bib paper.
- I will put the test files and a `test/run_tests.py` in the repo before you start.

| # | Test | What we learn | Pass |
|---|------|---------------|------|
| T0 | `Test-NetConnection OKIC542PS -Port 9100` (also 515, 631) in PowerShell | Which raw ports the printer accepts | 9100 open |
| T1 | Send a tiny hand-written PS file (one A4 page with text) to 9100 | Raw PS works at all | A page comes out |
| T2 | Send `1.pdf` with `@PJL ENTER LANGUAGE=PDF` to 9100 | Whether Fallback 1 exists | Bib prints, or error page / nothing |
| T3 | Send a **calibration page** (frame 5 mm inside the edges, "TOP" arrow, 10 mm ruler marks, the text "225x160") four ways: PageSize portrait + PS rotate 90, portrait + rotate 270, landscape PageSize with printer matching, landscape + `/Policies` | Which combination lands right side up, unscaled, from Tray 1 | Frame fully visible, ruler marks measure 10 mm, correct tray, no "load paper" prompt |
| T4 | Convert `1.pdf` with Ghostscript and with pdftops, send with the winning T3 setup | Converter choice; transparency, fonts, colours, barcode sharpness | Looks identical to an Acrobat print held next to it, barcode scans |
| T5 | Same as T4 but through the spooler (`spooler_raw`) | Whether the queue path works too | Same result, job visible in the queue |
| T6 | Run the full program: Startnummer 1, Antal 2 | End-to-end process, file move to `printed` | 20 pages, both files in `printed` |
| T7 | Time 10 files (100 pages) with the native path vs Acrobat | Speed | Native not slower |
| T8 | Error cases: printer off, paper out mid-batch, missing file number | Messages and that a file is only moved when it was really sent | Clear message, unsent files stay in `out_bibs` |
| T9 | Only if T1–T5 all fail: GDI fallback with the same calibration page | Whether Fallback 2 is needed | As T3 |

Please note for each test: what came out (photo is fine), which tray it took,
orientation, and any message on the printer panel. Also tell me the exact
printer model and firmware (panel: Configuration / Print Information).

## 6. Order of work

1. I add the test assets (calibration page, PJL variants, `test/run_tests.py`)
   to this repo. You run T0–T5 and report.
2. From the results I fix backend, converter and rotation in `settings.py`
   defaults and write `bib_print.py` + `print_backend.py`.
3. You run T6–T8 on the real setup.
4. README with the install steps, the same style as the Acrobat settings guide.
5. Optional: PyInstaller `.exe`.

## 7. Open questions for you

- Is the 10-page file meant to print all 10 pages (one bib per leg)? I assume yes, as Acrobat does today.
- Is it fine to bundle Ghostscript (AGPL) or poppler (GPL) in the repo? For an internal tool that is normally no problem; the alternative is installing them separately.
