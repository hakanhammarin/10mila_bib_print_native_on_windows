# 10mila nummerlappsutskrift på Windows utan Acrobat

PDF → PostScript (medföljande Ghostscript) → rått till OKI-skrivaren på port 9100,
eller via Windows utskriftskö som RAW. Samma arbetsgång som
[Acrobat-versionen](https://github.com/hakanhammarin/10mila_bib_print_via_acrobat_reader_on_windows).

## Installera

1. Python 3.1x. Inga pip-paket behövs.
2. Kopiera repot till `C:\bibs`, nummerlapparna till `C:\bibs\out_bibs` (`1.pdf`, `2.pdf` ...).
3. Hosts-raden `192.168.1.27 OKIC542PS` i `C:\Windows\System32\drivers\etc\hosts`.
4. Fack 1 på skrivaren: Custom 160 x 225 mm, kortsidan in.
5. Om `python test\run_tests.py info` säger att Visual C++ runtime saknas: kör `tools\vcredist_x64.exe` en gång.
6. Lägg `nummerlappar.cmd` på skrivbordet.

## Använd

Kör `nummerlappar.cmd`.

- `Startnummer:` och `Antal:` skriver ut `<nr>.pdf` och flyttar filerna till `out_bibs\printed`.
- Varje fil skrivs i omvänd ordning, sida 10 först och sida 1 sist.
- `R101` skriver ut nummerlapp 101 igen från `printed`.
- `exit` avslutar.

Inställningar finns i `settings.py`. Tester och kalibreringssidor finns i `test/` (se `test/README.md`), planen i `PLAN.md`.
