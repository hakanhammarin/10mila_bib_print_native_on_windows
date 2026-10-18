#!/usr/bin/env python3
"""
Skriver ut nummerlappar på Windows utan Acrobat.
Samma arbetsgång som acrobat_print_2.py: ange startnummer och antal, filerna
<nr>.pdf skrivs ut och flyttas till printed. R<nr> skriver ut en nummerlapp igen
från printed (t.ex. R101).
"""
import os
import re
import shutil
import tempfile
from pathlib import Path

from print_backend import print_pdf
from settings import (
    WIN_PRINT_BACKEND,
    WIN_PRINT_VARIANT,
    WIN_PRINTER_HOST,
    WIN_PRINTER_NAME,
    WIN_PRINTER_PORT,
    WIN_REVERSE_PAGES,
    WIN_SOURCE_DIR,
    WIN_TRAY,
    WIN_USE_PJL,
)

REPRINT = re.compile(r"^r\s*(\d+)$")


def get_target_dir():
    return os.path.join(WIN_SOURCE_DIR, "printed")


def send(file_path, work_dir):
    """Skriver ut en PDF. True först när skrivaren (eller kön) har tagit emot hela jobbet."""
    ps_path = os.path.join(work_dir, Path(file_path).stem + ".ps")
    try:
        print_pdf(file_path, ps_path, WIN_PRINT_VARIANT, WIN_PRINT_BACKEND, WIN_PRINTER_HOST,
                  WIN_PRINTER_PORT, WIN_PRINTER_NAME, WIN_TRAY, WIN_USE_PJL, WIN_REVERSE_PAGES)
        return True
    except Exception as e:
        print(f"Fel vid utskrift: {e}")
        return False
    finally:
        if os.path.exists(ps_path):
            os.remove(ps_path)


def reprint(nr, target_dir, work_dir):
    """Skriver ut nr.pdf igen från printed. Filen ligger kvar i printed."""
    filename = f"{nr}.pdf"
    path = os.path.abspath(os.path.join(target_dir, filename))
    if not os.path.exists(path):
        if os.path.exists(os.path.join(WIN_SOURCE_DIR, filename)):
            print(f"⚠️ {filename} är inte utskriven än, den ligger i {WIN_SOURCE_DIR}")
        else:
            print(f"⚠️ Saknas i printed: {filename}")
        return
    if send(path, work_dir):
        print(f"✅ Omtryck skickat {filename}")
    else:
        print(f"❌ Omtryck misslyckades {filename}")


def main():
    target_dir = get_target_dir()
    os.makedirs(target_dir, exist_ok=True)
    work_dir = tempfile.mkdtemp(prefix="bibs_")

    while True:
        print("\n=== Bib Printer (utan Acrobat) ===")
        print("--- Skriv 'exit' för att avsluta, 'R101' för att skriva ut 101 igen ---")

        user_input = input("Startnummer: ").strip().lower()
        if user_input == 'exit':
            break

        m = REPRINT.match(user_input)
        if m:
            reprint(int(m.group(1)), target_dir, work_dir)
            continue

        try:
            start_nr = int(user_input)
            antal = int(input("Antal: "))
        except ValueError:
            print("❌ Felaktig inmatning. Ange siffror, R<nr> eller 'exit'.")
            continue

        print(f"\nSkriver ut {antal} filer till {WIN_PRINTER_HOST if WIN_PRINT_BACKEND == 'raw9100' else WIN_PRINTER_NAME}...")

        for i in range(start_nr, start_nr + antal):
            filename = f"{i}.pdf"
            source_path = os.path.abspath(os.path.join(WIN_SOURCE_DIR, filename))

            if not os.path.exists(source_path):
                print(f"⚠️ Saknas: {filename}")
                continue

            if send(source_path, work_dir):
                target_path = os.path.join(target_dir, filename)
                try:
                    shutil.move(source_path, target_path)
                    print(f"✅ Skickat {filename}")
                except Exception as e:
                    print(f"⚠️ Filen utskriven men kunde inte flyttas: {e}")
            else:
                print(f"❌ Misslyckades med {filename}")

        print("\n--- Omgången klar! Återgår till start ---")

    shutil.rmtree(work_dir, ignore_errors=True)
    print("Programmet avslutas.")


if __name__ == "__main__":
    main()
