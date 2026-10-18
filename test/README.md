# Tester på Windows-datorn och PS-skrivaren

Se PLAN.md avsnitt 5 för vad varje test visar.

## Förbered

1. Kopiera hela repot till `C:\bibs` (eller klona det dit).
2. Python 3.1x installerat. Inga pip-paket behövs.
3. OKI C542 PS-drivrutinen installerad som `OKIC542PS`, hosts-raden `192.168.1.27 OKIC542PS` på plats.
4. Fack 1 = Custom 160 x 225 mm, nummerlappspapper med kortsidan in.
   För `tc`: vanligt A4- eller A5-papper i facket och facket inställt på samma storlek.

## Kalibreringssidorna

`calibration_A4.pdf`, `calibration_A5.pdf` och `calibration_225x160.pdf` har en heldragen ram
5 mm från papperskanten, en streckad ram 10 mm in, mm-streck 1-10 mm in från varje kant och
två linjaler på 100 mm. Mät linjalerna med en riktig linjal: 100 mm = 100 % skalning.
Det första synliga strecket vid varje kant visar hur många mm skrivaren inte kan skriva ut.
`python make_calibration.py` skapar om dem (kräver reportlab).

## Kör

```
cd C:\bibs\test
python run_tests.py info      # verktyg, VC++ runtime, skrivare, PPD (kopieras till test\out)
python run_tests.py t0        # portar 9100/515/631/80
python run_tests.py t1        # minimal PostScript-sida
python run_tests.py tc --size A4   # kalibrering på vanligt A4: 100 % skalning och marginaler
python run_tests.py tc --size A5   # samma på vanligt A5
python run_tests.py t2        # PDF direkt till skrivaren
python run_tests.py t3        # kalibreringssidan i 4 varianter (4 ark)
python run_tests.py t4 --orient gs_cw    # riktig nummerlapp, 10 sidor, med den variant som var bäst i T3
python run_tests.py t5 --orient gs_cw    # samma via Windows utskriftskö (RAW)
```

Utan argument visas en meny. Efter varje utskrift frågar programmet vad som kom ut och
sparar svaret i `test\out\results.md`.

Nummerlappar skrivs i omvänd ordning, sida 10 först och sida 1 sist (Ghostscript-varianterna).

Flaggor vid behov: `--host 192.168.1.27`, `--tray N` (tvinga fack), `--no-pjl`, `--dry-run` (skicka inget).

## Skicka tillbaka

`test\out\results.md`, `test\out\info.txt`, PPD-filen i `test\out` och gärna foton på arken.
