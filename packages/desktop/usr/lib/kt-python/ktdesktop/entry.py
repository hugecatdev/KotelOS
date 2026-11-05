# Desktop Entry (freedesktop.org): .desktop, Exec, иконки по Icon Naming и типы файлов
import os

from . import HOME, exists, isdir, join, basename, read, which, stat

# каталоги данных по XDG Base Directory: свой (~/.local/share) главнее системных
DATA_HOME = os.getenv("XDG_DATA_HOME") or HOME + "/.local/share"
DATA_DIRS = [d for d in (os.getenv("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d]
APPS = [d + "/applications" for d in reversed(DATA_DIRS)] + [DATA_HOME + "/applications"]  # позже - главнее
ICONS = [d + "/icons/hicolor" for d in [DATA_HOME] + DATA_DIRS]
PIXMAPS = [d + "/pixmaps" for d in DATA_DIRS]
SIZES = ["scalable", "48x48", "64x64", "96x96", "128x128", "256x256", "32x32", "24x24", "16x16"]
CONTEXTS = ["apps", "places", "mimetypes", "devices", "categories", "actions", "status"]
LANG = (os.getenv("LC_ALL") or os.getenv("LC_MESSAGES") or os.getenv("LANG") or "").split(".")[0]
if LANG in ("", "C", "POSIX"):
    LANG = "ru"  # интерфейс системы русский: без явного языка берём Name[ru]

# основные категории freedesktop -> заголовок в меню
CATEGORIES = [("Development", "Программирование"), ("Education", "Образование"), ("Science", "Наука"),
              ("Graphics", "Графика"), ("AudioVideo", "Мультимедиа"), ("Office", "Офис"), ("Network", "Интернет"),
              ("Game", "Игры"), ("Utility", "Стандартные"), ("Settings", "Настройки"), ("System", "Системные")]

EXT = {"py": "text/x-python", "pyw": "text/x-python", "txt": "text/plain", "md": "text/markdown",
       "sh": "text/x-shellscript", "c": "text/x-csrc", "h": "text/x-chdr", "cpp": "text/x-c++src",
       "lua": "text/x-lua", "js": "application/javascript", "json": "application/json", "html": "text/html",
       "htm": "text/html", "css": "text/css", "xml": "application/xml", "csv": "text/csv", "ini": "text/plain",
       "cfg": "text/plain", "conf": "text/plain", "log": "text/plain", "toml": "text/plain", "yaml": "text/plain",
       "yml": "text/plain", "rb": "text/x-ruby", "pl": "text/x-perl", "php": "text/x-php", "java": "text/x-java",
       "png": "image/png", "gif": "image/gif", "svg": "image/svg+xml", "jpg": "image/jpeg", "jpeg": "image/jpeg",
       "desktop": "application/x-desktop"}
TEXTISH = ("application/json", "application/javascript", "application/xml")


class Entry:
    def __init__(self, path, d):
        self.path = path
        self.id = basename(path)
        self.d = d
        self.name = d.get("Name", self.id)
        self.comment = d.get("Comment", "")
        self.icon = d.get("Icon", "")
        self.exec = d.get("Exec", "")
        self.terminal = d.get("Terminal", "").lower() == "true"
        self.type = d.get("Type", "Application")
        self.cats = [c for c in d.get("Categories", "").split(";") if c]
        self.mimes = [m for m in d.get("MimeType", "").split(";") if m]
        self.hidden = d.get("NoDisplay", "").lower() == "true" or d.get("Hidden", "").lower() == "true"
        self.workdir = d.get("Path", "")

    def ok(self):
        """Программа на месте: есть TryExec и первое слово Exec."""
        if self.type != "Application":
            return self.type == "Link"
        t = self.d.get("TryExec")
        if t and not which(t):
            return False
        a = argv(self.exec)
        return bool(a) and which(a[0]) is not None

    def category(self):
        for k, title in CATEGORIES:
            if k in self.cats:
                return title
        return "Прочие"


def parse(path):
    """Секция [Desktop Entry]; локализованный ключ (Name[ru]) главнее общего."""
    d, loc, sec = {}, {}, None
    for line in read(path, 65536).split("\n"):
        line = line.strip()
        if not line or line[0] == "#":
            continue
        if line[0] == "[":
            sec = line
            continue
        if sec != "[Desktop Entry]" or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), unescape(v.strip())
        if "[" in k:
            base, l = k[:-1].split("[", 1)
            if l == LANG or l == LANG.split("_")[0]:
                loc[base] = v
        else:
            d[k] = v
    if sec is None and not d:
        return None
    d.update(loc)
    return Entry(path, d)


def unescape(v):
    out, i = [], 0
    while i < len(v):
        c = v[i]
        if c == "\\" and i + 1 < len(v):
            i += 1
            c = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}.get(v[i], "\\" + v[i])
        out.append(c)
        i += 1
    return "".join(out)


def argv(cmd):
    """Exec в список слов: двойные кавычки и \\ внутри них, как в спецификации."""
    out, cur, i, quoted, has = [], [], 0, False, False
    while i < len(cmd):
        c = cmd[i]
        if quoted:
            if c == "\\" and i + 1 < len(cmd) and cmd[i + 1] in '"`$\\':
                i += 1
                cur.append(cmd[i])
            elif c == '"':
                quoted = False
            else:
                cur.append(c)
        elif c == '"':
            quoted = has = True
        elif c in " \t":
            if cur or has:
                out.append("".join(cur))
            cur, has = [], False
        else:
            cur.append(c)
        i += 1
    if cur or has:
        out.append("".join(cur))
    return out


def expand(e, files=()):
    """Слова Exec с подставленными файлами (%f %F %u %U), %c, %k; %i и прочие - убрать."""
    out, used = [], False
    for a in argv(e.exec):
        if a in ("%f", "%u"):
            if files:
                out.append(files[0])
            used = True
        elif a in ("%F", "%U"):
            out.extend(files)
            used = True
        elif a == "%i":
            if e.icon:
                out.extend(["--icon", e.icon])
        elif a == "%c":
            out.append(e.name)
        elif a == "%k":
            out.append(e.path)
        elif a in ("%d", "%D", "%n", "%N", "%v", "%m"):
            pass
        else:
            out.append(a.replace("%%", "\0").replace("%c", e.name).replace("%k", e.path).replace("\0", "%"))
    if files and not used:
        out.extend(files[:1])
    return out


def apps():
    """Программы для меню: видимые и стоящие."""
    out = [e for e in _all() if not e.hidden and e.ok()]
    out.sort(key=lambda e: e.name.lower())
    return out


def handlers(mime):
    """Программы, которые открывают этот тип; text/* без своей программы - те, что знают text/plain."""
    all_ = [e for e in _all() if e.ok()]
    exact = [e for e in all_ if mime in e.mimes]
    if (mime.startswith("text/") or mime in TEXTISH) and mime != "text/plain":
        exact += [e for e in all_ if "text/plain" in e.mimes and e not in exact]
    default = _default(mime)
    exact.sort(key=lambda e: 0 if e.id == default else 1)
    return exact


def _all():
    """Все .desktop из applications; ~/.local главнее /usr/share с тем же именем."""
    seen = {}
    for d in APPS:
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for n in names:
            if n.endswith(".desktop"):
                e = parse(join(d, n))
                if e:
                    seen[n] = e
    return list(seen.values())


def _default(mime):
    """mimeapps.list: [Default Applications] mime=program.desktop."""
    for p in (HOME + "/.config/mimeapps.list", "/usr/share/applications/mimeapps.list"):
        sec = None
        for line in read(p).split("\n"):
            line = line.strip()
            if line.startswith("["):
                sec = line
            elif sec == "[Default Applications]" and line.startswith(mime + "="):
                return line.split("=", 1)[1].split(";")[0]
    return None


def set_default(mime, app_id):
    from . import write
    p = HOME + "/.config/mimeapps.list"
    lines = [l for l in read(p).split("\n") if l.strip() and not l.startswith(mime + "=")]
    if "[Default Applications]" not in lines:
        lines.insert(0, "[Default Applications]")
    lines.insert(lines.index("[Default Applications]") + 1, mime + "=" + app_id)
    write(p, "\n".join(lines) + "\n")


def mime(path, st=None):
    st = st or stat(path)
    if st and st[0] & 0o170000 == 0o040000:
        return "inode/directory"
    n = basename(path)
    if "." in n[1:]:
        m = EXT.get(n.rsplit(".", 1)[1].lower())
        if m:
            return m
    if st and st[0] & 0o111:
        head = read(path, 2) if st[6] < 64 << 20 else ""
        return "text/x-shellscript" if head == "#!" else "application/x-executable"
    return "application/octet-stream"


def is_text(path):
    try:
        with open(path, "rb") as f:
            b = f.read(1024)
    except OSError:
        return False
    if b"\0" in b:
        return False
    try:
        b.decode("utf-8")
    except UnicodeError:
        return len(b) == 1024  # мог разрезать символ на краю
    return True


def icon_name(m):
    if m == "inode/directory":
        return "folder"
    if m == "text/x-python":
        return "text-x-python"
    if m == "text/x-shellscript":
        return "text-x-script"
    if m.startswith("image/"):
        return "image-x-generic"
    if m == "application/x-executable":
        return "application-x-executable"
    if m.startswith("text/") or m in TEXTISH:
        return "text-x-generic"
    return "application-x-generic"


_icons = {}


def icon_path(name):
    """Путь к картинке иконки: абсолютный путь как есть, иначе поиск по hicolor и pixmaps."""
    if not name:
        return None
    if name in _icons:
        return _icons[name]
    found = None
    if name.startswith("/"):
        found = name if exists(name) else None
    else:
        for root in ICONS:
            if not isdir(root):
                continue
            for size in SIZES:
                for ctx in CONTEXTS:
                    for ext in (".svg", ".png", ".gif") if size == "scalable" else (".png", ".gif"):
                        p = "%s/%s/%s/%s%s" % (root, size, ctx, name, ext)
                        if exists(p):
                            found = p
                            break
                    if found:
                        break
                if found:
                    break
            if found:
                break
        for d in PIXMAPS if not found else ():
            for ext in (".svg", ".png", ".gif"):
                if exists(d + "/" + name + ext):
                    found = d + "/" + name + ext
                    break
            if found:
                break
    _icons[name] = found
    return found
