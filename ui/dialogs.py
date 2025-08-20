from __future__ import annotations
from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox

class SessionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Test Session")
        self.tc = QLineEdit()
        self.title = QLineEdit()
        self.build = QLineEdit()
        self.env = QLineEdit()
        self.tester = QLineEdit()
        self.tracker = QLineEdit()
        lay = QFormLayout(self)
        lay.addRow("Test Case ID", self.tc)
        lay.addRow("Title", self.title)
        lay.addRow("Build/Version", self.build)
        lay.addRow("Environment", self.env)
        lay.addRow("Tester", self.tester)
        lay.addRow("Tracker ID", self.tracker)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addRow(btns)

    def data(self):
        return {
            "test_case_id": self.tc.text().strip(),
            "title": self.title.text().strip(),
            "build": self.build.text().strip(),
            "environment": self.env.text().strip(),
            "tester": self.tester.text().strip(),
            "tracker_id": self.tracker.text().strip(),
        }
