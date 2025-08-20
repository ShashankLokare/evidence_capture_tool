import os, zipfile

def zip_session(session_dir: str, zip_path: str) -> str:
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(session_dir):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, session_dir)
                zf.write(full, rel)
    return zip_path

def docx_to_pdf(docx_path: str, pdf_path: str) -> bool:
    try:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
        return True
    except Exception:
        return False
