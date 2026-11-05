# окно файлов: путь сверху, панель мест, папка значками, меню, история; полоса меню не прокручивается
import tkinter as tk
from tkinter import ttk

from . import DESKTOP, HOME, TRASH, basename, dirname, exists, isdir
from .view import IconView, SEL_BG, SEL_FG

# постоянные места; свои добавляются из меню папки («Добавить в места») - ~/.config/ktdesktop/places
PLACES = [("Домашняя папка", HOME, "user-home"), ("Рабочий стол", DESKTOP, "user-desktop"),
          ("Корзина", TRASH + "/files", "user-trash"), ("Корень /", "/", "folder")]
SHORT = {"Домашняя папка": "Домой", "Корень /": "/"}
SIDE = 150  # ширина панели мест сбоку, px
SIDE_BG, SIDE_FG = "#22272e", "#d8d8d2"


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
        f.add_command(label="Терминал здесь", command=lambda: app.in_terminal(cwd=self.view.folder))
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
        mb.add_command(label="←", command=self.back)
        mb.add_command(label="↑", command=self.up)
        w.config(menu=mb)
        # путь сверху: видно, где ты, и можно вписать свой (Enter - перейти)
        self.path = tk.Entry(w)
        self.path.pack(side="top", fill="x", padx=4, pady=(4, 2))
        self.path.bind("<Return>", lambda e: self._path() or "break")
        # места: на широком экране столбцом слева, на узком - рядом кнопок под путём, иначе значкам не хватит ширины
        self.narrow = narrow = w.winfo_screenwidth() <= 520
        self.side = tk.Frame(w, bg=SIDE_BG)
        self.side.pack(side="top" if narrow else "left", fill="x" if narrow else "y")
        ttk.Separator(w, orient="horizontal" if narrow else "vertical").pack(
            side="top" if narrow else "left", fill="x" if narrow else "y")
        self.pmenu = tk.Menu(w, tearoff=0)
        self.places = []
        self.build_places()
        self.view = IconView(w, app, w, path, on_change=self.title)
        self.view.reserve = 0 if narrow else SIDE + 12
        self.view.on_dir = self.go
        self.view.pack(fill="both", expand=1)
        for seq, fn in (("<BackSpace>", self.up), ("<Alt-Up>", self.up), ("<Alt-Left>", self.back),
                        ("<F5>", lambda: self.view.load(keep=True)), ("<Delete>", self._delete),
                        ("<F2>", self._rename), ("<Return>", self._open), ("<Control-l>", self.goto),
                        ("<Control-w>", self.close), ("<Control-c>", lambda: self._clip(False)),
                        ("<Control-x>", lambda: self._clip(True)), ("<Control-a>", lambda: self.view.select_all()),
                        ("<Control-v>", lambda: self.view.paste(self.view.folder)), ("<Control-h>", self._toggle)):
            # в строке пути клавиши её собственные: BackSpace стирает, а не идёт вверх
            w.bind(seq, lambda ev, fn=fn: None if ev.widget is self.path else (fn() and None))
        self.title()
        app.add(self)

    def title(self):
        f = self.view.folder
        n = "Корзина" if f == TRASH + "/files" else "Домашняя папка" if f == HOME else basename(f)
        s = len(self.view.sel)
        self.w.title("%s%s - Файлы" % (n, " (выделено: %d)" % s if s > 1 else ""))
        if self.path.get() != f:
            self.path.delete(0, "end")
            self.path.insert(0, f)
        for place, b in self.places:
            on = place == f
            b.configure(bg=SEL_BG if on else SIDE_BG, fg=SEL_FG if on else SIDE_FG)

    def build_places(self):
        """Постоянные места и свои; своё убирается из его меню (правая кнопка, долгое нажатие)."""
        for _, b in self.places:
            b.destroy()
        self.places = []
        own = [(name, path, "folder", True) for path, name in self.app.places()]
        for name, place, icon, mine in [(n, p, i, False) for n, p, i in PLACES] + own:
            b = tk.Button(self.side, text=SHORT.get(name, name) if self.narrow else name, image=self.app.image(icon, 24),
                          compound="left", relief="flat", anchor="w", padx=4, bg=SIDE_BG, fg=SIDE_FG,
                          command=lambda place=place: self.go(place))
            if mine:
                b.bind("<Button-3>", lambda e, place=place: self.place_menu(e, place))
            if self.narrow:
                b.pack(side="left", padx=1, pady=2)
            else:
                b.configure(width=SIDE)
                b.pack(side="top", fill="x", padx=2, pady=1)
            self.places.append((place, b))
        if getattr(self, "view", None) is not None:
            self.title()

    def place_menu(self, e, place):
        m = self.pmenu
        m.delete(0, "end")
        m.add_command(label="Убрать из мест", command=lambda: self.app.remove_place(place))
        m.tk_popup(e.x_root, e.y_root)

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
        self.path.focus_set()
        self.path.selection_range(0, "end")

    def _path(self):
        p = self.path.get().strip()
        if not p.startswith("/"):
            p = self.view.folder.rstrip("/") + "/" + p
        p = p.rstrip("/") or "/"
        if isdir(p):
            self.go(p)
        elif exists(p):
            self.app.open_path(p)
            self.title()
        else:
            self.title()  # нет такого пути - вернуть текущий

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
