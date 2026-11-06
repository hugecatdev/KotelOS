# реестр: ключи kt cfg таблицей - ключ, значение (правится на месте), описание, «↺» - вернуть умолчание.
# Какие значения бывают у ключей, он не знает: тип берёт у текущего значения
import os
import tkinter as tk
from tkinter import messagebox, simpledialog

import kt

from . import read
from .entry import DATA_DIRS


def descriptions():
    """«ключ описание» из /usr/share/kt/cfg/*: kt - встроенные, пакеты кладут свои (ai)."""
    out = {}
    for base in reversed(DATA_DIRS):
        try:
            names = sorted(os.listdir(base + "/kt/cfg"))
        except OSError:
            continue
        for n in names:
            for line in read(base + "/kt/cfg/" + n).split("\n"):
                k, _, d = line.strip().partition(" ")
                if k:
                    out[k] = d.strip()
    return out


def show(v):
    if v is True or v is False:
        return "on" if v else "off"
    return "" if v is None else str(v)


def parse(s, old):
    """Строку из поля - в тип ключа: числа - числами, on/off - True/False, как у kt cfg."""
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
        self.app, self.vals, self.rows = app, {}, []
        w = self.w = tk.Toplevel(app.root)
        w.title("Реестр")
        w.protocol("WM_DELETE_WINDOW", self.close)
        if not app.touch:
            w.geometry("720x520")
        mb = tk.Menu(w)
        mb.add_command(label="Обновить", command=self.load)
        mb.add_command(label="Новый ключ…", command=self.new)
        w.config(menu=mb)
        self.t = tk.Frame(w)
        self.t.pack(fill="both", expand=1, padx=4, pady=4)
        self.t.columnconfigure(1, weight=1)
        tk.Label(self.t, text="ключ", fg="#888", anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 8))
        tk.Label(self.t, text="значение", fg="#888", anchor="w").grid(row=0, column=1, sticky="w")
        self.load()
        app.add(self)

    def load(self):
        try:
            self.vals = kt.cfg() or {}
        except Exception as e:
            messagebox.showerror("Реестр", str(e), parent=self.w)
            self.vals = {}
        descs = descriptions()
        for r in self.rows:
            for x in r:
                x.destroy()
        self.rows = []
        for i, k in enumerate(sorted(set(self.vals) | set(descs))):
            r = 1 + i * 2
            v = self.vals.get(k)
            key = tk.Label(self.t, text=k, anchor="w")
            key.grid(row=r, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
            cell = self.cell(k, v)
            cell.grid(row=r, column=1, sticky="we", pady=(6, 0))
            back = tk.Button(self.t, text="↺", padx=6, command=lambda k=k: self.reset(k))
            back.grid(row=r, column=2, padx=(4, 0), pady=(6, 0))
            row = [key, cell, back]
            if descs.get(k):
                d = tk.Label(self.t, text=descs[k], fg="#888", anchor="w", justify="left")
                d.grid(row=r + 1, column=0, columnspan=3, sticky="w")
                row.append(d)
            self.rows.append(row)

    def cell(self, k, v):
        """Значение текстом; по Enter или уходу из поля - в kt cfg, в тип текущего значения."""
        secret = k.rsplit(".", 1)[-1] in ("key", "token", "pass", "password", "secret")
        e = tk.Entry(self.t, show="•" if secret else "")  # ключ API на экране не нужен
        e.insert(0, show(v))
        e._old = show(v)

        def commit(ev=None):
            if e.get() != e._old:
                e._old = e.get()
                self.set(k, parse(e.get(), self.vals.get(k)))
        e.bind("<Return>", commit)
        e.bind("<FocusOut>", commit)
        return e

    def set(self, k, v):
        try:
            kt.cfg[k] = v
            self.vals[k] = v
        except Exception as e:
            messagebox.showerror(k, str(e), parent=self.w)
            self.load()

    def reset(self, k):
        try:
            del kt.cfg[k]
        except KeyError:
            pass
        except Exception as e:
            messagebox.showerror(k, str(e), parent=self.w)
        self.load()

    def new(self):
        k = simpledialog.askstring("Новый ключ", "Имя (свои - вида имя.ключ):", parent=self.w)
        if not k or not k.strip():
            return
        v = simpledialog.askstring(k.strip(), "Значение:", parent=self.w)
        if v is None:
            return
        self.set(k.strip(), parse(v, None))
        self.load()

    def close(self):
        self.w.destroy()
        self.app.remove(self)
