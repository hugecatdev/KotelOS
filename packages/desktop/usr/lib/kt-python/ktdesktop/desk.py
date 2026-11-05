# рабочий стол: окно типа desktop со значками ~/Desktop и панель типа dock - Пуск, окна, часы
import os
import time
import tkinter as tk
from tkinter import messagebox

import kt

from . import CONFIG, DESKTOP, HOME, PIDFILE, TRASH, exists, getpid, join, mkdirs, mtime, q, read, sh, write
from . import entry
from .view import IconView, SEL_BG, SEL_FG

BG, FG = "#20384a", "#e9e9e4"
SEEN = CONFIG + "/seen"
BACK = "Обратно в Терминал"


def seed():
    """Новые программы из системных applications - ярлыками на рабочий стол, один раз:
    убранный ярлык не возвращается (имя остаётся в ~/.config/ktdesktop/seen)."""
    mkdirs(DESKTOP)
    seen = set(read(SEEN).split())
    new = [e for e in entry.apps() if e.id not in seen and not e.path.startswith(entry.DATA_HOME + "/")]
    for e in new:
        if not exists(join(DESKTOP, e.id)):
            sh("ln -s %s %s" % (q(e.path), q(join(DESKTOP, e.id))))
        seen.add(e.id)
    if new:
        write(SEEN, "\n".join(sorted(seen)) + "\n")
    return bool(new)


def apps_stamp():
    return [mtime(d) for d in entry.APPS]


class Desktop:
    def __init__(self, app):
        self.app = app
        app.desk = self
        seed()
        self.apps_stamp = apps_stamp()
        w = self.w = tk.Toplevel(app.root, bg=BG)
        w.title("Рабочий стол")
        w.attributes("-type", "desktop")
        w.protocol("WM_DELETE_WINDOW", lambda: None)
        self.view = IconView(w, app, w, DESKTOP, desktop=True, bg=BG, fg=FG)
        self.view.pack(fill="both", expand=1)

        p = self.p = tk.Toplevel(app.root)
        p.title("Панель")
        p.attributes("-type", "dock")
        p.protocol("WM_DELETE_WINDOW", lambda: None)
        self.start = tk.Button(p, text="Пуск", image=app.image("start-here", 24), compound="left",
                               command=self.menu_open, relief="flat", padx=6)
        self.start.pack(side="left", padx=2, pady=2)
        self.narrow = w.winfo_screenwidth() <= 520
        # выход из рабочего стола; на узком экране - одна иконка, подпись не влезет рядом с окнами
        self.exit = tk.Button(p, text="" if self.narrow else BACK, image=app.image("system-log-out", 24),
                              compound="left", command=self.quit, relief="flat", padx=4)
        self.exit.pack(side="left", padx=2, pady=2)
        self.clock = tk.Label(p, text="", padx=8)
        self.clock.pack(side="right")
        self.clock.bind("<Button-1>", lambda e: self.date())
        self.tasks = tk.Frame(p)
        self.tasks.pack(side="left", fill="x", expand=1)
        self.btns, self.wins, self.active, self.pending = {}, [], None, []
        self.menu = tk.Menu(p, tearoff=0)
        self.wmenu = tk.Menu(p, tearoff=0)
        kt.on("tkwm", self.on_wins)
        kt.on("desktop", self.on_cmd)
        try:
            write(PIDFILE, "%d\n" % getpid())
        except OSError as e:
            print("ktdesktop: %s: %s" % (PIDFILE, e))
        self._tick = None
        self.tick_clock()

    def on_restore(self):
        self.narrow = self.w.winfo_screenwidth() <= 520
        self.exit.configure(text="" if self.narrow else BACK)
        self.redraw()

    # --- показать и спрятать (уйти в терминал)

    def hide(self):
        self.w.withdraw()
        self.p.withdraw()

    def show(self):
        hidden = not self.visible()
        self.w.deiconify()
        self.p.deiconify()
        self.refresh()
        if hidden:
            self.tick_clock()

    def visible(self):
        return self.w.state() == "normal"

    def refresh(self):
        """Раз в несколько секунд: новые программы и перемены в ~/Desktop."""
        s = apps_stamp()
        if s != self.apps_stamp:
            self.apps_stamp = s
            entry._icons.clear()
            if seed():
                self.view.load(keep=True)
        self.view.refresh()

    # --- команды из шелла: desktop, files, notepad... при уже запущенном рабочем столе

    def on_cmd(self, d):
        if not isinstance(d, list) or not d:
            return
        c, f = d[0], (d[1] if len(d) > 1 else "") or None
        if c == "show":
            self.show()
        elif c == "hide":
            self.hide()
        elif c == "quit":
            self.quit()
        elif c == "open" and f:
            self.app.open_path(f)
        elif c in ("files", "notepad", "imgview", "cfgedit"):
            getattr(self.app, c)(f)

    # --- панель: кнопки окон всех программ (список даёт страница событием tkwm)

    def on_wins(self, d):
        wins = [x for x in d.get("w", []) if isinstance(x, list) and len(x) >= 3]
        new = [x[0] for x in wins if x[0] not in [y[0] for y in self.wins]]
        self.wins, self.active = wins, d.get("a")
        if new and self.pending:
            self.pending.pop(0)
        self.redraw()

    def starting(self, e):
        """Программа запускается (IDLE в эмуляторе - секунды): серая кнопка до её первого окна."""
        self.pending.append((e.name, time.time() + 40))
        self.redraw()

    def redraw(self):
        now = time.time()
        self.pending = [x for x in self.pending if x[1] > now]
        n = 10 if self.narrow else 22
        cut = lambda s: s if len(s) <= n else s[:n - 1] + "…"
        keep = set()
        for wid, title, iconic in self.wins:
            keep.add(wid)
            b = self.btns.get(wid)
            if b is None:
                b = self.btns[wid] = tk.Button(self.tasks, relief="flat", padx=6,
                                               command=lambda wid=wid: self.click(wid))
                b.bind("<Button-3>", lambda e, wid=wid: self.win_menu(e, wid))
                b.pack(side="left", padx=1, pady=2)
            act = wid == self.active and not iconic
            b.configure(text=cut(("[%s]" if iconic else "%s") % (title or "окно")),
                        bg=SEL_BG if act else "", fg=SEL_FG if act else "")
        for wid in [k for k in self.btns if k not in keep]:
            self.btns.pop(wid).destroy()
        old = getattr(self, "_pend", [])
        for b in old:
            b.destroy()
        self._pend = []
        for name, _ in self.pending:
            b = tk.Label(self.tasks, text="⏳ " + cut(name), fg="#888", padx=6)
            b.pack(side="left", padx=1, pady=2)
            self._pend.append(b)

    def _wm(self, wid, op):
        try:
            kt.js("(i, o) => ktTkS.wm(i, o)", wid, op)
        except Exception as ex:
            print("ktdesktop:", ex)

    def click(self, wid):
        st = dict((x[0], x[2]) for x in self.wins).get(wid)
        if st:
            self._wm(wid, "normal")
        elif wid == self.active:
            self._wm(wid, "iconic")
        else:
            self._wm(wid, "raise")

    def win_menu(self, e, wid):
        m = self.wmenu
        m.delete(0, "end")
        iconic = dict((x[0], x[2]) for x in self.wins).get(wid)
        m.add_command(label="Развернуть" if iconic else "Свернуть",
                      command=lambda: self._wm(wid, "normal" if iconic else "iconic"))
        m.add_command(label="Закрыть", command=lambda: self._wm(wid, "close"))
        m.tk_popup(e.x_root, e.y_root)

    # --- часы

    def tick_clock(self):
        """Часы с секундами, пока рабочий стол на экране: спрятанный не будит питон зря."""
        if self._tick:
            self.clock.after_cancel(self._tick)
            self._tick = None
        if not self.visible():
            return
        now = time.time()
        t = time.localtime(int(now))
        self.clock.configure(text="%02d:%02d:%02d" % (t[3], t[4], t[5]))
        self._tick = self.clock.after(max(50, int((1 - now % 1) * 1000) + 20), self.tick_clock)
        if self.pending and t[5] % 5 == 0:
            self.redraw()

    def date(self):
        t = time.localtime()
        days = "понедельник вторник среда четверг пятница суббота воскресенье".split()
        months = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()
        messagebox.showinfo("Сегодня", "%s, %d %s %d" % (days[t[6]], t[2], months[t[1] - 1], t[0]))

    # --- меню «Пуск»: программы по категориям freedesktop, места, о системе, обратно в терминал

    def menu_open(self):
        m, a = self.menu, self.app
        m.delete(0, "end")
        groups = {}
        for e in entry.apps():
            groups.setdefault(e.category(), []).append(e)
        order = [t for _, t in entry.CATEGORIES] + ["Прочие"]
        for cat in order:
            if cat not in groups:
                continue
            sub = tk.Menu(m, tearoff=0)
            for e in groups[cat]:
                sub.add_command(label=e.name, image=a.image(e.icon, 24) or a.image("application-x-executable", 24),
                                compound="left",
                                command=lambda e=e: a.launch(e))
            m.add_cascade(label=cat, menu=sub)
        m.add_separator()
        m.add_command(label="Домашняя папка", image=a.image("user-home", 24), compound="left",
                      command=lambda: a.files(HOME))
        m.add_command(label="Корзина", image=a.image("user-trash", 24), compound="left",
                      command=lambda: a.files(TRASH + "/files"))
        m.add_command(label="О системе", command=self.about)
        m.add_separator()
        m.add_command(label=BACK, image=a.image("system-log-out", 24), compound="left", command=self.quit)
        m.tk_popup(self.start.winfo_rootx(), self.start.winfo_rooty())

    def about(self):
        rel = dict(l.split("=", 1) for l in read("/etc/os-release").split("\n") if "=" in l)
        mem = dict((l.split(":")[0], l.split()[1]) for l in read("/proc/meminfo").split("\n") if ":" in l)
        up = int(float((read("/proc/uptime").split() or ["0"])[0]))
        tot, av = int(mem.get("MemTotal", 0)) // 1024, int(mem.get("MemAvailable", 0)) // 1024
        messagebox.showinfo("О системе", "%s\nядро %s\nпамять: занято %d из %d МБ\nработает %d ч %d мин" % (
            rel.get("PRETTY_NAME", "KotelOS").strip('"'), (read("/proc/sys/kernel/osrelease") or "?").strip(),
            tot - av, tot, up // 3600, up // 60 % 60))

    def quit(self):
        """Обратно в Терминал: рабочий стол закрывается. Свои окна (файлы, блокнот) закрываются с ним -
        блокнот спросит про несохранённое; свёрнутые окна других программ разворачиваются,
        иначе без панели их не достать."""
        for w in list(self.app.wins):
            w.close()
            if w in self.app.wins:
                return  # блокнот: «Отмена»
        for wid, _, iconic in self.wins:
            if iconic:
                self._wm(wid, "normal")
        try:
            if read(PIDFILE).strip() == str(getpid()):
                os.remove(PIDFILE)
        except OSError:
            pass
        self.app.root.destroy()

