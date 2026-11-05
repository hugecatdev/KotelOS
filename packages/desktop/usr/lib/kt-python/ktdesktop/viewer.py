# просмотр картинок: PNG, GIF и SVG сами, остальное (JPEG...) - через Pillow, если он стоит
import os
import tkinter as tk
from tkinter import messagebox

from . import basename, dirname, join
from . import entry

KINDS = ("image/png", "image/gif", "image/svg+xml", "image/jpeg")


class Viewer:
    def __init__(self, app, path):
        self.app = app
        w = self.w = tk.Toplevel(app.root)
        w.protocol("WM_DELETE_WINDOW", self.close)
        mb = tk.Menu(w)
        mb.add_command(label="←", command=lambda: self.step(-1))
        mb.add_command(label="→", command=lambda: self.step(1))
        mb.add_command(label="Подогнать", command=self.toggle)
        w.config(menu=mb)
        self.fit = True
        self.lab = tk.Label(w)
        self.lab.pack(fill="both", expand=1)
        self.img = None
        for seq, d in (("<Left>", -1), ("<Right>", 1), ("<space>", 1)):
            w.bind(seq, lambda ev, d=d: self.step(d))
        w.bind("<Escape>", lambda ev: self.close())
        app.add(self)
        self.show(path)

    def load(self, path):
        m = entry.mime(path)
        if m in ("image/png", "image/gif", "image/svg+xml"):
            return tk.PhotoImage(file=path)
        try:
            import io
            from PIL import Image  # как ImageTk: перевести в PNG и отдать Tk
            b = io.BytesIO()
            Image.open(path).save(b, "PNG")
            return tk.PhotoImage(data=b.getvalue())
        except ImportError:
            raise OSError("для %s нужен Pillow (kt pkg add python-pillow)" % m)

    def show(self, path):
        try:
            img = self.load(path)
        except Exception as e:
            messagebox.showerror(basename(path), str(e), parent=self.w)
            if self.img is None:
                self.close()
            return
        self.path, self.base = path, img
        self._draw()
        self.w.title("%s (%dx%d) - Картинки" % (basename(path), img.width(), img.height()))

    def _draw(self):
        img = self.base
        if self.fit:
            sw, sh = self.w.winfo_screenwidth() - 24, self.w.winfo_screenheight() - 120
            k = max(1, -(-img.width() // max(1, sw)), -(-img.height() // max(1, sh)))
            if k > 1:
                img = img.subsample(k)
        self.img = img
        self.lab.configure(image=img)

    def toggle(self):
        self.fit = not self.fit
        self._draw()

    def step(self, d):
        folder = dirname(self.path)
        try:
            names = sorted(n for n in os.listdir(folder) if entry.mime(join(folder, n)) in KINDS)
        except OSError:
            return
        if basename(self.path) not in names or len(names) < 2:
            return
        i = (names.index(basename(self.path)) + d) % len(names)
        self.show(join(folder, names[i]))

    def close(self):
        self.w.destroy()
        self.app.remove(self)
