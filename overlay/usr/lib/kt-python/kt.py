import binascii
import json
import os
import random
import socket
import time

RUN = "/run/kt"
PAGE = ("192.168.86.1", 7771)
CFG = "/usr/share/kt/cfg"
# как KT_WAIT в kt.sh: ответа ждём, пока соединение со страницей живо; машину восстановили посреди
# запроса (сменился агент) - ответ ждётся ещё столько секунд, по соединению или файлом от агента
WAIT = 30

try:
    _ms, _diff, _sleep = time.ticks_ms, time.ticks_diff, time.sleep_ms
except AttributeError:
    def _ms():
        return int(time.monotonic() * 1000)

    def _diff(a, b):
        return a - b

    def _sleep(ms):
        time.sleep(ms / 1000)


class Error(Exception):
    """Страница ответила ошибкой или отменой - как код 1 у команд kt."""


class JSError(Error):
    """Ошибка в коде JavaScript."""


def _b64(data):
    if isinstance(data, str):
        data = data.encode()
    return binascii.b2a_base64(data).decode().replace("\n", "")


def _rid():
    return str(random.getrandbits(24) + 1)


def _take(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        os.remove(path)
        return data
    except OSError:
        return None


def _until(path):
    start = _ms()
    while True:
        data = _take(path)
        if data is not None:
            return data
        if _diff(_ms(), start) > WAIT * 1000:
            raise OSError("браузер не ответил")
        _sleep(30)


def _agent():
    try:
        with open(RUN + "/agent.pid") as f:
            return f.read().strip()
    except OSError:
        return ""


def _timedout(e):
    t = getattr(socket, "timeout", None)
    return (t is not None and isinstance(e, t)) or (bool(e.args) and e.args[0] in (11, 110))


def _request(verb, arg="", body=b"", timeout=None):
    """Запрос к странице; ответ - байты, первый - статус (0 - успех). timeout - общий предел, секунд."""
    rid = _rid()
    s = socket.socket()
    try:
        try:
            s.connect(socket.getaddrinfo(PAGE[0], PAGE[1])[0][-1])
        except OSError:
            raise OSError("нет связи с браузером")
        data = ("%s %s %d %s\n" % (verb, rid, len(body), arg)).encode() + body
        if hasattr(s, "sendall"):
            s.sendall(data)
        else:
            s.write(data)
        s.settimeout(1)
        agent, start, lost, out = _agent(), _ms(), None, []
        while True:
            try:
                b = s.recv(65536)
            except OSError as e:
                if not _timedout(e):
                    raise OSError("браузер не ответил")
                b = None
            if b:
                out.append(b)
                continue
            if b is not None:
                return b"".join(out)
            if lost is None and _agent() != agent:
                lost = _ms()
            if lost is not None:
                r = _take("%s/reply.%s" % (RUN, rid))
                if r is not None:
                    return r
                if _diff(_ms(), lost) > WAIT * 1000:
                    raise OSError("браузер не ответил")
            if timeout and _diff(_ms(), start) > timeout * 1000:
                raise OSError("браузер не ответил за %d с" % timeout)
    finally:
        s.close()


def _status(r, cls=Error):
    text = r[1:].decode()
    if r[:1] == b"0":
        return text[:-1] if text.endswith("\n") else text
    text = text.strip()
    if text.startswith("Error: "):
        text = text[7:]
    raise cls(text or "браузер не ответил")


def call(verb, arg="", timeout=None):
    """Команда страницы (как kt_page в kt.sh): текст ответа, при ошибке или отмене - kt.Error."""
    return _status(_request(verb, arg, timeout=timeout))


def _upload(verb, arg, d):
    """Файлы от страницы в каталог d (upload, paste, fetch): (пути, текст ошибки или "")."""
    try:
        os.remove(RUN + "/upload.done")
    except OSError:
        pass
    with open(RUN + "/upload.dir", "w") as f:
        f.write(d + "\n")
    r = _request(verb, arg)
    done = _until(RUN + "/upload.done").decode()
    try:
        _status(r)
        err = ""
    except Error as e:
        err = str(e)
    return [p for p in done.split("\n") if p], err


def _receive(verb, arg=""):
    d = "%s/in.%s.d" % (RUN, _rid())
    os.mkdir(d)
    data = None
    try:
        paths, err = _upload(verb, arg, d)
        for name in os.listdir(d):
            with open(d + "/" + name, "rb") as f:
                data = f.read()
            break
    finally:
        for name in os.listdir(d):
            os.remove(d + "/" + name)
        os.rmdir(d)
    if err:
        raise Error(err)
    return data or b""


def q(value):
    return json.dumps(value)


def js(code, *args, timeout=None):
    """Выполнить JS на странице, результат - через JSON. Ответа ждёт, сколько нужно; timeout - предел, секунд."""
    if args:
        code = "(%s)(%s)" % (code, ", ".join(q(a) for a in args))
    body = _status(_request("jsjson", _b64(code), timeout=timeout), JSError).strip()
    return json.loads(body) if body else None


class Cfg:
    """kt.cfg: как kt cfg. Ключи страницы - её умолчания, свои ключи пакетов - умолчания из их описаний."""

    def __call__(self, key=None, value=None):
        if key is None:
            out = js("kt.cfg()")
            for k, (v, _) in self.describe().items():
                if v is not None and k not in out:
                    out[k] = v
            return out
        if value is not None:
            self[key] = value
        return self[key]

    def describe(self):
        """{ключ: (умолчание, описание)} из /usr/share/kt/cfg. У ключей страницы (файл kt) умолчание знает
        она - здесь None; у ключа пакета - «ключ=умолчание» в его описании, без него - пустая строка."""
        out = {}
        try:
            names = sorted(os.listdir(CFG))
        except OSError:
            return out
        for n in (["kt"] if "kt" in names else []) + [n for n in names if n != "kt"]:
            try:
                with open(CFG + "/" + n) as f:
                    lines = f.read().split("\n")
            except OSError:
                continue
            for line in lines:
                k, _, d = line.strip().partition(" ")
                k, eq, v = k.partition("=")
                if k and k not in out:
                    out[k] = (None if n == "kt" else v, d.strip())
        return out

    def _default(self, key):
        return self.describe().get(key, (None, ""))[0]

    def __getitem__(self, key):
        v = js("(k) => k in kt.cfg ? [kt.cfg[k]] : null", key)
        if v is not None:
            return v[0]
        d = self._default(key)
        if d is None:
            raise KeyError(key)
        return d

    def __setitem__(self, key, value):
        try:
            if self._default(key) == str(value):
                js("(k) => { delete kt.cfg[k] }", key)
            else:
                js("(k, v) => kt.cfg(k, v)", key, value)
        except JSError as e:
            raise ValueError(str(e))

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        js("(k) => { delete kt.cfg[k] }", key)

    def __contains__(self, key):
        return bool(js("(k) => k in kt.cfg", key)) or self._default(key) is not None

    def __iter__(self):
        return iter(self.keys())

    def keys(self):
        return list(self().keys())

    def values(self):
        return list(self().values())

    def items(self):
        return list(self().items())

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __repr__(self):
        return repr(self())


cfg = Cfg()


def dl(data, name=None):
    if name is None:
        name = data.split("/")[-1]
        with open(data, "rb") as f:
            data = f.read()
    if isinstance(data, str):
        data = data.encode()
    _status(_request("dl", _b64(name), bytes(data)))


def up(path="."):
    """Файлы с устройства в каталог path: пути; отмена - kt.Error."""
    if path == ".":
        path = os.getcwd()
    paths, err = _upload("upload", "", path)
    if err:
        raise Error(err)
    return paths


def copy(value):
    call("copy", _b64(value))


def paste():
    """Текст из буфера обмена; пустой буфер или отмена - kt.Error."""
    return _receive("paste").decode()


def notify(message="готово"):
    try:
        f = open("/usr/lib/kt-notify.js")
    except OSError:
        raise Error("kt.notify: нужен пакет notify (kt pkg add notify)")
    with f:
        js(f.read(), message)


def save(name=""):
    return call("save", _b64(name))


def info():
    out = {}
    for line in call("info").split("\n"):
        if ": " in line:
            k, v = line.split(": ", 1)
            out[k] = v
    return out


def emit(name, data=None):
    js("kt.emit", name, data)


_pos = None
_ino = 0
_me = None


def _pid():
    try:
        return os.getpid()
    except AttributeError:
        with open("/proc/self/stat") as f:
            return int(f.read().split()[0])


def _listen():
    global _me
    _me = _pid()
    open("%s/ev.%d" % (RUN, _me), "w").close()
    try:
        import atexit
        atexit.register(_leave)
    except ImportError:
        import sys
        if hasattr(sys, "atexit"):
            old = sys.atexit(_leave)
            if old:
                sys.atexit(lambda: (_leave(), old()))


def _leave():
    if _me != _pid():
        return
    try:
        os.remove("%s/ev.%d" % (RUN, _me))
    except OSError:
        return
    for name in os.listdir(RUN):
        if name.startswith("ev."):
            try:
                os.stat("/proc/" + name[3:])
                return
            except OSError:
                pass
    try:
        os.remove(RUN + "/events")
    except OSError:
        pass


def poll():
    global _pos, _ino
    path = RUN + "/events"
    if _pos is None:
        _listen()
    try:
        st = os.stat(path)
        ino, size = st[1], st[6]
    except OSError:
        ino = size = 0
    if _pos is None:
        _pos, _ino = size, ino
    elif ino != _ino or _pos > size:
        _pos, _ino = 0, ino
    if size == _pos:
        return []
    with open(path, "rb") as f:
        f.seek(_pos)
        data = f.read()
    end = data.rfind(b"\n") + 1
    _pos += end
    return [json.loads(line) for line in data[:end].split(b"\n") if line]


def events(*names, timeout=None):
    poll()
    start = _ms()
    while True:
        evs = poll()
        for ev in evs:
            if not names or ev["name"] in names:
                yield ev
        if not evs:
            if timeout is not None and _diff(_ms(), start) > timeout * 1000:
                return
            _sleep(30)


def wait(name=None, timeout=None):
    for ev in events(*([name] if name else []), timeout=timeout):
        return ev["data"]


_handlers = {}
_running = False


def on(name, fn=None):
    if fn is None:
        return lambda f: on(name, f)
    _handlers.setdefault(name, []).append(fn)
    return fn


def off(name, fn=None):
    if fn is None:
        _handlers.pop(name, None)
    elif fn in _handlers.get(name, []):
        _handlers[name].remove(fn)


def stop():
    global _running
    _running = False


def run():
    global _running
    _running = True
    for ev in events():
        for fn in list(_handlers.get(ev["name"], [])):
            fn(ev["data"])
        if not _running:
            return
