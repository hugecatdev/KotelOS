import binascii
import json
import os
import random
import socket
import time

RUN = "/run/kt"
PAGE = ("192.168.86.1", 7771)

try:
    _ms, _diff, _sleep = time.ticks_ms, time.ticks_diff, time.sleep_ms
except AttributeError:
    def _ms():
        return int(time.monotonic() * 1000)

    def _diff(a, b):
        return a - b

    def _sleep(ms):
        time.sleep(ms / 1000)


class JSError(Exception):
    pass


def _b64(data):
    if isinstance(data, str):
        data = data.encode()
    return binascii.b2a_base64(data).decode().replace("\n", "")


def _request(verb, arg="", rid="-", body=b"", timeout=30):
    s = socket.socket()
    try:
        if timeout:
            s.settimeout(timeout)
        try:
            s.connect(socket.getaddrinfo(PAGE[0], PAGE[1])[0][-1])
        except OSError:
            raise OSError("нет связи с браузером")
        data = ("%s %s %d %s\n" % (verb, rid, len(body), arg)).encode() + body
        if hasattr(s, "sendall"):
            s.sendall(data)
        else:
            s.write(data)
        out = []
        while True:
            try:
                b = s.recv(65536)
            except OSError:
                raise OSError("браузер не ответил")
            if not b:
                return b"".join(out)
            out.append(b)
    finally:
        s.close()


def _rid():
    return str(random.getrandbits(24) + 1)


def _wait(path, timeout):
    start = _ms()
    while True:
        try:
            with open(path, "rb") as f:
                data = f.read()
            os.remove(path)
            return data
        except OSError:
            pass
        if timeout and _diff(_ms(), start) > timeout * 1000:
            raise OSError("браузер не ответил")
        _sleep(30)


def call(verb, arg="", timeout=30):
    return _request(verb, arg, _rid(), timeout=timeout)


def _upload(verb, arg, d):
    try:
        os.remove(RUN + "/upload.done")
    except OSError:
        pass
    with open(RUN + "/upload.dir", "w") as f:
        f.write(d + "\n")
    err = _request(verb, arg, _rid(), timeout=0)[1:].decode().strip()
    try:
        done = _wait(RUN + "/upload.done", 5).decode()
    except OSError:
        done = ""
    return [p for p in done.split("\n") if p], err


def _receive(verb, arg=""):
    d = "%s/in.%s.d" % (RUN, _rid())
    os.mkdir(d)
    paths, err = _upload(verb, arg, d)
    data = None
    for name in os.listdir(d):
        if data is None:
            with open(d + "/" + name, "rb") as f:
                data = f.read()
        os.remove(d + "/" + name)
    os.rmdir(d)
    if data is None and err:
        raise OSError(err)
    return data


def q(value):
    return json.dumps(value)


def js(code, *args, timeout=30):
    if args:
        code = "(%s)(%s)" % (code, ", ".join(q(a) for a in args))
    r = call("jsjson", _b64(code), timeout)
    body = r[1:].decode().strip()
    if r[:1] != b"0":
        raise JSError(body)
    return json.loads(body) if body else None


class Cfg:
    def __call__(self, key=None, value=None):
        if key is None:
            return js("kt.cfg()")
        if value is not None:
            self[key] = value
        return self[key]

    def __getitem__(self, key):
        v = js("(k) => k in kt.cfg ? [kt.cfg[k]] : null", key)
        if v is None:
            raise KeyError(key)
        return v[0]

    def __setitem__(self, key, value):
        try:
            js("(k, v) => { kt.cfg[k] = v }", key, value)
        except JSError as e:
            raise ValueError(str(e).replace("Error: ", ""))

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        js("(k) => { delete kt.cfg[k] }", key)

    def __contains__(self, key):
        return bool(js("(k) => k in kt.cfg", key))

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
    _request("dl", _b64(name), _rid(), bytes(data), timeout=120)


def up(path="."):
    if path == ".":
        path = os.getcwd()
    return _upload("upload", "", path)[0]


def copy(value):
    call("copy", _b64(value))


def paste():
    data = _receive("paste")
    return data.decode() if data else ""


def notify(message="готово"):
    try:
        f = open("/usr/lib/kt-notify.js")
    except OSError:
        raise JSError("kt.notify: нужен пакет notify (kt pkg add notify)")
    with f:
        js(f.read(), message, timeout=120)


def save(name=""):
    return call("save", _b64(name), timeout=120).decode().strip()


def info():
    out = {}
    for line in call("info").decode().split("\n"):
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
