# Medföljande verktyg (Windows x64)

| Mapp | Verktyg | Version | Källa | Licens |
|------|---------|---------|-------|--------|
| `gs/bin` | Ghostscript `gswin64c.exe` + `gsdll64.dll` | 10.04.0 | [gs10040w64.exe](https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10040/gs10040w64.exe), sha256 `7e81126cb545e62e7ce9c92b5f11390c76c6321d25b049fdaf9aa6c6fc4eac4f` | AGPL, se `gs/COPYING` |
| `poppler` | `pdftops.exe` + de dll-filer den behöver | 24.08.0 | [Release-24.08.0-0.zip](https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip), sha256 `58a6f9ae269756231d2f9aa6cba39d75fec6deacaf3c4a50683383b5f3d5a527` | GPL 2, se `poppler/COPYING` |
| `.` | `vcredist_x64.exe` (Microsoft Visual C++ 2015–2022 runtime) | från Ghostscript-installern | samma som Ghostscript | Microsoft |

Båda verktygen behöver Visual C++ runtime. `python test\run_tests.py info` säger om den saknas;
kör då `tools\vcredist_x64.exe` en gång (kräver admin).
