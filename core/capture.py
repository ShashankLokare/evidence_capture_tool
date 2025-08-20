from __future__ import annotations
import time
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QAction

class RegionSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setWindowOpacity(0.35)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.start = None
        self.end = None
        self.selection = QRect()

    def paintEvent(self, event):
        if self.start and self.end:
            p = QPainter(self)
            p.setPen(QPen(QColor(0, 120, 255), 2, Qt.PenStyle.SolidLine))
            p.drawRect(self.selection)

    def mousePressEvent(self, event):
        self.start = event.position().toPoint()
        self.end = self.start
        self.selection = QRect(self.start, self.end)
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.position().toPoint()
        self.selection = QRect(self.start, self.end).normalized()
        self.update()

    def mouseReleaseEvent(self, event):
        self.end = event.position().toPoint()
        self.selection = QRect(self.start, self.end).normalized()
        self.close()

def grab_fullscreen() -> QPixmap:
    app = QApplication.instance()
    screen = app.primaryScreen()
    pm = screen.grabWindow(0)
    return pm

def grab_region() -> QPixmap | None:
    sel = RegionSelector()
    sel.show()
    app = QApplication.instance()
    app.processEvents()
    while sel.isVisible():
        app.processEvents()
        time.sleep(0.01)
    rect = sel.selection
    if rect.isNull() or rect.width() < 3 or rect.height() < 3:
        return None
    full = grab_fullscreen()
    return full.copy(rect)
