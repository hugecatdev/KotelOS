# общее для всех окон одного процесса: иконки, буфер обмена, открытие файлов (как xdg-open), запуск программ
import os
import tkinter as tk
from tkinter import messagebox

import kt

from . import CONFIG, HOME, TRASH, basename, exists, mkdirs, q, read, spawn, stat, write
from . import entry

# свои программы этого пакета: при запущенном рабочем столе окно открывается в его же процессе
INTERNAL = ("files", "notepad", "imgview", "cfgedit")
PLACES = CONFIG + "/places"


class App:
    def __init__(self):
        self.root = tk.Tk(className="ktdesktop")
        self.root.withdraw()
        self.desk = None
        self.wins = []
        self.clip = None  # (перенести?, [пути])
        self._img = {}
        self.touch = self.is_touch()
        kt.on("restore", self.on_restore)

    @staticmethod
    def is_touch():
        """Палец или мышь: касание открывает значок сразу, мышью - двойной щелчок."""
        t = os.getenv("KTDESKTOP_TOUCH")
        if t is None:
            try:
                t = kt.js("() => matchMedia('(pointer: coarse)').matches")
            except Exception:
                t = False
        return bool(int(t)) if isinstance(t, str) else bool(t)

    def on_restore(self, d=None):
        # сохранение или снимок бандла открыли в другом браузере: телефон вместо ПК или наоборот
        self.touch = self.is_touch()
        if self.desk:
            self.desk.on_restore()

    # --- иконки: картинка нужного размера (Tk-шные subsample/zoom), кэш по пути и размеру

    def image(self, icon, size):
        p = entry.icon_path(icon) if icon else None
        if not p:
            return None
        key = (p, size)
        im = self._img.get(key)
        if im is None:
            base = self._img.get((p, 0))
            if base is None:
                try:
                    base = tk.PhotoImage(file=p)
                except Exception:
                    return None
                self._img[(p, 0)] = base
            w = base.width() or size
            if w > size * 1.4:
                im = base.subsample(max(1, int(w / size + 0.5)))
            elif w * 2 <= size:
                im = base.zoom(size // w)
            else:
                im = base
            self._img[key] = im
        return im

    # --- окна процесса: без рабочего стола процесс живёт, пока открыто хоть одно

    def add(self, w):
        self.wins.append(w)

    def remove(self, w):
        if w in self.wins:
            self.wins.remove(w)
        if not self.wins and self.desk is None:
            self.root.destroy()

    def changed(self):
        """Файлы поменялись - обновить все открытые папки."""
        for w in self.wins + ([self.desk] if self.desk else []):
            v = getattr(w, "view", None)
            if v is not None:
                v.refresh()

    # --- свои места окна файлов: строка - путь, после табуляции - имя (без него - имя папки)

    def places(self):
        out = []
        for line in read(PLACES).split("\n"):
            path, _, name = line.partition("\t")
            if path.strip():
                out.append((path.strip(), name.strip() or basename(path.strip())))
        return out

    def _save_places(self, items):
        write(PLACES, "".join("%s\t%s\n" % x for x in items))
        from .fm import FileManager
        for w in self.wins:
            if isinstance(w, FileManager):
                w.build_places()

    def add_place(self, path):
        items = self.places()
        if path not in [p for p, _ in items]:
            self._save_places(items + [(path, basename(path))])

    def remove_place(self, path):
        self._save_places([x for x in self.places() if x[0] != path])

    def set_clip(self, items, move):
        self.clip = (move, [i.path for i in items])

    # --- открыть файл или папку

    def open_path(self, path):
        st = stat(path)
        if st is None:
            messagebox.showerror("Нет файла", path)
            return
        m = entry.mime(path, st)
        if m == "inode/directory":
            return self.files(path)
        if m == "application/x-desktop":
            e = entry.parse(path)
            if e and e.ok():
                return self.launch(e)
            messagebox.showerror("Ярлык", "Программа «%s» не найдена" % (e.exec if e else basename(path)))
            return
        exe = st[0] & 0o111 and m in ("application/x-executable", "text/x-shellscript")
        if exe:
            r = messagebox.askyesnocancel(basename(path), "Запустить в терминале?\n«Нет» - открыть как текст")
            if r is None:
                return
            if r:
                return self.in_terminal(q(path))
        hs = entry.handlers(m)
        if hs:
            return self.launch(hs[0], [path])
        if entry.is_text(path):
            return self.notepad(path)
        messagebox.showinfo(basename(path), "Нет программы для файлов типа %s" % m)

    def launch(self, e, files=()):
        a = entry.expand(e, list(files))
        if not a:
            return
        if basename(a[0]) in INTERNAL:
            return getattr(self, basename(a[0]))(*a[1:2])
        cmd = " ".join(q(x) for x in a)
        if e.terminal:
            return self.in_terminal(cmd, title=e.name)
        spawn(cmd, e.workdir or None)
        if self.desk:
            self.desk.starting(e)

    def in_terminal(self, cmd=None, cwd=None, title=None):
        """Команда в терминале. Есть программа-терминал (Categories=TerminalEmulator) - в её окне
        (`-T`, `--cd`, `-e`), нет - в консоли: рабочий стол прячется, команда набирается, как с клавиатуры."""
        emu = [e for e in entry.apps() if "TerminalEmulator" in e.cats]
        if emu:
            a = entry.argv(emu[0].exec)[:1]
            if title:
                a += ["-T", title]
            if cwd:
                a += ["--cd", cwd]
            if cmd:
                a += ["-e", "sh", "-c", cmd]
            spawn(" ".join(q(x) for x in a))
            return
        if cwd:
            cmd = "cd " + q(cwd) + ("; " + cmd if cmd else "")
        if self.desk:
            self.desk.hide()
        try:
            kt.js("(t) => { kt.type(t); kt.fit?.(); }", cmd + "\n")
        except Exception as ex:
            print("ktdesktop: терминал:", ex)

    # --- свои программы

    def files(self, path=None, new=False):
        """Папка в окне файлов: уже открытое окно переходит в неё и поднимается, новое - только если
        окна ещё нет или просили (new)."""
        from .fm import FileManager
        path = path or HOME
        if path == TRASH + "/files":
            mkdirs(path)
        fms = [w for w in self.wins if isinstance(w, FileManager)]
        if fms and not new:
            fm = fms[-1]
            fm.go(path)
            fm.w.deiconify()
            fm.w.lift()
            return
        FileManager(self, path)

    def tick(self):
        """Раз в 3 с: перечитать открытые папки, если они поменялись (stat каталога)."""
        if self.desk and self.desk.visible():
            self.desk.refresh()
        for w in self.wins:
            v = getattr(w, "view", None)
            if v is not None:
                v.refresh()
        self.root.after(3000, self.tick)

    def notepad(self, path=None):
        from .notepad import Notepad
        Notepad(self, path)

    def cfgedit(self, path=None):
        from .registry import Registry
        for w in self.wins:
            if isinstance(w, Registry):
                w.w.deiconify()
                w.w.lift()
                return
        Registry(self)

    def imgview(self, path=None):
        from .viewer import Viewer
        if path and exists(path):
            Viewer(self, path)
        else:
            self.files(os.getenv("HOME"))
