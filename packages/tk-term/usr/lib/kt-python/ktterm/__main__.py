# python -m ktterm [-T заголовок] [--cd папка] [-e команда...]: терминал в окне tkinter - консоль kt tty в рамке окна.
# Шелл держит kt-ttyd, экран рисует xterm страницы; байты идут страница <-> kt-ttyd мимо питона,
# окну остаётся рамка, заголовок и закрытие. Ряд клавиш на телефоне - тот же, что у страницы (keys.main,
# keys.more, CTRL/ALT с фиксацией): страница строит его в рамке под экраном и шлёт в консоль этого окна
import sys
import tkinter as tk

import kt

EL = "document.querySelector(`[data-tk=\"${CSS.escape(%s)}\"]`)"
HOST, KEYS = EL % "h", EL % "k"


def q(s):
    return "'" + str(s).replace("'", "'\\''") + "'"


def args(argv):
    cwd, cmd, title = None, None, None
    while argv:
        a = argv.pop(0)
        if a == "--cd" and argv:
            cwd = argv.pop(0)
        elif a == "-T" and argv:
            title = argv.pop(0)
        elif a == "-e":
            cmd = argv
            break
    return cwd, cmd, title


class Term:
    def __init__(self, cwd, cmd, title):
        self.name = title or "Терминал"
        self.id, self.done = None, False
        r = self.root = tk.Tk(className="terminal")
        r.title(self.name)
        r.protocol("WM_DELETE_WINDOW", self.close)
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        r.geometry("%dx%d" % ((sw - 8, int(sh * 0.6)) if sw <= 520 else (720, 460)))
        mb = tk.Menu(r)
        mb.add_command(label="A−", command=lambda: self.font(-1))  # шрифт этого окна, до закрытия
        mb.add_command(label="A+", command=lambda: self.font(1))
        r.config(menu=mb)
        # ряд клавиш страницы (на телефоне) - у нижнего края окна; консоль - всё остальное и тянется с окном
        self.keys = tk.Frame(r)
        self.keys.pack(side="bottom", fill="x")
        self.host = tk.Frame(r, bg="black")
        self.host.pack(side="top", fill="both", expand=1)
        # команда для kt-ttyd: пусто - шелл входа; папка - cd и шелл входа там
        line = " ".join(q(a) for a in cmd) if cmd else ""
        if cwd:
            line = "cd %s && %s" % (q(cwd), line or "exec sh -l")
        kt.on("ktty", self.event)
        kt.on("restore", lambda d: self.attach())
        r.update()  # рамка уже на странице - есть куда поставить консоль
        self.id = kt.js("(c, h, k) => kt.tty.open(c, %s, %s)" % (HOST, KEYS), line, self.host._w, self.keys._w)
        if not self.id:
            self.finish()  # консоли нет (kt-ttyd не запустился) - и окну незачем

    def attach(self):
        """После восстановления страницы рамка новая, консоль та же - снова в окно."""
        if self.id and not self.done:
            self.root.update()
            kt.js("(i, h, k) => kt.tty.attach(i, %s, %s)" % (HOST, KEYS), self.id, self.host._w, self.keys._w)

    def event(self, d):
        if not isinstance(d, dict) or d.get("id") != self.id or self.done:
            return
        if "exit" in d:
            self.finish()
        elif "title" in d:
            self.root.title(d["title"] or self.name)

    def font(self, d):
        if self.id:
            kt.js("(i, d) => kt.tty.font(i, d)", self.id, d)

    def close(self):
        if self.id:
            kt.js("(i) => kt.tty.kill(i)", self.id)  # шеллу SIGHUP; консоль уберёт сама страница
        self.finish()

    def finish(self):
        if not self.done:
            self.done = True
            self.root.destroy()


def main():
    cwd, cmd, title = args(sys.argv[1:])
    Term(cwd, cmd, title).root.mainloop()


main()
