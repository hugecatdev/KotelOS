# реестр: ключи kt cfg (браузерные настройки машины) списком - значение, описание, правка, сброс к умолчанию
import os
import tkinter as tk
from tkinter import messagebox, simpledialog

import kt

from . import read

DESC = "/usr/share/kt/cfg"


def descriptions():
    """«ключ описание» из /usr/share/kt/cfg/*: kt - встроенные, пакеты кладут свои (ai)."""
    out = {}
    try:
        names = sorted(os.listdir(DESC))
    except OSError:
        names = []
    for n in names:
        for line in read(DESC + "/" + n).split("\n"):
            k, _, d = line.strip().partition(" ")
            if k:
                out[k] = d.strip()
    return out


def show(v):
    if v is True or v is False:
        return "on" if v else "off"
    return "" if v is None else str(v)


def parse(s, old):
    """Строку из поля - в тип ключа: on/off - True/False, числа - числами, как у kt cfg."""
    t = s.strip()
    if old is True or old is False or t.lower() in ("on", "off", "true", "false"):
        if t.lower() in ("on", "true", "1", "да"):
            return True
        if t.lower() in ("off", "false", "0", "нет"):
            return False
    if isinstance(old, (int, float)) and not isinstance(old, bool):
        try:
            return int(t) if "." not in t else float(t)
        except ValueError:
            pass
    return s


class Registry:
    def __init__(self, app):
        self.app, self.keys, self.vals = app, [], {}
        w = self.w = tk.Toplevel(app.root)
        w.title("Реестр")
        w.protocol("WM_DELETE_WINDOW", self.close)
        mb = tk.Menu(w)
        mb.add_command(label="Обновить", command=self.load)
        mb.add_command(label="Новый ключ…", command=self.new)
        w.config(menu=mb)
        self.lb = tk.Listbox(w, width=44, height=14)
        self.lb.pack(fill="both", expand=1, padx=4, pady=4)
        self.lb.bind("<<ListboxSelect>>", lambda e: self.pick())
        self.desc = tk.Label(w, text="Выберите ключ", anchor="w", justify="left", wraplength=360)
        self.desc.pack(fill="x", padx=6)
        self.ent = tk.Entry(w)
        self.ent.pack(fill="x", padx=4, pady=4)
        self.ent.bind("<Return>", lambda e: self.save())
        row = tk.Frame(w)
        row.pack(fill="x", padx=4, pady=(0, 6))
        tk.Button(row, text="Сохранить", command=self.save).pack(side="left")
        tk.Button(row, text="По умолчанию", command=self.reset).pack(side="left", padx=6)
        self.load()
        app.add(self)

    def load(self, keep=None):
        try:
            self.vals = kt.cfg() or {}
        except Exception as e:
            messagebox.showerror("Реестр", str(e), parent=self.w)
            self.vals = {}
        self.descs = descriptions()
        self.keys = sorted(set(self.vals) | set(self.descs))
        self.lb.delete(0, "end")
        for k in self.keys:
            self.lb.insert("end", "%s = %s" % (k, show(self.vals.get(k))))
        if keep in self.keys:
            i = self.keys.index(keep)
            self.lb.selection_set(i)
            self.lb.see(i)
            self.pick()

    def current(self):
        s = self.lb.curselection()
        return self.keys[s[0]] if s else None

    def pick(self):
        k = self.current()
        if k is None:
            return
        d = self.descs.get(k, "")
        self.desc.configure(text="%s%s" % (k, " - " + d if d else ""))
        self.ent.delete(0, "end")
        self.ent.insert(0, show(self.vals.get(k)))

    def save(self):
        k = self.current()
        if k is None:
            return
        try:
            kt.cfg[k] = parse(self.ent.get(), self.vals.get(k))
        except Exception as e:
            messagebox.showerror(k, str(e), parent=self.w)
            return
        self.load(keep=k)

    def reset(self):
        k = self.current()
        if k is None:
            return
        try:
            del kt.cfg[k]
        except KeyError:
            pass
        except Exception as e:
            messagebox.showerror(k, str(e), parent=self.w)
        self.load(keep=k)

    def new(self):
        k = simpledialog.askstring("Новый ключ", "Имя (свои - вида имя.ключ):", parent=self.w)
        if not k or not k.strip():
            return
        k = k.strip()
        v = simpledialog.askstring(k, "Значение:", parent=self.w)
        if v is None:
            return
        try:
            kt.cfg[k] = parse(v, None)
        except Exception as e:
            messagebox.showerror(k, str(e), parent=self.w)
            return
        self.load(keep=k)

    def close(self):
        self.w.destroy()
        self.app.remove(self)
