# Evidence Capture App (PyQt6)

A cross-platform (Windows/macOS) desktop app to capture screenshots, annotate them, log evidence, and write steps & images into a Word (.docx) report.

**Created:** 2025-08-19 22:33

## Quickstart

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### Optional Packaging (PyInstaller)
```bash
pip install pyinstaller
pyinstaller --name EvidenceCapture --windowed --onefile app.py
```

## Shortcuts
- Ctrl/Cmd+1: Capture Region
- Ctrl/Cmd+2: Capture Full Screen
- Ctrl/Cmd+S: Save Annotated Image
- Ctrl/Cmd+W: Save to Word (image)
- Ctrl/Cmd+Z / Ctrl/Cmd+Y: Undo / Redo (basic)

## Notes
- Window-specific capture is OS-API-dependent; this app falls back to region selection for reliability.
- PDF export (docx→pdf) needs `docx2pdf` + MS Word/LibreOffice; optional.
