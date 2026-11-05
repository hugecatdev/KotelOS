# окно файлов: папка значками, меню, история; полоса меню не прокручивается, значки - тело окна
import tkinter as tk
from tkinter import simpledialog

from . import DESKTOP, HOME, TRASH, basename, dirname, exists, isdir, q
from .view import IconView

PLACES = [("Домашняя папка", HOME), ("Рабочий стол", DESKTOP), ("Примеры", HOME + "/examples"),
          ("Корзина", TRASH + "/files"), ("Корень /", "/")]


class FileManager:
    def __init__(self, app, path):
        self.app, self.hist = app, []
        w = self.w = tk.Toplevel(app.root)
        w.protocol("WM_DELETE_WINDOW", self.close)
        if not app.touch:
            w.geometry("700x460")
        w.minsize(0, 280)
        mb = tk.Menu(w)
        f = tk.Menu(mb, tearoff=0)
        f.add_command(label="Новое окно", command=lambda: app.files(self.view.folder, new=True))
        f.add_command(label="Создать папку…", command=lambda: self.view.new_folder())
        f.add_command(label="Создать файл…", command=lambda: self.view.new_file())
        f.add_separator()
        f.add_command(label="Перейти…", accelerator="Ctrl+L", command=self.goto)
        f.add_command(label="Терминал здесь", command=lambda: app.in_terminal("cd " + q(self.view.folder)))
        f.add_separator()
        f.add_command(label="Закрыть", accelerator="Ctrl+W", command=self.close)
        mb.add_cascade(label="Файл", menu=f)
        e = tk.Menu(mb, tearoff=0)
        e.add_command(label="Вырезать", accelerator="Ctrl+X", command=lambda: self._clip(True))
        e.add_command(label="Копировать", accelerator="Ctrl+C", command=lambda: self._clip(False))
        e.add_command(label="Вставить", accelerator="Ctrl+V", command=lambda: self.view.paste(self.view.folder))
        e.add_separator()
        e.add_command(label="Переименовать…", accelerator="F2", command=self._rename)
        e.add_command(label="В корзину", accelerator="Del", command=self._delete)
        e.add_separator()
        e.add_command(label="Выделить всё", accelerator="Ctrl+A", command=lambda: self.view.select_all())
        mb.add_cascade(label="Правка", menu=e)
        self.hid = tk.BooleanVar(value=False)
        v = tk.Menu(mb, tearoff=0)
        v.add_checkbutton(label="Скрытые файлы", variable=self.hid, accelerator="Ctrl+H", command=self._hidden)
        v.add_command(label="Обновить", accelerator="F5", command=lambda: self.view.load(keep=True))
        mb.add_cascade(label="Вид", menu=v)
        p = tk.Menu(mb, tearoff=0)
        for name, place in PLACES:
            p.add_command(label=name, command=lambda place=place: self.go(place))
        mb.add_cascade(label="Места", menu=p)
        mb.add_command(label="←", command=self.back)
        mb.add_command(label="↑", command=self.up)
        w.config(menu=mb)
        self.view = IconView(w, app, w, path, on_change=self.title)
        self.view.on_dir = self.go
        self.view.pack(fill="both", expand=1)
        for seq, fn in (("<BackSpace>", self.up), ("<Alt-Up>", self.up), ("<Alt-Left>", self.back),
                        ("<F5>", lambda: self.view.load(keep=True)), ("<Delete>", self._delete),
                        ("<F2>", self._rename), ("<Return>", self._open), ("<Control-l>", self.goto),
                        ("<Control-w>", self.close), ("<Control-c>", lambda: self._clip(False)),
                        ("<Control-x>", lambda: self._clip(True)), ("<Control-a>", lambda: self.view.select_all()),
                        ("<Control-v>", lambda: self.view.paste(self.view.folder)), ("<Control-h>", self._toggle)):
            w.bind(seq, lambda ev, fn=fn: fn() and None)
        self.title()
        app.add(self)

    def title(self):
        f = self.view.folder
        n = "Корзина" if f == TRASH + "/files" else "Домашняя папка" if f == HOME else basename(f)
        s = len(self.view.sel)
        self.w.title("%s%s - Файлы" % (n, " (выделено: %d)" % s if s > 1 else ""))

    def go(self, path):
        if path == TRASH + "/files" and not exists(path):
            from . import mkdirs
            mkdirs(path)
        if not isdir(path):
            return
        if path != self.view.folder:
            self.hist.append(self.view.folder)
            self.view.load(path)

    def back(self):
        if self.hist:
            self.view.load(self.hist.pop())

    def up(self):
        self.go(dirname(self.view.folder))

    def goto(self):
        p = simpledialog.askstring("Перейти", "Папка или файл:", initialvalue=self.view.folder, parent=self.w)
        if not p:
            return
        if not p.startswith("/"):
            p = self.view.folder.rstrip("/") + "/" + p
        if isdir(p):
            self.go(p)
        elif exists(p):
            self.app.open_path(p)

    def _open(self):
        for it in self.view.selected()[:1]:
            self.app.open_path(it.path)

    def _clip(self, move):
        items = self.view.selected()
        if items:
            self.app.set_clip(items, move)

    def _rename(self):
        items = self.view.selected()
        if len(items) == 1:
            self.view.rename(items[0])

    def _delete(self):
        items = self.view.selected()
        if items:
            self.view.delete(items)

    def _hidden(self):
        if self.view.hidden != self.hid.get():
            self.view.toggle_hidden()

    def _toggle(self):
        self.hid.set(not self.hid.get())
        self._hidden()

    def close(self):
        self.w.destroy()
        self.app.remove(self)
