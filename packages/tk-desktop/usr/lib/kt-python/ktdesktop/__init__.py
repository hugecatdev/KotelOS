# общее для рабочего стола, файлового менеджера и мелких программ; идёт и в MicroPython, и в CPython
import os
import time

HOME = os.getenv("HOME") or "/root"
DESKTOP = HOME + "/Desktop"
CONFIG = HOME + "/.config/ktdesktop"
LOG = HOME + "/.cache/desktop.log"
PIDFILE = "/run/ktdesktop.pid"
TRASH = HOME + "/.local/share/Trash"


def join(a, b):
    return b if b.startswith("/") else (a.rstrip("/") + "/" + b if a != "/" else "/" + b)


def dirname(p):
    p = p.rstrip("/") or "/"
    i = p.rfind("/")
    return p[:i] or "/"


def basename(p):
    p = p.rstrip("/")
    return p[p.rfind("/") + 1:] or "/"


def stat(p):
    try:
        return os.stat(p)
    except OSError:
        return None


def isdir(p):
    s = stat(p)
    return s is not None and s[0] & 0o170000 == 0o040000


def exists(p):
    return stat(p) is not None


def mtime(p):
    s = stat(p)
    return s[8] if s else 0


def mkdirs(p):
    if p and not isdir(p):
        mkdirs(dirname(p))
        try:
            os.mkdir(p)
        except OSError:
            pass


def read(p, n=-1):
    try:
        with open(p) as f:
            return f.read(n)
    except (OSError, UnicodeError):
        return ""


def write(p, s):
    mkdirs(dirname(p))
    with open(p, "w") as f:
        f.write(s)


def q(s):
    """Строка в одинарных кавычках для sh."""
    return "'" + str(s).replace("'", "'\\''") + "'"


def sh(cmd):
    """Команда шелла с ожиданием; True, если код 0."""
    return os.system(cmd) == 0


def spawn(cmd, cwd=None):
    """Запустить в фоне, вывод - в ~/.cache/desktop.log."""
    mkdirs(dirname(LOG))
    pre = "cd %s && " % q(cwd) if cwd else ""
    os.system("(%s%s) >> %s 2>&1 < /dev/null &" % (pre, cmd, q(LOG)))


def which(cmd):
    if "/" in cmd:
        return cmd if exists(cmd) else None
    for d in (os.getenv("PATH") or "/usr/local/bin:/bin:/usr/bin").split(":"):
        if d and exists(d + "/" + cmd):
            return d + "/" + cmd
    return None


def getpid():
    try:
        return os.getpid()
    except AttributeError:
        with open("/proc/self/stat") as f:
            return int(f.read().split()[0])


def size_str(n):
    for u in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024 or u == "ГБ":
            return ("%d %s" if u == "Б" else "%.1f %s") % (n, u)
        n /= 1024


def date_str(t):
    y, mo, d, h, mi = time.localtime(t)[:5]
    return "%02d.%02d.%d %02d:%02d" % (d, mo, y, h, mi)
