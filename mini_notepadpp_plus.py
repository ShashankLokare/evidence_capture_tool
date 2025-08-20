#!/usr/bin/env python3
# mini_notepadpp_plus.py
# Full-featured Notepad++-like editor using PySide6.
# Features:
# - Tabs, line numbers, current line highlight
# - Syntax highlighting (basic regex-based for Python/C/HTML/JSON)
# - Find/Replace dialog; Find Next/Prev
# - Find in Files (directory search) with dockable results
# - Recent files with "Clear Recent"
# - Word wrap toggle (correctly applied), Show whitespace, Zoom + %, Status bar
# - Toggle comment, Go to line
# - Reload from Disk, Save All
# - Drag & drop open
# - Dark/Light theme, toolbar with icons
#
# Quick start:
#   pip install PySide6
#   python mini_notepadpp_plus.py

from __future__ import annotations
import os
import re
import sys
import fnmatch
from pathlib import Path
from typing import Optional, List, Tuple

from PySide6.QtCore import (
    Qt, QRect, QSize, QSettings, Signal, QRegularExpression
)
from PySide6.QtGui import (
    QAction, QKeySequence, QPainter, QColor, QFont, QTextCursor,
    QSyntaxHighlighter, QTextCharFormat, QTextFormat, QCloseEvent,
    QPalette, QTextDocument, QTextOption, QIcon
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QPlainTextEdit, QTextEdit, QWidget, QVBoxLayout,
    QTabWidget, QMessageBox, QToolBar, QStatusBar, QLabel, QDialog, QGridLayout,
    QLineEdit, QCheckBox, QPushButton, QInputDialog, QStyle, QStyleFactory, QHBoxLayout,
    QDockWidget, QTreeWidget, QTreeWidgetItem, QHeaderView, QMenu
)

APP_ORG = "OpenDev"
APP_NAME = "MiniNotepadPP+"
MAX_RECENTS = 12
BASE_FONT_SIZE = 12

# ---------- Helpers: Syntax Highlighters ----------

def fmt(color: str = "#000", bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f

class RegexHighlighter(QSyntaxHighlighter):
    """Generic regex-driven highlighter for a few common languages."""
    def __init__(self, doc, language: str):
        super().__init__(doc)
        self.language = language.lower()
        self.rules: List[Tuple[re.Pattern, QTextCharFormat]] = []
        self._build_rules()

    def _rx(self, pattern, flags=re.MULTILINE):
        return re.compile(pattern, flags)

    def _build_rules(self):
        if self.language in {"python", ".py"}:
            kw = r"\b(False|True|None|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b"
            self.rules += [
                (self._rx(kw), fmt("#4e9a06", True)),
                (self._rx(r"#.*$"), fmt("#6a737d", italic=True)),
                (self._rx(r'("""|\'\'\')(?:.|\n)*?\1'), fmt("#1a7f37", italic=True)),
                (self._rx(r'"[^"\\]*(\\.[^"\\]*)*"'), fmt("#1f6feb")),
                (self._rx(r"'[^'\\]*(\\.[^'\\]*)*'"), fmt("#1f6feb")),
                (self._rx(r"\b\d+(\.\d+)?\b"), fmt("#d73a49")),
                (self._rx(r"\b(self|cls)\b"), fmt("#6f42c1", True)),
                (self._rx(r"\bdef\s+\w+|\bclass\s+\w+"), fmt("#0a9396", True)),
            ]
        elif self.language in {"c", "cpp", "h", "hpp", "js", "java", ".c", ".cpp", ".h", ".js", ".java"}:
            kw = r"\b(auto|break|case|catch|char|class|const|constexpr|continue|default|delete|do|double|else|enum|explicit|export|extern|float|for|friend|goto|if|inline|int|long|namespace|new|noexcept|nullptr|operator|private|protected|public|register|reinterpret_cast|return|short|signed|sizeof|static|struct|switch|template|this|throw|try|typedef|typename|union|unsigned|using|virtual|void|volatile|while)\b"
            self.rules += [
                (self._rx(kw), fmt("#4e9a06", True)),
                (self._rx(r"//.*$"), fmt("#6a737d", italic=True)),
                (self._rx(r"/\*.*?\*/", re.DOTALL), fmt("#6a737d", italic=True)),
                (self._rx(r'"[^"\\]*(\\.[^"\\]*)*"'), fmt("#1f6feb")),
                (self._rx(r"'[^'\\]*(\\.[^'\\]*)*'"), fmt("#1f6feb")),
                (self._rx(r"\b\d+(\.\d+)?\b"), fmt("#d73a49")),
                (self._rx(r"\b(?:class|struct)\s+\w+"), fmt("#0a9396", True)),
            ]
        elif self.language in {"html", "htm", ".html", ".htm"}:
            self.rules += [
                (self._rx(r"<!--(?:.|\n)*?-->"), fmt("#6a737d", italic=True)),
                (self._rx(r"</?[a-zA-Z0-9:_-]+"), fmt("#4e9a06", True)),
                (self._rx(r"\s[a-zA-Z-:]+(?=\=)"), fmt("#6f42c1")),
                (self._rx(r'="[^"]*"'), fmt("#1f6feb")),
            ]
        elif self.language in {"json", ".json"}:
            self.rules += [
                (self._rx(r'"[^"]*"\s*:'), fmt("#4e9a06", True)),
                (self._rx(r'(:\s*)"[^"]*"'), fmt("#1f6feb")),
                (self._rx(r"\b(true|false|null)\b"), fmt("#d73a49")),
                (self._rx(r"\b-?\d+(\.\d+)?([eE][+-]?\d+)?\b"), fmt("#d73a49")),
            ]

    def highlightBlock(self, text: str):
        for pattern, format_ in self.rules:
            for m in pattern.finditer(text):
                start, end = m.span()
                self.setFormat(start, end - start, format_)

def guess_language_by_suffix(path: Optional[str]) -> str:
    if not path:
        return "plain"
    ext = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".c": "c", ".h": "c",
        ".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp",
        ".js": "js", ".ts": "js",
        ".java": "java",
        ".html": "html", ".htm": "html",
        ".json": "json",
        ".css": "css",
        ".md": "markdown",
        ".txt": "plain",
    }.get(ext, "plain")

def line_comment_token_for(path: Optional[str]) -> str:
    lang = guess_language_by_suffix(path)
    if lang in {"python", "markdown", "plain", "json"}:
        return "#"
    if lang in {"c", "cpp", "js", "java", "css"}:
        return "//"
    if lang in {"html"}:
        return "<!--"
    return "#"

# ---------- Editor with line numbers ----------

class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)

class CodeEditor(QPlainTextEdit):
    cursorPositionChangedX = Signal()
    zoomChanged = Signal(int)  # percent

    def __init__(self, parent=None):
        super().__init__(parent)
        self._show_line_numbers = True
        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.cursorPositionChanged.connect(self.cursorPositionChangedX.emit)
        self.update_line_number_area_width(0)
        self._highlight_current_line()
        font = QFont("Menlo" if sys.platform == "darwin" else "Consolas", BASE_FONT_SIZE)
        self.setFont(font)
        self._base_point_size = font.pointSizeF() if font.pointSizeF() > 0 else BASE_FONT_SIZE
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(' '))
        self.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._show_whitespace = False
        self._apply_whitespace_flag()
        self.installEventFilter(self)

    # ----- whitespace toggling -----
    def set_show_whitespace(self, on: bool):
        self._show_whitespace = on
        self._apply_whitespace_flag()

    def _apply_whitespace_flag(self):
        opt = self.document().defaultTextOption()
        flags = opt.flags()
        if self._show_whitespace:
            flags |= QTextOption.Flag.ShowTabsAndSpaces
        else:
            flags &= ~QTextOption.Flag.ShowTabsAndSpaces
        opt.setFlags(flags)
        self.document().setDefaultTextOption(opt)

    # ----- wrapping -----
    def set_wrapping(self, on: bool):
        if on:
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        else:
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.setWordWrapMode(QTextOption.WrapMode.NoWrap)

    # ----- line numbers infra -----
    def line_number_area_width(self) -> int:
        if not self._show_line_numbers:
            return 0
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance('9') * digits

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        if not self._show_line_numbers:
            return
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(245, 245, 245) if self.palette().color(QPalette.Base).lightness() > 127 else QColor(40, 40, 40))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self.palette().color(QPalette.Text))
                painter.drawText(0, top, self._line_number_area.width() - 4, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self):
        extra = []
        sel = QTextEdit.ExtraSelection()
        lineColor = QColor(0, 0, 0, 12) if self.palette().color(QPalette.Base).lightness() > 127 else QColor(255, 255, 255, 22)
        sel.format.setBackground(lineColor)
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        extra.append(sel)
        self.setExtraSelections(extra)

    def toggle_line_numbers(self, on: bool):
        self._show_line_numbers = on
        self.update_line_number_area_width(0)
        self._line_number_area.update()

    # ----- zoom -----
    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = e.angleDelta().y()
            if delta > 0:
                self.zoomIn(1)
            else:
                self.zoomOut(1)
            self._emit_zoom_percent()
            e.accept()
        else:
            super().wheelEvent(e)

    def keyPressEvent(self, e):
        # Auto-indent basics
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            cursor.beginEditBlock()
            QPlainTextEdit.keyPressEvent(self, e)
            cursor_new = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.PreviousBlock, QTextCursor.MoveMode.MoveAnchor)
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            prev = cursor.selectedText()
            import re as _re
            indent = _re.match(r'^(\s+)', prev)
            if indent:
                cursor_new.insertText(indent.group(1))
            cursor.endEditBlock()
            return
        super().keyPressEvent(e)

    def set_base_font_size(self, pt: float):
        self._base_point_size = pt

    def zoom_reset(self):
        self.setFont(QFont(self.font().family(), BASE_FONT_SIZE))
        self._emit_zoom_percent()

    def _emit_zoom_percent(self):
        cur = self.font().pointSizeF() if self.font().pointSizeF() > 0 else BASE_FONT_SIZE
        pct = int(round(cur / self._base_point_size * 100))
        self.zoomChanged.emit(pct)

# ---------- Find & Replace Dialog ----------

class FindReplaceDialog(QDialog):
    find_next = Signal(str, bool, bool, bool, bool)  # pattern, case, whole, regex, backwards
    replace_one = Signal(str, str, bool, bool, bool) # pattern, repl, case, whole, regex
    replace_all = Signal(str, str, bool, bool, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find & Replace")
        self.setModal(False)
        layout = QGridLayout(self)
        self.find_edit = QLineEdit()
        self.replace_edit = QLineEdit()
        self.case_cb = QCheckBox("Case sensitive")
        self.word_cb = QCheckBox("Whole word")
        self.regex_cb = QCheckBox("Regex")
        self.backwards_cb = QCheckBox("Search backwards")

        btn_find = QPushButton("Find Next")
        btn_prev = QPushButton("Find Previous")
        btn_repl = QPushButton("Replace")
        btn_all = QPushButton("Replace All")
        btn_close = QPushButton("Close")

        layout.addWidget(QLabel("Find:"), 0, 0)
        layout.addWidget(self.find_edit, 0, 1, 1, 4)
        layout.addWidget(QLabel("Replace:"), 1, 0)
        layout.addWidget(self.replace_edit, 1, 1, 1, 4)
        layout.addWidget(self.case_cb, 2, 0)
        layout.addWidget(self.word_cb, 2, 1)
        layout.addWidget(self.regex_cb, 2, 2)
        layout.addWidget(self.backwards_cb, 2, 3)
        layout.addWidget(btn_find, 3, 0)
        layout.addWidget(btn_prev, 3, 1)
        layout.addWidget(btn_repl, 3, 2)
        layout.addWidget(btn_all, 3, 3)
        layout.addWidget(btn_close, 3, 4)

        btn_find.clicked.connect(self._emit_find_next)
        btn_prev.clicked.connect(self._emit_find_prev)
        btn_repl.clicked.connect(self._emit_replace_one)
        btn_all.clicked.connect(self._emit_replace_all)
        btn_close.clicked.connect(self.close)

    def _opts(self):
        return (self.find_edit.text(), self.replace_edit.text(),
                self.case_cb.isChecked(), self.word_cb.isChecked(),
                self.regex_cb.isChecked(), self.backwards_cb.isChecked())

    def _emit_find_next(self):
        pat, _, cs, ww, rx, _ = self._opts()
        self.find_next.emit(pat, cs, ww, rx, False)

    def _emit_find_prev(self):
        pat, _, cs, ww, rx, _ = self._opts()
        self.find_next.emit(pat, cs, ww, rx, True)

    def _emit_replace_one(self):
        pat, rep, cs, ww, rx, _ = self._opts()
        self.replace_one.emit(pat, rep, cs, ww, rx)

    def _emit_replace_all(self):
        pat, rep, cs, ww, rx, _ = self._opts()
        self.replace_all.emit(pat, rep, cs, ww, rx)

# ---------- Find in Files ----------

class FindInFilesDialog(QDialog):
    search_requested = Signal(str, str, bool, bool, bool, bool)  # root, pattern, regex, case, whole, subdirs

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find in Files")
        layout = QGridLayout(self)

        self.dir_edit = QLineEdit()
        browse_btn = QPushButton("Browse…")
        self.pattern_edit = QLineEdit("*.py;*.txt;*.md;*.json;*.html;*.cpp;*.h;*.js")
        self.text_edit = QLineEdit()
        self.regex_cb = QCheckBox("Regex")
        self.case_cb = QCheckBox("Case sensitive")
        self.word_cb = QCheckBox("Whole word")
        self.recursive_cb = QCheckBox("Include subfolders")
        self.recursive_cb.setChecked(True)

        run_btn = QPushButton("Search")
        close_btn = QPushButton("Close")

        layout.addWidget(QLabel("Folder:"), 0, 0)
        layout.addWidget(self.dir_edit, 0, 1)
        layout.addWidget(browse_btn, 0, 2)
        layout.addWidget(QLabel("File masks (semicolon-separated):"), 1, 0, 1, 3)
        layout.addWidget(self.pattern_edit, 2, 0, 1, 3)
        layout.addWidget(QLabel("Find what:"), 3, 0, 1, 3)
        layout.addWidget(self.text_edit, 4, 0, 1, 3)

        flags_row = QHBoxLayout()
        flags_row.addWidget(self.regex_cb)
        flags_row.addWidget(self.case_cb)
        flags_row.addWidget(self.word_cb)
        flags_row.addWidget(self.recursive_cb)
        flags_wrap = QWidget(); flags_wrap.setLayout(flags_row)
        layout.addWidget(flags_wrap, 5, 0, 1, 3)

        btn_row = QHBoxLayout()
        btn_row.addWidget(run_btn)
        btn_row.addWidget(close_btn)
        btn_wrap = QWidget(); btn_wrap.setLayout(btn_row)
        layout.addWidget(btn_wrap, 6, 0, 1, 3)

        browse_btn.clicked.connect(self._browse_dir)
        run_btn.clicked.connect(self._run)
        close_btn.clicked.connect(self.close)

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Choose folder", "")
        if d:
            self.dir_edit.setText(d)

    def _run(self):
        root = self.dir_edit.text().strip()
        pattern = self.text_edit.text()
        masks = self.pattern_edit.text().strip()
        regex = self.regex_cb.isChecked()
        case = self.case_cb.isChecked()
        whole = self.word_cb.isChecked()
        subdirs = self.recursive_cb.isChecked()
        if not root or not pattern:
            QMessageBox.warning(self, "Find in Files", "Please choose a folder and enter text to find.")
            return
        self.search_requested.emit(root, pattern if regex else re.escape(pattern), regex, case, whole, subdirs)

# ---------- Results Dock ----------

class SearchResultsDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Search Results", parent)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["File", "Line", "Column", "Preview"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.setWidget(self.tree)

    def clear_results(self):
        self.tree.clear()

# ---------- Tabs ----------

class EditorTab(QWidget):
    def __init__(self, path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.file_path: Optional[str] = path
        self.file_mtime: Optional[float] = None
        self.editor = CodeEditor()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor)
        lang = guess_language_by_suffix(path)
        self.highlighter = None
        if lang != "plain":
            self.highlighter = RegexHighlighter(self.editor.document(), lang)

# ---------- Main Window ----------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 780)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.setCentralWidget(self.tabs)
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.pos_label = QLabel("Ln 1, Col 1")
        self.zoom_label = QLabel("100%")
        self.encoding_label = QLabel("UTF-8")
        self.mod_label = QLabel("")
        for w in (self.pos_label, self.zoom_label, self.encoding_label, self.mod_label):
            self.status.addPermanentWidget(w)

        self.settings = QSettings(APP_ORG, APP_NAME)

        self.find_dialog = FindReplaceDialog(self)
        self.find_dialog.find_next.connect(self._find_next)
        self.find_dialog.replace_one.connect(self._replace_one)
        self.find_dialog.replace_all.connect(self._replace_all)

        self.find_files_dialog = FindInFilesDialog(self)
        self.find_files_dialog.search_requested.connect(self._search_in_files)

        self.results_dock = SearchResultsDock(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.results_dock)
        self.results_dock.hide()
        self.results_dock.tree.itemDoubleClicked.connect(self._open_result_item)

        self._make_actions()
        self._make_menus_and_toolbar()
        self._load_recent_files()

        self.tabs.currentChanged.connect(self._on_current_changed)
        self.tabs.tabCloseRequested.connect(self._close_tab_index)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._tab_context_menu)
        self.setAcceptDrops(True)

        self._apply_theme(self.settings.value("theme", "light"))
        self.new_file()

    # ----- UI: actions/menus -----
    def _icon(self, std):
        return self.style().standardIcon(std)

    def _make_actions(self):
        # File
        self.act_new = QAction(self._icon(QStyle.StandardPixmap.SP_FileIcon), "&New", self)
        self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_new.triggered.connect(self.new_file)

        self.act_open = QAction(self._icon(QStyle.StandardPixmap.SP_DirOpenIcon), "&Open...", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.triggered.connect(self.open_files)

        self.act_reload = QAction("Re&load from Disk", self)
        self.act_reload.setShortcut(QKeySequence("Ctrl+R"))
        self.act_reload.triggered.connect(self.reload_from_disk)

        self.act_save = QAction(self._icon(QStyle.StandardPixmap.SP_DialogSaveButton), "&Save", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.triggered.connect(self.save_file)

        self.act_save_as = QAction("Save &As...", self)
        self.act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_as.triggered.connect(lambda: self.save_file(save_as=True))

        self.act_save_all = QAction("Save A&ll", self)
        self.act_save_all.setShortcut(QKeySequence("Ctrl+Alt+S"))
        self.act_save_all.triggered.connect(self.save_all)

        self.act_close_tab = QAction("&Close Tab", self)
        self.act_close_tab.setShortcut(QKeySequence.StandardKey.Close)
        self.act_close_tab.triggered.connect(self._close_current_tab)

        self.act_exit = QAction("E&xit", self)
        self.act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_exit.triggered.connect(self.close)

        # Edit
        self.act_undo = QAction(self._icon(QStyle.StandardPixmap.SP_ArrowBack), "&Undo", self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.triggered.connect(lambda: self.current_editor().undo())

        self.act_redo = QAction(self._icon(QStyle.StandardPixmap.SP_ArrowForward), "&Redo", self)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.act_redo.triggered.connect(lambda: self.current_editor().redo())

        self.act_cut = QAction(self._icon(QStyle.StandardPixmap.SP_DesktopIcon), "Cu&t", self)
        self.act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        self.act_cut.triggered.connect(lambda: self.current_editor().cut())

        self.act_copy = QAction(self._icon(QStyle.StandardPixmap.SP_FileDialogContentsView), "&Copy", self)
        self.act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self.act_copy.triggered.connect(lambda: self.current_editor().copy())

        self.act_paste = QAction(self._icon(QStyle.StandardPixmap.SP_DialogOpenButton), "&Paste", self)
        self.act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        self.act_paste.triggered.connect(lambda: self.current_editor().paste())

        self.act_select_all = QAction("Select &All", self)
        self.act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.act_select_all.triggered.connect(lambda: self.current_editor().selectAll())

        self.act_find = QAction("&Find/Replace", self)
        self.act_find.setShortcut(QKeySequence.StandardKey.Find)
        self.act_find.triggered.connect(lambda: (self.find_dialog.show(), self.find_dialog.raise_()))

        self.act_find_next = QAction("Find &Next", self)
        self.act_find_next.setShortcut(QKeySequence.StandardKey.FindNext)
        self.act_find_next.triggered.connect(lambda: self._find_next(self.find_dialog.find_edit.text(), False, False, False, False))

        self.act_find_prev = QAction("Find &Previous", self)
        self.act_find_prev.setShortcut(QKeySequence.StandardKey.FindPrevious)
        self.act_find_prev.triggered.connect(lambda: self._find_next(self.find_dialog.find_edit.text(), False, False, False, True))

        self.act_find_files = QAction("Find in &Files…", self)
        self.act_find_files.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.act_find_files.triggered.connect(lambda: (self.find_files_dialog.show(), self.find_files_dialog.raise_()))

        self.act_goto = QAction("&Go to Line...", self)
        self.act_goto.setShortcut(QKeySequence("Ctrl+L"))
        self.act_goto.triggered.connect(self._goto_line)

        self.act_toggle_comment = QAction("Toggle &Comment", self)
        self.act_toggle_comment.setShortcut(QKeySequence("Ctrl+/"))
        self.act_toggle_comment.triggered.connect(self._toggle_comment)

        self.act_whitespace = QAction("Show &Whitespace", self, checkable=True)
        self.act_whitespace.setChecked(False)
        self.act_whitespace.triggered.connect(self._toggle_whitespace)

        # View
        self.act_wrap = QAction("&Word Wrap", self, checkable=True)
        self.act_wrap.triggered.connect(self._toggle_wrap)

        self.act_ln = QAction("&Line Numbers", self, checkable=True)
        self.act_ln.setChecked(True)
        self.act_ln.triggered.connect(self._toggle_line_numbers)

        self.act_zoom_in = QAction("Zoom &In", self)
        self.act_zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.act_zoom_in.triggered.connect(lambda: (self.current_editor().zoomIn(1), self._update_zoom_label()))

        self.act_zoom_out = QAction("Zoom &Out", self)
        self.act_zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.act_zoom_out.triggered.connect(lambda: (self.current_editor().zoomOut(1), self._update_zoom_label()))

        self.act_zoom_reset = QAction("Zoom &Reset", self)
        self.act_zoom_reset.setShortcut(QKeySequence("Ctrl+0"))
        self.act_zoom_reset.triggered.connect(self._zoom_reset)

        self.act_theme_dark = QAction("&Dark Theme", self, checkable=True)
        self.act_theme_light = QAction("&Light Theme", self, checkable=True)
        self.act_theme_dark.triggered.connect(lambda: self._apply_theme("dark"))
        self.act_theme_light.triggered.connect(lambda: self._apply_theme("light"))

        self.act_about = QAction("&About", self)
        self.act_about.triggered.connect(self._about)

        # Recent placeholders
        self.recent_actions: List[QAction] = [QAction(self) for _ in range(MAX_RECENTS)]
        for act in self.recent_actions:
            act.setVisible(False)
            act.triggered.connect(self._open_recent_triggered)
        self.act_clear_recent = QAction("Clear Recent", self)
        self.act_clear_recent.triggered.connect(self._clear_recent)

    def _make_menus_and_toolbar(self):
        # Menus
        m_file = self.menuBar().addMenu("&File")
        m_file.addAction(self.act_new)
        m_file.addAction(self.act_open)
        m_file.addAction(self.act_reload)
        m_file.addSeparator()
        m_file.addAction(self.act_save)
        m_file.addAction(self.act_save_as)
        m_file.addAction(self.act_save_all)
        m_file.addSeparator()
        self.recent_menu = m_file.addMenu("Open &Recent")
        for act in self.recent_actions:
            self.recent_menu.addAction(act)
        self.recent_menu.addSeparator()
        self.recent_menu.addAction(self.act_clear_recent)
        m_file.addSeparator()
        m_file.addAction(self.act_close_tab)
        m_file.addAction(self.act_exit)

        m_edit = self.menuBar().addMenu("&Edit")
        m_edit.addAction(self.act_undo)
        m_edit.addAction(self.act_redo)
        m_edit.addSeparator()
        m_edit.addAction(self.act_cut)
        m_edit.addAction(self.act_copy)
        m_edit.addAction(self.act_paste)
        m_edit.addAction(self.act_select_all)
        m_edit.addSeparator()
        m_edit.addAction(self.act_find)
        m_edit.addAction(self.act_find_next)
        m_edit.addAction(self.act_find_prev)
        m_edit.addAction(self.act_find_files)
        m_edit.addAction(self.act_goto)
        m_edit.addSeparator()
        m_edit.addAction(self.act_toggle_comment)
        m_edit.addAction(self.act_whitespace)

        m_view = self.menuBar().addMenu("&View")
        m_view.addAction(self.act_wrap)
        m_view.addAction(self.act_ln)
        m_view.addSeparator()
        m_view.addAction(self.act_zoom_in)
        m_view.addAction(self.act_zoom_out)
        m_view.addAction(self.act_zoom_reset)
        m_view.addSeparator()
        theme_menu = m_view.addMenu("&Theme")
        theme_menu.addAction(self.act_theme_dark)
        theme_menu.addAction(self.act_theme_light)

        m_help = self.menuBar().addMenu("&Help")
        m_help.addAction(self.act_about)

        # Toolbar
        tb = QToolBar("Main", self)
        tb.setMovable(True)
        for a in (self.act_new, self.act_open, self.act_reload, self.act_save, self.act_save_all,
                  self.act_undo, self.act_redo, self.act_find, self.act_find_files,
                  self.act_wrap):
            tb.addAction(a)
        self.addToolBar(tb)

    # ----- Tabs / Editors -----
    def current_tab(self) -> EditorTab:
        return self.tabs.currentWidget()  # type: ignore

    def current_editor(self) -> CodeEditor:
        return self.current_tab().editor

    def _on_current_changed(self, idx: int):
        if idx < 0 or self.tabs.count() == 0:
            return
        ed = self.current_editor()
        ed.cursorPositionChangedX.connect(self._update_status_pos)
        ed.textChanged.connect(self._on_modified_changed)
        ed.zoomChanged.connect(lambda _: self._update_zoom_label())
        self._update_title()
        self._update_status_pos()
        self._update_modified_label()
        self._update_zoom_label()

    def new_file(self):
        tab = EditorTab(None)
        self._wire_editor(tab)
        idx = self.tabs.addTab(tab, "Untitled")
        self.tabs.setCurrentIndex(idx)

    def open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Open Files", "", "All Files (*.*)")
        for p in paths:
            self._open_path(p)

    def _open_path(self, path: str):
        if not path:
            return
        # Reuse tab if already open
        for i in range(self.tabs.count()):
            w: EditorTab = self.tabs.widget(i)  # type: ignore
            if w.file_path and os.path.abspath(w.file_path) == os.path.abspath(path):
                self.tabs.setCurrentIndex(i)
                return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            mtime = os.path.getmtime(path)
        except Exception as e:
            QMessageBox.critical(self, "Open failed", f"Could not open:\n{path}\n\n{e}")
            return
        tab = EditorTab(path)
        tab.editor.setPlainText(text)
        tab.editor.document().setModified(False)
        tab.file_mtime = mtime
        self._wire_editor(tab)
        idx = self.tabs.addTab(tab, os.path.basename(path))
        self.tabs.setCurrentIndex(idx)
        self._add_recent(path)

    def _wire_editor(self, tab: EditorTab):
        ed = tab.editor
        ed.cursorPositionChangedX.connect(self._update_status_pos)
        ed.textChanged.connect(self._on_modified_changed)
        ed.zoomChanged.connect(lambda _: self._update_zoom_label())
        ed.set_base_font_size(BASE_FONT_SIZE)
        ed.setFocus()

    def save_file(self, save_as: bool = False):
        tab = self.current_tab()
        path = tab.file_path
        if save_as or not path:
            start_dir = os.path.dirname(path) if path else ""
            new_path, _ = QFileDialog.getSaveFileName(self, "Save As", start_dir, "All Files (*.*)")
            if not new_path:
                return
            tab.file_path = new_path
        try:
            with open(tab.file_path, "w", encoding="utf-8") as f:  # type: ignore
                f.write(tab.editor.toPlainText())
            tab.editor.document().setModified(False)
            # update mtime
            try:
                tab.file_mtime = os.path.getmtime(tab.file_path)  # type: ignore
            except Exception:
                tab.file_mtime = None
            self._update_title()
            self._add_recent(tab.file_path)  # type: ignore
        except Exception as e:
            QMessageBox.critical(self, "Save failed", f"Could not save file:\n{tab.file_path}\n\n{e}")

    def save_all(self):
        for i in range(self.tabs.count()):
            w: EditorTab = self.tabs.widget(i)  # type: ignore
            if w.file_path is None or w.editor.document().isModified():
                self.tabs.setCurrentIndex(i)
                self.save_file(save_as=(w.file_path is None))

    def reload_from_disk(self):
        tab = self.current_tab()
        if not tab.file_path:
            QMessageBox.information(self, "Reload", "This tab has not been saved to disk yet.")
            return
        if tab.editor.document().isModified():
            r = QMessageBox.question(self, "Reload from Disk",
                                     "This document has unsaved changes.\nReload and lose changes?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes:
                return
        try:
            with open(tab.file_path, "r", encoding="utf-8") as f:
                text = f.read()
            tab.editor.setPlainText(text)
            tab.editor.document().setModified(False)
            tab.file_mtime = os.path.getmtime(tab.file_path)
            self._update_title()
        except Exception as e:
            QMessageBox.critical(self, "Reload failed", f"Could not reload:\n{tab.file_path}\n\n{e}")

    def _close_current_tab(self):
        self._close_tab_index(self.tabs.currentIndex())

    def _close_tab_index(self, idx: int):
        if idx < 0:
            return
        w: EditorTab = self.tabs.widget(idx)  # type: ignore
        if w.editor.document().isModified():
            r = QMessageBox.question(self, "Unsaved changes",
                                     f"Save changes to {os.path.basename(w.file_path) if w.file_path else 'Untitled'}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Cancel:
                return
            if r == QMessageBox.StandardButton.Yes:
                self.tabs.setCurrentIndex(idx)
                self.save_file(save_as=(w.file_path is None))
        self.tabs.removeTab(idx)
        w.deleteLater()
        if self.tabs.count() == 0:
            self.new_file()

    # ----- Status / Title -----
    def _update_title(self):
        tab = self.current_tab()
        name = os.path.basename(tab.file_path) if tab.file_path else "Untitled"
        if tab.editor.document().isModified():
            name += "*"
        self.tabs.setTabText(self.tabs.currentIndex(), name)
        self.setWindowTitle(f"{name} - {APP_NAME}")

    def _update_status_pos(self):
        c = self.current_editor().textCursor()
        ln = c.blockNumber() + 1
        col = c.positionInBlock() + 1
        self.pos_label.setText(f"Ln {ln}, Col {col}")

    def _on_modified_changed(self):
        self._update_title()
        self._update_modified_label()

    def _update_modified_label(self):
        mod = self.current_editor().document().isModified()
        self.mod_label.setText("*" if mod else "")

    def _update_zoom_label(self):
        ed = self.current_editor()
        cur = ed.font().pointSizeF() if ed.font().pointSizeF() > 0 else BASE_FONT_SIZE
        pct = int(round(cur / BASE_FONT_SIZE * 100))
        self.zoom_label.setText(f"{pct}%")

    # ----- View toggles -----
    def _toggle_wrap(self, on: bool):
        for i in range(self.tabs.count()):
            w: EditorTab = self.tabs.widget(i)  # type: ignore
            w.editor.set_wrapping(on)
        self.settings.setValue("wrap", on)
        self.act_wrap.setChecked(on)

    def _toggle_line_numbers(self, on: bool):
        for i in range(self.tabs.count()):
            w: EditorTab = self.tabs.widget(i)  # type: ignore
            w.editor.toggle_line_numbers(on)

    def _toggle_whitespace(self, on: bool):
        for i in range(self.tabs.count()):
            w: EditorTab = self.tabs.widget(i)  # type: ignore
            w.editor.set_show_whitespace(on)

    def _zoom_reset(self):
        for i in range(self.tabs.count()):
            w: EditorTab = self.tabs.widget(i)  # type: ignore
            w.editor.zoom_reset()
        self._update_zoom_label()

    # ----- Find/Replace helpers -----
    def _qtext_find_flags(self, case: bool, word: bool, regex: bool, backwards: bool) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if case:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if word:
            flags |= QTextDocument.FindFlag.FindWholeWords
        if backwards:
            flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def _find_next(self, pattern: str, case: bool, word: bool, regex: bool, backwards: bool):
        ed = self.current_editor()
        if not pattern:
            return
        flags = self._qtext_find_flags(case, word, regex, backwards)
        if regex:
            reg = QRegularExpression(pattern)
            if not reg.isValid():
                QMessageBox.warning(self, "Regex error", reg.errorString())
                return
            found = ed.find(reg, flags)
        else:
            found = ed.find(pattern, flags)
        if not found:
            # Wrap search
            c = ed.textCursor()
            c.movePosition(QTextCursor.MoveOperation.Start if not backwards else QTextCursor.MoveOperation.End)
            ed.setTextCursor(c)
            if regex:
                ed.find(QRegularExpression(pattern), flags)
            else:
                ed.find(pattern, flags)

    def _replace_one(self, pattern: str, replacement: str, case: bool, word: bool, regex: bool):
        ed = self.current_editor()
        if ed.textCursor().hasSelection():
            cur_text = ed.textCursor().selectedText()
            try:
                if regex:
                    flags = 0 if case else re.IGNORECASE
                    new = re.sub(pattern, replacement, cur_text, count=1, flags=flags)
                else:
                    new = replacement
            except re.error as e:
                QMessageBox.warning(self, "Regex error", str(e))
                return
            ed.textCursor().insertText(new)
        self._find_next(pattern, case, word, regex, False)

    def _replace_all(self, pattern: str, replacement: str, case: bool, word: bool, regex: bool):
        ed = self.current_editor()
        text = ed.toPlainText()
        try:
            if regex:
                flags = 0 if case else re.IGNORECASE
                new = re.sub(pattern, replacement, text, flags=flags)
            else:
                if not case:
                    new = re.sub(re.escape(pattern), replacement, text, flags=re.IGNORECASE)
                else:
                    new = text.replace(pattern, replacement)
        except re.error as e:
            QMessageBox.warning(self, "Regex error", str(e))
            return
        ed.setPlainText(new)

    def _goto_line(self):
        ed = self.current_editor()
        max_ln = ed.blockCount()
        ln, ok = QInputDialog.getInt(self, "Go to line", "Line number:", min=1, max=max_ln, value=1)
        if not ok:
            return
        c = ed.textCursor()
        c.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(ln - 1):
            c.movePosition(QTextCursor.MoveOperation.Down)
        ed.setTextCursor(c)
        ed.centerCursor()

    # ----- Toggle comment -----
    def _toggle_comment(self):
        tab = self.current_tab()
        ed = tab.editor
        token = line_comment_token_for(tab.file_path)
        c = ed.textCursor()
        if not c.hasSelection():
            c.select(QTextCursor.SelectionType.LineUnderCursor)
        start = c.selectionStart()
        end = c.selectionEnd()
        c.setPosition(start)
        start_block = c.blockNumber()
        c.setPosition(end)
        end_block = c.blockNumber()
        # Apply line-by-line
        ed.blockSignals(True)
        cursor = ed.textCursor()
        cursor.beginEditBlock()
        for b in range(start_block, end_block + 1):
            block = ed.document().findBlockByNumber(b)
            text = block.text()
            if token == "<!--":
                if text.strip().startswith("<!--") and text.strip().endswith("-->"):
                    new = text.replace("<!--", "", 1).rsplit("-->", 1)[0]
                else:
                    new = f"<!--{text}-->"
            else:
                if text.lstrip().startswith(token):
                    idx = text.find(token)
                    new = text[:idx] + text[idx+len(token):]
                    new = new.lstrip() if new.strip() else ""
                else:
                    new = f"{token} {text}" if text.strip() else token
            # replace block text
            tc = QTextCursor(block)
            tc.select(QTextCursor.SelectionType.LineUnderCursor)
            tc.insertText(new)
        cursor.endEditBlock()
        ed.blockSignals(False)

    # ----- Recent files -----
    def _add_recent(self, path: str):
        recents = self.settings.value("recent_files", [], list)
        path = os.path.abspath(path)
        if path in recents:
            recents.remove(path)
        recents.insert(0, path)
        recents = recents[:MAX_RECENTS]
        self.settings.setValue("recent_files", recents)
        self._load_recent_files()

    def _load_recent_files(self):
        recents = self.settings.value("recent_files", [], list)
        for i, act in enumerate(self.recent_actions):
            if i < len(recents):
                p = recents[i]
                act.setText(p)
                act.setData(p)
                act.setVisible(True)
            else:
                act.setVisible(False)
        theme = self.settings.value("theme", "light")
        self._apply_theme(theme if theme in ("light", "dark") else "light")
        wrap = self.settings.value("wrap", False, bool)
        self.act_wrap.setChecked(wrap)
        self._toggle_wrap(wrap)

    def _open_recent_triggered(self):
        act = self.sender()
        if not isinstance(act, QAction):
            return
        p = act.data()
        if p and os.path.exists(p):
            self._open_path(p)
        else:
            QMessageBox.information(self, "Not found", f"File not found:\n{p}")

    def _clear_recent(self):
        self.settings.setValue("recent_files", [])
        self._load_recent_files()

    # ----- Drag & Drop -----
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p:
                self._open_path(p)

    # ----- Tab context menu -----
    def _tab_context_menu(self, pos):
        index = self.tabs.tabBar().tabAt(pos)
        if index < 0:
            return
        menu = QMenu(self)
        close_act = menu.addAction("Close")
        close_others_act = menu.addAction("Close Others")
        close_all_act = menu.addAction("Close All")
        action = menu.exec(self.tabs.mapToGlobal(pos))
        if action == close_act:
            self._close_tab_index(index)
        elif action == close_others_act:
            current = index
            # Close all except current
            for i in reversed(range(self.tabs.count())):
                if i != current:
                    self._close_tab_index(i)
        elif action == close_all_act:
            for i in reversed(range(self.tabs.count())):
                self._close_tab_index(i)

    # ----- Search in Files -----
    def _search_in_files(self, root: str, pattern: str, regex: bool, case: bool, whole: bool, subdirs: bool):
        masks_text = self.find_files_dialog.pattern_edit.text().strip()
        masks = [m.strip() for m in masks_text.split(";") if m.strip()]
        self.results_dock.clear_results()
        self.results_dock.show()

        re_flags = 0 if case else re.IGNORECASE
        if not regex:
            # pattern already escaped
            if whole:
                pattern = rf"\b{pattern}\b"
        try:
            rx = re.compile(pattern, re_flags | re.MULTILINE)
        except re.error as e:
            QMessageBox.warning(self, "Regex error", str(e))
            return

        def file_iter():
            path = Path(root)
            if not path.exists():
                return
            if subdirs:
                it = path.rglob("*")
            else:
                it = path.glob("*")
            for p in it:
                if p.is_file():
                    if masks:
                        if not any(fnmatch.fnmatch(p.name, m) for m in masks):
                            continue
                    yield p

        for p in file_iter():
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception:
                continue
            for m in rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                col = m.start() - (text.rfind("\n", 0, m.start()) + 1)
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 40)
                snippet = text[start:end].replace("\n", " ")
                item = QTreeWidgetItem([str(p), str(line), str(col + 1), snippet])
                self.results_dock.tree.addTopLevelItem(item)

    def _open_result_item(self, item: QTreeWidgetItem, _column: int):
        path = item.text(0)
        line = int(item.text(1))
        col = int(item.text(2))
        self._open_path(path)
        ed = self.current_editor()
        c = ed.textCursor()
        c.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(line - 1):
            c.movePosition(QTextCursor.MoveOperation.Down)
        for _ in range(col - 1):
            c.movePosition(QTextCursor.MoveOperation.Right)
        ed.setTextCursor(c)
        ed.centerCursor()

    # ----- Themes -----
    def _apply_theme(self, which: str):
        # Mutually exclusive toggle
        self.act_theme_dark.setChecked(which == "dark")
        self.act_theme_light.setChecked(which == "light")
        if which == "dark":
            pal = QPalette()
            pal.setColor(QPalette.Window, QColor(30, 30, 30))
            pal.setColor(QPalette.WindowText, Qt.white)
            pal.setColor(QPalette.Base, QColor(22, 22, 22))
            pal.setColor(QPalette.AlternateBase, QColor(44, 44, 44))
            pal.setColor(QPalette.Text, Qt.white)
            pal.setColor(QPalette.Button, QColor(45, 45, 45))
            pal.setColor(QPalette.ButtonText, Qt.white)
            pal.setColor(QPalette.Highlight, QColor(64, 128, 255))
            pal.setColor(QPalette.HighlightedText, Qt.white)
            self.setPalette(pal)
        else:
            self.setPalette(QApplication.palette())

        # Repaint editors to sync line-number shading
        for i in range(self.tabs.count()):
            w: EditorTab = self.tabs.widget(i)  # type: ignore
            w.editor._highlight_current_line()
            w.editor._line_number_area.update()

        self.settings.setValue("theme", which)

    # ----- Close handling -----
    def closeEvent(self, event: QCloseEvent):
        # Prompt for unsaved tabs
        for i in range(self.tabs.count()):
            w: EditorTab = self.tabs.widget(i)  # type: ignore
            if w.editor.document().isModified():
                self.tabs.setCurrentIndex(i)
                r = QMessageBox.question(self, "Unsaved changes",
                                         f"Save changes to {os.path.basename(w.file_path) if w.file_path else 'Untitled'}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
                if r == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
                if r == QMessageBox.StandardButton.Yes:
                    self.save_file(save_as=(w.file_path is None))
        event.accept()

    # ----- About -----
    def _about(self):
        QMessageBox.information(self, "About",
            f"<b>{APP_NAME}</b><br>"
            "A Notepad++-style editor in Python (PySide6).<br><br>"
            "Features: Tabs, line numbers, syntax highlighting, find/replace, find in files, recent files, "
            "word wrap, show whitespace, zoom %, dark/light themes, toggle comment, go to line, reload, save all, "
            "drag & drop.<br><br>"
            "© 2025 MIT License")

# ---------- Main ----------

def main():
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORG)
    app.setApplicationName(APP_NAME)
    QApplication.setStyle(QStyleFactory.create("Fusion"))
    # macOS: better titlebar icons
    if sys.platform == "darwin":
        app.setWindowIcon(QIcon.fromTheme("text-editor"))
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    # PySide6 required: pip install PySide6
    main()
