# папка значками - общий вид рабочего стола и окна файлов (как pcmanfm и pcmanfm --desktop)
import os
import time
import tkinter as tk
from tkinter import messagebox, simpledialog

from . import HOME, TRASH, basename, date_str, isdir, join, q, size_str, stat
from . import entry, ops

CELL, CELL_H, CHARS = 86, 96, 10
SEL_BG, SEL_FG = "#3b6ea5", "white"
THUMB = 48 * 1024  # картинки до стольки байт показываются уменьшенными вместо значка


def wrap(name, n=CHARS, lines=2):
    """Подпись под значком: перенос по пробелам и знакам, не больше lines строк, дальше «…»."""
    out, s = [], name
    while s and len(out) < lines:
        if len(s) <= n:
            out.append(s)
            s = ""
            break
        cut = -1
        for i in range(n, 0, -1):
            if s[i - 1] in " _-":
                cut = i
                break
            if s[i - 1] == "." and i > 1:
                cut = i - 1  # точку расширения - на новую строку: «заметка» / «.txt»
                break
        if cut < n // 2:
            cut = n
        out.append(s[:cut].rstrip())
        s = s[cut:].lstrip()
    if s:
        out[-1] = out[-1][:n - 1] + "…"
    return "\n".join(out)


class Item:
    def __init__(self, name, path, icon, kind="file", st=None, app=None):
        self.name, self.path, self.icon, self.kind, self.st, self.app = name, path, icon, kind, st, app


class IconView(tk.Frame):
    """Значки папки сеткой; колонки - по ширине окна top. desktop=True - рабочий стол."""

    def __init__(self, master, app, top, folder, desktop=False, bg=None, fg=None, on_change=None):
        tk.Frame.__init__(self, master, bg=bg)
        self.app, self.top, self.desktop = app, top, desktop
        self.bg, self.fg, self.on_change = bg, fg, None
        self.folder, self.items, self.labels = folder, [], []
        self.sel, self.cols, self.hidden, self.stamp = set(), 0, False, None
        self.press = None
        self.on_dir = None  # папка: окно файлов открывает её у себя, рабочий стол - в окне файлов
        self.menu = tk.Menu(self, tearoff=0)
        top.bind("<Configure>", self._conf, add="+")
        self.bind("<Button-1>", lambda e: self.select(set()))
        self.bind("<Button-3>", self._bg_menu)
        tag = "IconItem%d" % id(self)
        self.tag = tag
        self.bind_class(tag, "<Button-1>", self._press)
        self.bind_class(tag, "<ButtonRelease-1>", self._release)
        self.bind_class(tag, "<Double-Button-1>", lambda e: self.open_item(e.widget._i))
        self.bind_class(tag, "<Button-3>", self._item_menu)
        self.load(folder)
        self.on_change = on_change  # после первой загрузки: владелец ещё строится

    # --- содержимое

    def scan(self):
        out = []
        if self.desktop:
            out.append(Item("Домашняя папка", HOME, "user-home", "dir"))
            out.append(Item("Корзина", TRASH + "/files", "user-trash", "dir"))
        try:
            names = os.listdir(self.folder)
        except OSError:
            names = []
        rows = []
        for n in names:
            if n[0] == "." and not self.hidden:
                continue
            p = join(self.folder, n)
            st = stat(p)
            if st is None:
                continue  # битая ссылка: программу удалили, а ярлык остался
            if st[0] & 0o170000 == 0o040000:
                rows.append((0, n.lower(), Item(n, p, "folder", "dir", st)))
                continue
            m = entry.mime(p, st)
            if m == "application/x-desktop":
                e = entry.parse(p)
                if e is None or not e.ok():
                    if self.desktop:
                        continue
                    rows.append((1, n.lower(), Item(n, p, "application-x-generic", "file", st)))
                    continue
                rows.append((1, e.name.lower(), Item(e.name, p, e.icon or "application-x-executable", "app", st, e)))
                continue
            icon = entry.icon_name(m)
            if m in ("image/png", "image/gif", "image/svg+xml") and st[6] <= THUMB:
                icon = p
            rows.append((1, n.lower(), Item(n, p, icon, "file", st)))
        rows.sort(key=lambda r: (r[0], r[1]))
        return out + [r[2] for r in rows]

    def load(self, folder=None, keep=False):
        if folder is not None and folder != self.folder:
            self.folder, keep = folder, False
        old = set(i.path for k, i in enumerate(self.items) if k in self.sel) if keep else set()
        self.items = self.scan()
        self.sel = set(k for k, i in enumerate(self.items) if i.path in old)
        self.stamp = self._stamp()
        for l in self.labels:
            l.destroy()
        self.labels = []
        for k, it in enumerate(self.items):
            img = self.app.image(it.icon, 48) or self.app.image("application-x-generic", 48)
            l = tk.Label(self, image=img, text=wrap(it.name), compound="top", width=CELL, height=CELL_H,
                         anchor="n", bg=self.bg, fg=self.fg)
            l._i = k
            l.bindtags((l._w, self.tag, self.top._w, "all"))
            self.labels.append(l)
        self.cols = 0
        self._layout()
        self._paint()
        if self.on_change:
            self.on_change()

    def _stamp(self):
        s = stat(self.folder)
        return (s[8], s[9]) if s else None

    def refresh(self):
        """Перечитать, если папка поменялась (время изменения каталога)."""
        if self._stamp() != self.stamp:
            self.load(keep=True)

    def _conf(self, e):
        if e.widget is self.top:
            self._layout(e.width)

    def _layout(self, width=None):
        if width is None:
            width = self.top.winfo_width() if self.labels else 0
        cols = max(1, (width - 16) // (CELL + 4)) if width > 1 else 4  # 16 - полоса прокрутки
        if cols == self.cols:
            return
        self.cols = cols
        for k, l in enumerate(self.labels):
            l.grid(row=k // cols, column=k % cols, pady=2, sticky="n")

    def _paint(self):
        for k, l in enumerate(self.labels):
            on = k in self.sel
            l.configure(bg=SEL_BG if on else self.bg, fg=SEL_FG if on else self.fg)

    def select(self, s):
        if s != self.sel:
            self.sel = set(s)
            self._paint()
            if self.on_change:
                self.on_change()

    def selected(self):
        return [self.items[k] for k in sorted(self.sel) if k < len(self.items)]

    # --- мышь и палец: мышью клик выделяет, двойной открывает; пальцем касание открывает,
    # долгое нажатие (страница шлёт его как правую кнопку) - меню

    def _press(self, e):
        k = e.widget._i
        self.press = (k, time.time())
        if e.state & 4:
            self.select(self.sel ^ {k})
        elif k not in self.sel:
            self.select({k})

    def _release(self, e):
        p, self.press = self.press, None
        if self.app.touch and p and p[0] == e.widget._i and time.time() - p[1] < 0.6:
            self.open_item(p[0])

    def open_item(self, k):
        if 0 <= k < len(self.items):
            it = self.items[k]
            self.select(set())  # открытый значок не остаётся выделенным
            if it.kind == "dir":
                (self.on_dir or self.app.files)(it.path)
            else:
                self.app.open_path(it.path)

    # --- меню

    def _post(self, e):
        self.press = None
        self.menu.tk_popup(e.x_root, e.y_root)

    def _item_menu(self, e):
        k = e.widget._i
        if k not in self.sel:
            self.select({k})
        items = self.selected()
        m = self.menu
        m.delete(0, "end")
        one = items[0] if len(items) == 1 else None
        trash = ops.in_trash(self.folder)
        if one and not trash:
            m.add_command(label="Открыть", command=lambda: self.open_item(k))
            if one.kind == "dir" and self.on_dir:
                m.add_command(label="Открыть в новом окне", command=lambda p=one.path: self.app.files(p, new=True))
            if one.kind == "file":
                hs = entry.handlers(entry.mime(one.path, one.st))
                if hs:
                    sub = tk.Menu(m, tearoff=0)
                    for h in hs:
                        sub.add_command(label=h.name, image=self.app.image(h.icon, 24), compound="left",
                                        command=lambda h=h, p=one.path: self.app.launch(h, [p]))
                    m.add_cascade(label="Открыть с помощью", menu=sub)
                if one.st and one.st[0] & 0o111 and entry.mime(one.path, one.st) != "application/x-desktop":
                    m.add_command(label="Запустить в терминале", command=lambda p=one.path: self.app.in_terminal(q(p)))
            m.add_separator()
        if trash:
            m.add_command(label="Восстановить", command=lambda: self._do(ops.restore, items))
            m.add_command(label="Удалить насовсем", command=lambda: self._purge(items))
        else:
            if not (one and one.path in (HOME, TRASH + "/files")):
                m.add_command(label="Вырезать", command=lambda: self.app.set_clip(items, True))
                m.add_command(label="Копировать", command=lambda: self.app.set_clip(items, False))
            if one and one.kind == "dir" and self.app.clip:
                m.add_command(label="Вставить в папку", command=lambda: self.paste(one.path))
            if one and one.path not in (HOME, TRASH + "/files"):
                m.add_command(label="Переименовать…", command=lambda: self.rename(one))
            if not (one and one.path in (HOME, TRASH + "/files")):
                m.add_command(label="Убрать с рабочего стола" if self.desktop and one and one.kind == "app" else "В корзину",
                              command=lambda: self.delete(items))
        if one:
            m.add_separator()
            m.add_command(label="Свойства", command=lambda: self.props(one))
        self._post(e)

    def _bg_menu(self, e):
        if e.widget is not self:
            return
        self.select(set())
        m = self.menu
        m.delete(0, "end")
        if ops.in_trash(self.folder):
            m.add_command(label="Очистить корзину", command=self.empty_trash)
        else:
            m.add_command(label="Создать папку…", command=self.new_folder)
            m.add_command(label="Создать файл…", command=self.new_file)
            if self.app.clip:
                m.add_command(label="Вставить", command=lambda: self.paste(self.folder))
        m.add_separator()
        if self.labels and not self.app.touch:
            m.add_command(label="Выделить всё", command=self.select_all)
        m.add_command(label="Обновить", command=lambda: self.load(keep=True))
        v = tk.BooleanVar(value=self.hidden)
        m.add_checkbutton(label="Скрытые файлы", variable=v, command=self.toggle_hidden)
        m.add_separator()
        if self.desktop:
            m.add_command(label="Открыть в файлах", command=lambda: self.app.files(self.folder))
        m.add_command(label="Терминал здесь", command=lambda: self.app.in_terminal("cd " + q(self.folder)))
        self._post(e)

    # --- действия

    def select_all(self):
        self.select(set(range(len(self.items))))

    def toggle_hidden(self):
        self.hidden = not self.hidden
        self.load(keep=True)

    def _done(self, errs):
        self.load(keep=True)
        if errs:
            messagebox.showerror("Не получилось", "\n".join(errs[:12]), parent=self.top)

    def _do(self, fn, items):
        self._done(fn([i.path for i in items]))

    def paste(self, folder):
        clip = self.app.clip
        if not clip:
            return
        move, paths = clip
        errs = ops.paste(paths, folder, move)
        if move:
            self.app.clip = None
        self._done(errs)
        self.app.changed()

    def rename(self, it):
        n = simpledialog.askstring("Переименовать", "Новое имя:", initialvalue=basename(it.path), parent=self.top)
        if n and n != basename(it.path):
            err = ops.rename(it.path, n)
            self._done([err] if err else [])

    def delete(self, items):
        paths = [i.path for i in items if i.path not in (HOME, TRASH + "/files")]
        if not paths:
            return
        self._done(ops.trash(paths))
        self.app.changed()

    def _purge(self, items):
        what = items[0].name if len(items) == 1 else "%d объектов" % len(items)
        if messagebox.askyesno("Удалить насовсем", "Удалить %s без возврата?" % what, parent=self.top):
            self._do(ops.purge, items)

    def empty_trash(self):
        if messagebox.askyesno("Корзина", "Очистить корзину?", parent=self.top):
            ops.empty_trash()
            self.load()
            self.app.changed()

    def new_folder(self):
        n = simpledialog.askstring("Новая папка", "Имя папки:", initialvalue="Новая папка", parent=self.top)
        if n:
            err = ops.new_folder(self.folder, n)
            self._done([err] if err else [])

    def new_file(self):
        n = simpledialog.askstring("Новый файл", "Имя файла:", initialvalue="новый.txt", parent=self.top)
        if n:
            err = ops.new_file(self.folder, n)
            self._done([err] if err else [])

    def props(self, it):
        st = it.st or stat(it.path)
        rows = ["Путь: " + it.path]
        if ops.in_trash(it.path):
            rows.append("Откуда: %s" % (ops.origin(it.path) or "?"))
        if it.kind == "app":
            e = it.app
            rows += ["Программа: " + e.exec] + (["Описание: " + e.comment] if e.comment else [])
        elif isdir(it.path):
            try:
                rows.append("Внутри: %d" % len(os.listdir(it.path)))
            except OSError:
                pass
        elif st:
            rows += ["Тип: " + entry.mime(it.path, st), "Размер: " + size_str(st[6])]
        if st:
            m = st[0]
            perm = "".join("rwx"[i % 3] if m & (0o400 >> i) else "-" for i in range(9))
            rows += ["Изменён: " + date_str(st[8]), "Права: " + perm]
        messagebox.showinfo(it.name, "\n".join(rows), parent=self.top)

