# python3 -m ktterm [-T заголовок] [--cd папка] [-e команда...]: терминал в окне - шелл в pty, экран рисует xterm.js страницы
import base64
import fcntl
import os
import pty
import select
import signal
import struct
import sys
import termios
import time
import tkinter as tk

import kt

JS = "/usr/lib/kt-term.js"
TAIL = 64 * 1024  # хвост вывода: после восстановления машины экран рисуется заново из него
FRAME = 0.03  # пачка вывода - не чаще раза в 30 мс: каждая уходит на страницу своим kt.js
# опрос pty: пока идёт ввод-вывод - часто, после 2 с тишины - редко (питон в эмуляторе дорог и на холостом ходу)
FAST, SLOW, QUIET = 10, 100, 2.0
# ряд клавиш под экраном на телефоне: на экранной клавиатуре их нет
KEYS = [("Esc", "\x1b"), ("Tab", "\t"), ("^C", "\x03"), ("^D", "\x04"), ("↑", "\x1b[A"), ("↓", "\x1b[B"),
        ("←", "\x1b[D"), ("→", "\x1b[C")]


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
    def __init__(self, cwd, cmd, title=None):
        env = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor")
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            try:
                if cwd:
                    os.chdir(cwd)
                if cmd:
                    os.execvpe(cmd[0], cmd, env)
                os.execve("/bin/sh", ["-sh"], env)  # «-» - шелл входа: /etc/profile, kt, PS1
            finally:
                os._exit(127)
        fl = fcntl.fcntl(self.fd, fcntl.F_GETFL)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        self.id = "%d" % os.getpid()
        self.out, self.tail, self.sent, self.live, self.done = bytearray(), bytearray(), 0, False, False
        self.busy, self.job = time.time(), None
        r = self.root = tk.Tk(className="terminal")
        self.name = title or "Терминал"
        r.title(self.name)
        r.protocol("WM_DELETE_WINDOW", self.close)
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        touch = bool(kt.js("() => matchMedia('(pointer: coarse)').matches"))
        w, h = (sw - 24, int(sh * 0.55)) if sw <= 520 else (720, 440)
        self.host = tk.Frame(r, width=w, height=h, bg="black")
        self.host.pack(fill="both", expand=1)
        if touch:
            row = tk.Frame(r)
            row.pack(fill="x")
            for label, seq in KEYS:
                tk.Button(row, text=label, padx=6, command=lambda seq=seq: self.key(seq)).pack(side="left", padx=1, pady=2)
        kt.on("ktterm", self.event)
        kt.on("restore", lambda d: self.open())
        r.update()  # рамка уже на странице - есть куда поставить xterm
        self.open()
        self.wake()

    def js(self, m):
        try:
            if self.live and kt.js("(m) => window.ktTerm ? ktTerm(m) : -1", m) != -1:
                return
            with open(JS) as f:
                kt.js(f.read(), m)
            self.live = True
        except Exception as e:
            print("terminal:", e, file=sys.stderr)

    def open(self):
        self.root.update()
        self.js({"op": "open", "id": self.id, "host": self.host._w,
                 "tail": base64.b64encode(bytes(self.tail)).decode()})

    def event(self, d):
        if not isinstance(d, dict) or d.get("id") != self.id or self.done:
            return
        if "d" in d:
            self.write(d["d"].encode())
            self.wake()
        if "r" in d:
            cols, rows = d["r"]
            if cols > 0 and rows > 0:
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        if "t" in d:
            self.root.title(d["t"] or self.name)

    def write(self, b):
        while b:
            try:
                n = os.write(self.fd, b)
            except BlockingIOError:
                time.sleep(0.01)
                continue
            except OSError:
                return
            b = b[n:]

    def wake(self):
        """Ввод: ответ шелла ждать часто, а не через SLOW."""
        self.busy = time.time()
        if self.job:
            self.root.after_cancel(self.job)
        self.job = self.root.after(FAST, self.pump)

    def key(self, seq):
        self.write(seq.encode())
        self.wake()
        self.js({"op": "focus", "id": self.id})  # кнопка забрала фокус - вернуть клавиатуру терминалу

    def pump(self):
        if self.done:
            return
        self.job = None
        gone = False
        try:
            while len(self.out) < 256 * 1024 and select.select([self.fd], [], [], 0)[0]:
                b = os.read(self.fd, 65536)
                if not b:
                    gone = True
                    break
                self.out += b
        except BlockingIOError:
            pass
        except OSError:  # EIO: шелл вышел, ведомой стороны pty больше нет
            gone = True
        now = time.time()
        if self.out:
            self.busy = now
        if self.out and (gone or now - self.sent >= FRAME or len(self.out) >= 32768):
            self.flush(now)
        if gone:
            return self.close()
        self.job = self.root.after(FAST if self.out or now - self.busy < QUIET else SLOW, self.pump)

    def flush(self, now):
        data = bytes(self.out)
        self.out.clear()
        self.tail += data
        del self.tail[:-TAIL]
        self.sent = now
        self.js({"op": "w", "id": self.id, "d": base64.b64encode(data).decode()})

    def close(self):
        if self.done:
            return
        self.done = True
        try:
            os.kill(self.pid, signal.SIGHUP)
        except OSError:
            pass
        try:
            os.waitpid(self.pid, 0)
        except OSError:
            pass
        self.js({"op": "close", "id": self.id})
        self.root.destroy()


def main():
    cwd, cmd, title = args(sys.argv[1:])
    t = Term(cwd, cmd, title)
    t.root.mainloop()


main()
