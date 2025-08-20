from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene, QToolBar, QInputDialog
from PyQt6.QtGui import QPixmap, QPainter, QPen, QBrush, QFont, QAction
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem

class Annotator(QWidget):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.base_pixmap_item = None
        self.current_tool = "arrow"
        self.drawing = False
        self.start_pos = QPointF()
        self.temp_item = None

        lay = QVBoxLayout(self)
        self.toolbar = QToolBar()
        self.act_rect = QAction("Rect", self)
        self.act_arrow = QAction("Arrow", self)
        self.act_text = QAction("Text", self)
        self.act_highlight = QAction("Highlight", self)
        self.act_redact = QAction("Redact", self)
        for a, t in [(self.act_rect, "rect"), (self.act_arrow, "arrow"), (self.act_text, "text"),
                     (self.act_highlight, "highlight"), (self.act_redact, "redact")]:
            a.setCheckable(True)
            a.triggered.connect(lambda checked, tool=t: self.set_tool(tool))
            self.toolbar.addAction(a)
        self.act_arrow.setChecked(True)

        lay.addWidget(self.toolbar)
        lay.addWidget(self.view)

        self.view.viewport().installEventFilter(self)

    def set_tool(self, tool):
        self.current_tool = tool
        for a in [self.act_rect, self.act_arrow, self.act_text, self.act_highlight, self.act_redact]:
            a.setChecked(False)
        mapping = {
            "rect": self.act_rect,
            "arrow": self.act_arrow,
            "text": self.act_text,
            "highlight": self.act_highlight,
            "redact": self.act_redact
        }
        mapping[tool].setChecked(True)

    def load_pixmap(self, pm: QPixmap):
        self.scene.clear()
        self.base_pixmap_item = QGraphicsPixmapItem(pm)
        self.scene.addItem(self.base_pixmap_item)
        self.view.fitInView(self.base_pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def eventFilter(self, obj, event):
        if obj is self.view.viewport() and self.base_pixmap_item:
            if event.type() == event.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.drawing = True
                self.start_pos = self.view.mapToScene(event.position().toPoint())
                if self.current_tool == "text":
                    text, ok = QInputDialog.getText(self, "Add Text", "Label:")
                    if ok and text:
                        item = QGraphicsTextItem(text)
                        item.setDefaultTextColor(Qt.GlobalColor.black)
                        font = QFont()
                        font.setPointSize(12)
                        item.setFont(font)
                        item.setPos(self.start_pos)
                        self.scene.addItem(item)
                    self.drawing = False
                    return True
                elif self.current_tool in ("rect","highlight","redact"):
                    self.temp_item = QGraphicsRectItem(QRectF(self.start_pos, self.start_pos))
                    pen = QPen(Qt.GlobalColor.red, 2)
                    if self.current_tool == "highlight":
                        brush = QBrush(Qt.GlobalColor.yellow, Qt.BrushStyle.SolidPattern)
                        self.temp_item.setBrush(brush)
                        pen = QPen(Qt.GlobalColor.yellow, 2)
                        self.temp_item.setOpacity(0.35)
                    elif self.current_tool == "redact":
                        brush = QBrush(Qt.GlobalColor.black, Qt.BrushStyle.SolidPattern)
                        self.temp_item.setBrush(brush)
                        pen = QPen(Qt.GlobalColor.black, 2)
                        self.temp_item.setOpacity(0.95)
                    self.temp_item.setPen(pen)
                    self.scene.addItem(self.temp_item)
                    return True
                elif self.current_tool == "arrow":
                    self.temp_item = QGraphicsLineItem(self.start_pos.x(), self.start_pos.y(), self.start_pos.x(), self.start_pos.y())
                    self.temp_item.setPen(QPen(Qt.GlobalColor.red, 3))
                    self.scene.addItem(self.temp_item)
                    return True

            if event.type() == event.Type.MouseMove and self.drawing and self.temp_item:
                pos = self.view.mapToScene(event.position().toPoint())
                if isinstance(self.temp_item, QGraphicsRectItem):
                    self.temp_item.setRect(QRectF(self.start_pos, pos).normalized())
                elif isinstance(self.temp_item, QGraphicsLineItem):
                    self.temp_item.setLine(self.start_pos.x(), self.start_pos.y(), pos.x(), pos.y())
                return True

            if event.type() == event.Type.MouseButtonRelease and self.drawing:
                self.drawing = False
                self.temp_item = None
                return True
        return super().eventFilter(obj, event)

    def export_annotated(self) -> QPixmap | None:
        if not self.base_pixmap_item:
            return None
        rect = self.scene.itemsBoundingRect()
        image = QPixmap(rect.size().toSize())
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.scene.render(painter)
        painter.end()
        return image
