# блокнот: простой редактор текста на Text, открывается в процессе рабочего стола сразу
import tkinter as tk
from tkinter import messagebox, simpledialog

from . import HOME, basename, exists, isdir, join


class Notepad:
    def __init__(self, app, path=None):
        self.app, self.path = app, path
        w = self.w = tk.Toplevel(app.root)
        w.protocol("WM_DELETE_WINDOW", self.close)
        mb = tk.Menu(w)
        f = tk.Menu(mb, tearoff=0)
        f.add_command(label="Новый", command=lambda: app.notepad())
        f.add_command(label="Открыть…", accelerator="Ctrl+O", command=self.open)
        f.add_command(label="Сохранить", accelerator="Ctrl+S", command=self.save)
        f.add_command(label="Сохранить как…", command=self.save_as)
        f.add_separator()
        f.add_command(label="Закрыть", accelerator="Ctrl+W", command=self.close)
        mb.add_cascade(label="Файл", menu=f)
        e = tk.Menu(mb, tearoff=0)
        e.add_command(label="Отменить", accelerator="Ctrl+Z", command=lambda: self._ev("<<Undo>>"))
        e.add_separator()
        e.add_command(label="Вырезать", accelerator="Ctrl+X", command=lambda: self._ev("<<Cut>>"))
        e.add_command(label="Копировать", accelerator="Ctrl+C", command=lambda: self._ev("<<Copy>>"))
        e.add_command(label="Вставить", accelerator="Ctrl+V", command=lambda: self._ev("<<Paste>>"))
        e.add_command(label="Выделить всё", accelerator="Ctrl+A", command=self._all)
        mb.add_cascade(label="Правка", menu=e)
        self.wrap = tk.BooleanVar(value=True)
        v = tk.Menu(mb, tearoff=0)
        v.add_checkbutton(label="Перенос строк", variable=self.wrap, command=self._wrap)
        mb.add_cascade(label="Вид", menu=v)
        w.config(menu=mb)
        self.t = tk.Text(w, width=72, height=22, wrap="word", undo=True)
        self.t.pack(fill="both", expand=1)
        for seq, fn in (("<Control-s>", self.save), ("<Control-o>", self.open), ("<Control-w>", self.close)):
            self.t.bind(seq, lambda ev, fn=fn: fn() or "break")
        self.t.bind("<<Modified>>", lambda ev: self.after_key())
        self.t.bind("<Key>", lambda ev: self.t.after(1, self.after_key), add="+")
        self.dirty = False
        if path and exists(path):
            self.load(path)
        self.title()
        self.t.focus_set()
        app.add(self)

    def _ev(self, name):
        self.t.event_generate(name)

    def _all(self):
        self.t.tag_add("sel", "1.0", "end-1c")

    def _wrap(self):
        self.t.configure(wrap="word" if self.wrap.get() else "none")

    def after_key(self):
        if not self.dirty and self.t.edit_modified():
            self.dirty = True
            self.title()

    def title(self):
        n = basename(self.path) if self.path else "Без имени"
        self.w.title("%s%s - Блокнот" % ("*" if self.dirty else "", n))

    def load(self, path):
        try:
            with open(path, "rb") as f:
                s = f.read().decode("utf-8", "replace")
        except OSError as e:
            messagebox.showerror("Открыть", str(e), parent=self.w)
            return
        self.path = path
        self.t.delete("1.0", "end")
        self.t.insert("1.0", s)
        self.t.edit_reset()
        self.t.edit_modified(False)
        self.t.mark_set("insert", "1.0")
        self.dirty = False
        self.title()

    def _ask(self, title, init):
        p = simpledialog.askstring(title, "Путь к файлу:", initialvalue=init, parent=self.w)
        if p and not p.startswith("/"):
            p = join(HOME, p)
        return p

    def open(self):
        if not self._keep():
            return
        p = self._ask("Открыть", self.path or HOME + "/")
        if p:
            self.load(p)

    def save(self):
        if not self.path:
            return self.save_as()
        try:
            with open(self.path, "w") as f:
                f.write(self.t.get("1.0", "end-1c"))
        except OSError as e:
            messagebox.showerror("Сохранить", str(e), parent=self.w)
            return False
        self.t.edit_modified(False)
        self.dirty = False
        self.title()
        self.app.changed()
        return True

    def save_as(self):
        p = self._ask("Сохранить как", self.path or HOME + "/новый.txt")
        if not p or isdir(p):
            return False
        if exists(p) and p != self.path and not messagebox.askyesno("Сохранить", "Заменить %s?" % p, parent=self.w):
            return False
        self.path = p
        return self.save()

    def _keep(self):
        """Можно ли уйти от текста: сохранён, сохранили сейчас или «не сохранять»."""
        if not self.dirty:
            return True
        r = messagebox.askyesnocancel("Блокнот", "Сохранить изменения?", parent=self.w)
        return r is False or (r is True and self.save())

    def close(self):
        if not self._keep():
            return
        self.w.destroy()
        self.app.remove(self)
