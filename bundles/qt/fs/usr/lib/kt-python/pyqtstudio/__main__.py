"""pyqt-studio [-n] [папка | файл.ui]: форма из Designer и её код на PyQt5 в одном окне.

Сверху - живая форма (form.ui), под ней - код (main.py), внизу - его вывод. После каждого
сохранения формы (в Designer) или кода (Ctrl+S здесь или в другом редакторе) форма
собирается заново и main.py выполняется заново: setup(form) получает свежую форму. Код
идёт в этом же процессе, так что новых окон не появляется. Designer с формой
запускается сам, после того как показано это окно (-n - без него): в dwm он встаёт
главным окном слева. В пустую папку (по умолчанию ~/form) кладётся пример.
"""
import keyword
import os
import re
import runpy
import shutil
import sys
import time
import traceback

from PyQt5 import QtCore, QtGui, QtWidgets, uic

SHARE = "/usr/share/pyqt-studio"
RUN_NAME = "__pyqt_studio__"


def project(args):
    arg = args[0] if args else "~/form"
    path = os.path.abspath(os.path.expanduser(arg))
    if path.endswith(".ui"):
        ui, py = path, path[:-3] + ".py"
    else:
        ui, py = os.path.join(path, "form.ui"), os.path.join(path, "main.py")
    os.makedirs(os.path.dirname(ui), exist_ok=True)
    if not os.path.exists(ui):
        shutil.copy(os.path.join(SHARE, "form.ui"), ui)
    if not os.path.exists(py):
        with open(os.path.join(SHARE, "main.py"), encoding="utf-8") as f:
            code = f.read().replace("form.ui", os.path.basename(ui))
        with open(py, "w", encoding="utf-8") as f:
            f.write(code)
    return ui, py


def mono():
    # в машине моноширинный - растровый fixed из xorg (6x13, как в st); на «monospace» fontconfig отдаёт Cantarell
    for family in ("Misc Fixed", "Fixed", "Monospace"):
        font = QtGui.QFont(family)
        font.setPixelSize(13)
        font.setStyleHint(QtGui.QFont.TypeWriter)
        if QtGui.QFontInfo(font).fixedPitch():
            return font
    return QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)


class Highlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)

        def fmt(color, bold=False):
            f = QtGui.QTextCharFormat()
            f.setForeground(QtGui.QColor(color))
            if bold:
                f.setFontWeight(QtGui.QFont.Bold)
            return f

        self.rules = [
            (re.compile(r"\b(%s)\b" % "|".join(keyword.kwlist)), fmt("#7a3e9d", True)),
            (re.compile(r"\b(self|print|len|range|str|int|float|list|dict|set|super|isinstance)\b"), fmt("#1f6f8b")),
            (re.compile(r"\b\d+(\.\d+)?\b"), fmt("#b35c00")),
            (re.compile(r"@\w+"), fmt("#1f6f8b")),
            (re.compile(r"(?<=\bdef )\w+|(?<=\bclass )\w+"), fmt("#0b5cad", True)),
            (re.compile(r"[rbfRBF]{0,2}('[^'\\\n]*(\\.[^'\\\n]*)*'|\"[^\"\\\n]*(\\.[^\"\\\n]*)*\")"), fmt("#2e7d32")),
            (re.compile(r"#[^\n]*"), fmt("#8a8a8a")),
        ]
        self.triple = fmt("#2e7d32")

    def highlightBlock(self, text):
        for rx, f in self.rules:
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), f)
        # строки в тройных кавычках через несколько строк: состояние блока - незакрытая кавычка
        quotes = {1: '"""', 2: "'''"}
        self.setCurrentBlockState(0)
        quote, pos, begin = quotes.get(self.previousBlockState()), 0, 0
        while True:
            if quote is None:
                m = re.compile(r'"""|\'\'\'').search(text, pos)
                if not m:
                    return
                quote, begin, pos = m.group(), m.start(), m.end()
            end = text.find(quote, pos)
            if end < 0:
                self.setFormat(begin, len(text) - begin, self.triple)
                self.setCurrentBlockState(1 if quote == '"""' else 2)
                return
            self.setFormat(begin, end + 3 - begin, self.triple)
            quote, pos = None, end + 3


class Editor(QtWidgets.QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setFont(mono())
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.highlighter = Highlighter(self.document())

    def keyPressEvent(self, e):
        cur = self.textCursor()
        if e.key() == QtCore.Qt.Key_Tab and not cur.hasSelection():
            cur.insertText(" " * (4 - cur.positionInBlock() % 4))
            return
        if e.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            line = cur.block().text()[:cur.positionInBlock()]
            indent = line[:len(line) - len(line.lstrip(" "))]
            if line.rstrip().endswith(":"):
                indent += "    "
            cur.insertText("\n" + indent)
            self.ensureCursorVisible()
            return
        if e.key() == QtCore.Qt.Key_Backspace and not cur.hasSelection():
            line = cur.block().text()[:cur.positionInBlock()]
            if line and not line.strip(" "):
                for _ in range((len(line) - 1) % 4 + 1):
                    cur.deletePreviousChar()
                return
        super().keyPressEvent(e)


class Output(QtWidgets.QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setFont(mono())
        self.setMaximumBlockCount(2000)
        self.plain = QtGui.QTextCharFormat()
        self.error = QtGui.QTextCharFormat()
        self.error.setForeground(QtGui.QColor("#c62828"))
        self.dim = QtGui.QTextCharFormat()
        self.dim.setForeground(QtGui.QColor("#8a8a8a"))

    def put(self, text, f=None):
        cur = self.textCursor()
        cur.movePosition(QtGui.QTextCursor.End)
        cur.insertText(text, f or self.plain)
        self.setTextCursor(cur)
        self.ensureCursorVisible()


class Stream:
    """sys.stdout/sys.stderr кода формы: в окно вывода и в настоящий поток."""

    def __init__(self, out, real, error):
        self.out, self.real, self.error = out, real, error

    def write(self, s):
        if self.real:
            self.real.write(s)
        self.out.put(s, self.out.error if self.error else None)
        return len(s)

    def flush(self):
        if self.real:
            self.real.flush()


class Studio(QtWidgets.QMainWindow):
    def __init__(self, ui, py, designer=True):
        super().__init__()
        self.ui, self.py, self.dir = ui, py, os.path.dirname(ui)
        self.stamp = None
        self.form = None
        self.designer = designer

        self.area = QtWidgets.QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.editor = Editor()
        self.output = Output()
        # форма | (код над выводом): в высоком окне форма сверху, в широком (dwm-studio на экране телефона
        # стоя кладёт студию под Designer) - слева
        code = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        code.addWidget(self.editor)
        code.addWidget(self.output)
        code.setStretchFactor(0, 3)
        code.setStretchFactor(1, 1)
        self.split = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.split.addWidget(self.area)
        self.split.addWidget(code)
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 4)
        for s in (code, self.split):
            s.setChildrenCollapsible(False)
        self.setCentralWidget(self.split)

        QtWidgets.QShortcut(QtGui.QKeySequence.Save, self, self.save)
        QtWidgets.QShortcut(QtGui.QKeySequence("F5"), self, lambda: self.reload(force=True))

        sys.stdout = Stream(self.output, sys.__stdout__, False)
        sys.stderr = Stream(self.output, sys.__stderr__, True)
        sys.excepthook = self.exception

        self.load_code()
        self.watcher = QtCore.QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self.changed)
        self.watcher.directoryChanged.connect(self.changed)
        self.timer = QtCore.QTimer(self, singleShot=True, interval=250, timeout=self.reload)
        self.watch()
        self.reload()

    def watch(self):
        # сохранение через новый файл (Designer, nano) снимает наблюдение с прежнего - ставим снова
        for p in (self.ui, self.py, self.dir):
            if os.path.exists(p) and p not in self.watcher.files() + self.watcher.directories():
                self.watcher.addPath(p)

    def changed(self, _path):
        self.watch()
        self.timer.start()

    def files_stamp(self):
        out = []
        for p in (self.ui, self.py):
            try:
                st = os.stat(p)
                out.append((st.st_mtime_ns, st.st_size))
            except OSError:
                out.append(None)
        return out

    def load_code(self):
        try:
            with open(self.py, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return
        if text == self.editor.toPlainText():
            return
        cur = self.editor.textCursor()
        pos, scroll = cur.position(), self.editor.verticalScrollBar().value()
        self.editor.setPlainText(text)
        cur.setPosition(min(pos, len(text)))
        self.editor.setTextCursor(cur)
        self.editor.verticalScrollBar().setValue(scroll)
        self.editor.document().setModified(False)

    def save(self):
        with open(self.py, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())
        self.editor.document().setModified(False)
        self.reload()

    def exception(self, kind, value, tb):
        self.output.put("".join(traceback.format_exception(kind, value, tb)), self.output.error)

    def reload(self, force=False):
        stamp = self.files_stamp()
        if stamp == self.stamp and not force:
            return
        self.stamp = stamp
        if not self.editor.document().isModified():
            self.load_code()
        self.output.put("── %s ──\n" % time.strftime("%H:%M:%S"), self.output.dim)
        try:
            form = uic.loadUi(self.ui)
        except Exception:
            self.exception(*sys.exc_info())
            return
        # модули из папки формы - заново, как при новом запуске
        for name, mod in list(sys.modules.items()):
            f = getattr(mod, "__file__", None) or ""
            if f.startswith(self.dir + os.sep):
                del sys.modules[name]
        if self.dir not in sys.path:
            sys.path.insert(0, self.dir)
        os.chdir(self.dir)
        try:
            code = runpy.run_path(self.py, run_name=RUN_NAME)
            if callable(code.get("setup")):
                code["setup"](form)
        except SystemExit:
            pass
        except Exception:
            self.exception(*sys.exc_info())
        form.setWindowFlags(QtCore.Qt.Widget)
        # setWidget сам удалил бы прежнюю форму сразу, а она может быть ещё в обработчике события
        old = self.area.takeWidget()
        self.area.setWidget(form)
        self.form = form
        if old is not None:
            old.deleteLater()
        self.setWindowTitle(form.windowTitle() or os.path.basename(self.ui))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        w, h = e.size().width(), e.size().height()
        wide = self.split.orientation() == QtCore.Qt.Horizontal
        # с запасом, чтобы почти квадратное окно не перекладывалось туда-сюда
        if wide != (w > h * (1.0 if wide else 1.25)):
            wide = not wide
            self.split.setOrientation(QtCore.Qt.Horizontal if wide else QtCore.Qt.Vertical)
            n = w if wide else h
            self.split.setSizes([n * 3 // 7, n - n * 3 // 7])

    def showEvent(self, e):
        super().showEvent(e)
        if self.designer:
            self.designer = False
            QtCore.QTimer.singleShot(0, self.start_designer)

    def start_designer(self):
        if not QtCore.QProcess.startDetached("designer", [self.ui], self.dir):
            self.output.put("designer не запустился\n", self.output.error)


def main():
    args = sys.argv[1:]
    designer = "-n" not in args
    args = [a for a in args if a != "-n"]
    app = QtWidgets.QApplication(sys.argv[:1])
    ui, py = project(args)
    w = Studio(ui, py, designer)
    w.resize(560, 700)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
