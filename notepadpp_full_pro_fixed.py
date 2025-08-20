#!/usr/bin/env python3
# notepadpp_full_pro_fixed.py
# Premium Notepad++-style editor, async via QThread (no QtConcurrent).

from __future__ import annotations
import os, sys, re, json, fnmatch, importlib.util, subprocess, shlex, time, traceback
from dataclasses import dataclass
from typing import Optional, List, Tuple
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QSettings, QSize, QTimer, QEvent, pyqtSignal, QPoint, QObject, QThread
)
from PyQt6.QtGui import (
    QAction, QKeySequence, QCloseEvent, QFont, QFontDatabase, QColor, QIcon
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QWidget, QVBoxLayout,
    QTabWidget, QToolBar, QStatusBar, QLabel, QDockWidget, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QDialog, QGridLayout, QLineEdit, QCheckBox, QPushButton,
    QHBoxLayout, QListWidget, QListWidgetItem, QMenu, QSplitter, QTextEdit, QStyle,
    QInputDialog, QProgressBar
)
from PyQt6.Qsci import (
    QsciScintilla, QsciLexerPython, QsciLexerCPP, QsciLexerHTML, QsciLexerJSON,
    QsciLexerJavaScript, QsciLexerJava, QsciLexerBash, QsciLexerFortran, QsciLexerFortran77
)

APP_ORG = "OpenDev"
APP_NAME = "Notepad++ Pro (PyQt)"
SESSION_FILE = str(Path.home() / ".npp_pro_session.json")
PLUGINS_DIR = str(Path(__file__).parent / "plugins")
CHECK_DISK_MS = 2000
MAX_RECENTS = 20

# ---------------- Fonts & Theme ----------------
def best_mono_font(size: int = 13) -> QFont:
    families = set(QFontDatabase.families())
    for name in ["SF Mono", "Menlo", "Monaco", "Courier New"]:
        if name in families:
            f = QFont(name, size)
            f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
            return f
    f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    f.setPointSize(size)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f

DARK = {
    "bg": QColor("#1e1e1e"),
    "bg2": QColor("#252526"),
    "panel": QColor("#2b2b2b"),
    "panel2": QColor("#333333"),
    "text": QColor("#d4d4d4"),
    "muted": QColor("#b0b0b0"),
    "comment": QColor("#6A9955"),
    "string": QColor("#CE9178"),
    "number": QColor("#B5CEA8"),
    "keyword": QColor("#569CD6"),
    "func": QColor("#DCDCAA"),
    "class": QColor("#4EC9B0"),
    "accent": QColor("#0a84ff"),
    "selection": QColor("#264f78"),
    "caretline": QColor("#2a2d2e"),
    "margin_bg": QColor("#2d2d2d"),
    "margin_fg": QColor("#8b8b8b"),
}

def premium_dark_qss() -> str:
    return f"""
    QWidget {{ color: {DARK['text'].name()}; }}
    QMainWindow {{ background: {DARK['bg'].name()}; }}
    QMenuBar, QMenu {{ background: {DARK['bg2'].name()}; color: {DARK['text'].name()}; }}
    QMenu::item:selected {{ background: {DARK['accent'].name()}; color: white; }}
    QToolBar {{
        background: {DARK['bg2'].name()};
        border: 0px; padding: 6px; spacing: 6px;
    }}
    QToolBar QToolButton {{
        padding: 6px 10px; border-radius: 8px;
    }}
    QToolBar QToolButton:hover {{ background: {DARK['panel'].name()}; }}
    QTabWidget::pane {{ border: 0; }}
    QTabBar::tab {{
        background: {DARK['panel'].name()};
        color: {DARK['muted'].name()};
        padding: 7px 12px; margin: 4px 6px;
        border-top-left-radius: 10px; border-top-right-radius: 10px;
    }}
    QTabBar::tab:selected {{
        background: {DARK['panel2'].name()};
        color: white;
        border-bottom: 2px solid {DARK['accent'].name()};
    }}
    QStatusBar {{
        background: {DARK['bg2'].name()};
        color: {DARK['muted'].name()};
    }}
    QDockWidget::title {{
        text-align: left; padding-left: 8px;
        background: {DARK['panel'].name()};
    }}
    QTreeWidget, QListWidget {{
        background: {DARK['panel'].name()};
        border: 0;
    }}
    QTreeWidget::item:selected, QListWidget::item:selected {{
        background: {DARK['selection'].name()};
        color: white;
    }}
    QLineEdit {{
        background: {DARK['panel2'].name()};
        border: 1px solid {DARK['panel2'].name()};
        padding: 6px; border-radius: 8px;
        color: {DARK['text'].name()};
    }}
    QPushButton {{
        background: {DARK['panel2'].name()};
        border: 1px solid {DARK['panel2'].name()};
        padding: 6px 10px; border-radius: 8px;
        color: {DARK['text'].name()};
    }}
    QPushButton:hover {{
        background: {DARK['panel'].name()};
    }}
    """

def style_editor_dark(ed: QsciScintilla):
    ed.setPaper(DARK["bg"])
    try: ed.setColor(DARK["text"])
    except Exception: pass
    ed.setCaretLineVisible(True)
    ed.setCaretLineBackgroundColor(DARK["caretline"])
    ed.setSelectionBackgroundColor(DARK["selection"])
    ed.setMarginsBackgroundColor(DARK["margin_bg"])
    ed.setMarginsForegroundColor(DARK["margin_fg"])
    ed.setFoldMarginColors(DARK["panel"], DARK["panel2"])
    ed.setWhitespaceForegroundColor(DARK["panel2"])
    ed.setWhitespaceBackgroundColor(DARK["bg"])

def style_lexer_dark(lexer):
    def setc(name, color):
        if hasattr(lexer, name):
            try: lexer.setColor(color, getattr(lexer, name))
            except Exception: pass
    try:
        lexer.setDefaultPaper(DARK["bg"])
        lexer.setDefaultColor(DARK["text"])
    except Exception: pass
    setc("Default", DARK["text"])
    setc("Comment", DARK["comment"])
    setc("CommentBlock", DARK["comment"])
    setc("Number", DARK["number"])
    setc("DoubleQuotedString", DARK["string"])
    setc("SingleQuotedString", DARK["string"])
    setc("TripleSingle", DARK["string"])
    setc("TripleDouble", DARK["string"])
    setc("Keyword", DARK["keyword"])
    setc("ClassName", DARK["class"])
    setc("FunctionMethodName", DARK["func"])
    setc("Operator", DARK["text"])
    setc("Identifier", DARK["text"])
    setc("Decorator", QColor("#C586C0"))

# ---------------- Async Runner (QThread-based) ----------------
class _Worker(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            res = self._fn(*self._args, **self._kwargs)
            self.result.emit(res)
        except Exception as e:
            self.error.emit(str(e))

def run_async(parent, fn, on_done, on_error=None, *args, **kwargs):
    """Run fn in a background QThread and post result/error back to the GUI thread."""
    thread = QThread(parent)
    worker = _Worker(fn, *args, **kwargs)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    def cleanup():
        worker.deleteLater()
        thread.quit()
        thread.wait()
        thread.deleteLater()
    worker.result.connect(lambda res: (on_done(res), cleanup()))
    if on_error:
        worker.error.connect(lambda msg: (on_error(msg), cleanup()))
    else:
        worker.error.connect(lambda msg: (print('[ERROR]', msg), cleanup()))
    thread.start()

# ---------------- Helpers: Busy Indicator & Error ----------------
class BusyIndicator:
    def __init__(self, status: QStatusBar, message: str):
        self.status = status
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setMaximumWidth(140)
        self.status.addPermanentWidget(self.bar)
        self.status.showMessage(message)

    def done(self, message: str | None = None):
        if message:
            self.status.showMessage(message, 3000)
        self.status.removeWidget(self.bar)
        self.bar.deleteLater()

def handle_exception(context: str, exc: BaseException):
    print(f"[ERROR] {context}: {exc}\n{traceback.format_exc()}", file=sys.stderr)

# ---------------- Data ----------------
@dataclass
class FileState:
    path: Optional[str]
    encoding: str = "utf-8"
    eol: str = "LF"
    mtime: Optional[float] = None

# ---------------- Editor ----------------
class SciEditor(QsciScintilla):
    bookmarkClicked = pyqtSignal(int)
    zoomChangedX = pyqtSignal(int)
    caretMovedX = pyqtSignal(int, int)

    MARK_BOOKMARK = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_state = FileState(path=None)
        self._recording = False
        self._macro: List[Tuple[str, str]] = []
        self._init_editor()

    def _init_editor(self):
        f = best_mono_font(13)
        self.setFont(f)

        self.setMarginsFont(f)
        self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self.setMarginWidth(0, "00000")
        self.setMarginLineNumbers(0, True)

        self.setMarginType(1, QsciScintilla.MarginType.SymbolMargin)
        self.setMarginWidth(1, 14)
        self.setMarginSensitivity(1, True)
        self.marginClicked.connect(self._margin_clicked)

        self.setFolding(QsciScintilla.FoldStyle.PlainFoldStyle, 2)
        self.setMarginType(2, QsciScintilla.MarginType.SymbolMargin)
        self.setMarginWidth(2, 12)

        self.markerDefine(QsciScintilla.MarkerSymbol.RightTriangle, self.MARK_BOOKMARK)
        self.setMarkerBackgroundColor(DARK["accent"], self.MARK_BOOKMARK)
        self.setMarkerForegroundColor(DARK["bg"], self.MARK_BOOKMARK)

        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.setIndentationsUseTabs(False)
        self.setTabWidth(4)
        self.setAutoIndent(True)
        self.setIndentationGuides(True)
        self.setWrapMode(QsciScintilla.WrapMode.WrapNone)
        self.setWhitespaceVisibility(QsciScintilla.WhitespaceVisibility.WsInvisible)
        self.setEolVisibility(False)

        self.cursorPositionChanged.connect(lambda l, c: self.caretMovedX.emit(l, c))
        self.modificationChanged.connect(lambda m: None)
        self._zoom_steps = 0

        style_editor_dark(self)

    def apply_lexer_for(self, path: Optional[str]):
        lexer = None
        ext = Path(path).suffix.lower() if path else ".py"
        mapping = {
            ".py": QsciLexerPython,
            ".c": QsciLexerCPP, ".h": QsciLexerCPP,
            ".cpp": QsciLexerCPP, ".hpp": QsciLexerCPP, ".cc": QsciLexerCPP,
            ".html": QsciLexerHTML, ".htm": QsciLexerHTML,
            ".json": QsciLexerJSON,
            ".js": QsciLexerJavaScript,
            ".java": QsciLexerJava,
            ".sh": QsciLexerBash,
            ".f": QsciLexerFortran77, ".f77": QsciLexerFortran77,
            ".f90": QsciLexerFortran, ".f95": QsciLexerFortran,
        }
        L = mapping.get(ext)
        if L:
            lexer = L(self)
            try: lexer.setDefaultFont(best_mono_font(13))
            except Exception: pass
            style_lexer_dark(lexer)
        self.setLexer(lexer)

    def set_eol(self, eol: str):
        e = eol.upper()
        if e == "CRLF": self.setEolMode(QsciScintilla.EolMode.EolWindows)
        elif e == "CR": self.setEolMode(QsciScintilla.EolMode.EolMac)
        else: self.setEolMode(QsciScintilla.EolMode.EolUnix); e = "LF"
        self.file_state.eol = e

    def eol_str(self) -> str:
        m = self.eolMode()
        return "CRLF" if m == QsciScintilla.EolMode.EolWindows else ("CR" if m == QsciScintilla.EolMode.EolMac else "LF")

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if e.angleDelta().y() > 0: super().zoomIn(); self._zoom_steps += 1
            else: super().zoomOut(); self._zoom_steps -= 1
            self.zoomChangedX.emit(self.zoom_percent()); e.accept(); return
        super().wheelEvent(e)

    def zoom_reset(self):
        super().zoomTo(0); self._zoom_steps = 0; self.zoomChangedX.emit(self.zoom_percent())

    def zoom_percent(self) -> int:
        return 100 + self._zoom_steps * 10

    def _margin_clicked(self, margin, line, state):
        if margin == 1:
            marks = self.markersAtLine(line)
            if marks & (1 << self.MARK_BOOKMARK):
                self.markerDelete(line, self.MARK_BOOKMARK)
            else:
                self.markerAdd(line, self.MARK_BOOKMARK)
            self.bookmarkClicked.emit(line)

    def next_bookmark_line(self, from_line: int) -> Optional[int]:
        maxl = self.lines()
        for l in range(from_line + 1, maxl):
            if self.markersAtLine(l) & (1 << self.MARK_BOOKMARK): return l
        for l in range(0, from_line + 1):
            if self.markersAtLine(l) & (1 << self.MARK_BOOKMARK): return l
        return None

    def prev_bookmark_line(self, from_line: int) -> Optional[int]:
        for l in range(from_line - 1, -1, -1):
            if self.markersAtLine(l) & (1 << self.MARK_BOOKMARK): return l
        for l in range(self.lines() - 1, from_line - 1, -1):
            if self.markersAtLine(l) & (1 << self.MARK_BOOKMARK): return l
        return None

    def start_macro(self): self._macro.clear(); self._recording = True
    def stop_macro(self): self._recording = False
    def play_macro(self):
        for t, d in self._macro:
            if t == "text":
                self.replaceSelectedText(d) if self.hasSelectedText() else self.insert(d)
            elif t == "key":
                if d == "Backspace":
                    l, c = self.getCursorPosition()
                    if c > 0: self.setSelection(l, c-1, l, c); self.removeSelectedText()
                elif d == "Tab": self.insert("\t")
                elif d == "Return": self.insert("\n")

    def event(self, e):
        if self._recording and e.type() == QEvent.Type.KeyPress:
            k = e; text = k.text()
            if text: self._macro.append(("text", text))
            else:
                name = {Qt.Key.Key_Backspace:"Backspace", Qt.Key.Key_Tab:"Tab", Qt.Key.Key_Return:"Return", Qt.Key.Key_Enter:"Return"}.get(k.key())
                if name: self._macro.append(("key", name))
        return super().event(e)

# ---------------- Dialogs ----------------
class FindReplaceDialog(QDialog):
    find_next = pyqtSignal(str, bool, bool, bool, bool, bool)
    replace_one = pyqtSignal(str, str, bool, bool, bool, bool)
    replace_all = pyqtSignal(str, str, bool, bool, bool, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find & Replace")
        grid = QGridLayout(self)
        self.find_edit = QLineEdit()
        self.replace_edit = QLineEdit()
        self.case_cb = QCheckBox("Case sensitive")
        self.word_cb = QCheckBox("Whole word")
        self.regex_cb = QCheckBox("Regex")
        self.sel_cb = QCheckBox("In selection")
        self.inc_cb = QCheckBox("Incremental")

        btn_find = QPushButton("Find Next")
        btn_prev = QPushButton("Find Previous")
        btn_repl = QPushButton("Replace")
        btn_all = QPushButton("Replace All")
        btn_close = QPushButton("Close")

        grid.addWidget(QLabel("Find:"), 0, 0); grid.addWidget(self.find_edit, 0, 1, 1, 4)
        grid.addWidget(QLabel("Replace:"), 1, 0); grid.addWidget(self.replace_edit, 1, 1, 1, 4)

        row = QHBoxLayout()
        for w in (self.case_cb, self.word_cb, self.regex_cb, self.sel_cb, self.inc_cb): row.addWidget(w)
        wrap = QWidget(); wrap.setLayout(row); grid.addWidget(wrap, 2, 0, 1, 5)

        row2 = QHBoxLayout()
        for b in (btn_find, btn_prev, btn_repl, btn_all, btn_close): row2.addWidget(b)
        wrap2 = QWidget(); wrap2.setLayout(row2); grid.addWidget(wrap2, 3, 0, 1, 5)

        btn_close.clicked.connect(self.close)
        btn_find.clicked.connect(lambda: self._emit(False))
        btn_prev.clicked.connect(lambda: self._emit(True))
        btn_repl.clicked.connect(self._emit_repl_one)
        btn_all.clicked.connect(self._emit_repl_all)
        self.find_edit.textChanged.connect(self._incremental)

    def _opts(self):
        return (self.find_edit.text(), self.replace_edit.text(),
                self.case_cb.isChecked(), self.word_cb.isChecked(), self.regex_cb.isChecked(), self.sel_cb.isChecked())

    def _emit(self, backwards: bool):
        pat, _, cs, ww, rx, sel = self._opts()
        self.find_next.emit(pat, cs, ww, rx, sel, backwards)

    def _emit_repl_one(self):
        pat, rep, cs, ww, rx, sel = self._opts()
        self.replace_one.emit(pat, rep, cs, ww, rx, sel)

    def _emit_repl_all(self):
        pat, rep, cs, ww, rx, sel = self._opts()
        self.replace_all.emit(pat, rep, cs, ww, rx, sel)

    def _incremental(self, _):
        if self.inc_cb.isChecked():
            self._emit(False)

class FindInFilesDialog(QDialog):
    search_requested = pyqtSignal(str, str, str, bool, bool, bool)
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Find in Files")
        grid = QGridLayout(self)
        self.dir_edit = QLineEdit(); browse = QPushButton("Browse…")
        self.masks_edit = QLineEdit("*.py;*.cpp;*.h;*.txt;*.md;*.json;*.html;*.js;*.f90;*.f")
        self.text_edit = QLineEdit()
        self.case_cb = QCheckBox("Case sensitive"); self.word_cb = QCheckBox("Whole word"); self.regex_cb = QCheckBox("Regex")
        self.recur_cb = QCheckBox("Include subfolders"); self.recur_cb.setChecked(True)
        run = QPushButton("Search"); close = QPushButton("Close")
        grid.addWidget(QLabel("Folder:"), 0, 0); grid.addWidget(self.dir_edit, 0, 1); grid.addWidget(browse, 0, 2)
        grid.addWidget(QLabel("Masks:"), 1, 0); grid.addWidget(self.masks_edit, 1, 1, 1, 2)
        grid.addWidget(QLabel("Find what:"), 2, 0); grid.addWidget(self.text_edit, 2, 1, 1, 2)
        row = QHBoxLayout(); [row.addWidget(w) for w in (self.case_cb, self.word_cb, self.regex_cb, self.recur_cb)]
        wrap = QWidget(); wrap.setLayout(row); grid.addWidget(wrap, 3, 0, 1, 3)
        row2 = QHBoxLayout(); row2.addWidget(run); row2.addWidget(close)
        wrap2 = QWidget(); wrap2.setLayout(row2); grid.addWidget(wrap2, 4, 0, 1, 3)
        browse.clicked.connect(self._browse); close.clicked.connect(self.close); run.clicked.connect(self._run)
    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Choose folder", ""); 
        if d: self.dir_edit.setText(d)
    def _run(self):
        root = self.dir_edit.text().strip(); masks = self.masks_edit.text().strip(); text = self.text_edit.text()
        if not root or not text: QMessageBox.warning(self, "Find in Files", "Choose folder and enter text."); return
        self.search_requested.emit(root, masks, text, self.case_cb.isChecked(), self.word_cb.isChecked(), self.regex_cb.isChecked())

# ---------------- Docks ----------------
class ResultsDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Search Results", parent); self.setObjectName("SearchResultsDock")
        self.tree = QTreeWidget(); self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["File", "Line", "Column", "Preview"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.addWidget(self.tree); self.setWidget(w)
    def clear(self): self.tree.clear()

class FunctionListDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Function List", parent); self.setObjectName("FunctionListDock")
        self.list = QListWidget(); w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.addWidget(self.list); self.setWidget(w)

class ConsoleDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Console", parent); self.setObjectName("ConsoleDock")
        self.out = QTextEdit(); self.out.setReadOnly(True)
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.addWidget(self.out); self.setWidget(w)

# ---------------- Tab wrapper ----------------
class EditorTab(QWidget):
    def __init__(self, path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.editor = SciEditor(); self.editor.apply_lexer_for(path)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.addWidget(self.editor)
        if path:
            pass

# ---------------- Main Window ----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME); self.resize(1380, 880)
        self.settings = QSettings(APP_ORG, APP_NAME)
        self.setUnifiedTitleAndToolBarOnMac(True)

        # Central: Split view with two tab bars
        self.splitter = QSplitter()
        self.tabs_left = QTabWidget(); self._setup_tabs(self.tabs_left)
        self.tabs_right = QTabWidget(); self._setup_tabs(self.tabs_right); self.tabs_right.hide()
        self.splitter.addWidget(self.tabs_left); self.splitter.addWidget(self.tabs_right)
        self.setCentralWidget(self.splitter)

        # Status bar
        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.pos_label = QLabel("Ln 1, Col 1"); self.eol_label = QLabel("LF"); self.enc_label = QLabel("UTF-8")
        self.zoom_label = QLabel("100%"); self.mod_label = QLabel("")
        for w in (self.pos_label, self.eol_label, self.enc_label, self.zoom_label, self.mod_label):
            self.status.addPermanentWidget(w)

        # Docks
        self.results_dock = ResultsDock(self); self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.results_dock); self.results_dock.hide()
        self.func_dock = FunctionListDock(self); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.func_dock); self.func_dock.hide()
        self.console_dock = ConsoleDock(self); self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock); self.console_dock.hide()

        # Dialogs
        self.find_dialog = FindReplaceDialog(self)
        self.find_dialog.find_next.connect(self._find_next)
        self.find_dialog.replace_one.connect(self._replace_one)
        self.find_dialog.replace_all.connect(self._replace_all)
        self.find_files_dialog = FindInFilesDialog(self)

        # Menus/Toolbar/Theme
        QApplication.instance().setStyleSheet(premium_dark_qss())
        self._make_actions(); self._make_menus(); self._make_toolbar()

        # Connections
        self.tabs_left.currentChanged.connect(lambda _: self._on_current_changed(self.tabs_left))
        self.tabs_right.currentChanged.connect(lambda _: self._on_current_changed(self.tabs_right))
        self.tabs_left.tabCloseRequested.connect(lambda i: self._close_tab(self.tabs_left, i))
        self.tabs_right.tabCloseRequested.connect(lambda i: self._close_tab(self.tabs_right, i))
        self.func_dock.list.itemActivated.connect(self._goto_function_item)
        self.results_dock.tree.itemDoubleClicked.connect(self._open_result_item)

        # Timers & session
        self.disk_timer = QTimer(self); self.disk_timer.timeout.connect(self._check_disk_changes); self.disk_timer.start(CHECK_DISK_MS)
        self._load_session()

        # Drag & drop
        self.setAcceptDrops(True)

        # Audio input device (for dictation)
        self.mic_device_idx = int(self.settings.value('mic_device_idx', -1))

        if self.tabs_left.count() == 0: self.new_file()

    # Tabs setup
    def _setup_tabs(self, tabs: QTabWidget):
        tabs.setTabsClosable(True); tabs.setDocumentMode(True); tabs.setMovable(True)
        tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tabs.customContextMenuRequested.connect(lambda pos, t=tabs: self._tab_context_menu(t, pos))
        tabs.setElideMode(Qt.TextElideMode.ElideRight)
        tabs.setUsesScrollButtons(True)

    # Utilities
    def _current_tabs(self) -> QTabWidget:
        if self.tabs_right.isVisible() and self.tabs_right.hasFocus(): return self.tabs_right
        return self.tabs_left

    def _current_tab(self) -> Optional[EditorTab]:
        tabs = self._current_tabs(); w = tabs.currentWidget()
        return w if isinstance(w, EditorTab) else None

    def _editor(self) -> Optional[SciEditor]:
        t = self._current_tab(); return t.editor if t else None

    def _other_tabs(self) -> QTabWidget:
        return self.tabs_right if self._current_tabs() is self.tabs_left else self.tabs_left

    # File ops (ASYNC read)
    def new_file(self, right: bool=False):
        tab = EditorTab(None); ed = tab.editor
        ed.caretMovedX.connect(self._update_status_pos); ed.zoomChangedX.connect(lambda pct: self.zoom_label.setText(f"{pct}%"))
        ed.modificationChanged.connect(lambda m: self.mod_label.setText("MOD" if m else ""))
        tabs = self.tabs_right if right else self.tabs_left
        idx = tabs.addTab(tab, "Untitled"); tabs.setCurrentIndex(idx)
        self._update_status_all()

    def open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Open Files", "", "All Files (*.*)")
        for p in paths: self._open_path(p)

    def _open_path(self, path: str, in_other: bool=False):
        if not path: return
        # Prevent duplicates
        for tabs in (self.tabs_left, self.tabs_right):
            for i in range(tabs.count()):
                w: EditorTab = tabs.widget(i)  # type: ignore
                if w.editor.file_state.path and os.path.abspath(w.editor.file_state.path) == os.path.abspath(path):
                    tabs.setCurrentIndex(i); return
        # Create tab immediately
        tab = EditorTab(path); ed = tab.editor
        ed.caretMovedX.connect(self._update_status_pos); ed.zoomChangedX.connect(lambda pct: self.zoom_label.setText(f"{pct}%"))
        ed.modificationChanged.connect(lambda m: self.mod_label.setText("MOD" if m else ""))
        tabs = self._other_tabs() if in_other else self._current_tabs()
        idx = tabs.addTab(tab, os.path.basename(path)); tabs.setCurrentIndex(idx)
        self._update_status_all()
        # Start async load
        busy = BusyIndicator(self.status, f"Opening {os.path.basename(path)}…")
        def worker_read(path: str):
            for enc in ("utf-8", "latin-1"):
                try:
                    with open(path, "r", encoding=enc, errors=("strict" if enc=="utf-8" else "ignore")) as f:
                        text = f.read()
                    mtime = os.path.getmtime(path)
                    return {"ok": True, "data": (text, enc, mtime)}
                except FileNotFoundError:
                    return {"ok": False, "error": f"File not found: {path}"}
                except PermissionError:
                    return {"ok": False, "error": f"Permission denied: {path}"}
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    return {"ok": False, "error": str(e)}
            return {"ok": False, "error": "Unable to decode with UTF-8 or Latin-1."}

        def on_done(res):
            busy.done()
            if res.get("ok"):
                text, enc, mtime = res["data"]
                ed.setText(text)
                ed.file_state.path = path; ed.file_state.encoding = enc; ed.file_state.mtime = mtime
                ed.apply_lexer_for(path)
                self._set_cur_tab_title(os.path.basename(path))
                self._add_recent(path)
                self._update_status_all(); self._update_function_list()
            else:
                self._handle_error("Open file", res.get("error", "Unknown error"))

        def on_err(msg):
            busy.done()
            self._handle_error("Open file", msg)

        run_async(self, worker_read, on_done, on_err, path)

    def save_file(self, save_as: bool=False):
        ed = self._editor()
        if not ed: return
        path = ed.file_state.path
        if save_as or not path:
            start_dir = os.path.dirname(path) if path else ""
            new_path, _ = QFileDialog.getSaveFileName(self, "Save As", start_dir, "All Files (*.*)")
            if not new_path: return
            path = new_path
        try:
            text = ed.text()
            if ed.file_state.eol == "CRLF":
                text = text.replace("\r\n", "\n").replace("\n", "\r\n")
            elif ed.file_state.eol == "CR":
                text = text.replace("\r\n", "\n").replace("\n", "\r")
            else:
                text = text.replace("\r\n", "\n").replace("\r", "\n")
            with open(path, "w", encoding=ed.file_state.encoding, errors="strict") as f:
                f.write(text)
            ed.file_state.path = path
            try: ed.file_state.mtime = os.path.getmtime(path)
            except Exception: ed.file_state.mtime = None
            self._set_cur_tab_title(os.path.basename(path)); self._add_recent(path)
            self.status.showMessage(f"Saved {path}", 2000)
        except PermissionError:
            self._handle_error("Save file", f"Permission denied: {path}")
        except Exception as e:
            self._handle_error("Save file", str(e))
        self._update_status_all()

    def save_all(self):
        for tabs in (self.tabs_left, self.tabs_right):
            for i in range(tabs.count()):
                w: EditorTab = tabs.widget(i)  # type: ignore
                self._current_tabs().setCurrentIndex(i)
                ed = w.editor
                if not ed.file_state.path:
                    self.save_file(save_as=True)
                else:
                    self.save_file(save_as=False)
        self._update_status_all()

    def reload_from_disk(self):
        ed = self._editor()
        if not ed or not ed.file_state.path: return
        if ed.isModified():
            r = QMessageBox.question(self, "Reload", "Document has unsaved changes. Reload and lose changes?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes: return
        self._open_path(ed.file_state.path)

    def closeEvent(self, e: QCloseEvent):
        self._save_session(); super().closeEvent(e)

    def _close_tab(self, tabs: QTabWidget, index: int):
        tabs.removeTab(index)
        if tabs.count() == 0 and tabs is self.tabs_left: self.new_file()

    def _set_cur_tab_title(self, title: str):
        tabs = self._current_tabs(); i = tabs.currentIndex()
        if i >= 0: tabs.setTabText(i, title)

    # Recent
    def _add_recent(self, path: str):
        rec = self.settings.value("recent_files", [], list); abspath = os.path.abspath(path)
        if abspath in rec: rec.remove(abspath)
        rec.insert(0, abspath); rec = rec[:MAX_RECENTS]
        self.settings.setValue("recent_files", rec); self._rebuild_recents_menu()

    def _rebuild_recents_menu(self):
        self.recent_menu.clear(); rec = self.settings.value("recent_files", [], list)
        if not rec: a = self.recent_menu.addAction("(Empty)"); a.setEnabled(False)
        else:
            for p in rec:
                act = self.recent_menu.addAction(p)
                act.triggered.connect(lambda _, path=p: self._open_path(path))
            self.recent_menu.addSeparator(); self.recent_menu.addAction("Clear List", lambda: (self.settings.setValue("recent_files", []), self._rebuild_recents_menu()))

    # Search/Replace helpers
    def _pos_from_linecol(self, text: str, line: int, col: int) -> int:
        lines = text.splitlines(keepends=True); acc = 0
        for i in range(min(line, len(lines))): acc += len(lines[i])
        return acc + col

    def _linecol_from_pos(self, text: str, pos: int) -> Tuple[int,int]:
        lines = text.splitlines(keepends=True); acc = 0
        for i, ln in enumerate(lines):
            if acc + len(ln) > pos: return i, pos - acc
            acc += len(ln)
        return len(lines)-1, 0

    def _find_in_text(self, ed: SciEditor, pattern: str, cs: bool, ww: bool, rx: bool, sel_only: bool, backwards: bool) -> bool:
        text = ed.text()
        if sel_only and ed.hasSelectedText():
            s = ed.selectedText().replace('\r\n', '\n')
            text = s
            l1, c1, _, _ = ed.getSelection()
            start_pos = self._pos_from_linecol(ed.text(), l1, c1)
        else:
            start_pos = self._pos_from_linecol(text, *ed.getCursorPosition())
        if not rx: pattern = re.escape(pattern)
        if ww: pattern = r"\b" + pattern + r"\b"
        flags = 0 if cs else re.IGNORECASE
        R = re.compile(pattern, flags | re.MULTILINE)
        if backwards:
            m = None
            for mm in R.finditer(text, 0, start_pos): m = mm
        else:
            st = start_pos + 1 if ed.hasSelectedText() else start_pos
            m = R.search(text, st)
        if not m: m = R.search(text, 0)
        if not m: return False
        s, e = m.start(), m.end()
        l1, c1 = self._linecol_from_pos(ed.text(), s); l2, c2 = self._linecol_from_pos(ed.text(), e)
        ed.setSelection(l1, c1, l2, c2); ed.ensureLineVisible(l1); return True

    def _replace_one(self, pat, rep, cs, ww, rx, sel_only):
        ed = self._editor(); 
        if not ed: return
        if ed.hasSelectedText(): ed.replaceSelectedText(rep)
        self._find_next(pat, cs, ww, rx, sel_only, False)

    def _replace_all(self, pat, rep, cs, ww, rx, sel_only):
        ed = self._editor(); 
        if not ed: return
        text = ed.text()
        if sel_only and ed.hasSelectedText():
            l1, c1, l2, c2 = ed.getSelection(); sel_text = ed.selectedText().replace('\r\n','\n')
            R = re.compile(pat if rx else re.escape(pat), 0 if cs else re.IGNORECASE | re.MULTILINE)
            new_sel = R.sub(rep, sel_text); ed.setSelection(l1,c1,l2,c2); ed.replaceSelectedText(new_sel)
        else:
            R = re.compile(pat if rx else re.escape(pat), 0 if cs else re.IGNORECASE | re.MULTILINE)
            ed.setText(R.sub(rep, text))

    def _find_next(self, pat, cs, ww, rx, sel_only, backwards):
        ed = self._editor(); 
        if not ed or not pat: return
        if not self._find_in_text(ed, pat, cs, ww, rx, sel_only, backwards): self.status.showMessage("No matches", 1500)

    # Find in Files (ASYNC via QThread)
    def find_in_files(self):
        self.find_files_dialog.show(); self.find_files_dialog.raise_()
        self.find_files_dialog.search_requested.connect(self._run_find_in_files, type=Qt.ConnectionType.UniqueConnection)

    def _run_find_in_files(self, root: str, masks: str, text: str, case: bool, whole: bool, regex: bool):
        busy = BusyIndicator(self.status, "🔍 Searching…")
        recursive = self.find_files_dialog.recur_cb.isChecked()
        def worker(root, masks, text, case, whole, regex, recursive):
            import re, fnmatch
            mask_list = [m.strip() for m in masks.split(";") if m.strip()]
            flags = 0 if case else re.IGNORECASE
            if not regex: text = re.escape(text)
            if whole: text = r"\b" + text + r"\b"
            R = re.compile(text, flags | re.MULTILINE)
            results = []
            try:
                p = Path(root)
                if not p.exists():
                    return {"ok": False, "error": f"Folder not found: {root}"}
                it = p.rglob("*") if recursive else p.glob("*")
                for f in it:
                    if f.is_file():
                        if mask_list and not any(fnmatch.fnmatch(f.name, m) for m in mask_list): 
                            continue
                        try:
                            data = f.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            continue
                        for m in R.finditer(data):
                            line = data.count("\n", 0, m.start()) + 1
                            col = m.start() - (data.rfind("\n", 0, m.start()) + 1)
                            snippet = data[max(0, m.start()-40):m.end()+40].replace("\n", " ")
                            results.append((str(f), line, col+1, snippet))
                return {"ok": True, "data": results}
            except re.error as e:
                return {"ok": False, "error": f"Regex error: {e}"}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        def on_done(res):
            busy.done("Search complete")
            if res.get("ok"):
                self.results_dock.clear(); self.results_dock.show()
                for (path, line, col, snippet) in res["data"]:
                    self.results_dock.tree.addTopLevelItem(QTreeWidgetItem([path, str(line), str(col), snippet]))
            else:
                self._handle_error("Find in Files", res.get("error","Unknown error"))

        def on_err(msg):
            busy.done("Search failed")
            self._handle_error("Find in Files", msg)

        run_async(self, worker, on_done, on_err, root, masks, text, case, whole, regex, recursive)

    def _open_result_item(self, item: QTreeWidgetItem, _col: int):
        path, line, col = item.text(0), int(item.text(1)), int(item.text(2))
        self._open_path(path); ed = self._editor()
        if not ed: return
        ed.setCursorPosition(line-1, col-1); ed.ensureLineVisible(line-1); ed.setSelection(line-1, col-1, line-1, col)

    # Function list
    def _update_function_list(self):
        ed = self._editor(); 
        if not ed: return
        path = ed.file_state.path or ""; text = ed.text(); items: List[Tuple[str,int]] = []
        ext = Path(path).suffix.lower()
        if ext == ".py" or not ext:
            rx = re.compile(r"^\s*(def|class)\s+([A-Za-z_]\w*)", re.MULTILINE)
            for m in rx.finditer(text): items.append((f"{m.group(1)} {m.group(2)}", text.count("\n", 0, m.start())+1))
        elif ext in (".c",".h",".cpp",".hpp",".cc",".java",".js"):
            rx = re.compile(r"^\s*(?:[A-Za-z_][\w<>\[\]\s\*:&]+)?\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{?", re.MULTILINE)
            for m in rx.finditer(text): items.append((m.group(1)+"()", text.count("\n", 0, m.start())+1))
        elif ext in (".f",".f90",".f95",".for"):
            rx = re.compile(r"^\s*(SUBROUTINE|FUNCTION)\s+([A-Za-z_]\w*)", re.IGNORECASE | re.MULTILINE)
            for m in rx.finditer(text): items.append((f"{m.group(1).title()} {m.group(2)}", text.count("\n", 0, m.start())+1))
        self.func_dock.list.clear()
        if items:
            self.func_dock.show()
            for label, ln in items:
                it = QListWidgetItem(f"{label}  —  line {ln}"); it.setData(Qt.ItemDataRole.UserRole, ln); self.func_dock.list.addItem(it)
        else:
            self.func_dock.hide()

    def _goto_function_item(self, item: QListWidgetItem):
        ln = int(item.data(Qt.ItemDataRole.UserRole)); ed = self._editor()
        if not ed: return
        ed.setCursorPosition(ln-1, 0); ed.ensureLineVisible(ln-1)

    # Disk changes
    def _check_disk_changes(self):
        for tabs in (self.tabs_left, self.tabs_right):
            for i in range(tabs.count()):
                w: EditorTab = tabs.widget(i)  # type: ignore
                ed = w.editor; p = ed.file_state.path
                if not p: continue
                try: m = os.path.getmtime(p)
                except Exception: continue
                if ed.file_state.mtime and m > ed.file_state.mtime and not ed.isModified():
                    self._open_path(p)

    # Status updates
    def _update_status_pos(self, line: int, col: int):
        self.pos_label.setText(f"Ln {line+1}, Col {col+1}")

    def _update_status_all(self):
        ed = self._editor(); 
        if not ed: return
        l, c = ed.getCursorPosition(); self._update_status_pos(l, c)
        self.eol_label.setText(ed.eol_str()); self.enc_label.setText(ed.file_state.encoding.upper())
        self.zoom_label.setText(f"{ed.zoom_percent()}%"); self.mod_label.setText("MOD" if ed.isModified() else "")

    def _on_current_changed(self, tabs: QTabWidget):
        self._update_status_all(); self._update_function_list()

    # Menus & toolbar
    def _make_actions(self):
        style = QApplication.instance().style()
        # File
        self.act_new = QAction(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon), "&New", self, shortcut=QKeySequence.StandardKey.New, triggered=self.new_file)
        self.act_open = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon), "&Open…", self, shortcut=QKeySequence.StandardKey.Open, triggered=self.open_files)
        self.act_reload = QAction("Re&load from Disk", self, shortcut="Ctrl+R", triggered=self.reload_from_disk)
        self.act_save = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "&Save", self, shortcut=QKeySequence.StandardKey.Save, triggered=self.save_file)
        self.act_save_as = QAction("Save &As…", self, shortcut="Ctrl+Shift+S", triggered=lambda: self.save_file(True))
        self.act_save_all = QAction("Save A&ll", self, shortcut="Ctrl+Alt+S", triggered=self.save_all)
        self.act_close = QAction("&Close Tab", self, shortcut=QKeySequence.StandardKey.Close, triggered=lambda: self._close_tab(self._current_tabs(), self._current_tabs().currentIndex()))
        self.act_exit = QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)

        # Edit
        self.act_undo = QAction(style.standardIcon(QStyle.StandardPixmap.SP_ArrowBack), "&Undo", self, shortcut=QKeySequence.StandardKey.Undo, triggered=lambda: self._editor() and self._editor().undo())
        self.act_redo = QAction(style.standardIcon(QStyle.StandardPixmap.SP_ArrowForward), "&Redo", self, shortcut=QKeySequence.StandardKey.Redo, triggered=lambda: self._editor() and self._editor().redo())
        self.act_cut = QAction("Cu&t", self, shortcut=QKeySequence.StandardKey.Cut, triggered=lambda: self._editor() and self._editor().cut())
        self.act_copy = QAction("&Copy", self, shortcut=QKeySequence.StandardKey.Copy, triggered=lambda: self._editor() and self._editor().copy())
        self.act_paste = QAction("&Paste", self, shortcut=QKeySequence.StandardKey.Paste, triggered=lambda: self._editor() and self._editor().paste())
        self.act_select_all = QAction("Select &All", self, shortcut=QKeySequence.StandardKey.SelectAll, triggered=lambda: self._editor() and self._editor().selectAll())

        # Search
        self.act_find = QAction(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView), "&Find/Replace…", self, shortcut=QKeySequence.StandardKey.Find, triggered=lambda: (self.find_dialog.show(), self.find_dialog.raise_()))
        self.act_find_in_files = QAction("Find in &Files…", self, shortcut="Ctrl+Shift+F", triggered=self.find_in_files)
        self.act_goto = QAction("&Go to Line…", self, shortcut="Ctrl+L", triggered=self._goto_line)
        self.act_next_bookmark = QAction("Next &Bookmark", self, shortcut="F2", triggered=lambda: self._jump_bookmark(True))
        self.act_prev_bookmark = QAction("&Previous Bookmark", self, shortcut="Shift+F2", triggered=lambda: self._jump_bookmark(False))

        # View
        self.act_wrap = QAction("&Word Wrap", self, checkable=True, triggered=self._toggle_wrap)
        self.act_ws = QAction("Show &Whitespace", self, checkable=True, triggered=self._toggle_ws)
        self.act_eol = QAction("Show &EOL", self, checkable=True, triggered=self._toggle_eol)
        self.act_zoom_in = QAction("Zoom &In", self, shortcut=QKeySequence.StandardKey.ZoomIn, triggered=lambda: self._editor() and self._editor().zoomIn())
        self.act_zoom_out = QAction("Zoom &Out", self, shortcut=QKeySequence.StandardKey.ZoomOut, triggered=lambda: self._editor() and self._editor().zoomOut())
        self.act_zoom_reset = QAction("Zoom &Reset", self, shortcut="Ctrl+0", triggered=lambda: self._editor() and self._editor().zoom_reset())
        self.act_split = QAction("&Split View", self, checkable=True, triggered=self._toggle_split)

        # Encoding/EOL
        self.act_eol_lf = QAction("Convert EOL to LF (Unix)", self, triggered=lambda: self._convert_eol("LF"))
        self.act_eol_crlf = QAction("Convert EOL to CRLF (Windows)", self, triggered=lambda: self._convert_eol("CRLF"))
        self.act_eol_cr = QAction("Convert EOL to CR (Mac Classic)", self, triggered=lambda: self._convert_eol("CR"))
        self.act_reopen_utf8 = QAction("Reopen with UTF-8", self, triggered=lambda: self._reopen_encoding("utf-8"))
        self.act_reopen_latin1 = QAction("Reopen with Latin-1", self, triggered=lambda: self._reopen_encoding("latin-1"))
        self.act_convert_to_utf8 = QAction("Convert to UTF-8", self, triggered=lambda: self._convert_encoding("utf-8"))
        self.act_convert_to_latin1 = QAction("Convert to Latin-1 (lossy)", self, triggered=lambda: self._convert_encoding("latin-1", lossy=True))

        # Macro
        self.act_macro_rec = QAction("&Start Recording", self, triggered=lambda: self._editor() and self._editor().start_macro())
        self.act_macro_stop = QAction("S&top Recording", self, triggered=lambda: self._editor() and self._editor().stop_macro())
        self.act_macro_play = QAction("&Play Macro", self, triggered=lambda: self._editor() and self._editor().play_macro())

        # Plugins
        self.act_plugins_reload = QAction("&Reload Plugins", self, triggered=self._load_plugins)
        self.act_plugins_open_dir = QAction("Open Plugins Folder", self, triggered=lambda: os.startfile(PLUGINS_DIR) if sys.platform.startswith("win") else subprocess.Popen(["open" if sys.platform=="darwin" else "xdg-open", PLUGINS_DIR]))

        # Tools
        self.act_run_python = QAction(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Run &Python (current file)", self, triggered=self._run_python_current)
        self.act_external_cmd = QAction("Run &External…", self, triggered=self._run_external)
        self.act_dictation = QAction("Start &Dictation", self, triggered=self._start_dictation)
        self.act_selftest = QAction("Self Test Report", self, triggered=self._self_test)

    def _make_menus(self):
        mb = self.menuBar()
        # File
        m_file = mb.addMenu("&File")
        for a in (self.act_new, self.act_open, self.act_reload): m_file.addAction(a)
        m_file.addSeparator(); 
        for a in (self.act_save, self.act_save_as, self.act_save_all): m_file.addAction(a)
        m_file.addSeparator(); self.recent_menu = m_file.addMenu("Open &Recent"); self._rebuild_recents_menu()
        m_file.addSeparator(); 
        for a in (self.act_close, self.act_exit): m_file.addAction(a)

        # Edit
        m_edit = mb.addMenu("&Edit")
        for a in (self.act_undo, self.act_redo): m_edit.addAction(a)
        m_edit.addSeparator()
        for a in (self.act_cut, self.act_copy, self.act_paste, self.act_select_all): m_edit.addAction(a)

        # Search
        m_search = mb.addMenu("&Search")
        for a in (self.act_find, self.act_find_in_files, self.act_goto, self.act_next_bookmark, self.act_prev_bookmark): m_search.addAction(a)

        # View
        m_view = mb.addMenu("&View")
        for a in (self.act_wrap, self.act_ws, self.act_eol, self.act_zoom_in, self.act_zoom_out, self.act_zoom_reset, self.act_split): m_view.addAction(a)

        # Encoding/EOL
        m_enc = mb.addMenu("&Encoding / EOL")
        for a in (self.act_eol_lf, self.act_eol_crlf, self.act_eol_cr): m_enc.addAction(a)
        m_enc.addSeparator()
        for a in (self.act_reopen_utf8, self.act_reopen_latin1): m_enc.addAction(a)
        m_enc.addSeparator()
        for a in (self.act_convert_to_utf8, self.act_convert_to_latin1): m_enc.addAction(a)

        # Macro
        m_macro = mb.addMenu("&Macro"); 
        for a in (self.act_macro_rec, self.act_macro_stop, self.act_macro_play): m_macro.addAction(a)

        # Plugins
        self.m_plugins = mb.addMenu("&Plugins")
        for a in (self.act_plugins_reload, self.act_plugins_open_dir): self.m_plugins.addAction(a)
        self.m_plugins.addSeparator(); self._load_plugins()

        # Tools
        m_tools = mb.addMenu("&Tools")
        for a in (self.act_run_python, self.act_external_cmd, self.act_dictation, self.act_selftest): m_tools.addAction(a)
        m_audio = m_tools.addMenu("Audio Input")
        m_audio.addAction("Select Microphone…", self._select_microphone)

        # Help
        m_help = mb.addMenu("&Help")
        m_help.addAction("About", lambda: QMessageBox.information(self, "About", f"<b>{APP_NAME}</b><br>Premium Notepad++-style editor in Python.<br>© 2025 MIT"))

    def _make_toolbar(self):
        tb = QToolBar("Main"); tb.setIconSize(QSize(20,20)); tb.setMovable(False); self.addToolBar(tb)
        for a in (self.act_new, self.act_open, self.act_reload, self.act_save, self.act_save_all,
                  self.act_undo, self.act_redo, self.act_find, self.act_find_in_files, self.act_wrap):
            tb.addAction(a)
        tb.addSeparator()
        self.quick_find = QLineEdit(); self.quick_find.setPlaceholderText("Search in file…")
        self.quick_find.setFixedWidth(220)
        self.quick_find.returnPressed.connect(lambda: self._find_next(self.quick_find.text(), False, False, False, False, False))
        tb.addWidget(self.quick_find)

    # View toggles
    def _toggle_wrap(self, _on: bool):
        ed = self._editor()
        if ed: ed.setWrapMode(QsciScintilla.WrapMode.WrapWord if self.act_wrap.isChecked() else QsciScintilla.WrapMode.WrapNone)

    def _toggle_ws(self, _on: bool):
        ed = self._editor()
        if ed: ed.setWhitespaceVisibility(QsciScintilla.WhitespaceVisibility.WsVisible if self.act_ws.isChecked() else QsciScintilla.WhitespaceVisibility.WsInvisible)

    def _toggle_eol(self, _on: bool):
        ed = self._editor()
        if ed: ed.setEolVisibility(self.act_eol.isChecked())

    def _toggle_split(self, on: bool):
        self.tabs_right.setVisible(on)

    def _convert_eol(self, which: str):
        ed = self._editor(); 
        if not ed: return
        ed.set_eol(which); self.eol_label.setText(ed.eol_str())

    def _reopen_encoding(self, enc: str):
        ed = self._editor(); 
        if not ed or not ed.file_state.path: return
        self._open_path(ed.file_state.path)

    def _convert_encoding(self, enc: str, lossy: bool=False):
        ed = self._editor(); 
        if not ed: return
        try:
            data = ed.text().encode(enc, errors=("ignore" if lossy else "strict")).decode(enc, errors="strict")
            ed.setText(data); ed.file_state.encoding = enc; self.enc_label.setText(enc.upper())
        except UnicodeEncodeError as e:
            self._handle_error("Encoding conversion", f"Cannot encode text to {enc}: {e}")
        except UnicodeDecodeError as e:
            self._handle_error("Encoding conversion", f"Cannot decode bytes with {enc}: {e}")
        except Exception as e:
            self._handle_error("Encoding conversion", str(e))

    def _goto_line(self):
        ed = self._editor(); 
        if not ed: return
        ln, ok = QInputDialog.getInt(self, "Go to line", "Line number:", 1, 1, max(1, ed.lines()), 1)
        if not ok: return
        ed.setCursorPosition(ln-1, 0); ed.ensureLineVisible(ln-1)

    def _jump_bookmark(self, next: bool=True):
        ed = self._editor(); 
        if not ed: return
        l, _ = ed.getCursorPosition()
        target = ed.next_bookmark_line(l) if next else ed.prev_bookmark_line(l)
        if target is not None: ed.setCursorPosition(target, 0); ed.ensureLineVisible(target)

    # Plugins
    def _load_plugins(self):
        Path(PLUGINS_DIR).mkdir(parents=True, exist_ok=True)
        acts = self.m_plugins.actions()
        while len(acts) > 3:
            self.m_plugins.removeAction(acts[-1]); acts = self.m_plugins.actions()
        self.m_plugins.addSeparator()
        for pyf in sorted(Path(PLUGINS_DIR).glob("*.py")):
            try:
                spec = importlib.util.spec_from_file_location(pyf.stem, str(pyf))
                mod = importlib.util.module_from_spec(spec); assert spec and spec.loader
                spec.loader.exec_module(mod)  # type: ignore
                submenu = self.m_plugins.addMenu(pyf.stem)
                if hasattr(mod, "register"):
                    mod.register(self, submenu)  # type: ignore
                else:
                    submenu.addAction("(no register(app, menu) found)").setEnabled(False)
            except Exception as e:
                self.m_plugins.addAction(f"{pyf.stem} (load error: {e})").setEnabled(False)

    # Tools
    def _run_python_current(self):
        ed = self._editor()
        if not ed or not ed.file_state.path:
            QMessageBox.information(self, "Run Python", "Save the file first."); return
        cmd = f"{shlex.quote(sys.executable)} {shlex.quote(ed.file_state.path)}"
        self._run_command_async(cmd, cwd=os.path.dirname(ed.file_state.path))

    def _run_external(self):
        ed = self._editor(); cur_file = ed.file_state.path if ed and ed.file_state.path else ""
        cmd_tpl, ok = QInputDialog.getText(self, "Run External", "Command (use {file} placeholder):", text="echo Running {file}")
        if not ok: return
        cmd = cmd_tpl.replace("{file}", shlex.quote(cur_file)); self._run_command_async(cmd, cwd=os.path.dirname(cur_file) if cur_file else None)

    def _run_command_async(self, cmd: str, cwd: Optional[str]=None):
        self.console_dock.show(); self.console_dock.raise_(); self.console_dock.out.append(f"$ {cmd}\n")
        busy = BusyIndicator(self.status, "Running command…")
        def worker(cmd, cwd):
            try:
                proc = subprocess.Popen(cmd, cwd=cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                out, _ = proc.communicate()
                rc = proc.returncode
                return {"ok": True, "data": (rc, out)}
            except FileNotFoundError:
                return {"ok": False, "error": "Command not found"}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        def on_done(res):
            busy.done("Command finished")
            if res.get("ok"):
                rc, out = res["data"]
                self.console_dock.out.append(out)
                if rc != 0:
                    self._handle_error("External command", f"Process exited with code {rc}")
            else:
                self._handle_error("External command", res.get("error","Unknown error"))

        def on_err(msg):
            busy.done("Command failed")
            self._handle_error("External command", msg)

        run_async(self, worker, on_done, on_err, cmd, cwd)

    # Dictation
    def _start_dictation(self):
        """Robust dictation with sounddevice (preferred) and PyAudio fallback."""
        try:
            import speech_recognition as sr
        except Exception as e:
            self._handle_error("Dictation", f"SpeechRecognition not available: {e}\nInstall with: pip install SpeechRecognition sounddevice numpy")
            return
        recognizer = sr.Recognizer()

        # Preferred: sounddevice path
        try:
            import sounddevice as sd, numpy as np, queue, time
            device = self.mic_device_idx if getattr(self, "mic_device_idx", -1) >= 0 else None
            samplerate = 16000; blocksize = 1024
            silence_ms = 1200; max_ms = 20000; ambient_ms = 500; start_timeout_ms = 8000
            q = queue.Queue()
            def callback(indata, frames, t, status):
                q.put(indata.copy())
            # Ambient calibration
            self.status.showMessage("🎙️ Dictation: calibrating…", 2000); QApplication.processEvents()
            ambient_chunks = []
            with sd.InputStream(channels=1, samplerate=samplerate, dtype='int16', blocksize=blocksize, callback=callback, device=device):
                target_frames = int((ambient_ms/1000) * samplerate)
                got = 0
                while got < target_frames:
                    ambient_chunks.append(q.get(timeout=2))
                    got += len(ambient_chunks[-1])
            if ambient_chunks:
                amb = np.concatenate(ambient_chunks).astype(np.int16)
                energy_threshold = float(np.sqrt(np.mean(amb.astype(np.float32)**2))) * 3.0
            else:
                energy_threshold = 500.0

            # Listen until silence
            q = queue.Queue()
            started = False; start_time = time.time(); last_voice_ms = 0
            collected = bytearray()
            with sd.InputStream(channels=1, samplerate=samplerate, dtype='int16', blocksize=blocksize, callback=callback, device=device):
                self.status.showMessage("🎙️ Dictation: listening…", 3000); QApplication.processEvents()
                while True:
                    try:
                        data = q.get(timeout=0.5)
                    except queue.Empty:
                        if not started and (time.time() - start_time) * 1000 > start_timeout_ms:
                            raise TimeoutError("No speech detected (start timeout).")
                        continue
                    arr = data.reshape(-1).astype(np.int16)
                    rms = float(np.sqrt(np.mean(arr.astype(np.float32)**2)))
                    now_ms = (time.time() - start_time) * 1000
                    if not started and rms >= energy_threshold:
                        started = True; last_voice_ms = now_ms
                        collected.extend(arr.tobytes())
                    elif started:
                        collected.extend(arr.tobytes())
                        if rms >= energy_threshold * 0.6:
                            last_voice_ms = now_ms
                    if started and (now_ms - last_voice_ms) > silence_ms:
                        break
                    if now_ms > max_ms:
                        break

            if not collected:
                raise TimeoutError("Nothing captured from microphone.")
            audio = sr.AudioData(bytes(collected), samplerate, 2)
            self.status.showMessage("🧠 Transcribing…", 3000); QApplication.processEvents()
            text = recognizer.recognize_google(audio)
            ed = self._editor()
            if ed: ed.insert(text)
            self.status.showMessage("✅ Dictation complete", 4000)
            return
        except Exception as e:
            # Fallback to Microphone (PyAudio path)
            try:
                self.status.showMessage("🎙️ Dictation (fallback)…", 3000); QApplication.processEvents()
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = recognizer.listen(source, timeout=8, phrase_time_limit=20)
                self.status.showMessage("🧠 Transcribing…", 3000); QApplication.processEvents()
                text = recognizer.recognize_google(audio)
                ed = self._editor()
                if ed: ed.insert(text)
                self.status.showMessage("✅ Dictation complete", 4000)
                return
            except Exception as e2:
                self._handle_error("Dictation", f"{e}\nFallback also failed: {e2}\n\nTroubleshooting:\n"
                                 "• pip install sounddevice numpy SpeechRecognition\n"
                                 "• Tools → Audio Input → Select Microphone…\n"
                                 "• System Settings → Privacy → Microphone: allow Python\n"
                                 "• Ensure default input device has signal\n")

    # Audio input selection
    def _select_microphone(self):
        try:
            import sounddevice as sd
        except Exception as e:
            self._handle_error("Audio Input", f"sounddevice not available: {e}\nInstall with: pip install sounddevice numpy")
            return
        try:
            devices = sd.query_devices()
            inputs = [(i, d['name']) for i, d in enumerate(devices) if d.get('max_input_channels', 0) > 0]
            if not inputs:
                QMessageBox.warning(self, "Audio Input", "No input devices found."); return
            names = [f"[{i}] {n}" for i, n in inputs]
            item, ok = QInputDialog.getItem(self, "Select Microphone", "Device:", names, 0, False)
            if not ok or not item: return
            sel_idx = int(item.split(']')[0][1:])
            self.mic_device_idx = sel_idx
            self.settings.setValue('mic_device_idx', sel_idx)
            QMessageBox.information(self, "Audio Input", f"Selected: {devices[sel_idx]['name']}")
        except Exception as e:
            self._handle_error("Audio Input", str(e))

    # Self-test
    def _self_test(self):
        checks = [
            ("Actions", all(hasattr(self, n) for n in [
                "act_new","act_open","act_save","act_find","act_find_in_files","act_wrap",
                "act_eol_lf","act_macro_rec","act_run_python","act_dictation"])),
            ("Editor present", isinstance(self._editor(), SciEditor)),
            ("Results dock", hasattr(self, "results_dock")),
            ("Function dock", hasattr(self, "func_dock")),
        ]
        msg = "\n".join(f"{k}: {'OK' if v else 'MISSING'}" for k, v in checks)
        QMessageBox.information(self, "Self Test Report", msg)

    # Error handling
    def _handle_error(self, context: str, message: str):
        handle_exception(context, RuntimeError(message))
        QMessageBox.critical(self, context, message)

    # Tab context menu
    def _tab_context_menu(self, tabs: QTabWidget, pos: QPoint):
        index = tabs.tabBar().tabAt(pos); 
        if index < 0: return
        menu = QMenu(self)
        act_close = menu.addAction("Close")
        act_close_others = menu.addAction("Close Others")
        act_close_all = menu.addAction("Close All")
        act_clone_other = menu.addAction("Clone to Other View")
        act = menu.exec(tabs.mapToGlobal(pos))
        if act == act_close: self._close_tab(tabs, index)
        elif act == act_close_others:
            for i in reversed(range(tabs.count())):
                if i != index: self._close_tab(tabs, i)
        elif act == act_close_all:
            for i in reversed(range(tabs.count())):
                self._close_tab(tabs, i)
        elif act == act_clone_other:
            w: EditorTab = tabs.widget(index)  # type: ignore
            path = w.editor.file_state.path
            if path:
                self._open_path(path, in_other=True); self.tabs_right.setVisible(True)

    # Session
    def _save_session(self):
        sess = {"left": [], "right": [], "active": "left" if self._current_tabs() is self.tabs_left else "right"}
        for label, tabs in (("left", self.tabs_left), ("right", self.tabs_right)):
            for i in range(tabs.count()):
                w: EditorTab = tabs.widget(i)  # type: ignore
                ed = w.editor; l, c = ed.getCursorPosition()
                sess[label].append({"path": ed.file_state.path, "encoding": ed.file_state.encoding, "eol": ed.eol_str(), "line": l, "col": c})
        try: Path(SESSION_FILE).write_text(json.dumps(sess, indent=2))
        except Exception: pass

    def _load_session(self):
        try: data = json.loads(Path(SESSION_FILE).read_text())
        except Exception: data = None
        if not data: return
        for label, tabs in (("left", self.tabs_left), ("right", self.tabs_right)):
            for ent in data.get(label, []):
                path = ent.get("path")
                if path and os.path.exists(path):
                    self._open_path(path, in_other=(label=="right"))
                    ed = self._editor()
                    if ed:
                        ed.set_eol(ent.get("eol","LF")); ed.file_state.encoding = ent.get("encoding","utf-8")
                        ed.setCursorPosition(int(ent.get("line",0)), int(ent.get("col",0)))
        self.tabs_right.setVisible(self.tabs_right.count() > 0)

    # Drag & Drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p: self._open_path(p)

# ---------------- Main ----------------
def main():
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORG); app.setApplicationName(APP_NAME)
    base_font = QFont("SF Pro Text", 13) if "SF Pro Text" in QFontDatabase.families() else app.font()
    app.setFont(base_font)
    w = MainWindow(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
