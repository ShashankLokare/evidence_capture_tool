from __future__ import annotations
import os, sys, json, csv, hashlib
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox, QTabWidget,
    QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel, QLineEdit, QTableWidget,
    QTableWidgetItem, QToolBar, QStatusBar, QSplitter
)
from PyQt6.QtGui import QKeySequence, QPixmap, QAction
from PyQt6.QtCore import Qt

from core.settings import load_settings
from core.capture import grab_fullscreen, grab_region
from core.annotate import Annotator
from core.word_writer import WordWriter
from core.db import EvidenceDB
from core.metadata import SessionInfo, session_root
from core.exporter import zip_session, docx_to_pdf
from ui.dialogs import SessionDialog

APP_TITLE = "Evidence Capture App"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1200, 800)
        self.settings = load_settings()

        self.session_info: SessionInfo | None = None
        self.session_dir: str | None = None
        self.images_dir: str | None = None
        self.word_path: str | None = None
        self.word: WordWriter | None = None
        self.db: EvidenceDB | None = None
        self.step_counter = 0

        # Toolbar
        tb = QToolBar("Main")
        self.addToolBar(tb)
        act_new_session = QAction("New Session", self)
        act_new_session.triggered.connect(self.new_session)
        tb.addAction(act_new_session)

        act_new_word = QAction("New Word File", self)
        act_new_word.triggered.connect(self.new_word_file)
        tb.addAction(act_new_word)

        tb.addSeparator()
        self.act_cap_region = QAction("Capture Region", self)
        self.act_cap_region.setShortcut(QKeySequence("Ctrl+1"))
        self.act_cap_region.triggered.connect(self.capture_region)
        tb.addAction(self.act_cap_region)

        self.act_cap_full = QAction("Capture Full Screen", self)
        self.act_cap_full.setShortcut(QKeySequence("Ctrl+2"))
        self.act_cap_full.triggered.connect(self.capture_full)
        tb.addAction(self.act_cap_full)

        tb.addSeparator()
        self.act_save_img = QAction("Save Image", self)
        self.act_save_img.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save_img.triggered.connect(self.save_image_only)
        tb.addAction(self.act_save_img)

        self.act_save_word = QAction("Save to Word", self)
        self.act_save_word.setShortcut(QKeySequence("Ctrl+W"))
        self.act_save_word.triggered.connect(self.save_image_to_word)
        tb.addAction(self.act_save_word)

        tb.addSeparator()
        self.act_export_zip = QAction("Export ZIP", self)
        self.act_export_zip.triggered.connect(self.export_zip)
        tb.addAction(self.act_export_zip)

        self.act_export_pdf = QAction("Export PDF", self)
        self.act_export_pdf.triggered.connect(self.export_pdf)
        tb.addAction(self.act_export_pdf)

        # Left session panel
        left = QWidget()
        lv = QVBoxLayout(left)
        self.lbl_session = QLabel("No session")
        lv.addWidget(self.lbl_session)
        lv.addWidget(QLabel("Caption for next image:"))
        self.ed_caption = QLineEdit()
        lv.addWidget(self.ed_caption)
        lv.addStretch()
        self.btn_open_session = QPushButton("Open Session Folder")
        self.btn_open_session.clicked.connect(self.open_session_folder)
        lv.addWidget(self.btn_open_session)

        # Tabs
        self.tabs = QTabWidget()
        # Steps tab
        steps_tab = QWidget()
        stv = QVBoxLayout(steps_tab)
        self.ed_steps = QTextEdit()
        self.ed_steps.setPlaceholderText("Type your steps here. Each line = one step.")
        stv.addWidget(self.ed_steps)
        btns = QHBoxLayout()
        self.btn_append_steps = QPushButton("Append to Word")
        self.btn_append_steps.clicked.connect(self.append_steps_to_word)
        btns.addWidget(self.btn_append_steps)
        self.btn_append_clear = QPushButton("Append & Clear")
        self.btn_append_clear.clicked.connect(lambda: (self.append_steps_to_word(), self.ed_steps.clear()))
        btns.addWidget(self.btn_append_clear)
        stv.addLayout(btns)
        self.tabs.addTab(steps_tab, "Steps Editor")

        # Annotator tab
        self.annotator = Annotator()
        self.tabs.addTab(self.annotator, "Screenshot Preview")

        # Evidence Log tab
        log_tab = QWidget()
        ltv = QVBoxLayout(log_tab)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Timestamp","Tester","TestCase","WindowTitle","ImagePath","SHA256"])
        ltv.addWidget(self.table)
        btn_export_csv = QPushButton("Export Evidence CSV")
        btn_export_csv.clicked.connect(self.export_evidence_csv)
        ltv.addWidget(btn_export_csv)
        self.tabs.addTab(log_tab, "Evidence Log")

        # Issues tab
        issues_tab = QWidget()
        iv = QVBoxLayout(issues_tab)
        self.ed_issue_title = QLineEdit()
        self.ed_issue_title.setPlaceholderText("Issue Title")
        self.ed_issue_steps = QTextEdit()
        self.ed_issue_steps.setPlaceholderText("Steps to Reproduce / Expected vs Actual")
        self.ed_issue_sev = QLineEdit()
        self.ed_issue_sev.setPlaceholderText("Severity (e.g., Minor/Major/Critical)")
        btn_issue = QPushButton("Save Issue (CSV & Word)")
        btn_issue.clicked.connect(self.save_issue)
        iv.addWidget(QLabel("Title")); iv.addWidget(self.ed_issue_title)
        iv.addWidget(QLabel("Details")); iv.addWidget(self.ed_issue_steps)
        iv.addWidget(QLabel("Severity")); iv.addWidget(self.ed_issue_sev)
        iv.addWidget(btn_issue)
        self.tabs.addTab(issues_tab, "Issues")

        # Layout
        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.tabs)
        split.setStretchFactor(1, 1)
        self.setCentralWidget(split)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

    # --- Session ---
    def new_session(self):
        dlg = SessionDialog(self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        data = dlg.data()
        if not data["test_case_id"] or not data["title"]:
            QMessageBox.warning(self, "Invalid", "Test Case ID and Title are required.")
            return
        base_dir = QFileDialog.getExistingDirectory(self, "Choose Base Folder for Session")
        if not base_dir:
            return
        self.session_info = SessionInfo(**data)
        self.session_dir = session_root(base_dir, self.session_info)
        self.images_dir = os.path.join(self.session_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)
        # init DB
        self.db = EvidenceDB(os.path.join(self.session_dir, "evidence.sqlite"))
        # save session json
        with open(os.path.join(self.session_dir, "session.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.lbl_session.setText(f"Session: {self.session_dir}")
        self.status.showMessage("Session created.")
        self.refresh_log()

    def new_word_file(self):
        if not self.session_dir:
            QMessageBox.information(self, "No session", "Create a session first.")
            return
        default = os.path.join(self.session_dir, "report.docx")
        path, _ = QFileDialog.getSaveFileName(self, "Create Word file", default, "Word Document (*.docx)")
        if not path:
            return
        self.word_path = path
        self.word = WordWriter(self.word_path)
        QMessageBox.information(self, "Done", f"Word file created at:\\n{path}")

    def open_session_folder(self):
        if not self.session_dir:
            QMessageBox.information(self, "No session", "Create a session first.")
            return
        path = os.path.abspath(self.session_dir)
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')

    # --- Capture ---
    def ensure_session_and_word(self):
        if not self.session_dir:
            QMessageBox.information(self, "No session", "Create a session first.")
            return False
        if not self.word:
            QMessageBox.information(self, "No Word file", "Create a Word file first.")
            return False
        return True

    def capture_full(self):
        pm = grab_fullscreen()
        self.annotator.load_pixmap(pm)
        self.tabs.setCurrentWidget(self.annotator)
        self.status.showMessage("Captured full screen.")

    def capture_region(self):
        pm = grab_region()
        if pm is None:
            self.status.showMessage("Region capture canceled.")
            return
        self.annotator.load_pixmap(pm)
        self.tabs.setCurrentWidget(self.annotator)
        self.status.showMessage("Captured region.")

    # --- Save ---
    def _save_pixmap(self, pm: QPixmap, caption: str) -> tuple[str,str]:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"TC_{self.session_info.test_case_id}_Fig_{ts}.png"
        full = os.path.join(self.images_dir, fname)
        pm.save(full, "PNG")
        sha256 = hashlib.sha256(open(full, "rb").read()).hexdigest()
        # DB row
        self.db.add_capture({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "tester": self.session_info.tester,
            "test_case": self.session_info.test_case_id,
            "window_title": caption,
            "process": "",
            "dpi": "",
            "screen_size": "",
            "image_path": full,
            "sha256": sha256,
            "caption": caption
        })
        return full, sha256

    def save_image_only(self):
        if not self.session_dir:
            QMessageBox.information(self, "No session", "Create a session first.")
            return
        pm = self.annotator.export_annotated()
        if not pm:
            QMessageBox.information(self, "No image", "Nothing to save. Capture first.")
            return
        caption = self.ed_caption.text().strip() or "Screenshot"
        path, sha = self._save_pixmap(pm, caption)
        QMessageBox.information(self, "Saved", f"Image saved:\\n{path}\\nSHA-256: {sha}")
        self.refresh_log()

    def save_image_to_word(self):
        if not self.ensure_session_and_word():
            return
        pm = self.annotator.export_annotated()
        if not pm:
            QMessageBox.information(self, "No image", "Nothing to save. Capture first.")
            return
        caption = self.ed_caption.text().strip() or "Screenshot"
        path, sha = self._save_pixmap(pm, caption)
        self.word.add_image_with_caption(path, caption, max_width_px=self.settings.get("embed_max_width_px", 1200))
        QMessageBox.information(self, "Saved", f"Embedded into Word:\\n{self.word_path}\\n\\nImage:\\n{path}\\nSHA-256: {sha}")
        self.refresh_log()

    # --- Steps ---
    def append_steps_to_word(self):
        if not self.ensure_session_and_word():
            return
        text = self.ed_steps.toPlainText().strip()
        if not text:
            return
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return
        self.word.append_steps(lines)
        # Log steps (simple counter)
        for l in lines:
            self.step_counter += 1
            if self.db:
                self.db.add_step(datetime.now().isoformat(timespec="seconds"), self.step_counter, l)
        QMessageBox.information(self, "Added", f"Appended {len(lines)} step(s) to Word.")

    # --- Evidence Log ---
    def refresh_log(self):
        if not self.db:
            return
        rows = self.db.fetch_captures()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, val in enumerate(r[:6]):
                it = QTableWidgetItem(str(val))
                self.table.setItem(i, j, it)

    def export_evidence_csv(self):
        if not self.db:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", os.path.join(self.session_dir, "evidence.csv"), "CSV (*.csv)")
        if not path:
            return
        self.db.export_captures_csv(path)
        QMessageBox.information(self, "Exported", f"CSV saved to:\\n{path}")

    # --- Issues ---
    def save_issue(self):
        if not self.ensure_session_and_word():
            return
        title = self.ed_issue_title.text().strip()
        details = self.ed_issue_steps.toPlainText().strip()
        sev = self.ed_issue_sev.text().strip() or "Unspecified"
        if not title or not details:
            QMessageBox.information(self, "Incomplete", "Provide title and details.")
            return
        # Append to CSV
        csv_path = os.path.join(self.session_dir, "issues.csv")
        new = not os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["ts","title","severity","details"])
            w.writerow([datetime.now().isoformat(timespec="seconds"), title, sev, details])
        # Append to Word
        self.word.doc.add_heading("Issues", level=1)
        self.word.doc.add_paragraph(f"Title: {title}")
        self.word.doc.add_paragraph(f"Severity: {sev}")
        self.word.doc.add_paragraph(details)
        self.word.save()
        QMessageBox.information(self, "Saved", f"Issue saved to CSV and Word.")

    # --- Export ---
    def export_zip(self):
        if not self.session_dir:
            return
        default = os.path.join(os.path.dirname(self.session_dir), os.path.basename(self.session_dir) + ".zip")
        path, _ = QFileDialog.getSaveFileName(self, "Export Session ZIP", default, "ZIP (*.zip)")
        if not path:
            return
        zip_session(self.session_dir, path)
        QMessageBox.information(self, "Exported", f"ZIP saved:\\n{path}")

    def export_pdf(self):
        if not self.word_path:
            QMessageBox.information(self, "No Word", "Create and populate a Word document first.")
            return
        default = os.path.join(self.session_dir, "report.pdf")
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", default, "PDF (*.pdf)")
        if not path:
            return
        ok = docx_to_pdf(self.word_path, path)
        if ok:
            QMessageBox.information(self, "Exported", f"PDF saved:\\n{path}")
        else:
            QMessageBox.warning(self, "Unavailable", "PDF export requires 'docx2pdf' with MS Word/LibreOffice. Install with:\\n  pip install docx2pdf\\nOr export manually.")

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
