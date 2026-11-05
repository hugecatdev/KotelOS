import binascii
import json as _json
import random
import sys

import kt

__version__ = "2.32.0-kt"

_warned = set()


def _warn(what):
    if what not in _warned:
        _warned.add(what)
        sys.stderr.write("requests: %s - нет в kt-версии, игнорирую\n" % what)


class RequestException(Exception):
    def __init__(self, *args, response=None):
        super().__init__(*args)
        self.response = response


class ConnectionError(RequestException):
    pass


class HTTPError(RequestException):
    pass


class Timeout(RequestException):
    pass


class exceptions:
    RequestException = RequestException
    ConnectionError = ConnectionError
    HTTPError = HTTPError
    Timeout = Timeout


class adapters:
    class HTTPAdapter:
        def __init__(self, *args, **kwargs):
            pass


try:
    sys.modules[__name__ + ".exceptions"] = exceptions
    sys.modules[__name__ + ".adapters"] = adapters
except (AttributeError, TypeError):
    pass


class CaseInsensitiveDict:
    def __init__(self, data=None):
        self._d = {}
        if data:
            self.update(data)

    def __setitem__(self, key, value):
        self._d[key.lower()] = (key, value)

    def __getitem__(self, key):
        return self._d[key.lower()][1]

    def __delitem__(self, key):
        del self._d[key.lower()]

    def __contains__(self, key):
        return key.lower() in self._d

    def __iter__(self):
        return iter([k for k, v in self._d.values()])

    def __len__(self):
        return len(self._d)

    def get(self, key, default=None):
        return self[key] if key in self else default

    def keys(self):
        return list(self)

    def items(self):
        return list(self._d.values())

    def update(self, other):
        for k in other:
            self[k] = other[k]

    def copy(self):
        return CaseInsensitiveDict(self)

    def __repr__(self):
        return repr(dict(self.items()))


class Response:
    def __init__(self, r):
        self.status_code = r["status"]
        self.reason = r["reason"]
        self.url = r["url"]
        self.headers = CaseInsensitiveDict(r["headers"])
        self.content = binascii.a2b_base64(r["body"])
        self.encoding = "utf-8"
        self.history = []
        self.cookies = {}

    @property
    def ok(self):
        return self.status_code < 400

    @property
    def text(self):
        return self.content.decode(self.encoding or "utf-8")

    def json(self, **kwargs):
        return _json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            kind = "Client" if self.status_code < 500 else "Server"
            raise HTTPError("%d %s Error: %s for url: %s" % (self.status_code, kind, self.reason, self.url), response=self)

    def iter_content(self, chunk_size=1, decode_unicode=False):
        data = self.text if decode_unicode else self.content
        step = chunk_size or len(data) or 1
        for i in range(0, len(data), step):
            yield data[i:i + step]

    def iter_lines(self, chunk_size=512, decode_unicode=False, delimiter=None):
        for line in self.content.split(b"\n"):
            line = line.rstrip(b"\r")
            yield line.decode() if decode_unicode else line

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return "<Response [%d]>" % self.status_code


_SAFE = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~")


def _quote(s):
    if not isinstance(s, (str, bytes)):
        s = str(s)
    if isinstance(s, str):
        s = s.encode()
    return "".join(chr(b) if b in _SAFE else "%%%02X" % b for b in s)


def _encode(data):
    if isinstance(data, (str, bytes)):
        return data
    pairs = data.items() if hasattr(data, "items") else data
    out = []
    for k, v in pairs:
        for x in (v if isinstance(v, (list, tuple)) else [v]):
            if x is not None:
                out.append(_quote(k) + "=" + _quote(x))
    return "&".join(out)


def _bytes(v):
    if hasattr(v, "read"):
        v = v.read()
    if isinstance(v, str):
        v = v.encode()
    return v if isinstance(v, bytes) else str(v).encode()


def _multipart(data, files):
    boundary = "kt%016x" % random.getrandbits(64)
    out = []

    def part(name, value, filename=None, ctype=None):
        head = 'Content-Disposition: form-data; name="%s"' % name
        if filename is not None:
            head += '; filename="%s"' % filename.replace('"', "%22")
            head += "\r\nContent-Type: " + (ctype or "application/octet-stream")
        out.append(b"--" + boundary.encode() + b"\r\n" + head.encode() + b"\r\n\r\n" + _bytes(value) + b"\r\n")

    pairs = data.items() if hasattr(data, "items") else (data or [])
    for k, v in pairs:
        for x in (v if isinstance(v, (list, tuple)) else [v]):
            if x is not None:
                part(k, x)
    for k, v in (files.items() if hasattr(files, "items") else files):
        if isinstance(v, (tuple, list)):
            part(k, v[1], v[0] or k, v[2] if len(v) > 2 else None)
        else:
            part(k, v, getattr(v, "name", k).split("/")[-1] if isinstance(getattr(v, "name", None), str) else k)
    out.append(b"--" + boundary.encode() + b"--\r\n")
    return b"".join(out), "multipart/form-data; boundary=" + boundary


_FETCH = """async (url, o) => {
  if (o.body != null) o.body = Uint8Array.from(atob(o.body), (c) => c.charCodeAt(0));
  const r = await fetch(url, o);
  const b = new Uint8Array(await r.arrayBuffer());
  let s = "";
  for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode.apply(null, b.subarray(i, i + 32768));
  return { status: r.status, reason: r.statusText, url: r.url, headers: Object.fromEntries(r.headers), body: btoa(s) };
}"""


def request(method, url, params=None, data=None, headers=None, cookies=None, files=None, auth=None,
            timeout=None, allow_redirects=True, proxies=None, hooks=None, stream=None, verify=None,
            cert=None, json=None):
    for name, bad in (("proxies", proxies), ("verify=False", verify is False), ("cert", cert),
                      ("stream", stream), ("cookies", cookies),
                      ("allow_redirects=False", not allow_redirects), ("hooks", hooks)):
        if bad:
            _warn(name)
    h = CaseInsensitiveDict(headers or {})
    if params:
        url += ("&" if "?" in url else "?") + _encode(params)
    body = None
    if files:
        body, h["Content-Type"] = _multipart(data, files)
    elif json is not None:
        body = _json.dumps(json)
        if "Content-Type" not in h:
            h["Content-Type"] = "application/json"
    elif data is not None:
        if hasattr(data, "read"):
            body = data.read()
        elif isinstance(data, (str, bytes)):
            body = data
        else:
            body = _encode(data)
            if "Content-Type" not in h:
                h["Content-Type"] = "application/x-www-form-urlencoded"
    if auth:
        if isinstance(auth, (tuple, list)):
            h["Authorization"] = "Basic " + kt._b64("%s:%s" % (auth[0], auth[1]))
        else:
            _warn("auth=" + type(auth).__name__)
    if isinstance(timeout, (tuple, list)):
        timeout = sum(t for t in timeout if t)
    try:
        o = {"method": method.upper(), "headers": dict(h.items())}
        if body is not None:
            o["body"] = kt._b64(body)
        r = kt.js(_FETCH, url, o, timeout=timeout or 60)
    except kt.JSError as e:
        raise ConnectionError("%s (сайт без CORS или нет сети)" % str(e).replace("TypeError: ", ""))
    except OSError as e:
        raise Timeout(str(e))
    return Response(r)


def get(url, params=None, **kwargs):
    return request("GET", url, params=params, **kwargs)


def options(url, **kwargs):
    return request("OPTIONS", url, **kwargs)


def head(url, **kwargs):
    return request("HEAD", url, **kwargs)


def post(url, data=None, json=None, **kwargs):
    return request("POST", url, data=data, json=json, **kwargs)


def put(url, data=None, **kwargs):
    return request("PUT", url, data=data, **kwargs)


def patch(url, data=None, **kwargs):
    return request("PATCH", url, data=data, **kwargs)


def delete(url, **kwargs):
    return request("DELETE", url, **kwargs)


class Session:
    def __init__(self):
        self.headers = CaseInsensitiveDict()
        self.params = {}
        self.auth = None
        self.cookies = {}
        self.proxies = {}
        self.verify = True

    def request(self, method, url, **kwargs):
        h = self.headers.copy()
        h.update(kwargs.get("headers") or {})
        kwargs["headers"] = h
        if self.auth and not kwargs.get("auth"):
            kwargs["auth"] = self.auth
        if self.params and not kwargs.get("params"):
            kwargs["params"] = self.params
        if self.cookies:
            _warn("Session.cookies")
        return request(method, url, **kwargs)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def options(self, url, **kwargs):
        return self.request("OPTIONS", url, **kwargs)

    def head(self, url, **kwargs):
        return self.request("HEAD", url, **kwargs)

    def post(self, url, data=None, json=None, **kwargs):
        return self.request("POST", url, data=data, json=json, **kwargs)

    def put(self, url, data=None, **kwargs):
        return self.request("PUT", url, data=data, **kwargs)

    def patch(self, url, data=None, **kwargs):
        return self.request("PATCH", url, data=data, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def mount(self, prefix, adapter):
        _warn("Session.mount")

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def session():
    return Session()


class sessions:
    Session = Session
    session = session


try:
    sys.modules[__name__ + ".sessions"] = sessions
except (AttributeError, TypeError):
    pass


def __getattr__(name):
    if not name.startswith("__"):
        _warn("requests." + name)
    raise AttributeError(name)
