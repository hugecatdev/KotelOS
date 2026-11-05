import sys as _sys
import time as _time
import random as _random
import kt as _kt
from tkinter.constants import *

TkVersion = 8.6
TclVersion = 8.6
READABLE = 2
WRITABLE = 4
EXCEPTION = 8
wantobjects = 1
_support_default_root = True
_JS = "/usr/lib/kt-tk.js"

try:
    _ms, _diff, _add, _nap = _time.ticks_ms, _time.ticks_diff, _time.ticks_add, _time.sleep_ms
except AttributeError:
    def _add(a, b):
        return a + b

    def _ms():
        return int(_time.monotonic() * 1000)

    def _diff(a, b):
        return a - b

    def _nap(ms):
        _time.sleep(ms / 1000)


class TclError(Exception):
    pass


def _stub(what, ret=None):
    def stub(*args, **kw):
        _warn(what)
        return ret
    return stub


def _noop(ret=None):
    def noop(*args, **kw):
        return ret
    return noop


_sid = "%06x" % _random.getrandbits(24)
_ops = []
_dirty = []
_tdirty = []
_widgets = []
_ids = {}
_cmds = {}
_count = [0]
_live = [False]
_timers = []
_warned = set()
_rgbs = {}
_iq = {}
_zq = {}
_guard = [0]
_sent = [0]
_sig = [None]
_FRAME = 30
_RUN = 100
_ack = [None]
_slow = [False]
_hot = [_add(_ms(), -1000)]
_roots = []
_quit = [False]
_dialogs = {}
_answers = {}
_all_b = {}
_class_b = {}
_funcs = {}
_parsed = {}
_varnames = {}
_tclvars = {"tk_patchLevel": "8.6.13", "tk_version": "8.6", "tcl_version": "8.6", "tcl_patchLevel": "8.6.13",
            "tcl_platform(os)": "Linux", "tcl_platform(platform)": "unix"}
_vevents = {"<<Cut>>": ["<Control-Key-x>", "<Key-F20>", "<Shift-Key-Delete>"],
            "<<Copy>>": ["<Control-Key-c>", "<Key-F16>", "<Control-Key-Insert>"],
            "<<Paste>>": ["<Control-Key-v>", "<Key-F18>", "<Shift-Key-Insert>"],
            "<<PasteSelection>>": ["<ButtonRelease-2>"],
            "<<SelectAll>>": ["<Control-Key-slash>"],
            "<<SelectNone>>": ["<Control-Key-backslash>"]}
_kinds_dirty = [True]
_images = {}
_pending = []
_clip = [""]
_screen = []
_default_root = None

_ALIAS = {"background": "bg", "foreground": "fg", "borderwidth": "bd", "border": "bd", "from_": "from",
          "resolution": "res", "maximum": "max", "vcmd": "validatecommand", "invcmd": "invalidcommand",
          "increment": "res"}
_CSS = {"text", "bg", "fg", "font", "width", "height", "relief", "bd", "padx", "pady", "anchor", "justify",
        "wraplength", "cursor", "wrap", "orient", "length", "label", "showvalue", "padding", "selectmode",
        "compound"}
_QUIET = {"highlightthickness", "highlightbackground", "highlightcolor", "activebackground", "activeforeground",
          "selectcolor", "exportselection", "insertbackground", "insertwidth", "selectbackground",
          "selectforeground", "selectborderwidth", "disabledforeground", "disabledbackground",
          "readonlybackground", "overrelief", "takefocus", "class_", "name", "style", "default", "underline",
          "indicatoron", "offrelief", "troughcolor", "sliderlength", "sliderrelief", "bigincrement",
          "digits", "tickinterval", "repeatdelay", "repeatinterval", "jump", "elementborderwidth", "tearoff",
          "postcommand", "spacing1", "spacing2", "spacing3", "tabs", "undo", "autoseparators", "maxundo",
          "insertofftime", "insertontime", "insertborderwidth", "blockcursor", "setgrid", "xscrollcommand",
          "yscrollcommand", "scrollregion", "confine", "closeenough", "xscrollincrement", "yscrollincrement",
          "aspect", "colormap", "container", "visual", "screen", "use", "inactiveselectbackground",
          "buttonbackground", "buttoncursor", "buttondownrelief", "buttonuprelief", "format", "activestyle",
          "labelanchor", "invalidcommand", "tristatevalue", "activerelief", "command", "hidemargin",
          "columnbreak", "selectimage", "tristateimage", "titlecolumns", "endline", "startline",
          "inactiveselectforeground", "wrapmode", "insertunfocussed", "tabstyle", "menu", "type", "relheight"}
_JSK = {"down", "up", "dbl", "move", "drag", "key", "keyup", "enter", "leave", "wheel", "fin", "fout", "conf"}
_MODS = {"Shift": 1, "Lock": 2, "Control": 4, "Alt": 8, "Mod1": 8, "M1": 8, "Option": 8, "Mod2": 16,
         "Meta": 32, "M": 32, "Mod4": 64, "Command": 4, "B1": 256, "Button1": 256, "B2": 512, "Button2": 512,
         "B3": 1024, "Button3": 1024, "Any": 0}
_TYPES = {"Button": "down", "ButtonPress": "down", "ButtonRelease": "up", "Motion": "move", "Key": "key",
          "KeyPress": "key", "KeyRelease": "keyup", "Enter": "enter", "Leave": "leave", "MouseWheel": "wheel",
          "FocusIn": "fin", "FocusOut": "fout", "Configure": "conf", "Destroy": "destroy", "Map": "map",
          "Unmap": "unmap", "Visibility": "vis", "Expose": "expose", "Activate": "act", "Deactivate": "deact",
          "Property": "prop", "Circulate": "circ", "Colormap": "cmap", "Gravity": "grav", "Reparent": "repar"}
_ETYPE = {"down": "ButtonPress", "up": "ButtonRelease", "dbl": "ButtonPress", "move": "Motion", "key": "KeyPress",
          "keyup": "KeyRelease", "enter": "Enter", "leave": "Leave", "wheel": "MouseWheel", "fin": "FocusIn",
          "fout": "FocusOut", "conf": "Configure"}
_SYM = {"minus": "-", "plus": "+", "comma": ",", "period": ".", "slash": "/", "backslash": "\\", "equal": "=",
        "colon": ":", "semicolon": ";", "less": "<", "greater": ">", "question": "?", "exclam": "!", "at": "@",
        "numbersign": "#", "dollar": "$", "percent": "%", "asterisk": "*", "parenleft": "(", "parenright": ")",
        "bracketleft": "[", "bracketright": "]", "braceleft": "{", "braceright": "}", "underscore": "_",
        "quotedbl": '"', "apostrophe": "'", "quoteright": "'", "grave": "`", "quoteleft": "`",
        "asciitilde": "~", "bar": "|", "ampersand": "&", "asciicircum": "^", "space": " "}
_REVSYM = {}
for _k in _SYM:
    if _SYM[_k] not in _REVSYM:
        _REVSYM[_SYM[_k]] = _k


def _warn(what):
    if what not in _warned:
        _warned.add(what)
        print("tkinter: %s не поддерживается" % what, file=_sys.stderr)


def _report(e):
    print("Exception in Tkinter callback", file=_sys.stderr)
    if hasattr(_sys, "print_exception"):
        _sys.print_exception(e)
    else:
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)


def _call(fn, *args):
    try:
        return fn(*args)
    except Exception as e:
        _report(e)


def _merge(cnf, kw):
    d = dict(cnf)
    d.update(kw)
    return d


def _cnfmerge(cnfs):
    if isinstance(cnfs, dict):
        return cnfs
    d = {}
    for c in cnfs or ():
        if c:
            d.update(c)
    return d


def _flatten(seq):
    out = []
    for x in seq:
        if isinstance(x, (tuple, list)):
            out.extend(_flatten(x))
        elif x is not None:
            out.append(x)
    return tuple(out)


def _join(value):
    return " ".join(str(x) for x in value)


def _stringify(value):
    if isinstance(value, (tuple, list)):
        return _join(value)
    return str(value)


def _splitdict(tk, v, cut_minus=True, conv=None):
    items = list(v) if isinstance(v, (tuple, list)) else _tclsplit(str(v))
    d = {}
    for i in range(0, len(items) - 1, 2):
        k = str(items[i])
        if cut_minus and k.startswith("-"):
            k = k[1:]
        d[k] = conv(items[i + 1]) if conv else items[i + 1]
    return d


def _ts(v):
    if v is True:
        return "1"
    if v is False:
        return "0"
    return str(v)


def _px(v):
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    if not s:
        return 0
    k = {"c": 37.8, "m": 3.78, "i": 96, "p": 4 / 3}.get(s[-1])
    try:
        return round(float(s[:-1]) * k, 1) if k else float(s)
    except ValueError:
        raise TclError('bad screen distance "%s"' % s)


def _pad(v):
    if isinstance(v, (tuple, list)):
        return [_px(x) for x in v[:2]]
    if isinstance(v, str) and " " in v.strip():
        return [_px(x) for x in v.split()[:2]]
    return _px(v)


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return int(float(v))


def _font(v):
    if hasattr(v, "_spec"):
        return v._spec()
    if isinstance(v, (tuple, list)):
        out = []
        for x in v:
            out.append(" ".join(str(y) for y in x) if isinstance(x, (tuple, list)) else str(x))
        return out
    return str(v)


def _fontpx(v):
    f = _font(v) if v else []
    a = f if isinstance(f, list) else _tclsplit(f)
    size = 10
    if len(a) > 1:
        try:
            size = float(a[1])
        except ValueError:
            pass
    return -size if size < 0 else (size * 4 / 3 if size else 13)


def _flat(a):
    out = []
    for x in a:
        if isinstance(x, (tuple, list)):
            out.extend(_flat(x))
        else:
            out.append(x if isinstance(x, (int, float)) else float(x))
    return out


def _aslist(v):
    if isinstance(v, (tuple, list)):
        return list(v)
    if v is None or v == "":
        return []
    return _tclsplit(str(v))


def _tclsplit(s):
    out = []
    i, n = 0, len(s)
    while i < n:
        while i < n and s[i] in " \t\n":
            i += 1
        if i >= n:
            break
        if s[i] == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if s[j] == "{":
                    depth += 1
                elif s[j] == "}":
                    depth -= 1
                j += 1
            out.append(s[i + 1:j - 1])
            i = j
        elif s[i] == '"':
            j = s.find('"', i + 1)
            j = n if j < 0 else j
            out.append(s[i + 1:j])
            i = j + 1
        else:
            j = i
            while j < n and s[j] not in " \t\n":
                j += 1
            out.append(s[i:j])
            i = j
    return out


def _norm(w, k, v):
    if k in ("width", "height"):
        return _int(v) if w._chars else _px(v)
    if k in ("padx", "pady", "bd", "wraplength", "length"):
        return _px(v)
    if k == "font":
        return _font(v)
    if k == "padding":
        return [_px(x) for x in v] if isinstance(v, (tuple, list)) else _px(v)
    if k in ("text", "label"):
        return str(v)
    if k in ("bg", "fg", "relief", "anchor", "justify", "cursor", "wrap", "orient", "selectmode", "compound"):
        return str(v)
    return v


def _op(*a):
    _guard[0] += 1
    try:
        p = _ops[-1] if _ops else None
        if a[0] == "c" and p and p[0] == "c" and p[1] == a[1]:
            p[2].update(a[2])
        elif a[0] == "i":
            p = _iq.get((a[1], a[2]))
            if p is None:
                p = _iq[(a[1], a[2])] = list(a)
                _ops.append(p)
                return
            if a[4] is not None:
                p[4] = a[4]
            if a[5]:
                p[5] = dict(p[5] or {})
                p[5].update(a[5])
        else:
            a = list(a)
            if a[0] == "x":
                for k in [k for k in _iq if k[0] == a[1] and (a[2] is None or k[1] in a[2])]:
                    del _iq[k]
            elif a[0] == "z":
                p = _zq.get((a[1], a[2]))
                if p is not None:
                    p[0] = ""
                _zq[(a[1], a[2])] = a
            _ops.append(a)
    finally:
        _guard[0] -= 1


def _take():
    ops = [o for o in _ops if o[0]]
    _ops.clear()
    _iq.clear()
    _zq.clear()
    return ops


def _alarm(*a):
    if _guard[0]:
        _sig[0].setitimer(_sig[0].ITIMER_REAL, 0.01)
    elif _ops:
        _send(_take())


def _defer():
    left = _FRAME - _diff(_ms(), _sent[0])
    if left <= 0 or not _ops or _dirty or _tdirty or _kinds_dirty[0]:
        return False
    if _sig[0] is None:
        try:
            import signal
            _sig[0] = signal if signal.getsignal(signal.SIGALRM) == signal.SIG_DFL else False
            if _sig[0]:
                signal.signal(signal.SIGALRM, _alarm)
        except (ImportError, AttributeError, ValueError, OSError):
            _sig[0] = False
    g = _sig[0]
    try:
        if not g or g.getsignal(g.SIGALRM) is not _alarm:
            return False
        g.setitimer(g.ITIMER_REAL, left / 1000)
    except (ValueError, OSError):
        return False
    return True


def _dirty_add(w):
    if w is not None and w not in _dirty:
        _dirty.append(w)


def _flush():
    _guard[0] += 1
    try:
        if _kinds_dirty[0]:
            _kinds_dirty[0] = False
            for w in _widgets:
                w._rekind()
        if _dirty:
            for w in _dirty:
                if w._alive:
                    _op("L", w._id, w._lay())
            _dirty.clear()
        if _tdirty:
            for w in _tdirty[:]:
                if w._alive:
                    _ops.extend(w._out())
            _tdirty.clear()
        if _ops or _ack[0] is not None:
            _send(_take())
    finally:
        _guard[0] -= 1


def _send(ops):
    _sent[0] = _ms()
    m = {"s": _sid, "o": ops, "a": _ack[0] or 0}
    _ack[0] = None
    if _slow[0]:
        m["l"] = 1
    try:
        if _live[0]:
            if _kt.js("(m) => window.ktTk ? ktTk(m) : 0", m):
                return
            m = {"s": _sid, "o": _state()}
        with open(_JS) as f:
            src = f.read()
        _kt.js(src, m)
        _live[0] = True
    except _kt.JSError as e:
        print("tkinter: %s" % e, file=_sys.stderr)
    except OSError as e:
        raise TclError(str(e))


def _state():
    out = []
    for w in _widgets:
        if w._kind == "Text":
            w._snap()
        out.append(["w", w._id, w._kind, w.master._id if w.master is not None else None, w._p])
    for w in _widgets:
        if w._box:
            out.append(["L", w._id, w._lay()])
        if w._kind == "Canvas":
            for i in w._order:
                t, xy, o = w._items[i]
                out.append(["i", w._id, i, t, xy, o])
            for i in (0, 1):
                if w._vf[i] is not None:
                    out.append(["cs", w._id, "xy"[i], "moveto", w._vf[i]])
    for d in _dialogs.values():
        out.append(d)
    return [["img", n, _images[n]._url, _images[n]._wh[0], _images[n]._wh[1]] for n in _images] + out


def _bye():
    if _live[0]:
        try:
            _kt.js("(s) => window.ktTk ? ktTk({s, o: [['q']]}) : 0", _sid)
        except Exception:
            pass


def _parse(seq):
    p = _parsed.get(seq)
    if p is None:
        p = _parsed[seq] = _parse1(seq) or ()
    return p or None


def _parse1(seq):
    if seq.startswith("<<"):
        return ("virt", seq, 0, 1)
    if not seq.startswith("<"):
        return ("key", seq, 0, 1) if len(seq) == 1 else None
    kind, det, mods, n = None, None, 0, 1
    for part in seq[1:-1].split("-"):
        if part in _MODS:
            mods |= _MODS[part]
        elif part == "Double":
            n = 2
        elif part == "Triple":
            n = 3
        elif part in _TYPES and kind is None:
            kind = _TYPES[part]
        elif part in ("1", "2", "3", "4", "5") and kind in (None, "down", "up"):
            kind = kind or "down"
            det = int(part)
        elif part:
            det = part
            kind = kind or "key"
    if kind is None:
        return None
    if kind in ("down", "up") and det in (4, 5):
        return ("wheel", None, mods, 1)
    if kind == "down" and n > 1:
        kind = "dbl"
    if kind == "move" and mods & 0x700:
        kind = "drag"
    return (kind, det, mods, n)


def _score(p, kind, d):
    k, det, mods, n = p
    if k == "drag":
        if kind != "move":
            return -1
    elif k != kind:
        return -1
    if mods & _state_of(d) != mods:
        return -1
    s = 0
    if det is not None:
        if kind in ("down", "up", "dbl"):
            if det != d.get("n"):
                return -1
        elif det != d.get("k") and _SYM.get(det, det) != d.get("ch"):
            return -1
        s = 16
    while mods:
        s += mods & 1
        mods >>= 1
    return s


def _state_of(d):
    b = d.get("b", 0)
    return d.get("m", 0) | (256 if b & 1 else 0) | (512 if b & 4 else 0) | (1024 if b & 2 else 0)


def _kinds_of(seq):
    p = _parse(seq)
    if not p:
        return ()
    if p[0] == "virt":
        out = []
        for s in _vevents.get(seq, ()):
            out.extend(_kinds_of(s))
        return out
    return (p[0],) if p[0] in _JSK else ()


class _EType(str):
    def __repr__(self):
        return "<EventType.%s: %r>" % (self.name, self.value)


class EventType:
    pass


for _i, _n in enumerate("KeyPress KeyRelease ButtonPress ButtonRelease Motion Enter Leave FocusIn FocusOut Keymap Expose "
                        "GraphicsExpose NoExpose Visibility Create Destroy Unmap Map MapRequest Reparent Configure "
                        "ConfigureRequest Gravity ResizeRequest Circulate CirculateRequest Property SelectionClear "
                        "SelectionRequest Selection Colormap ClientMessage Mapping VirtualEvent Activate Deactivate "
                        "MouseWheel".split()):
    _t = _EType(str(_i + 2))
    _t.name = _n
    _t.value = str(_i + 2)
    setattr(EventType, _n, _t)
EventType.Key = EventType.KeyPress
EventType.Button = EventType.ButtonPress


class Event:
    def __init__(self):
        self.widget = None
        self.x = self.y = self.x_root = self.y_root = 0
        self.char = ""
        self.keysym = "??"
        self.keysym_num = 0
        self.keycode = 0
        self.num = "??"
        self.delta = 0
        self.state = 0
        self.type = ""
        self.width = self.height = 0
        self.time = 0
        self.serial = 0
        self.send_event = False

    def __repr__(self):
        return "<%s event x=%s y=%s>" % (getattr(self.type, "name", self.type), self.x, self.y)


def _keyd(d):
    k = d.get("k")
    if k is None:
        return d
    c = d.get("c", "")
    d["ch"] = c
    if len(k) == 1:
        d["k"] = _REVSYM.get(k, k)
    m = d.get("m", 0)
    if m & 4 and len(c) == 1 and ("a" <= c.lower() <= "z" or c in "[\\]^_"):
        d["c"] = chr(ord(c.upper()) & 31)
    return d


def _event(w, d):
    e = Event()
    e.widget = w
    t = _ETYPE.get(d.get("t"), d.get("type", ""))
    e.type = getattr(EventType, t, t) if t else t
    e.x, e.y = d.get("x", 0), d.get("y", 0)
    e.x_root, e.y_root = d.get("X", e.x), d.get("Y", e.y)
    if "n" in d:
        e.num = d["n"]
    if "k" in d:
        e.keysym = d["k"]
        e.char = d.get("c", "")
        e.keycode = d.get("kc", 0)
        e.keysym_num = ord(e.char) if len(e.char) == 1 else 0
    e.state = _state_of(d)
    e.delta = d.get("d", 0)
    e.width, e.height = d.get("w", 0), d.get("h", 0)
    e.time = _ms()
    return e


def _tagmap(tag):
    if tag == "all":
        return _all_b
    w = _ids.get(tag)
    if w is not None:
        return w._b
    return _class_b.get(tag)


def _best(b, kind, d):
    best, bs, vbest, vbs = None, -1, None, -1
    for seq in b:
        if seq[:2] == "<<":
            for ps in _vevents.get(seq, ()):
                p = _parse(ps)
                if p:
                    s = _score(p, kind, d)
                    if s > vbs:
                        vbest, vbs = b[seq], s
        else:
            p = _parse(seq)
            if p:
                s = _score(p, kind, d)
                if s > bs:
                    best, bs = b[seq], s
    if best is not None and bs >= vbs:
        return best
    return vbest if vbest is not None else best


def _run(fns, e):
    for fn in fns[:]:
        if _call(fn, e) == "break":
            return "break"
    return None


def _dispatch(w, d):
    kind = d.get("t")
    if kind == "conf":
        w._size = (d.get("w", 0), d.get("h", 0))
    e = _event(w, d)
    if w._kind == "Canvas" and "sx" in d:
        w._sxy = (d["sx"], d["sy"])
    if w._kind == "Canvas" and w._item_ev(d, kind, e) == "break":
        return "break"
    if w._kind == "Text" and w._tb and w._tag_ev(d, kind, e) == "break":
        return "break"
    for tag in w.bindtags():
        b = _tagmap(tag)
        if b:
            fns = _best(b, kind, d)
            if fns and _run(fns, e) == "break":
                return "break"
    return None


def _virtual(w, seq, kw=None):
    e = Event()
    e.widget = w
    e.type = EventType.VirtualEvent
    if kw:
        e.x, e.y = kw.get("x", 0), kw.get("y", 0)
    for tag in w.bindtags():
        b = _tagmap(tag)
        if b and seq in b and _run(b[seq], e) == "break":
            return "break"
    return None


def _textev(w, d):
    t = d.get("t")
    w._jsel(d)
    if t in ("down", "up", "dbl", "move") and "x" in d:
        try:
            w._marks["current"][0] = w._at(d["x"], d["y"])
        except Exception:
            pass
    if t == "view":
        w._setview(d)
        return
    if t == "tsel":
        return
    if t == "paste":
        _clip[0] = d.get("s", "")
        _dispatch(w, _keyd({"t": "key", "k": "v", "c": "v", "m": 4}))
        return
    if t == "text":
        for ch in d.get("s", ""):
            _dispatch(w, _keyd({"t": "key", "k": ch, "c": ch, "m": 0}))
        return
    _dispatch(w, d)


def _moves(es, i, wid):
    if i >= len(es):
        return False
    it = es[i]
    return it[0] == wid and it[1] == "ev" and it[2].get("t") == "move"


def _handle(ev):
    name = ev.get("name")
    d = ev.get("data")
    if name == "restore":
        del _screen[:]  # машину могли восстановить в другом браузере: размер экрана - заново
        if _live[0]:
            _take()
            _dirty.clear()
            _tdirty.clear()
            _live[0] = False
            _send(_state())
    if name != "tk":
        # остальные события страницы - обработчикам kt.on, пока идёт mainloop
        for fn in list(getattr(_kt, "_handlers", {}).get(name, ())):
            _call(fn, d)
        return
    if not isinstance(d, dict) or d.get("s") != _sid:
        return
    if "n" in d:
        _ack[0] = d["n"]
    t0 = _hot[0] = _ms()
    v = d.get("v") or {}
    for k in v:
        w = _ids.get(k)
        if w is not None and w._alive:
            w._js(v[k])
    es = d.get("e") or []
    for i, it in enumerate(es):
        wid, kind = it[0], it[1]
        x = it[2] if len(it) > 2 else None
        if kind == "dlg":
            _answers[wid] = x
            continue
        w = _ids.get(wid)
        if w is None or not w._alive:
            continue
        if kind == "cmd":
            w._cmd(x)
        elif kind == "ev":
            move = x.get("t") == "move"
            if move and _moves(es, i + 1, wid) and (w._lag or _diff(_ms(), t0) > _RUN):
                continue
            _keyd(x)
            t = _ms()
            if w._kind == "Text":
                _textev(w, x)
            else:
                _dispatch(w, x)
            if move:
                w._lag = _slow[0] = _diff(_ms(), t) > _FRAME // 2
        elif kind == "close":
            w._close()
        elif kind == "wm":
            w._wmreq(x)
        elif kind == "sel":
            w._selev(x)
        _pending_run()


def _pending_run():
    while _pending:
        w, seq = _pending.pop(0)
        if w._alive:
            _virtual(w, seq)


def _timers_run():
    if not _timers:
        return False
    now = _ms()
    due = [t for t in _timers if _diff(t[0], now) <= 0]
    due.sort(key=lambda t: _diff(t[0], now))
    for t in due:
        if t in _timers:
            _timers.remove(t)
            _call(t[2], *t[3])
    _pending_run()
    return bool(due)


def _step(lazy=False):
    busy = False
    for ev in _kt.poll():
        _handle(ev)
        busy = True
    if _timers_run():
        busy = True
    if not (lazy and _defer()):
        _flush()
    return busy


def _idle():
    now = _ms()
    n = 5 if 0 <= _diff(now, _hot[0]) < 200 else 25
    for t in _timers:
        n = min(n, max(0, _diff(t[0], now)))
    return n


def _loop(done):
    while not done():
        if not _step():
            _nap(_idle())


def _app():
    a = _sys.argv[0] if _sys.argv and _sys.argv[0] else ""
    a = a.split("/")[-1]
    for ext in (".pyc", ".py"):
        if a.endswith(ext):
            a = a[:-len(ext)]
    return a or "tk"


def _root():
    if _default_root is None or not _default_root._alive:
        Tk()
    return _default_root


def _get_temp_root():
    return _root()


_destroy_temp_root = _noop()


def _dialog(title, msg, btns, inp=None, show=None, default=None):
    _count[0] += 1
    did = "%s.d%d" % (_sid, _count[0])
    keys = [b[0] for b in btns]
    op = ["m", did, {"title": str(title or ""), "msg": str(msg or ""), "btns": btns, "inp": inp,
                     "show": 1 if show else 0, "def": keys.index(default) if default in keys else 0}]
    _dialogs[did] = op
    _ops.append(op)
    try:
        _loop(lambda: did in _answers)
    finally:
        _dialogs.pop(did, None)
    return _answers.pop(did, None) or {"k": btns[-1][0], "v": None}


def _geo(s, old):
    g = dict(old or {})
    s = str(s).strip().lstrip("=")
    size, pos = s, ""
    for j in range(len(s)):
        if s[j] in "+-":
            size, pos = s[:j], s[j:]
            break
    if "x" in size:
        a, b = size.split("x")
        g["w"], g["h"] = int(a), int(b)
    nums = []
    for c in pos:
        if c in "+-":
            nums.append([c, ""])
        elif nums:
            nums[-1][1] += c
    if len(nums) == 2:
        for key, (sign, n) in zip(("x", "y"), nums):
            if sign == "+" and n:
                g[key] = int(n)
    return g


def _var(name):
    v = _varnames.get(str(name))
    if v is not None:
        return v._value
    if str(name) in _tclvars:
        return _tclvars[str(name)]
    raise TclError('can\'t read "%s": no such variable' % name)


def _setvar(name, value):
    v = _varnames.get(str(name))
    if v is not None:
        v._store(value, None)
    else:
        _tclvars[str(name)] = value


def _opts(args):
    d = {}
    i = 0
    while i < len(args):
        k = str(args[i])
        if k.startswith("-") and i + 1 < len(args):
            d[k[1:]] = args[i + 1]
            i += 2
        else:
            i += 1
    return d


def _c_rename(old, new):
    f = _cmds.pop(str(old), None)
    if new:
        _cmds[str(new)] = f
    return ""


def _c_set(name, *value):
    if value:
        _setvar(name, value[0])
        return value[0]
    return _var(name)


def _c_vwait(name):
    start = _tclvars.get(str(name), None)
    _loop(lambda: _tclvars.get(str(name), None) is not start)
    return ""


def _c_tk(sub, *a):
    if sub == "windowingsystem":
        return "x11"
    if sub == "scaling":
        return 4 / 3
    if sub == "appname":
        return _app()
    if sub in ("inactive", "useinputmethods"):
        return 0
    return ""


def _c_font(sub, *a):
    a = list(a)
    if "-displayof" in a:
        i = a.index("-displayof")
        del a[i:i + 2]
    if sub == "measure":
        return int(len(str(a[-1])) * _fontpx(a[0]) * 0.6 + 0.5)
    if sub == "metrics":
        px = _fontpx(a[0] if a else None)
        d = {"-ascent": int(px * 0.8), "-descent": int(px * 0.2 + 0.5), "-linespace": int(px * 1.4), "-fixed": 1}
        if len(a) > 1:
            return d.get(str(a[1]), 0)
        return _flatten(d.items())
    if sub == "families":
        return ("monospace", "sans-serif", "serif", "Courier", "Helvetica", "Times")
    if sub == "actual":
        f = _font(a[0]) if a else ["TkFixedFont", "10"]
        f = f if isinstance(f, list) else _tclsplit(f)
        d = {"-family": f[0] if f else "TkFixedFont", "-size": _int(f[1]) if len(f) > 1 else 10,
             "-weight": "bold" if "bold" in f[2:] else "normal",
             "-slant": "italic" if "italic" in f[2:] else "roman", "-underline": 0, "-overstrike": 0}
        if len(a) > 1:
            return d.get(str(a[1]), "")
        return _flatten(d.items())
    return ""


def _c_winfo(sub, *a):
    if sub == "server":
        return "X11R0 kt"
    if sub == "exists":
        w = _ids.get(str(a[0]))
        return 1 if w is not None and w._alive else 0
    w = _ids.get(str(a[0])) if a else None
    f = getattr(w, "winfo_" + sub, None) if w is not None else None
    if f is None:
        raise TclError('bad winfo "%s"' % sub)
    return f(*a[1:])


def _c_update(*a):
    if a and a[0] == "idletasks":
        _flush()
    else:
        _step()
    return ""


def _c_info(sub, *a):
    if sub == "patchlevel":
        return "8.6.13"
    if sub == "exists":
        return 1 if str(a[0]) in _tclvars or str(a[0]) in _varnames else 0
    if sub == "commands":
        return tuple(_cmds)
    return ""


def _c_event(sub, *a):
    if sub == "generate":
        w = _ids.get(str(a[0]))
        if w is not None:
            w.event_generate(str(a[1]), **_opts(a[2:]))
        return ""
    if sub == "add":
        _event_add(str(a[0]), *a[1:])
        return ""
    if sub == "delete":
        _event_delete(str(a[0]), *a[1:])
        return ""
    if sub == "info":
        return _event_info(a[0] if a else None)
    return ""


def _c_wm(sub, w, *a):
    w = _ids.get(str(w))
    f = getattr(w, "wm_" + sub, None) if w is not None else None
    if f is None:
        _warn("wm " + str(sub))
        return ""
    return f(*a)


def _c_selection(sub, *a):
    if sub == "get":
        return _clip[0]
    return ""


def _c_getsel(w, sel="PRIMARY"):
    if _clip[0]:
        return _clip[0]
    raise TclError("CLIPBOARD selection doesn't exist")


def _c_after(*a):
    if a and str(a[0]).isdigit() and len(a) == 1:
        _nap(int(a[0]))
    return ""


_TCL = {"rename": _c_rename, "set": _c_set, "vwait": _c_vwait, "tk": _c_tk, "font": _c_font, "winfo": _c_winfo,
        "update": _c_update, "info": _c_info, "event": _c_event, "wm": _c_wm, "selection": _c_selection,
        "tk::GetSelection": _c_getsel, "::tk::GetSelection": _c_getsel, "after": _c_after,
        "tcl_wordBreakAfter": _noop(-1), "tcl_wordBreakBefore": _noop(-1), "console": _noop(""),
        "::tk::unsupported::MacWindowStyle": _noop(""), "image": _noop(""), "ttk::style": _noop(""),
        "ttk::themes": _noop(("default",)), "ttk::setTheme": _noop("")}


class _Tcl:
    def call(self, *args):
        if len(args) == 1 and isinstance(args[0], (tuple, list)):
            args = tuple(args[0])
        if not args:
            return ""
        name = str(args[0])
        f = _cmds.get(name)
        if f is None:
            f = _TCL.get(name)
        if f is None:
            _warn("tk.call " + name)
            return ""
        return f(*args[1:])

    def eval(self, script):
        out = ""
        for line in str(script).split("\n"):
            words = _tclsplit(line)
            if words:
                out = self.call(*words)
        return out

    def createcommand(self, name, func):
        _cmds[str(name)] = func

    def deletecommand(self, name):
        _cmds.pop(str(name), None)

    def getvar(self, name="PY_VAR"):
        return _var(name)

    globalgetvar = getvar

    def setvar(self, name, value="1"):
        _setvar(name, value)

    globalsetvar = setvar

    def unsetvar(self, name):
        _tclvars.pop(str(name), None)

    globalunsetvar = unsetvar

    def splitlist(self, v):
        return tuple(_aslist(v))

    split = splitlist

    def getint(self, v):
        try:
            return _int(v)
        except (TypeError, ValueError):
            raise TclError('expected integer but got "%s"' % v)

    def getdouble(self, v):
        try:
            return float(v)
        except (TypeError, ValueError):
            raise TclError('expected floating-point number but got "%s"' % v)

    def getboolean(self, v):
        return getboolean(v)

    def wantobjects(self, *a):
        return 1

    def mainloop(self, n=0):
        mainloop(n)

    def dooneevent(self, flags=0):
        return 1 if _step() else 0

    def quit(self):
        _quit[0] = True

    interpaddr = _noop(0)
    willdispatch = record = adderrorinfo = loadtk = _noop()
    exprstring = exprlong = exprdouble = exprboolean = _stub("tk.expr")


_tcl = _Tcl()


def Tcl(screenName=None, baseName=None, className="Tk", useTk=False):
    return _tcl


def getint(v):
    return _int(v)


def getdouble(v):
    return float(v)


def getboolean(v):
    if isinstance(v, str):
        return v.lower() in ("1", "true", "yes", "on")
    return bool(v)


NoDefaultRoot = _noop()
image_names = _noop(())
image_types = _noop(("photo", "bitmap"))


def mainloop(n=0):
    _quit[0] = False
    try:
        _loop(lambda: _quit[0] or not _roots)
    finally:
        _quit[0] = False


def _event_add(virtual, *seqs):
    lst = _vevents.setdefault(str(virtual), [])
    for s in seqs:
        if s not in lst:
            lst.append(str(s))
    _kinds_dirty[0] = True


def _event_delete(virtual, *seqs):
    lst = _vevents.get(str(virtual))
    if lst is None:
        return
    if not seqs:
        del _vevents[str(virtual)]
    for s in seqs:
        if s in lst:
            lst.remove(s)
    _kinds_dirty[0] = True


def _event_info(virtual=None):
    if virtual is None:
        return tuple(_vevents)
    return tuple(_vevents.get(str(virtual), ()))


class Variable:
    _default = ""
    _count = [0]

    def __init__(self, master=None, value=None, name=None):
        Variable._count[0] += 1
        self._name = name or "PY_VAR%d" % Variable._count[0]
        self._value = self._default if value is None else value
        self._w = []
        self._tr = []
        _varnames[self._name] = self

    def __str__(self):
        return self._name

    def set(self, value):
        self._store(value, None)

    initialize = set

    def get(self):
        self._fire("read")
        return self._value

    def _store(self, value, src):
        self._value = value
        for w in self._w[:]:
            if w is not src and w._alive:
                w._sync(self)
        self._fire("write")

    def _fire(self, mode):
        for t in self._tr[:]:
            if mode in t[0]:
                _call(t[1], self._name, "", mode)

    def trace_add(self, mode, callback):
        modes = [mode] if isinstance(mode, str) else list(mode)
        name = "%x" % id(callback)
        self._tr.append((modes, callback, name))
        return name

    def trace_remove(self, mode, cbname):
        self._tr = [t for t in self._tr if t[2] != cbname]

    def trace_info(self):
        return [(tuple(t[0]), t[2]) for t in self._tr]

    def trace_variable(self, mode, callback):
        m = {"w": "write", "r": "read", "u": "unset"}
        return self.trace_add([m.get(c, c) for c in mode], callback)

    trace = trace_variable

    def trace_vdelete(self, mode, cbname):
        self.trace_remove(mode, cbname)

    def trace_vinfo(self):
        return self.trace_info()


class StringVar(Variable):
    def get(self):
        return str(Variable.get(self))


class IntVar(Variable):
    _default = 0

    def get(self):
        v = Variable.get(self)
        try:
            return _int(v)
        except (TypeError, ValueError):
            raise TclError('expected integer but got "%s"' % v)


class DoubleVar(Variable):
    _default = 0.0

    def get(self):
        v = Variable.get(self)
        try:
            return float(v)
        except (TypeError, ValueError):
            raise TclError('expected floating-point number but got "%s"' % v)


class BooleanVar(Variable):
    _default = False

    def get(self):
        return getboolean(Variable.get(self))


def _script(src):
    fns = []
    for line in str(src).split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("kt::call "):
            f = _funcs.get(line[9:].strip())
            if f is not None:
                fns.append(f)
        elif line.startswith("catch {") and line.endswith("}"):
            fns.append(_catcher(_tclsplit(line[7:-1])))
        else:
            _warn("Tcl-скрипт в bind")

    def run(e):
        r = None
        for f in fns:
            if f(e) == "break":
                r = "break"
        return r

    return run


def _catcher(words):
    def run(e):
        try:
            _tcl.call(*[str(e.widget) if x == "%W" else x for x in words])
        except Exception:
            pass

    return run


def _fid(func, seq):
    fid = "%s%x" % (seq, id(func))
    _funcs[fid] = func
    return fid


def _bind(b, seq, func, add):
    if seq is None:
        return tuple(b)
    if func is None:
        return "\n".join("kt::call " + _fid(f, seq) for f in b.get(seq, ()))
    if isinstance(func, str):
        if not func.strip():
            b.pop(seq, None)
            _kinds_dirty[0] = True
            return ""
        func = _script(func)
        add = None
    p = _parse(seq)
    if p is None or p[0] not in _JSK and p[0] not in ("virt", "destroy"):
        _warn("событие " + seq)
        if p is None:
            return ""
    if add is True or add and str(add)[:1] == "+":
        b.setdefault(seq, []).append(func)
    else:
        b[seq] = [func]
    _kinds_dirty[0] = True
    return _fid(func, seq)


def _unbind(b, seq, funcid):
    if funcid and seq in b:
        b[seq] = [f for f in b[seq] if "%s%x" % (seq, id(f)) != funcid]
        if not b[seq]:
            del b[seq]
    else:
        b.pop(seq, None)
    _kinds_dirty[0] = True


class Misc:
    master = None
    _alive = True
    _kind = "Frame"
    _box = False
    _chars = False
    _var = None
    _tvar = None
    _size = None
    _lag = False
    _btags = None
    _tb = None
    _windowingsystem = "x11"
    tk = _tcl

    def _setup(self, master, kw):
        _count[0] += 1
        self._id = self._w = "%s.%d" % (_sid, _count[0])
        self._class = self._kind
        self.master = master
        self.children = {}
        self.widgetName = self._kind.lower()
        self._p = {}
        self._o = {}
        self._b = {}
        self._kids = []
        self._geo = None
        self._pk = []
        self._gr = []
        self._pl = []
        self._cols = {}
        self._rows = {}
        self._propag = True
        self._new = True
        _widgets.append(self)
        _ids[self._id] = self
        _cmds[self._w] = self._tclcmd
        if master is not None:
            master._kids.append(self)
            master.children[self._id] = self
        self._init()
        self.configure(**kw)
        self._ready()
        f = getattr(self, "_restyle", None)
        if f:
            f()
        self._new = False
        _kinds_dirty[0] = True
        _op("w", self._id, self._kind, master._id if master is not None else None, dict(self._p))

    def _init(self):
        pass

    def _ready(self):
        pass

    def _prop(self, k, v):
        self._p[k] = v
        if not self._new and self._alive:
            _op("c", self._id, {k: v})

    def _set(self, k, v):
        self._o[k] = v
        f = getattr(self, "_o_" + k, None)
        if f:
            f(v)
        elif k in _CSS:
            self._prop(k, _norm(self, k, v))
        elif k not in _QUIET:
            _warn("%s(%s=...)" % (type(self).__name__, k))

    def _tclcmd(self, op, *args):
        op = str(op)
        if op in ("configure", "config"):
            r = self.configure(**_opts(args)) if len(args) != 1 else self.configure(str(args[0]).lstrip("-"))
            return "" if r is None else r
        if op == "cget":
            return self.cget(str(args[0]).lstrip("-"))
        f = getattr(self, "_t_" + op, None)
        if f is None:
            raise TclError('bad option "%s"' % op)
        return f(*args)

    def _o_state(self, v):
        self._prop("state", str(v))

    def _o_image(self, v):
        self._prop("image", str(v) if v else "")

    def _o_bitmap(self, v):
        if v:
            _warn("bitmap")

    def _o_textvariable(self, v):
        self._link("_tvar", v)

    def _o_validate(self, v):
        if v and v != "none":
            _warn("validate")

    _o_validatecommand = _noop()

    def _link(self, attr, var):
        if isinstance(var, str):
            var = _varnames.get(var) or StringVar(name=var)
        old = getattr(self, attr)
        if old is not None and self in old._w:
            old._w.remove(self)
        setattr(self, attr, var)
        if var is not None:
            var._w.append(self)
            self._sync(var)

    def _sync(self, var):
        if var is self._tvar:
            self._prop("text", str(var._value))

    _js = _noop()
    _selev = _noop()
    _close = _noop()

    def _cmd(self, x):
        c = self._o.get("command")
        if c and self._o.get("state") != "disabled":
            _call(c)

    def _is_top(self):
        return self._kind in ("Tk", "Toplevel")

    def _rekind(self):
        ks = []
        for tag in self.bindtags():
            b = _tagmap(tag)
            if b:
                for seq in b:
                    for k in _kinds_of(seq):
                        if k not in ks:
                            ks.append(k)
        if self._tb:
            for key in self._tb:
                for k in _kinds_of(key[1]):
                    if k not in ks:
                        ks.append(k)
        ks.sort()
        if ks != self._p.get("b", []):
            self._prop("b", ks)

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, str):
            k = _ALIAS.get(cnf, cnf)
            return (cnf, cnf, cnf, None, self.cget(k))
        if cnf:
            kw = _merge(cnf, kw)
        if not kw:
            return dict((k, (k, k, k, None, v)) for k, v in self._o.items())
        for k in kw:
            if kw[k] is not None:
                self._set(_ALIAS.get(k, k), kw[k])

    config = configure

    def cget(self, key):
        key = _ALIAS.get(key, key)
        if key in self._o:
            return self._o[key]
        if key in ("fg", "bg"):
            return "SystemButtonText" if key == "fg" else "SystemButtonFace"
        return 0 if key in ("bd", "padx", "pady", "highlightthickness") else ""

    def __getitem__(self, key):
        return self.cget(key)

    def __setitem__(self, key, value):
        self.configure(**{key: value})

    def keys(self):
        return sorted(self._o)

    def __str__(self):
        return self._w

    def __repr__(self):
        return "<tkinter.%s object %s>" % (type(self).__name__, self._w)

    def destroy(self):
        if not self._alive:
            return
        self._kill()
        m = self.master
        if m is not None:
            if self in m._kids:
                m._kids.remove(self)
            m.children.pop(self._id, None)
        self._forget()
        _op("d", self._id)

    def _kill(self):
        for c in self._kids[:]:
            c._kill()
        self._alive = False
        for v in (self._var, self._tvar):
            if v is not None and self in v._w:
                v._w.remove(self)
        if self in _widgets:
            _widgets.remove(self)
        if self in _tdirty:
            _tdirty.remove(self)
        _ids.pop(self._id, None)
        if _cmds.get(self._w) == self._tclcmd:
            del _cmds[self._w]
        if self in _roots:
            _roots.remove(self)
        for fn in (self._b.get("<Destroy>") or [])[:]:
            e = Event()
            e.widget = self
            e.type = EventType.Destroy
            _call(fn, e)

    def _forget(self):
        g = self._geo
        if not g:
            return
        m = g[2]
        for lst in (m._pk, m._gr, m._pl):
            if self in lst:
                lst.remove(self)
        if g[0] == "nb":
            m._tabs = [t for t in m._tabs if t[0] is not self]
        if g[0] == "pw":
            m._panes = [p for p in m._panes if p[0] is not self]
        if g[0] == "text":
            m._unwin(self)
        if g[0] == "canvas":
            m._unwin(self)
        self._geo = None
        _dirty_add(m)

    def _lay(self):
        def ok(lst):
            return [w for w in lst if w._alive]

        return {"p": [[w._id, _packopts(w._geo[1])] for w in ok(self._pk)],
                "g": [[w._id, _gridopts(w._geo[1])] for w in ok(self._gr)],
                "x": [[w._id, _placeopts(w._geo[1])] for w in ok(self._pl)],
                "c": self._cols, "r": self._rows, "prop": self._propag}

    def _root(self):
        w = self
        while w.master is not None:
            w = w.master
        return w

    def _getints(self, string):
        if not string:
            return ()
        return tuple(_int(x) for x in _aslist(string))

    def _getdoubles(self, string):
        if not string:
            return ()
        return tuple(float(x) for x in _aslist(string))

    def info_patchlevel(self):
        return _PATCH

    def after(self, ms, func=None, *args):
        if func is None:
            _nap(int(ms))
            return None
        _count[0] += 1
        t = "after#%d" % _count[0]
        _timers.append([_add(_ms(), int(ms)), t, func, args])
        return t

    def after_idle(self, func, *args):
        return self.after(0, func, *args)

    def after_cancel(self, id):
        for t in _timers:
            if t[1] == id:
                _timers.remove(t)
                break

    def update(self):
        _step(True)

    def update_idletasks(self):
        _flush()

    def mainloop(self, n=0):
        mainloop(n)

    def quit(self):
        _quit[0] = True

    def wait_window(self, window=None):
        w = window or self
        _loop(lambda: not w._alive)

    def wait_variable(self, name):
        hit = [False]

        def cb(*a):
            hit[0] = True

        v = name if isinstance(name, Variable) else _varnames.get(str(name))
        t = v.trace_add("write", cb)
        try:
            _loop(lambda: hit[0])
        finally:
            v.trace_remove("write", t)

    waitvar = wait_variable
    wait_visibility = _noop()

    def getvar(self, name="PY_VAR"):
        return _var(name)

    def setvar(self, name="PY_VAR", value="1"):
        _setvar(name, value)

    def _getboolean(self, s):
        return getboolean(s)

    def bindtags(self, tagList=None):
        if tagList is None:
            if self._btags is not None:
                return tuple(self._btags)
            top = self.winfo_toplevel()
            if top is self:
                return (self._w, self._class, "all")
            return (self._w, self._class, top._w, "all")
        self._btags = [str(t) for t in tagList]
        _kinds_dirty[0] = True

    def bind(self, sequence=None, func=None, add=None):
        return _bind(self._b, sequence, func, add)

    def unbind(self, sequence, funcid=None):
        _unbind(self._b, sequence, funcid)

    def bind_all(self, sequence=None, func=None, add=None):
        return _bind(_all_b, sequence, func, add)

    def unbind_all(self, sequence):
        _unbind(_all_b, sequence, None)

    def bind_class(self, className, sequence=None, func=None, add=None):
        return _bind(_class_b.setdefault(str(className), {}), sequence, func, add)

    def unbind_class(self, className, sequence):
        _unbind(_class_b.setdefault(str(className), {}), sequence, None)

    def event_add(self, virtual, *sequences):
        _event_add(virtual, *sequences)

    def event_delete(self, virtual, *sequences):
        _event_delete(virtual, *sequences)

    def event_info(self, virtual=None):
        return _event_info(virtual)

    def event_generate(self, sequence, **kw):
        if sequence.startswith("<<"):
            _virtual(self, sequence, kw)
            _pending_run()
            return
        p = _parse(sequence)
        if not p or p[0] not in _JSK:
            _warn("event_generate " + sequence)
            return
        k = p[0]
        d = {"t": "move" if k == "drag" else k, "x": _int(kw.get("x", 0)), "y": _int(kw.get("y", 0)),
             "m": p[2] & 0xff, "b": (1 if p[2] & 256 else 0) | (4 if p[2] & 512 else 0) | (2 if p[2] & 1024 else 0)}
        if k in ("down", "up", "dbl"):
            d["n"] = p[1] or _int(kw.get("button", 1))
        if k in ("key", "keyup"):
            ks = str(kw.get("keysym", p[1] or ""))
            ch = _SYM.get(ks, ks if len(ks) == 1 else "")
            d.update({"k": ks, "c": ch})
            _keyd(d)
        if k == "wheel":
            d["d"] = _int(kw.get("delta", 0))
        if self._kind == "Text" and k in ("key", "keyup"):
            _textev(self, d)
        else:
            _dispatch(self, d)
        _pending_run()

    def focus_set(self):
        _op("f", self._id)

    focus = focus_force = focus_set
    focus_get = focus_displayof = focus_lastfor = _noop()

    def tk_focusNext(self):
        return self

    tk_focusPrev = tk_focusNext
    grab_set = grab_release = grab_set_global = _noop()
    grab_current = _noop()
    grab_status = _noop("")
    option_add = option_clear = option_readfile = tk_setPalette = tk_strictMotif = bell = _noop()
    option_get = _noop("")
    winfo_containing = _noop()
    image_names = _noop(())

    def register(self, func, subst=None, needcleanup=1):
        return func

    _register = register

    def clipboard_clear(self, **kw):
        _clip[0] = ""

    def clipboard_append(self, string, **kw):
        _clip[0] += str(string)
        try:
            _kt.copy(_clip[0])
        except Exception as e:
            raise TclError(str(e))

    def clipboard_get(self, **kw):
        if _clip[0]:
            return _clip[0]
        try:
            return _kt.paste()
        except Exception as e:
            raise TclError(str(e))

    def selection_get(self, **kw):
        return self.clipboard_get()

    selection_handle = selection_own = selection_own_get = _noop()

    def nametowidget(self, name):
        return _ids.get(str(name))

    _nametowidget = nametowidget

    def winfo_exists(self):
        return 1 if self._alive else 0

    def winfo_children(self):
        return [c for c in self._kids if c._alive]

    def winfo_toplevel(self):
        w = self
        while w.master is not None and not w._is_top():
            w = w.master
        return w

    def winfo_manager(self):
        if self._is_top():
            return "wm"
        return self._geo[0] if self._geo else ""

    def _rect(self):
        _flush()
        try:
            r = _kt.js("""(id) => {
  const w = window.ktTkS && ktTkS.w[id], e = w && (w.body || w.el);
  if (!e || !e.isConnected) return null;
  const r = e.getBoundingClientRect();
  return [Math.round(r.width), Math.round(r.height), Math.round(r.left), Math.round(r.top)];
}""", self._id)
        except Exception:
            r = None
        return r or [1, 1, 0, 0]

    def winfo_width(self):
        return max(1, self._rect()[0])

    def winfo_height(self):
        return max(1, self._rect()[1])

    winfo_reqwidth = winfo_width
    winfo_reqheight = winfo_height

    def winfo_x(self):
        return self._rect()[2]

    def winfo_y(self):
        return self._rect()[3]

    winfo_rootx = winfo_x
    winfo_rooty = winfo_y

    def winfo_geometry(self):
        r = self._rect()
        return "%dx%d+%d+%d" % tuple(r)

    def _screen(self):
        if not _screen:
            try:
                _screen.extend(_kt.js("() => [innerWidth, innerHeight]"))
            except Exception:
                _screen.extend([1024, 768])
        return _screen

    def winfo_screenwidth(self):
        return self._screen()[0]

    def winfo_screenheight(self):
        return self._screen()[1]

    winfo_vrootwidth = winfo_screenwidth
    winfo_vrootheight = winfo_screenheight
    winfo_pointerx = winfo_pointery = _noop(0)
    winfo_pointerxy = _noop((0, 0))
    winfo_depth = _noop(24)
    def winfo_rgb(self, color):
        c = str(color)
        if c not in _rgbs:
            _flush()
            try:
                _rgbs[c] = _kt.js("(c) => window.ktTkS && ktTkS.rgb ? ktTkS.rgb(c) : 0", c)
            except Exception:
                _rgbs[c] = 0
        r = _rgbs[c]
        if r is None:
            raise TclError('unknown color name "%s"' % c)
        return tuple(v * 257 for v in r) if r else (0, 0, 0)

    def winfo_ismapped(self):
        return 1 if self._alive and (self._geo or self._is_top()) else 0

    winfo_viewable = winfo_ismapped

    def winfo_class(self):
        return self._class

    def winfo_name(self):
        return self._id.split(".")[-1]

    def winfo_parent(self):
        return str(self.master) if self.master is not None else ""

    def winfo_id(self):
        return int(self._id.split(".")[-1])

    def winfo_pixels(self, number):
        return int(_px(number))

    def winfo_fpixels(self, number):
        return float(_px(number))

    def grid_columnconfigure(self, index, cnf=None, **kw):
        return self._rc(self._cols, index, _merge(cnf, kw) if cnf else kw)

    def grid_rowconfigure(self, index, cnf=None, **kw):
        return self._rc(self._rows, index, _merge(cnf, kw) if cnf else kw)

    columnconfigure = grid_columnconfigure
    rowconfigure = grid_rowconfigure

    def _rc(self, d, index, kw):
        idx = list(index) if isinstance(index, (list, tuple)) else [index]
        if idx == ["all"]:
            n = self.grid_size()
            idx = list(range(n[0] if d is self._cols else n[1]))
        for i in idx:
            k = str(_int(i))
            c = d.get(k) or [0, 0]
            if not kw:
                return {"weight": c[0], "minsize": c[1], "pad": 0, "uniform": None}
            if "weight" in kw:
                c[0] = _int(kw["weight"])
            if "minsize" in kw:
                c[1] = _px(kw["minsize"])
            d[k] = c
        _dirty_add(self)

    def grid_size(self):
        c = r = 0
        for w in self._gr:
            o = w._geo[1]
            c = max(c, _int(o.get("column", 0)) + _int(o.get("columnspan", 1)))
            r = max(r, _int(o.get("row", 0)) + _int(o.get("rowspan", 1)))
        return (c, r)

    size = grid_size

    def grid_bbox(self, column=None, row=None, col2=None, row2=None):
        return (0, 0, 0, 0)

    def _next_row(self):
        return self.grid_size()[1]

    def pack_propagate(self, flag=None):
        if flag is None:
            return self._propag
        self._propag = bool(flag)
        _dirty_add(self)

    propagate = grid_propagate = pack_propagate
    bbox = grid_bbox

    def pack_slaves(self):
        return [w for w in self._pk if w._alive]

    slaves = pack_slaves

    def grid_slaves(self, row=None, column=None):
        out = []
        for w in self._gr:
            o = w._geo[1]
            if (row is None or _int(o.get("row", 0)) == row) and (column is None or _int(o.get("column", 0)) == column):
                out.append(w)
        return out

    def place_slaves(self):
        return [w for w in self._pl if w._alive]

    lift = tkraise = lower = _noop()


def _bool(v):
    return getboolean(v) if isinstance(v, str) else bool(v)


class _Patch:
    major, minor, micro, releaselevel, serial = 8, 6, 13, "final", 0

    def __str__(self):
        return "8.6.13"

    def __iter__(self):
        return iter((8, 6, 13, "final", 0))

    def __getitem__(self, i):
        return (8, 6, 13, "final", 0)[i]


_PATCH = _Patch()


def _packopts(o):
    r = {"side": str(o.get("side", "top"))}
    if o.get("fill"):
        r["fill"] = str(o["fill"])
    if o.get("expand") and _bool(o["expand"]):
        r["expand"] = 1
    if o.get("anchor"):
        r["anchor"] = str(o["anchor"])
    for k in ("padx", "pady", "ipadx", "ipady"):
        if o.get(k):
            r[k] = _pad(o[k]) if k in ("padx", "pady") else _px(o[k])
    return r


def _gridopts(o):
    r = {"row": _int(o.get("row", 0)), "column": _int(o.get("column", 0))}
    for k in ("rowspan", "columnspan"):
        if o.get(k):
            r[k] = _int(o[k])
    s = o.get("sticky")
    if s:
        r["sticky"] = ("".join(s) if isinstance(s, (tuple, list)) else str(s)).lower()
    for k in ("padx", "pady", "ipadx", "ipady"):
        if o.get(k):
            r[k] = _pad(o[k]) if k in ("padx", "pady") else _px(o[k])
    return r


def _placeopts(o):
    r = {}
    for k in ("x", "y", "width", "height"):
        if o.get(k) is not None:
            r[k] = _px(o[k])
    for k in ("relx", "rely", "relwidth", "relheight"):
        if o.get(k) is not None:
            r[k] = float(o[k])
    if o.get("anchor"):
        r["anchor"] = str(o["anchor"])
    return r


class Wm:
    def title(self, string=None):
        if string is None:
            return self._p.get("title", "")
        self._prop("title", str(string))

    wm_title = title

    def geometry(self, newGeometry=None):
        if newGeometry is None:
            return self.winfo_geometry()
        self._prop("geo", _geo(newGeometry, self._p.get("geo")))

    wm_geometry = geometry

    def resizable(self, width=None, height=None):
        if width is None:
            return tuple(self._p.get("rs", [1, 1]))
        self._prop("rs", [1 if _bool(width) else 0, 1 if _bool(width if height is None else height) else 0])

    wm_resizable = resizable

    def minsize(self, width=None, height=None):
        self._prop("minsize", [_px(width or 0), _px(height or 0)])

    def maxsize(self, width=None, height=None):
        self._prop("maxsize", [_px(width or 0), _px(height or 0)])

    wm_minsize = minsize
    wm_maxsize = maxsize

    def protocol(self, name=None, func=None):
        if func is None:
            return self._proto.get(name)
        self._proto[name] = func

    wm_protocol = protocol

    def withdraw(self):
        self._prop("hide", 1)

    def iconify(self):
        # свёрнутое окно прячется, как и снятое, но остаётся в списке панели задач (hide 2)
        self._prop("hide", 2)

    def deiconify(self):
        self._prop("hide", 0)
        self._prop("zoom", 0)

    wm_withdraw = withdraw
    wm_iconify = iconify
    wm_deiconify = deiconify

    def _wmreq(self, op):
        if op == "iconic":
            self.iconify()
        elif op == "normal":
            if self._p.get("hide"):
                self._prop("hide", 0)
            self.lift()

    def state(self, newstate=None):
        if newstate is None:
            h = self._p.get("hide")
            return "iconic" if h == 2 else "withdrawn" if h else "zoomed" if self._p.get("zoom") else "normal"
        if newstate == "withdrawn":
            self.withdraw()
        elif newstate == "iconic":
            self.iconify()
        elif newstate == "normal":
            self.deiconify()
        elif newstate == "zoomed":
            self._prop("hide", 0)
            self._prop("zoom", 1)
        else:
            _warn("state " + str(newstate))

    wm_state = state

    def attributes(self, *args, **kw):
        if len(args) == 1:
            k = str(args[0]).lstrip("-")
            return {"topmost": self._p.get("topmost", 0), "alpha": self._p.get("alpha", 1.0),
                    "zoomed": self._p.get("zoom", 0), "type": self._p.get("type", "normal")}.get(k, "")
        pairs = [(str(args[i]).lstrip("-"), args[i + 1]) for i in range(0, len(args) - 1, 2)]
        pairs.extend(kw.items())
        for k, v in pairs:
            if k == "topmost":
                self._prop("topmost", 1 if _bool(v) else 0)
            elif k == "alpha":
                self._prop("alpha", float(v))
            elif k in ("zoomed", "fullscreen"):
                self._prop("zoom", 1 if _bool(v) else 0)
            elif k == "type":
                # как _NET_WM_WINDOW_TYPE в X11: desktop - под всеми окнами во весь экран, dock - панель снизу
                t = (v.split() if isinstance(v, str) else list(v) or ["normal"])[0]
                self._prop("type", t if t in ("desktop", "dock") else "normal")
            else:
                _warn("attributes -" + k)

    wm_attributes = attributes

    def overrideredirect(self, flag=None):
        if flag is None:
            return self._p.get("bare", 0)
        self._prop("bare", 1 if _bool(flag) else 0)

    wm_overrideredirect = overrideredirect

    def transient(self, master=None):
        if master is None:
            m = getattr(self, "_tmaster", None)
            return m._w if m else ""
        self._tmaster = master if hasattr(master, "_id") else None
        self._prop("transient", self._tmaster._id if self._tmaster else "")
        return ""

    wm_transient = transient
    iconbitmap = iconphoto = iconname = iconmask = iconposition = iconwindow = group = _noop("")
    aspect = positionfrom = sizefrom = focusmodel = client = colormapwindows = command = _noop("")
    wm_iconbitmap = wm_iconphoto = wm_iconname = wm_iconmask = wm_iconposition = wm_iconwindow = _noop("")
    wm_group = wm_aspect = wm_positionfrom = wm_sizefrom = wm_focusmodel = _noop("")
    wm_client = wm_colormapwindows = wm_command = _noop("")

    def wm_frame(self):
        return self._w

    frame = wm_frame

    def lift(self, aboveThis=None):
        _op("r", self._id, 1)

    tkraise = lift

    def lower(self, belowThis=None):
        _op("r", self._id, 0)

    def _o_menu(self, v):
        self._prop("menu", v._id if v else "")

    def _close(self):
        f = self._proto.get("WM_DELETE_WINDOW")
        if f:
            _call(f)
        else:
            self.destroy()


class Tk(Wm, Misc):
    _kind = "Tk"
    _box = True

    def __init__(self, screenName=None, baseName=None, className="Tk", useTk=True, sync=False, use=None):
        global _default_root
        self._proto = {}
        self._name = baseName or _app()
        self._setup(None, {})
        self._class = className or "Tk"
        _roots.append(self)
        if _default_root is None or not _default_root._alive:
            _default_root = self

    def _init(self):
        self._p["title"] = self._name

    def destroy(self):
        global _default_root
        Misc.destroy(self)
        if _default_root is self:
            _default_root = None

    def report_callback_exception(self, exc, val, tb):
        _report(val)

    readprofile = loadtk = _noop()


class Toplevel(Wm, Misc):
    _kind = "Toplevel"
    _box = True

    def __init__(self, master=None, cnf=None, **kw):
        self._proto = {}
        if cnf:
            kw = _merge(cnf, kw)
        self._setup(master if master is not None else _root(), kw)

    def _init(self):
        self._p["title"] = _app()


class Widget(Misc):
    def __init__(self, master=None, cnf=None, **kw):
        if cnf:
            kw = _merge(cnf, kw)
        self._setup(master if master is not None else _root(), kw)

    def _manage(self, kind, kw, lst):
        m = kw.pop("in_", None) or kw.pop("in", None) or self.master
        old = self._geo
        same = old and old[0] == kind and old[2] is m
        o = dict(old[1]) if same else {}
        before, after = kw.pop("before", None), kw.pop("after", None)
        o.update(kw)
        if not same:
            self._forget()
            dest = getattr(m, lst)
            ref = before or after
            if ref is not None and ref in dest:
                dest.insert(dest.index(ref) + (1 if after is not None else 0), self)
            else:
                dest.append(self)
        self._geo = [kind, o, m]
        _dirty_add(m)
        return m, same

    def pack_configure(self, cnf=None, **kw):
        if cnf:
            kw = _merge(cnf, kw)
        self._manage("pack", kw, "_pk")

    pack = pack_configure

    def pack_forget(self):
        if self._geo and self._geo[0] == "pack":
            self._forget()

    forget = pack_forget

    def pack_info(self):
        if not self._geo or self._geo[0] != "pack":
            return {}
        d = {"anchor": "center", "expand": 0, "fill": "none", "ipadx": 0, "ipady": 0, "padx": 0, "pady": 0,
             "side": "top"}
        d.update(self._geo[1])
        d["in"] = self._geo[2]
        return d

    info = pack_info

    def grid_configure(self, cnf=None, **kw):
        if cnf:
            kw = _merge(cnf, kw)
        m = kw.get("in_") or kw.get("in") or self.master
        if "row" not in kw and not (self._geo and self._geo[0] == "grid"):
            kw["row"] = m._next_row()
        self._manage("grid", kw, "_gr")

    grid = grid_configure

    def grid_forget(self):
        if self._geo and self._geo[0] == "grid":
            self._forget()

    grid_remove = grid_forget

    def grid_info(self):
        if not self._geo or self._geo[0] != "grid":
            return {}
        d = {"column": 0, "row": 0, "columnspan": 1, "rowspan": 1, "ipadx": 0, "ipady": 0, "padx": 0, "pady": 0,
             "sticky": ""}
        d.update(self._geo[1])
        d["in"] = self._geo[2]
        return d

    def place_configure(self, cnf=None, **kw):
        if cnf:
            kw = _merge(cnf, kw)
        kw.pop("bordermode", None)
        self._manage("place", kw, "_pl")

    place = place_configure

    def place_forget(self):
        if self._geo and self._geo[0] == "place":
            self._forget()

    def place_info(self):
        if not self._geo or self._geo[0] != "place":
            return {}
        d = {"x": 0, "y": 0, "relx": 0, "rely": 0, "anchor": "nw", "bordermode": "inside"}
        d.update(self._geo[1])
        d["in"] = self._geo[2]
        return d


Pack = Grid = Place = Widget


class Frame(Widget):
    _kind = "Frame"
    _box = True


class LabelFrame(Widget):
    _kind = "LabelFrame"
    _box = True


Labelframe = LabelFrame


class Label(Widget):
    _kind = "Label"
    _chars = True


class Message(Label):
    _chars = False

    def _init(self):
        self._p["wraplength"] = 300

    def _o_width(self, v):
        self._prop("wraplength", _px(v))


class Button(Label):
    _kind = "Button"

    def invoke(self):
        c = self._o.get("command")
        if c and self._o.get("state") != "disabled":
            return c()

    flash = _noop()


class Entry(Widget):
    _kind = "Entry"
    _chars = True

    def _init(self):
        self._v = ""

    def _o_show(self, v):
        self._prop("show", 1 if v else 0)

    def _sync(self, var):
        if var is self._tvar:
            self._v = str(var._value)
            self._prop("value", self._v)

    def _o_validate(self, v):
        if str(v) in ("focus", "focusin", "focusout"):
            _warn("validate=" + str(v))

    def _vcall(self, opt, new, why):
        cmd = self._o.get(opt)
        f, args = (cmd[0], cmd[1:]) if isinstance(cmd, (tuple, list)) else (cmd, ())
        if not callable(f):
            return True
        old = self._v
        i, n = 0, min(len(old), len(new))
        while i < n and old[i] == new[i]:
            i += 1
        j = 0
        while j < n - i and old[len(old) - 1 - j] == new[len(new) - 1 - j]:
            j += 1
        ins = new[i:len(new) - j]
        sub = {"%P": new, "%s": old, "%S": ins or old[i:len(old) - j], "%d": "1" if ins else "0", "%i": str(i),
               "%v": str(self._o.get("validate", "none")), "%V": why, "%W": self._w}
        r = _call(f, *[sub.get(a, a) for a in args])
        return r not in (False, None, 0, "0", "false")

    def _js(self, v):
        v = str(v)
        if v != self._v and self._o.get("validate") in ("key", "all") and not self._vcall("validatecommand", v, "key"):
            self._prop("value", self._v)
            self._vcall("invalidcommand", v, "key")
            return
        self._v = v
        self._p["value"] = self._v
        if self._tvar is not None:
            self._tvar._store(self._v, self)

    def _put(self, s):
        if self._tvar is not None:
            self._tvar._store(s, None)
        else:
            self._v = s
            self._prop("value", s)

    def get(self):
        return self._v

    def _index(self, i):
        n = len(self._v)
        if i in ("end", "insert", "anchor"):
            return n
        try:
            return max(0, min(n, _int(i)))
        except (TypeError, ValueError):
            raise TclError('bad entry index "%s"' % i)

    def index(self, index):
        return self._index(index)

    def insert(self, index, string):
        if self._o.get("state") in ("disabled", "readonly"):
            return
        i = self._index(index)
        self._put(self._v[:i] + str(string) + self._v[i:])

    def delete(self, first, last=None):
        if self._o.get("state") in ("disabled", "readonly"):
            return
        a = self._index(first)
        b = a + 1 if last is None else self._index(last)
        if b > a:
            self._put(self._v[:a] + self._v[b:])

    def select_range(self, start, end):
        _op("sr", self._id, self._index(start), self._index(end))

    selection_range = select_range

    def icursor(self, index):
        i = self._index(index)
        _op("sr", self._id, i, i)

    select_clear = selection_clear = select_adjust = selection_adjust = select_from = selection_from = _noop()
    select_to = selection_to = _noop()
    select_present = selection_present = _noop(False)
    xview = xview_moveto = xview_scroll = scan_mark = scan_dragto = _noop()


class Spinbox(Entry):
    _kind = "Spinbox"

    def _init(self):
        Entry._init(self)
        self._vals = None

    def _num(self, v):
        v = float(v)
        return str(int(v)) if v == int(v) else str(v)

    def _o_from(self, v):
        self._prop("from", float(v))

    def _o_to(self, v):
        self._prop("to", float(v))

    def _o_res(self, v):
        self._prop("res", float(v))

    def _o_values(self, v):
        vals = [str(x) for x in _aslist(v)]
        if self._new:
            self._kind = "Combobox"
            self._prop("ro", 1)
        if self._kind == "Combobox":
            self._vals = vals
            self._prop("items", vals)
        else:
            _warn("Spinbox values после создания")

    def _ready(self):
        if self._tvar is None and not self._v:
            if self._vals:
                self._v = self._vals[0]
            elif "from" in self._p:
                self._v = self._num(self._p["from"])
            else:
                self._v = "0"
            self._p["value"] = self._v

    def _cmd(self, x):
        c = self._o.get("command")
        if c:
            _call(c)

    _selev = _cmd

    def set(self, value):
        self._put(str(value))


def _radd(rs, a, b):
    if a >= b:
        return rs
    out = []
    i, n = 0, len(rs)
    while i < n and rs[i][1] < a:
        out.append(rs[i])
        i += 1
    while i < n and rs[i][0] <= b:
        a = min(a, rs[i][0])
        b = max(b, rs[i][1])
        i += 1
    out.append([a, b])
    out.extend(rs[i:])
    return out


def _rsub(rs, a, b):
    out = []
    for s, e in rs:
        if e <= a or s >= b:
            out.append([s, e])
        else:
            if s < a:
                out.append([s, a])
            if e > b:
                out.append([b, e])
    return out


def _rins(rs, pos, n):
    out = []
    for s, e in rs:
        if s >= pos:
            out.append([s + n, e + n])
        elif e > pos:
            out.append([s, e + n])
        else:
            out.append([s, e])
    return out


def _rdel(rs, a, b):
    n = b - a
    out = []
    for s, e in rs:
        s2 = s if s <= a else (a if s <= b else s - n)
        e2 = e if e <= a else (a if e <= b else e - n)
        if e2 > s2:
            if out and out[-1][1] >= s2:
                out[-1][1] = max(out[-1][1], e2)
            else:
                out.append([s2, e2])
    return out


def _rhas(rs, i):
    for s, e in rs:
        if s <= i < e:
            return True
        if s > i:
            return False
    return False


def _glob(p, s):
    if not p:
        return not s
    if p[0] == "*":
        return _glob(p[1:], s) or (bool(s) and _glob(p, s[1:]))
    if s and (p[0] == "?" or p[0] == s[0]):
        return _glob(p[1:], s[1:])
    return False


def _isword(c):
    return c.isalnum() or c == "_" or ord(c) > 127


def _taglist(tags):
    if tags is None:
        return []
    if isinstance(tags, (tuple, list)):
        return [str(t) for t in tags]
    return _tclsplit(str(tags))


_TAGOPT = {"fg": "foreground", "bg": "background"}
_TAGCSS = {"foreground", "background", "font", "underline", "overstrike", "elide", "relief", "borderwidth",
           "justify", "wrap"}


class Text(Widget):
    _kind = "Text"
    _chars = True

    def _init(self):
        self._v = ""
        self._ls = None
        self._marks = {"insert": [0, "right"], "current": [0, "right"]}
        self._tags = {"sel": [[], {}]}
        self._torder = ["sel"]
        self._edits = []
        self._tchg = set()
        self._cchg = False
        self._full = True
        self._ver = 0
        self._seeoff = None
        self._yv = None
        self._view = {}
        self._mod = False
        self._wins = {}
        self._tb = {}
        self._ysc = None
        self._xsc = None
        self._p.update({"text": "", "tags": {}, "tcfg": {}, "torder": ["sel"], "ins": 0, "sel": None, "ver": 0})
        _tdirty.append(self)

    def _o_state(self, v):
        self._prop("state", "readonly" if str(v) == "disabled" else str(v))

    def _o_insertbackground(self, v):
        self._prop("caret", str(v))

    def _o_selectbackground(self, v):
        self._prop("selbg", str(v))

    def _o_inactiveselectbackground(self, v):
        self._prop("selbg2", str(v))

    def _o_yscrollcommand(self, v):
        self._ysc = v

    def _o_xscrollcommand(self, v):
        self._xsc = v

    def _touch(self):
        if self not in _tdirty:
            _tdirty.append(self)
            self._ver += 1

    def _lines(self):
        if self._ls is None:
            t = self._v
            ls = [0]
            i = t.find("\n")
            while i >= 0:
                ls.append(i + 1)
                i = t.find("\n", i + 1)
            self._ls = ls
        return self._ls

    def _lc(self, off):
        ls = self._lines()
        if off > len(self._v):
            return (len(ls) + 1, 0)
        lo, hi = 0, len(ls) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if ls[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        return (lo + 1, off - ls[lo])

    def _linelen(self, ln):
        ls = self._lines()
        if ln > len(ls):
            return 0
        end = ls[ln] - 1 if ln < len(ls) else len(self._v)
        return end - ls[ln - 1]

    def _lc2off(self, ln, col):
        ls = self._lines()
        if ln < 1:
            ln, col = 1, 0
        if ln > len(ls):
            return len(self._v) + 1
        n = self._linelen(ln)
        if col == "end":
            c = n
        else:
            try:
                c = _int(col)
            except (TypeError, ValueError):
                raise TclError('bad text index "%d.%s"' % (ln, col))
            c = max(0, min(c, n))
        return ls[ln - 1] + c

    def _idx(self, off):
        return "%d.%d" % self._lc(off)

    def _base(self, b, full):
        if not b:
            raise TclError('bad text index "%s"' % full)
        if b[0].isdigit():
            parts = b.split(".", 1)
            try:
                ln = int(parts[0])
            except ValueError:
                raise TclError('bad text index "%s"' % full)
            return self._lc2off(ln, parts[1] if len(parts) > 1 else 0)
        if b == "end":
            return len(self._v) + 1
        m = self._marks.get(b)
        if m is not None:
            return m[0]
        k = b.rfind(".")
        if k > 0 and b[k + 1:] in ("first", "last"):
            tg = self._tags.get(b[:k])
            rs = tg[0] if tg else None
            if not rs:
                raise TclError('text doesn\'t contain any characters tagged with "%s"' % b[:k])
            return rs[0][0] if b[k + 1:] == "first" else rs[-1][1]
        if b in self._wins:
            return self._wins[b][0][0]
        raise TclError('bad text index "%s"' % full)

    def _off(self, index):
        if isinstance(index, (tuple, list)) and len(index) == 1:
            index = index[0]
        if isinstance(index, Misc):
            index = index._w
        s = str(index).strip()
        if s[:1] == "@":
            j = 1
            while j < len(s) and (s[j].isdigit() or s[j] in ",-"):
                j += 1
            xy = s[1:j].split(",")
            try:
                off = self._at(int(xy[0]), int(xy[1]))
            except (ValueError, IndexError):
                raise TclError('bad text index "%s"' % s)
            rest = s[j:]
        else:
            j = 0
            while j < len(s) and s[j] not in " +-":
                j += 1
            off = self._base(s[:j], s)
            rest = s[j:]
        if rest:
            off = self._mods(off, rest, s)
        return max(0, min(off, len(self._v) + 1))

    def _word(self, rest, i):
        n = len(rest)
        while i < n and rest[i] == " ":
            i += 1
        j = i
        while j < n and rest[j].isalpha():
            j += 1
        return rest[i:j], j

    def _mods(self, off, rest, full):
        i, n = 0, len(rest)
        top = len(self._v) + 1
        while i < n:
            c = rest[i]
            if c == " ":
                i += 1
                continue
            if c in "+-":
                sign = 1 if c == "+" else -1
                i += 1
                while i < n and rest[i] == " ":
                    i += 1
                j = i
                while j < n and rest[j].isdigit():
                    j += 1
                if j == i:
                    raise TclError('bad text index "%s"' % full)
                cnt = int(rest[i:j]) * sign
                unit, i = self._word(rest, j)
                if unit in ("display", "any"):
                    unit, i = self._word(rest, i)
                if unit[:1] == "l":
                    ln, col = self._lc(off)
                    ln2 = max(1, min(len(self._lines()) + 1, ln + cnt))
                    off = len(self._v) + 1 if ln2 > len(self._lines()) else self._lc2off(ln2, col)
                elif unit[:1] in ("c", "i"):
                    off += cnt
                else:
                    raise TclError('bad text index "%s"' % full)
            else:
                word, i = self._word(rest, i)
                if word in ("display", "any"):
                    continue
                t = self._v + "\n"
                if word == "linestart":
                    off = t.rfind("\n", 0, max(0, off)) + 1 if off > 0 else 0
                elif word == "lineend":
                    k = t.find("\n", min(off, len(t) - 1))
                    off = len(self._v) if k < 0 else k
                elif word == "wordstart":
                    if off < len(t) and _isword(t[off]):
                        while off > 0 and _isword(t[off - 1]):
                            off -= 1
                elif word == "wordend":
                    if off < len(t) and _isword(t[off]):
                        while off < len(t) and _isword(t[off]):
                            off += 1
                    else:
                        off += 1
                else:
                    raise TclError('bad text index "%s"' % full)
            off = max(0, min(off, top))
        return off

    def _geom(self):
        v = self._view
        lh = v.get("lh") or _fontpx(self._o.get("font")) * 1.4
        cw = v.get("cw") or _fontpx(self._o.get("font")) * 0.6
        rows = v.get("rows") or _int(self._o.get("height", 24))
        return v.get("top", 0), rows, lh, cw, v.get("px", 5), v.get("py", 3)

    def _at(self, x, y):
        top, rows, lh, cw, px, py = self._geom()
        ln = None
        for l, ly, h in self._view.get("lines") or ():
            if y < ly + h:
                ln = l
                break
        if ln is None:
            ln = int(top + max(0, y - py) // lh) + 1
        ln = max(1, min(ln, len(self._lines())))
        col = int(max(0, x - px) // cw)
        return self._lc2off(ln, col)

    def _tk(self, op, *args):
        return self.tk.call(self._w, op, *args)

    def _changed(self):
        self._ls = None
        self._touch()
        if not self._mod:
            self._mod = True
            _pending.append((self, "<<Modified>>"))

    def _t_insert(self, index, chars, *args):
        if self._o.get("state") == "disabled":
            return ""
        pos = min(self._off(index), len(self._v))
        segs = [(chars, args[0] if args else None)]
        for k in range(1, len(args), 2):
            segs.append((args[k], args[k + 1] if k + 1 < len(args) else ()))
        for chars, tags in segs:
            s = str(chars)
            n = len(s)
            if not n:
                continue
            self._v = self._v[:pos] + s + self._v[pos:]
            for m in self._marks.values():
                if m[0] > pos or (m[0] == pos and m[1] == "right"):
                    m[0] += n
            for name in self._wins:
                r = self._wins[name][0]
                if r[0] >= pos:
                    r[0] += n
            for name in self._tags:
                tg = self._tags[name]
                if tg[0]:
                    tg[0] = _rins(tg[0], pos, n)
            if tags is None:
                for name in self._tags:
                    rs = self._tags[name][0]
                    if rs and pos > 0 and _rhas(rs, pos - 1) and _rhas(rs, pos + n) and not _rhas(rs, pos):
                        self._tags[name][0] = _radd(rs, pos, pos + n)
                        self._tchg.add(name)
            else:
                tl = _taglist(tags)
                for name in self._tags:
                    rs = self._tags[name][0]
                    if rs and name not in tl and _rhas(rs, pos):
                        self._tags[name][0] = _rsub(rs, pos, pos + n)
                        self._tchg.add(name)
                for name in tl:
                    self._newtag(name)
                    self._tags[name][0] = _radd(self._tags[name][0], pos, pos + n)
                    self._tchg.add(name)
            self._edits.append([pos, 0, s])
            pos += n
            self._ls = None
        self._changed()
        return ""

    def _t_delete(self, index1, index2=None, *more):
        if self._o.get("state") == "disabled":
            return ""
        a = self._off(index1)
        b = a + 1 if index2 is None else self._off(index2)
        b = min(b, len(self._v))
        if a >= b:
            return ""
        n = b - a
        self._v = self._v[:a] + self._v[b:]
        for m in self._marks.values():
            if m[0] > b:
                m[0] -= n
            elif m[0] > a:
                m[0] = a
        for name in list(self._wins):
            r = self._wins[name][0]
            if a <= r[0] < b:
                w = self._wins.pop(name)[1]
                if w._alive:
                    w._geo = None
            elif r[0] >= b:
                r[0] -= n
        for name in self._tags:
            tg = self._tags[name]
            if tg[0]:
                tg[0] = _rdel(tg[0], a, b)
        self._edits.append([a, n, ""])
        self._changed()
        return ""

    def _t_replace(self, index1, index2, chars, *args):
        a = self._idx(self._off(index1))
        self._t_delete(index1, index2)
        return self._t_insert(a, chars, *args)

    def _t_get(self, index1, index2=None, *more):
        t = self._v + "\n"
        a = self._off(index1)
        b = a + 1 if index2 is None else self._off(index2)
        s = t[a:b] if b > a else ""
        if self._wins and "￼" in s:
            s = s.replace("￼", "")
        return s

    def _t_index(self, index):
        return self._idx(self._off(index))

    def _t_compare(self, index1, op, index2):
        a, b = self._off(index1), self._off(index2)
        return {"<": a < b, "<=": a <= b, "==": a == b, ">=": a >= b, ">": a > b, "!=": a != b}[op]

    def _newtag(self, name):
        if name not in self._tags:
            self._tags[name] = [[], {}]
            self._torder.append(name)
            self._cchg = True
        return self._tags[name]

    def _t_tag(self, sub, *a):
        f = getattr(self, "_tag_" + str(sub), None)
        if f is None:
            raise TclError('bad tag option "%s"' % sub)
        return f(*a)

    def _tag_add(self, name, *idx):
        tg = self._newtag(str(name))
        idx = [i for i in idx if i is not None]
        for k in range(0, len(idx), 2):
            a = self._off(idx[k])
            b = self._off(idx[k + 1]) if k + 1 < len(idx) else a + 1
            if b > a:
                tg[0] = _radd(tg[0], a, b)
        self._tchg.add(str(name))
        self._touch()
        return ""

    def _tag_remove(self, name, *idx):
        tg = self._tags.get(str(name))
        if not tg or not tg[0]:
            return ""
        idx = [i for i in idx if i is not None]
        for k in range(0, len(idx), 2):
            a = self._off(idx[k])
            b = self._off(idx[k + 1]) if k + 1 < len(idx) else a + 1
            if b > a:
                tg[0] = _rsub(tg[0], a, b)
        self._tchg.add(str(name))
        self._touch()
        return ""

    def _tag_ranges(self, name):
        tg = self._tags.get(str(name))
        out = []
        for s, e in tg[0] if tg else ():
            out.append(self._idx(s))
            out.append(self._idx(e))
        return tuple(out)

    def _tag_nextrange(self, name, index1, index2=None):
        tg = self._tags.get(str(name))
        a = self._off(index1)
        b = self._off(index2) if index2 is not None else len(self._v) + 1
        for s, e in tg[0] if tg else ():
            if s >= b:
                break
            if e > a:
                return (self._idx(max(s, a)), self._idx(e))
        return ()

    def _tag_prevrange(self, name, index1, index2=None):
        tg = self._tags.get(str(name))
        a = self._off(index1)
        b = self._off(index2) if index2 is not None else 0
        best = None
        for s, e in tg[0] if tg else ():
            if s >= a:
                break
            if e > b:
                best = (s, min(e, a))
        if best is None:
            return ()
        return (self._idx(best[0]), self._idx(best[1]))

    def _tag_names(self, index=None):
        if index is None:
            return tuple(self._torder)
        o = self._off(index)
        return tuple(n for n in self._torder if _rhas(self._tags[n][0], o))

    def _tag_configure(self, name, *args):
        tg = self._newtag(str(name))
        d = _opts(args)
        if not d:
            if len(args) == 1:
                k = str(args[0]).lstrip("-")
                return (k, "", "", "", tg[1].get(k, ""))
            return dict((k, (k, "", "", "", v)) for k, v in tg[1].items())
        for k in d:
            v = d[k]
            k = _TAGOPT.get(k, k)
            tg[1][k] = _font(v) if k == "font" and v else v
        self._cchg = True
        self._touch()
        return ""

    _tag_config = _tag_configure

    def _tag_cget(self, name, option):
        tg = self._tags.get(str(name))
        k = _TAGOPT.get(str(option).lstrip("-"), str(option).lstrip("-"))
        return tg[1].get(k, "") if tg else ""

    def _tag_delete(self, *names):
        for name in names:
            name = str(name)
            if name == "sel":
                self._tags["sel"] = [[], {}]
            elif name in self._tags:
                del self._tags[name]
                self._torder.remove(name)
            self._tchg.add(name)
        self._cchg = True
        self._touch()
        return ""

    def _tag_raise(self, name, above=None):
        name = str(name)
        self._newtag(name)
        self._torder.remove(name)
        if above is None or str(above) not in self._torder:
            self._torder.append(name)
        else:
            self._torder.insert(self._torder.index(str(above)) + 1, name)
        self._cchg = True
        self._touch()
        return ""

    def _tag_lower(self, name, below=None):
        name = str(name)
        self._newtag(name)
        self._torder.remove(name)
        if below is None or str(below) not in self._torder:
            self._torder.insert(0, name)
        else:
            self._torder.insert(self._torder.index(str(below)), name)
        self._cchg = True
        self._touch()
        return ""

    def _tag_bind(self, name, seq=None, func=None, add=None):
        key = (str(name), seq)
        if func is None:
            return key in self._tb
        if add is True or add and str(add)[:1] == "+":
            self._tb.setdefault(key, []).append(func)
        else:
            self._tb[key] = [func]
        _kinds_dirty[0] = True
        return _fid(func, seq)

    def _tag_unbind(self, name, seq, funcid=None):
        self._tb.pop((str(name), seq), None)
        _kinds_dirty[0] = True
        return ""

    def _tag_ev(self, d, kind, e):
        if "x" not in d or kind not in ("down", "up", "dbl", "move", "enter", "leave"):
            return None
        o = self._marks["current"][0]
        r = None
        for key in list(self._tb):
            name, seq = key
            p = _parse(seq)
            tg = self._tags.get(name)
            if p and tg and _rhas(tg[0], o) and _score(p, kind, d) >= 0:
                if _run(self._tb[key], e) == "break":
                    r = "break"
        return r

    def _t_mark(self, sub, *a):
        f = getattr(self, "_mark_" + str(sub), None)
        if f is None:
            raise TclError('bad mark option "%s"' % sub)
        return f(*a)

    def _mark_set(self, name, index):
        name = str(name)
        off = self._off(index)
        if name == "insert":
            off = min(off, len(self._v))
        m = self._marks.get(name)
        if m is None:
            self._marks[name] = [off, "right"]
        else:
            m[0] = off
        if name == "insert":
            self._touch()
        return ""

    def _mark_unset(self, *names):
        for name in names:
            if str(name) not in ("insert", "current"):
                self._marks.pop(str(name), None)
        return ""

    def _mark_names(self):
        return tuple(self._marks)

    def _mark_gravity(self, name, direction=None):
        m = self._marks.get(str(name))
        if m is None:
            raise TclError('there is no mark named "%s"' % name)
        if direction is None:
            return m[1]
        m[1] = str(direction)
        return ""

    def _mark_next(self, index):
        o = self._off(index)
        best = None
        for name in self._marks:
            p = self._marks[name][0]
            if p >= o and (best is None or p < self._marks[best][0]):
                best = name
        return best or ""

    def _mark_previous(self, index):
        o = self._off(index)
        best = None
        for name in self._marks:
            p = self._marks[name][0]
            if p < o and (best is None or p > self._marks[best][0]):
                best = name
        return best or ""

    def _t_see(self, index):
        off = self._off(index)
        self._seeoff = off
        ln = self._lc(off)[0]
        top, rows = self._view.get("top", 0), self._geom()[1]
        if ln - 1 < top:
            self._view["top"] = ln - 1
        elif ln > top + rows:
            self._view["top"] = ln - rows
        self._touch()
        return ""

    def _total(self):
        return len(self._lines())

    def _fractions(self):
        top, rows = self._view.get("top", 0), self._geom()[1]
        n = max(1, self._total())
        return (min(1.0, top / n), min(1.0, (top + rows) / n))

    def _scrollto(self, top):
        n = self._total()
        rows = self._geom()[1]
        top = max(0, min(top, max(0, n - 1)))
        self._view["top"] = top
        self._yv = top
        self._touch()
        self._yscroll()

    def _t_yview(self, *a):
        if not a:
            return self._fractions()
        top, rows = self._view.get("top", 0), self._geom()[1]
        if a[0] == "moveto":
            self._scrollto(float(a[1]) * self._total())
        elif a[0] == "scroll":
            n, what = float(a[1]), str(a[2])
            step = rows if what.startswith("p") else 1 / self._geom()[2] if what.startswith("pi") else 1
            if what.startswith("pi"):
                step = 1 / self._geom()[2]
            self._scrollto(top + n * step)
        else:
            self._t_see(a[0])
        return ""

    def _t_xview(self, *a):
        if not a:
            return (0.0, 1.0)
        return ""

    def _yscroll(self):
        f = self._ysc
        if f is not None and callable(f):
            a, b = self._fractions()
            _call(f, str(a), str(b))

    def _t_dlineinfo(self, index):
        top, rows, lh, cw, px, py = self._geom()
        ln = self._lc(self._off(index))[0]
        if ln > self._total():
            return None
        for l, y, h in self._view.get("lines") or ():
            if l == ln:
                return (px, int(y), int(cw * max(1, self._linelen(ln))), int(h), int(h * 0.8))
        if top <= ln - 1 < top + rows:
            y = py + (ln - 1 - top) * lh
            return (px, int(y), int(cw * max(1, self._linelen(ln))), int(lh), int(lh * 0.8))
        return None

    def _t_bbox(self, index):
        o = self._off(index)
        info = self._t_dlineinfo(index)
        if info is None:
            return None
        cw = self._geom()[3]
        col = self._lc(o)[1]
        return (int(info[0] + col * cw), info[1], int(cw), info[3])

    def _t_count(self, index1, index2, *options):
        a, b = self._off(index1), self._off(index2)
        out = []
        for opt in [str(x).lstrip("-") for x in options] or ["indices"]:
            if opt in ("chars", "indices", "displaychars", "displayindices"):
                out.append(b - a)
            elif opt in ("lines", "displaylines"):
                out.append(self._lc(b)[0] - self._lc(a)[0])
            elif opt == "update":
                continue
            else:
                out.append(0)
        return tuple(out)

    def _t_search(self, pattern, index, *args):
        opts = [str(x) for x in args]
        stop = None
        flags = set()
        countvar = None
        i = 0
        while i < len(opts):
            o = opts[i]
            if o == "-count":
                countvar = args[i + 1]
                i += 2
                continue
            if o.startswith("-"):
                flags.add(o[1:])
            else:
                stop = args[i]
            i += 1
        t = self._v + "\n"
        start = self._off(index)
        end = self._off(stop) if stop is not None else None
        pat = str(pattern)
        back = "backwards" in flags
        found, size = -1, 0
        if "regexp" in flags:
            import re
            rx = re.compile(pat, re.I) if "nocase" in flags else re.compile(pat)
            matches = []
            pos = 0
            while pos <= len(t):
                m = rx.search(t[pos:])
                if not m:
                    break
                s, e = m.start() + pos, m.end() + pos
                matches.append((s, e))
                pos = e if e > s else s + 1
            if back:
                lo = end if end is not None else 0
                for s, e in matches:
                    if lo <= s < start:
                        found, size = s, e - s
            else:
                hi = end if end is not None else len(t)
                for s, e in matches:
                    if start <= s < hi:
                        found, size = s, e - s
                        break
                if found < 0 and end is None:
                    for s, e in matches:
                        if s < start:
                            found, size = s, e - s
                            break
        else:
            hay = t.lower() if "nocase" in flags else t
            needle = pat.lower() if "nocase" in flags else pat
            size = len(needle)
            if back:
                found = hay.rfind(needle, end or 0, start)
                if found < 0 and end is None:
                    found = hay.rfind(needle, start)
            else:
                found = hay.find(needle, start, end if end is not None else len(hay))
                if found < 0 and end is None:
                    found = hay.find(needle, 0, start)
        if found < 0:
            return ""
        if countvar is not None:
            if isinstance(countvar, Variable):
                countvar.set(size)
            else:
                _setvar(countvar, size)
        return self._idx(found)

    def _t_edit(self, sub, *a):
        if sub == "modified":
            if a:
                self._mod = _bool(a[0])
                return ""
            return self._mod
        return ""

    def _t_window(self, sub, *a):
        if sub == "create":
            return self._wcreate(a[0], **_opts(a[1:]))
        if sub == "names":
            return tuple(self._wins)
        if sub in ("configure", "cget"):
            return ""
        raise TclError('bad window option "%s"' % sub)

    def _wcreate(self, index, window=None, create=None, **kw):
        w = window if isinstance(window, Misc) else _ids.get(str(window))
        if w is None:
            _warn("Text.window_create create=")
            return ""
        pos = min(self._off(index), len(self._v))
        self._t_insert(pos, "￼", ())
        w._forget()
        w._geo = ["text", {}, self]
        self._wins[w._w] = [[pos], w]
        self._touch()
        return w._w

    def _unwin(self, w):
        self._wins.pop(w._w, None)
        self._touch()

    def _t_image(self, sub, *a):
        _warn("картинки в Text")
        return ""

    def _t_dump(self, *a):
        _warn("Text.dump")
        return ()

    def _t_peer(self, *a):
        _warn("Text.peer")
        return ""

    def insert(self, index, chars, *args):
        return self._tk("insert", index, chars, *args)

    def delete(self, index1, index2=None):
        return self._tk("delete", index1, index2)

    def replace(self, index1, index2, chars, *args):
        return self._tk("replace", index1, index2, chars, *args)

    def get(self, index1, index2=None):
        return self._tk("get", index1, index2)

    def index(self, index):
        return str(self._tk("index", index))

    def compare(self, index1, op, index2):
        return getboolean(self._tk("compare", index1, op, index2))

    def see(self, index):
        return self._tk("see", index)

    def search(self, pattern, index, stopindex=None, forwards=None, backwards=None, exact=None, regexp=None,
               nocase=None, count=None, elide=None):
        args = []
        for flag, on in (("-forwards", forwards), ("-backwards", backwards), ("-exact", exact),
                         ("-regexp", regexp), ("-nocase", nocase), ("-elide", elide)):
            if on:
                args.append(flag)
        if count is not None:
            args.extend(["-count", count])
        if stopindex is not None:
            args.append(stopindex)
        return str(self._tk("search", pattern, index, *args))

    def tag_add(self, tagName, index1, *args):
        return self._tk("tag", "add", tagName, index1, *args)

    def tag_remove(self, tagName, index1, index2=None):
        return self._tk("tag", "remove", tagName, index1, index2)

    def tag_ranges(self, tagName):
        r = self._tk("tag", "ranges", tagName)
        return tuple(r) if r else ()

    def tag_nextrange(self, tagName, index1, index2=None):
        r = self._tk("tag", "nextrange", tagName, index1, index2)
        return tuple(r) if r else ()

    def tag_prevrange(self, tagName, index1, index2=None):
        r = self._tk("tag", "prevrange", tagName, index1, index2)
        return tuple(r) if r else ()

    def tag_names(self, index=None):
        r = self._tk("tag", "names", index)
        return tuple(r) if r else ()

    def tag_configure(self, tagName, cnf=None, **kw):
        if isinstance(cnf, str):
            return self._tk("tag", "configure", tagName, "-" + cnf)
        if cnf:
            kw = _merge(cnf, kw)
        args = []
        for k in kw:
            args.extend(["-" + k, kw[k]])
        return self._tk("tag", "configure", tagName, *args) or None

    tag_config = tag_configure

    def tag_cget(self, tagName, option):
        return self._tk("tag", "cget", tagName, option)

    def tag_delete(self, first_tag_name, *tagNames):
        return self._tk("tag", "delete", first_tag_name, *tagNames)

    def tag_raise(self, tagName, aboveThis=None):
        return self._tk("tag", "raise", tagName, aboveThis)

    def tag_lower(self, tagName, belowThis=None):
        return self._tk("tag", "lower", tagName, belowThis)

    def tag_bind(self, tagName, sequence, func, add=None):
        return self._tag_bind(tagName, sequence, func, add)

    def tag_unbind(self, tagName, sequence, funcid=None):
        return self._tag_unbind(tagName, sequence, funcid)

    def mark_set(self, markName, index):
        return self._tk("mark", "set", markName, index)

    def mark_unset(self, *markNames):
        return self._tk("mark", "unset", *markNames)

    def mark_names(self):
        return tuple(self._tk("mark", "names"))

    def mark_gravity(self, markName, direction=None):
        return self._tk("mark", "gravity", markName, direction) if direction else self._tk("mark", "gravity",
                                                                                                markName)

    def mark_next(self, index):
        return self._tk("mark", "next", index) or None

    def mark_previous(self, index):
        return self._tk("mark", "previous", index) or None

    def yview(self, *args):
        return self._tk("yview", *args)

    def yview_moveto(self, fraction):
        return self._tk("yview", "moveto", fraction)

    def yview_scroll(self, number, what):
        return self._tk("yview", "scroll", number, what)

    def yview_pickplace(self, *what):
        return self._tk("see", what[-1])

    def xview(self, *args):
        return self._tk("xview", *args)

    xview_moveto = xview_scroll = scan_mark = scan_dragto = _noop()

    def dlineinfo(self, index):
        return self._tk("dlineinfo", index)

    def bbox(self, index):
        return self._tk("bbox", index)

    def count(self, index1, index2, *args, return_ints=False):
        r = self._tk("count", index1, index2, *args)
        if len(r) == 1:
            return r[0] if return_ints else r
        return r

    def edit_modified(self, arg=None):
        if arg is None:
            return self._tk("edit", "modified")
        return self._tk("edit", "modified", arg)

    edit_reset = edit_separator = edit_undo = edit_redo = _noop("")

    def edit(self, *args):
        return self._tk("edit", *args)

    def window_create(self, index, cnf=None, **kw):
        if cnf:
            kw = _merge(cnf, kw)
        return self._wcreate(index, **kw)

    def window_names(self):
        return tuple(self._wins)

    window_cget = window_configure = window_config = _noop("")
    image_create = image_cget = image_configure = image_names = _stub("картинки в Text", "")
    dump = _stub("Text.dump", ())
    peer_create = peer_names = _stub("Text.peer", ())

    def _js(self, v):
        pass

    def _jsel(self, d):
        if "ss" not in d or d.get("sv") != self._ver or self in _tdirty:
            return
        ss, se = d["ss"], d["se"]
        sel = self._tags["sel"][0]
        cur = (sel[0][0], sel[-1][1]) if sel else None
        ins = self._marks["insert"][0]
        if ss == se:
            if cur is None and ins == ss:
                return
            self._tags["sel"][0] = []
        else:
            if cur == (ss, se) and ins in (ss, se):
                return
            self._tags["sel"][0] = [[ss, se]]
            m = self._marks.setdefault("tk::anchor", [ss, "left"])
            m[0] = ss if d.get("sd") != "b" else se
        self._marks["insert"][0] = min(se if d.get("sd") != "b" else ss, len(self._v))
        self._tchg.add("sel")

    def _setview(self, d):
        old = (self._view.get("top"), self._view.get("rows"))
        for k in ("top", "rows", "lh", "cw", "px", "py", "lines"):
            if k in d:
                self._view[k] = d[k]
        if (self._view.get("top"), self._view.get("rows")) != old:
            self._yscroll()

    def _snap(self):
        self._p["text"] = self._v
        self._p["tags"] = dict((n, _flat(self._tags[n][0])) for n in self._tags)
        self._p["tcfg"] = dict((n, self._tags[n][1]) for n in self._tags)
        self._p["torder"] = list(self._torder)
        self._p.update(self._selins())
        self._p["wins"] = self._winmap()

    def _selins(self):
        sel = self._tags["sel"][0]
        return {"sel": [sel[0][0], sel[-1][1]] if sel else None, "ins": self._marks["insert"][0], "ver": self._ver}

    def _winmap(self):
        return dict((self._wins[n][1]._id, self._wins[n][0][0]) for n in self._wins)

    def _out(self):
        ops = []
        p = {}
        size = 0
        for e in self._edits:
            size += e[1] + len(e[2])
        if self._full or size > max(4096, len(self._v)):
            self._full = False
            p["text"] = self._v
            p["tags"] = dict((n, _flat(self._tags[n][0])) for n in self._tags)
            self._tchg = set()
        elif self._edits:
            ops.append(["te", self._id, self._edits])
        self._edits = []
        if self._tchg:
            p["tags"] = dict((n, _flat(self._tags[n][0]) if n in self._tags else None) for n in self._tchg)
            self._tchg = set()
        if self._cchg:
            self._cchg = False
            p["tcfg"] = dict((n, self._tags[n][1]) for n in self._tags)
            p["torder"] = list(self._torder)
        p.update(self._selins())
        if self._wins or self._p.get("wins"):
            p["wins"] = self._winmap()
        self._p["ver"] = self._ver
        ops.append(["c", self._id, p])
        if self._yv is not None:
            ops.append(["yv", self._id, self._yv])
            self._yv = None
        if self._seeoff is not None:
            ops.append(["see", self._id, self._seeoff])
            self._seeoff = None
        return ops


def _txc(*seqs):
    def deco(fn):
        b = _class_b.setdefault("Text", {})
        for seq in seqs:
            b.setdefault(seq, []).append(fn)
        return fn
    return deco


def _txsel(w):
    r = w._tags["sel"][0]
    return (r[0][0], r[-1][1]) if r else None


def _txdelsel(w):
    if _txsel(w) is None:
        return False
    w.delete("sel.first", "sel.last")
    return True


def _txins(w, s):
    if w._o.get("state") == "disabled":
        return
    r = _txsel(w)
    if r is not None and r[0] <= w._marks["insert"][0] <= r[1]:
        w.delete("sel.first", "sel.last")
    w.insert("insert", s)
    w.see("insert")


@_txc("<KeyPress>")
def _tx_key(e):
    c = e.char
    if len(c) == 1 and c >= " " and c != "\x7f" and not e.state & (4 | 8 | 32):
        _txins(e.widget, c)


@_txc("<Return>", "<KP_Enter>")
def _tx_return(e):
    _txins(e.widget, "\n")


@_txc("<Tab>")
def _tx_tab(e):
    if e.widget._o.get("state") != "disabled":
        _txins(e.widget, "\t")
    return "break"


@_txc("<Shift-Tab>")
def _tx_stab(e):
    return "break"


@_txc("<BackSpace>")
def _tx_bs(e):
    w = e.widget
    if not _txdelsel(w) and w.compare("insert", "!=", "1.0"):
        w.delete("insert-1c")
    w.see("insert")


@_txc("<Delete>")
def _tx_del(e):
    w = e.widget
    if not _txdelsel(w) and w.compare("insert", "<", "end-1c"):
        w.delete("insert")
    w.see("insert")


def _txgo(w, idx, extend):
    new = w._off(idx)
    if extend:
        if _txsel(w) is None or "tk::anchor" not in w._marks:
            w._marks["tk::anchor"] = [w._marks["insert"][0], "left"]
        a = w._marks["tk::anchor"][0]
        w._tags["sel"][0] = [[min(a, new), max(a, new)]] if a != new else []
    else:
        w._tags["sel"][0] = []
    w._tchg.add("sel")
    w.mark_set("insert", w._idx(min(new, len(w._v))))
    w.see("insert")


def _txword(w, back):
    t = w._v
    o = w._marks["insert"][0]
    if back:
        while o > 0 and not _isword(t[o - 1]):
            o -= 1
        while o > 0 and _isword(t[o - 1]):
            o -= 1
    else:
        while o < len(t) and not _isword(t[o]):
            o += 1
        while o < len(t) and _isword(t[o]):
            o += 1
    return w._idx(o)


def _txrows(w):
    return max(1, int(w._geom()[1]) - 1)


_TXMOVES = {"Left": lambda w: "insert-1c", "Right": lambda w: "insert+1c", "Up": lambda w: "insert-1l",
            "Down": lambda w: "insert+1l", "Home": lambda w: "insert linestart", "End": lambda w: "insert lineend",
            "Prior": lambda w: "insert-%dl" % _txrows(w), "Next": lambda w: "insert+%dl" % _txrows(w),
            "Control-Home": lambda w: "1.0", "Control-End": lambda w: "end-1c",
            "Control-Left": lambda w: _txword(w, True), "Control-Right": lambda w: _txword(w, False)}


def _txmove(spec, extend):
    def f(e):
        _txgo(e.widget, _TXMOVES[spec](e.widget), extend)
    return f


for _k in _TXMOVES:
    _txc("<%s>" % _k)(_txmove(_k, False))
    _txc("<Shift-%s>" % _k)(_txmove(_k, True))


@_txc("<<Copy>>")
def _tx_copy(e):
    w = e.widget
    r = _txsel(w)
    if r is not None:
        w.clipboard_clear()
        w.clipboard_append(w.get("sel.first", "sel.last"))


@_txc("<<Cut>>")
def _tx_cut(e):
    w = e.widget
    if _txsel(w) is not None:
        _tx_copy(e)
        w.delete("sel.first", "sel.last")


@_txc("<<Paste>>")
def _tx_paste(e):
    w = e.widget
    try:
        s = w.clipboard_get()
    except TclError:
        return
    _txdelsel(w)
    w.insert("insert", s)
    w.see("insert")


@_txc("<<Clear>>")
def _tx_clear(e):
    _txdelsel(e.widget)


@_txc("<<SelectAll>>")
def _tx_all(e):
    e.widget.tag_add("sel", "1.0", "end")


@_txc("<<SelectNone>>")
def _tx_none(e):
    e.widget.tag_remove("sel", "1.0", "end")


class Checkbutton(Widget):
    _kind = "Checkbutton"
    _chars = True

    def _init(self):
        self._o["onvalue"] = 1
        self._o["offvalue"] = 0

    def _ready(self):
        if self._var is None:
            self._link("_var", IntVar())

    def _o_variable(self, v):
        self._link("_var", v)

    def _o_onvalue(self, v):
        if self._var is not None:
            self._sync(self._var)

    _o_offvalue = _o_onvalue

    def _o_indicatoron(self, v):
        self._prop("ind", 1 if _bool(v) else 0)

    def _sync(self, var):
        if var is self._var:
            self._prop("on", 1 if _ts(var._value) == _ts(self._o["onvalue"]) else 0)
        if var is self._tvar:
            self._prop("text", str(var._value))

    def _js(self, v):
        self._p["on"] = 1 if v else 0
        if self._var is not None:
            self._var._store(self._o["onvalue"] if v else self._o["offvalue"], self)

    def select(self):
        self._var.set(self._o["onvalue"])

    def deselect(self):
        self._var.set(self._o["offvalue"])

    def toggle(self):
        if _ts(self._var._value) == _ts(self._o["onvalue"]):
            self.deselect()
        else:
            self.select()

    def invoke(self):
        self.toggle()
        c = self._o.get("command")
        if c:
            return c()


_radio = []


class Radiobutton(Widget):
    _kind = "Radiobutton"
    _chars = True

    def _ready(self):
        if self._var is None:
            if not _radio:
                _radio.append(StringVar(name="selectedButton"))
            self._link("_var", _radio[0])

    def _o_variable(self, v):
        self._link("_var", v)

    def _o_value(self, v):
        if self._var is not None:
            self._sync(self._var)

    def _sync(self, var):
        if var is self._var:
            self._prop("group", _sid + var._name)
            self._prop("on", 1 if _ts(var._value) == _ts(self._o.get("value", "")) else 0)
        if var is self._tvar:
            self._prop("text", str(var._value))

    def _js(self, v):
        if v and self._var is not None:
            self._p["on"] = 1
            self._var._store(self._o.get("value", ""), self)

    def select(self):
        self._var.set(self._o.get("value", ""))

    def deselect(self):
        self._var.set("")

    def invoke(self):
        self.select()
        c = self._o.get("command")
        if c:
            return c()


class Scale(Widget):
    _kind = "Scale"

    def _init(self):
        self._v = 0.0
        self._p.update({"from": 0, "to": 100, "res": 1, "orient": "vertical", "showvalue": 1})

    def _o_from(self, v):
        self._prop("from", float(v))

    def _o_to(self, v):
        self._prop("to", float(v))

    def _o_res(self, v):
        self._prop("res", float(v))

    def _o_variable(self, v):
        self._link("_var", v)

    def _ready(self):
        if self._var is None:
            self._v = float(self._p["from"])
            self._p["value"] = self._v

    def _out(self, v):
        r = float(self._p.get("res", 1))
        if r <= 0:
            return v
        v = round(v / r) * r
        if r == int(r):
            return int(v)
        d = len(str(r).split(".")[1])
        return round(v, d)

    def _sync(self, var):
        if var is self._var:
            try:
                self._v = float(var._value)
            except (TypeError, ValueError):
                self._v = 0.0
            self._prop("value", self._v)

    def _js(self, v):
        self._v = float(v)
        self._p["value"] = self._v
        if self._var is not None:
            self._var._store(self._out(self._v), self)

    def get(self):
        return self._out(self._v)

    def set(self, value):
        a, b = float(self._p["from"]), float(self._p["to"])
        v = max(min(a, b), min(max(a, b), float(value)))
        self._v = v
        self._prop("value", v)
        if self._var is not None:
            self._var._store(self._out(v), self)
        self._cmd(None)

    def _cmd(self, x):
        c = self._o.get("command")
        if c:
            _call(c, str(self._out(self._v)))


class Listbox(Widget):
    _kind = "Listbox"
    _chars = True

    def _init(self):
        self._items = []
        self._sel = []
        self._p["items"] = []
        self._p["sel"] = []

    def _o_listvariable(self, v):
        self._link("_var", v)

    def _sync(self, var):
        if var is self._var:
            self._items = [str(x) for x in _aslist(var._value)]
            self._sel = [i for i in self._sel if i < len(self._items)]
            self._prop("items", list(self._items))
            self._prop("sel", list(self._sel))

    def _upd(self):
        self._prop("items", list(self._items))
        self._prop("sel", list(self._sel))
        if self._var is not None:
            self._var._store(tuple(self._items), self)

    def _i(self, i, end=0):
        if isinstance(i, (tuple, list)) and len(i) == 1:
            i = i[0]
        if i == "end":
            return len(self._items) - 1 + end
        if i in ("active", "anchor"):
            return self._sel[0] if self._sel else 0
        if isinstance(i, str) and i[:1] == "@":
            return self.nearest(_int(i[1:].split(",")[-1]))
        try:
            return _int(i)
        except (TypeError, ValueError):
            raise TclError('bad listbox index "%s"' % (i,))

    def insert(self, index, *elements):
        i = max(0, min(len(self._items), self._i(index, 1)))
        n = len(elements)
        self._items = self._items[:i] + [str(e) for e in elements] + self._items[i:]
        self._sel = [s + n if s >= i else s for s in self._sel]
        self._upd()

    def delete(self, first, last=None):
        a = self._i(first)
        b = a if last is None else self._i(last)
        if b < a:
            return
        self._items = self._items[:a] + self._items[b + 1:]
        n = b - a + 1
        self._sel = [s - n if s > b else s for s in self._sel if s < a or s > b]
        self._upd()

    def get(self, first, last=None):
        a = self._i(first)
        if last is None:
            return self._items[a] if 0 <= a < len(self._items) else ""
        return tuple(self._items[a:self._i(last) + 1])

    def size(self):
        return len(self._items)

    def index(self, index):
        return self._i(index, 1)

    def curselection(self):
        return tuple(sorted(self._sel))

    def selection_set(self, first, last=None):
        a = self._i(first)
        b = a if last is None else self._i(last)
        for i in range(a, b + 1):
            if 0 <= i < len(self._items) and i not in self._sel:
                self._sel.append(i)
        self._sel.sort()
        self._prop("sel", list(self._sel))

    select_set = selection_set

    def selection_clear(self, first, last=None):
        a = self._i(first)
        b = a if last is None else self._i(last)
        self._sel = [i for i in self._sel if i < a or i > b]
        self._prop("sel", list(self._sel))

    select_clear = selection_clear

    def selection_includes(self, index):
        return self._i(index) in self._sel

    select_includes = selection_includes

    def see(self, index):
        _op("ls", self._id, self._i(index))

    activate = selection_anchor = select_anchor = _noop()
    yview = xview = yview_moveto = yview_scroll = xview_moveto = scan_mark = scan_dragto = _noop()

    def nearest(self, y):
        lh = 18
        return max(0, min(len(self._items) - 1, _int(y) // lh))

    itemconfigure = itemconfig = _stub("Listbox.itemconfigure")
    itemcget = _stub("Listbox.itemcget", "")

    def _js(self, v):
        self._sel = [_int(x) for x in v]
        self._p["sel"] = list(self._sel)

    def _selev(self, x):
        _virtual(self, "<<ListboxSelect>>")


class Scrollbar(Widget):
    _kind = "Scrollbar"
    set = activate = _noop()
    get = _noop((0.0, 1.0))
    fraction = _noop(0.0)
    delta = _noop(0.0)
    identify = _noop("")


class Canvas(Widget):
    _kind = "Canvas"
    _ITEM = {"fill", "outline", "width", "text", "font", "anchor", "dash", "start", "extent", "style", "state",
             "justify", "capstyle"}
    _IQUIET = {"activefill", "activeoutline", "activewidth", "disabledfill", "disabledoutline", "disabledwidth",
               "joinstyle", "outlinestipple", "stipple", "offset", "splinesteps", "activedash", "disableddash",
               "dashoffset", "activestipple", "outlineoffset", "activeoutlinestipple"}

    def _init(self):
        self._items = {}
        self._order = []
        self._itags = {}
        self._tb = {}
        self._n = 0
        self._cur = None
        self._sxy = (0, 0)
        self._vf = [None, None]

    def _o_scrollregion(self, v):
        r = self._getints(v)
        self._prop("sr", list(r) if len(r) == 4 else [0, 0, 0, 0])

    def _unwin(self, w):
        for i in [i for i in self._order if self._items[i][0] == "window" and self._items[i][2].get("win") == w._id]:
            del self._items[i]
            self._order.remove(i)
            _op("x", self._id, [i])

    def _iopts(self, t, kw, i):
        o = {}
        for k in kw:
            v = kw[k]
            if k in ("tags", "tag"):
                self._itags[i] = list(v) if isinstance(v, (tuple, list)) else str(v).split()
            elif k == "image" and t == "image":
                im = _images.get(str(v))
                o["img"] = str(v)
                o["iw"], o["ih"] = im._wh if im else (0, 0)
            elif k == "width" and t == "text":
                _warn("Canvas text width")
            elif k in self._ITEM:
                if k == "font":
                    v = _font(v)
                elif k == "width":
                    v = _px(v)
                elif k == "text":
                    v = str(v)
                elif k == "dash":
                    v = list(v) if isinstance(v, (tuple, list)) else [_int(x) for x in str(v).split()] or [4]
                elif k in ("start", "extent"):
                    v = float(v)
                elif v is not None:
                    v = str(v)
                o[k] = v
            elif k not in self._IQUIET:
                _warn("Canvas %s(%s=...)" % (t, k))
        return o

    def _create(self, t, args, kw):
        xy = _flat(args)
        need = 2 if t in ("text", "image") else 4
        if len(xy) < need:
            raise TclError("wrong # coordinates")
        self._n += 1
        i = self._n
        o = self._iopts(t, kw, i)
        self._items[i] = [t, xy, o]
        self._order.append(i)
        _op("i", self._id, i, t, xy, o)
        return i

    def create_line(self, *args, **kw):
        return self._create("line", args, kw)

    def create_rectangle(self, *args, **kw):
        return self._create("rectangle", args, kw)

    def create_oval(self, *args, **kw):
        return self._create("oval", args, kw)

    def create_polygon(self, *args, **kw):
        return self._create("polygon", args, kw)

    def create_arc(self, *args, **kw):
        return self._create("arc", args, kw)

    def create_text(self, *args, **kw):
        return self._create("text", args, kw)

    create_bitmap = _stub("bitmap", 0)

    def create_image(self, *args, **kw):
        return self._create("image", args[:1] if isinstance(args[0], (tuple, list)) else args[:2], kw)

    def create_window(self, *args, **kw):
        w = kw.pop("window", None)
        xy = _flat(args)[:2]
        self._n += 1
        i = self._n
        o = {"anchor": str(kw.pop("anchor", "center"))}
        for k in ("width", "height"):
            if kw.get(k):
                o[k] = _px(kw.pop(k))
        if "tags" in kw or "tag" in kw:
            v = kw.pop("tags", kw.pop("tag", None))
            self._itags[i] = list(v) if isinstance(v, (tuple, list)) else str(v).split()
        if kw.pop("state", None) == "hidden":
            o["state"] = "hidden"
        if w is not None:
            w._forget()
            w._geo = ["canvas", {}, self]
            o["win"] = w._id
        self._items[i] = ["window", xy, o]
        self._order.append(i)
        _op("i", self._id, i, "window", xy, o)
        return i

    def _find(self, tag):
        if tag is None:
            return []
        if isinstance(tag, int):
            return [tag] if tag in self._items else []
        s = str(tag)
        if s == "all":
            return list(self._order)
        if s.isdigit():
            return [int(s)] if int(s) in self._items else []
        if s == "current":
            return [self._cur] if self._cur in self._items else []
        return [i for i in self._order if s in self._itags.get(i, ())]

    def delete(self, *args):
        gone = []
        for a in args:
            for i in self._find(a):
                if i in self._items:
                    del self._items[i]
                    self._order.remove(i)
                    self._itags.pop(i, None)
                    gone.append(i)
        if gone:
            _op("x", self._id, None if not self._items else gone)

    def coords(self, tagOrId, *args):
        ids = self._find(tagOrId)
        if not ids:
            return []
        if not args:
            return [float(x) for x in self._items[ids[0]][1]]
        xy = _flat(args)
        self._items[ids[0]][1] = xy
        _op("i", self._id, ids[0], self._items[ids[0]][0], xy, None)

    def move(self, tagOrId, xAmount, yAmount):
        for i in self._find(tagOrId):
            it = self._items[i]
            it[1] = [v + (xAmount if k % 2 == 0 else yAmount) for k, v in enumerate(it[1])]
            _op("i", self._id, i, it[0], it[1], None)

    def moveto(self, tagOrId, x="", y=""):
        for i in self._find(tagOrId):
            b = self.bbox(i)
            if b:
                self.move(i, float(x) - b[0] if x != "" else 0, float(y) - b[1] if y != "" else 0)

    def scale(self, tagOrId, xOrigin, yOrigin, xScale, yScale):
        for i in self._find(tagOrId):
            it = self._items[i]
            it[1] = [(xOrigin + (v - xOrigin) * xScale) if k % 2 == 0 else (yOrigin + (v - yOrigin) * yScale)
                     for k, v in enumerate(it[1])]
            _op("i", self._id, i, it[0], it[1], None)

    def itemconfigure(self, tagOrId, cnf=None, **kw):
        if cnf:
            kw = _merge(cnf, kw)
        ids = self._find(tagOrId)
        if not kw:
            return dict((k, (k, "", "", "", v)) for k, v in self._items[ids[0]][2].items()) if ids else {}
        for i in ids:
            it = self._items[i]
            o = self._iopts(it[0], kw, i)
            it[2].update(o)
            _op("i", self._id, i, it[0], None, o)

    itemconfig = itemconfigure

    def itemcget(self, tagOrId, option):
        ids = self._find(tagOrId)
        return self._items[ids[0]][2].get(option, "") if ids else ""

    def type(self, tagOrId):
        ids = self._find(tagOrId)
        return self._items[ids[0]][0] if ids else None

    def gettags(self, tagOrId):
        ids = self._find(tagOrId)
        return tuple(self._itags.get(ids[0], ())) if ids else ()

    def addtag_withtag(self, newtag, tagOrId):
        for i in self._find(tagOrId):
            t = self._itags.setdefault(i, [])
            if newtag not in t:
                t.append(newtag)

    def addtag_all(self, newtag):
        self.addtag_withtag(newtag, "all")

    def dtag(self, tagOrId, tagToDelete=None):
        for i in self._find(tagOrId):
            t = self._itags.get(i, [])
            if (tagToDelete or tagOrId) in t:
                t.remove(tagToDelete or tagOrId)

    def find_all(self):
        return tuple(self._order)

    def find_withtag(self, tagOrId):
        return tuple(self._find(tagOrId))

    def _box1(self, i):
        t, xy, o = self._items[i]
        if t == "image":
            ww, hh = o.get("iw", 0), o.get("ih", 0)
            a = o.get("anchor", "center")
            x = xy[0] - (ww / 2 if a in ("center", "n", "s") else ww if "e" in a else 0)
            y = xy[1] - (hh / 2 if a in ("center", "e", "w") else hh if "s" in a else 0)
            return [x, y, x + ww, y + hh]
        if t == "window":
            w = _ids.get(o.get("win"))
            px = _fontpx(w._o.get("font")) if w is not None else 13
            text = str(w._o.get("text", "")) if w is not None else ""
            ww = o.get("width") or len(text) * px * 0.6 + 6
            hh = o.get("height") or px * 1.4 + 4
            a = o.get("anchor", "center")
            x = xy[0] - (ww / 2 if a in ("center", "n", "s") else ww if "e" in a else 0)
            y = xy[1] - (hh / 2 if a in ("center", "e", "w") else hh if "s" in a else 0)
            return [x, y, x + ww, y + hh]
        if t == "text":
            f = o.get("font")
            size = 10
            if isinstance(f, list) and len(f) > 1:
                try:
                    size = abs(float(f[1]))
                except ValueError:
                    pass
            lines = str(o.get("text", "")).split("\n")
            w = max(len(s) for s in lines) * size * 0.8
            h = len(lines) * size * 1.6
            a = o.get("anchor", "center")
            x = xy[0] - (w / 2 if a in ("center", "n", "s") else w if "e" in a else 0)
            y = xy[1] - (h / 2 if a in ("center", "e", "w") else h if "s" in a else 0)
            return [x, y, x + w, y + h]
        xs, ys = xy[0::2], xy[1::2]
        d = float(o.get("width", 1)) / 2
        return [min(xs) - d, min(ys) - d, max(xs) + d, max(ys) + d]

    def bbox(self, *args):
        boxes = []
        for a in args:
            for i in self._find(a):
                boxes.append(self._box1(i))
        if not boxes:
            return None
        return (int(min(b[0] for b in boxes)), int(min(b[1] for b in boxes)),
                int(max(b[2] for b in boxes) + 0.999), int(max(b[3] for b in boxes) + 0.999))

    def find_overlapping(self, x1, y1, x2, y2):
        out = []
        for i in self._order:
            b = self._box1(i)
            if b[0] <= x2 and b[2] >= x1 and b[1] <= y2 and b[3] >= y1:
                out.append(i)
        return tuple(out)

    def find_enclosed(self, x1, y1, x2, y2):
        out = []
        for i in self._order:
            b = self._box1(i)
            if b[0] > x1 and b[2] < x2 and b[1] > y1 and b[3] < y2:
                out.append(i)
        return tuple(out)

    def find_closest(self, x, y, halo=None, start=None):
        best, bd = None, None
        for i in self._order:
            b = self._box1(i)
            dx = max(b[0] - x, 0, x - b[2])
            dy = max(b[1] - y, 0, y - b[3])
            d = dx * dx + dy * dy
            if bd is None or d <= bd:
                best, bd = i, d
        return (best,) if best is not None else ()

    def tag_raise(self, tagOrId, aboveThis=None):
        for i in self._find(tagOrId):
            self._order.remove(i)
            self._order.append(i)
            _op("z", self._id, i, 1)

    def tag_lower(self, tagOrId, belowThis=None):
        for i in reversed(self._find(tagOrId)):
            self._order.remove(i)
            self._order.insert(0, i)
            _op("z", self._id, i, 0)

    lift = tkraise = tag_raise
    lower = tag_lower

    def tag_bind(self, tagOrId, sequence=None, func=None, add=None):
        key = (tagOrId, sequence)
        if func is None:
            return key in self._tb
        if add is True or add and str(add)[:1] == "+":
            self._tb.setdefault(key, []).append(func)
        else:
            self._tb[key] = [func]
        _kinds_dirty[0] = True
        return _fid(func, sequence)

    def tag_unbind(self, tagOrId, sequence, funcid=None):
        self._tb.pop((tagOrId, sequence), None)
        _kinds_dirty[0] = True

    def _item_ev(self, d, kind, e):
        i = d.get("i")
        self._cur = i
        if i is None or not self._tb:
            return None
        tags = self._itags.get(i, [])
        r = None
        for key in list(self._tb):
            tag, seq = key
            p = _parse(seq)
            if not p or _score(p, kind, d) < 0:
                continue
            if tag == i or str(tag) == str(i) or tag == "all" or tag in tags:
                if _run(self._tb[key], e) == "break":
                    r = "break"
        return r

    def canvasx(self, screenx, gridspacing=None):
        return float(screenx) + self._sxy[0]

    def canvasy(self, screeny, gridspacing=None):
        return float(screeny) + self._sxy[1]

    def xview_moveto(self, fraction):
        self._vf[0] = float(fraction)
        _op("cs", self._id, "x", "moveto", float(fraction))

    def yview_moveto(self, fraction):
        self._vf[1] = float(fraction)
        _op("cs", self._id, "y", "moveto", float(fraction))

    def xview_scroll(self, number, what):
        _op("cs", self._id, "x", "scroll", _int(number), str(what))

    def yview_scroll(self, number, what):
        _op("cs", self._id, "y", "scroll", _int(number), str(what))

    def yview(self, *args):
        if not args:
            return (0.0, 1.0)
        if args[0] == "moveto":
            self.yview_moveto(args[1])
        elif args[0] == "scroll":
            self.yview_scroll(args[1], args[2])

    def xview(self, *args):
        if not args:
            return (0.0, 1.0)
        if args[0] == "moveto":
            self.xview_moveto(args[1])
        elif args[0] == "scroll":
            self.xview_scroll(args[1], args[2])

    scan_mark = scan_dragto = _noop()
    postscript = _stub("Canvas.postscript", "")

    def focus(self, *a):
        Misc.focus_set(self)


class Menu(Widget):
    _kind = "Menu"
    _T = {"command": "c", "cascade": "m", "separator": "s", "checkbutton": "k", "radiobutton": "r"}

    def _init(self):
        self._items = []

    def _jsitem(self, it):
        t = it["t"]
        d = {"t": t, "label": str(it.get("label", ""))}
        if t == "m" and it.get("menu") is not None:
            m = it["menu"]
            d["sub"] = m._id if isinstance(m, Misc) else str(m)
        if t == "k":
            d["on"] = 1 if _ts(it["var"]._value) == _ts(it.get("onvalue", 1)) else 0
        if t == "r":
            d["on"] = 1 if _ts(it["var"]._value) == _ts(it.get("value", it.get("label", ""))) else 0
        if it.get("state"):
            d["state"] = str(it["state"])
        if it.get("accelerator"):
            d["acc"] = str(it["accelerator"])
        if it.get("image"):
            d["img"] = str(it["image"])
        return d

    def _push(self):
        self._prop("items", [self._jsitem(it) for it in self._items])

    def _sync(self, var):
        self._push()

    def _mk(self, t, kw):
        it = {"t": t}
        for k in kw:
            if k in ("label", "command", "menu", "variable", "onvalue", "offvalue", "value", "state",
                     "accelerator", "image"):
                it[k] = kw[k]
            elif k not in ("underline", "compound", "font", "foreground", "background", "activebackground",
                           "activeforeground", "selectcolor", "columnbreak", "hidemargin", "indicatoron",
                           "bitmap", "selectimage"):
                _warn("Menu(%s=...)" % k)
        if t in ("k", "r"):
            v = it.get("variable")
            if v is None:
                v = IntVar() if t == "k" else (_radio[0] if _radio else StringVar(name="selectedButton"))
                if t == "r" and not _radio:
                    _radio.append(v)
            if isinstance(v, str):
                v = _varnames.get(v) or StringVar(name=v)
            it["var"] = v
            if self not in v._w:
                v._w.append(self)
        return it

    def add(self, itemType, cnf=None, **kw):
        self.insert(len(self._items), itemType, cnf, **kw)

    def insert(self, index, itemType, cnf=None, **kw):
        if cnf:
            kw = _merge(cnf, kw)
        i = len(self._items) if index == "end" else max(0, min(len(self._items), _int(index)))
        self._items.insert(i, self._mk(self._T.get(itemType, "c"), kw))
        self._push()

    def add_command(self, cnf=None, **kw):
        self.add("command", cnf, **kw)

    def add_cascade(self, cnf=None, **kw):
        self.add("cascade", cnf, **kw)

    def add_separator(self, cnf=None, **kw):
        self.add("separator", cnf, **kw)

    def add_checkbutton(self, cnf=None, **kw):
        self.add("checkbutton", cnf, **kw)

    def add_radiobutton(self, cnf=None, **kw):
        self.add("radiobutton", cnf, **kw)

    def insert_command(self, index, cnf=None, **kw):
        self.insert(index, "command", cnf, **kw)

    def insert_cascade(self, index, cnf=None, **kw):
        self.insert(index, "cascade", cnf, **kw)

    def insert_separator(self, index, cnf=None, **kw):
        self.insert(index, "separator", cnf, **kw)

    def insert_checkbutton(self, index, cnf=None, **kw):
        self.insert(index, "checkbutton", cnf, **kw)

    def insert_radiobutton(self, index, cnf=None, **kw):
        self.insert(index, "radiobutton", cnf, **kw)

    def index(self, index):
        if index in ("end", "last"):
            return len(self._items) - 1 if self._items else None
        if index in ("active", "none"):
            return None
        if isinstance(index, int):
            return index
        s = str(index)
        if s.isdigit():
            return int(s)
        for i, it in enumerate(self._items):
            if str(it.get("label", "")) == s:
                return i
        for i, it in enumerate(self._items):
            if _glob(s, str(it.get("label", ""))):
                return i
        raise TclError('bad menu entry index "%s"' % s)

    def delete(self, index1, index2=None):
        if not self._items:
            return
        a = self.index(index1)
        b = a if index2 is None else self.index(index2)
        if a is None or b is None:
            return
        self._items = self._items[:a] + self._items[b + 1:]
        self._push()

    def entryconfigure(self, index, cnf=None, **kw):
        if cnf:
            kw = _merge(cnf, kw)
        i = self.index(index)
        it = self._items[i]
        if not kw:
            return dict((k, (k, "", "", "", v)) for k, v in it.items() if k != "t")
        new = self._mk(it["t"], kw)
        new.pop("t")
        it.update(new)
        self._push()

    entryconfig = entryconfigure

    def entrycget(self, index, option):
        return self._items[self.index(index)].get(option, "")

    def type(self, index):
        t = self._items[self.index(index)]["t"]
        for k in self._T:
            if self._T[k] == t:
                return k

    def invoke(self, index):
        return self._run(self.index(index))

    def _run(self, i):
        if i is None or not 0 <= i < len(self._items):
            return None
        it = self._items[i]
        if it.get("state") == "disabled":
            return None
        if it["t"] == "k":
            v = it["var"]
            on = it.get("onvalue", 1)
            v.set(it.get("offvalue", 0) if _ts(v._value) == _ts(on) else on)
        elif it["t"] == "r":
            it["var"].set(it.get("value", it.get("label", "")))
        c = it.get("command")
        if c:
            return _call(c)

    def _cmd(self, x):
        self._run(_int(x))

    def post(self, x, y):
        _op("P", self._id, x, y)

    def tk_popup(self, x, y, entry=""):
        self.post(x, y)

    unpost = activate = _noop()
    yposition = _noop(0)


class Menubutton(Button):
    _menu = None

    def _o_menu(self, v):
        self._menu = v

    def _cmd(self, x):
        if self._menu is not None and self._o.get("state") != "disabled":
            r = self._rect()
            self._menu.post(r[2], r[3] + r[1])


class _setit:
    def __init__(self, var, value, callback=None):
        self._var = var
        self._value = value
        self._callback = callback

    def __call__(self, *args):
        self._var.set(self._value)
        if self._callback is not None:
            self._callback(self._value, *args)


class _Combobox(Entry):
    _kind = "Combobox"

    def _init(self):
        Entry._init(self)
        self._p["items"] = []

    def _o_values(self, v):
        self._prop("items", [str(x) for x in _aslist(v)])

    def _o_state(self, v):
        v = str(v)
        self._prop("ro", 1 if v == "readonly" else 0)
        self._prop("state", "disabled" if v == "disabled" else "normal")

    def current(self, newindex=None):
        vals = self._p["items"]
        if newindex is None:
            return vals.index(self._v) if self._v in vals else -1
        self._put(vals[_int(newindex)])

    def set(self, value):
        self._put(str(value))

    def _selev(self, x):
        _virtual(self, "<<ComboboxSelected>>")


class _OMenu:
    def __init__(self, owner):
        self._owner = owner
        self._cmds = []

    def delete(self, index1, index2=None):
        self._cmds = []
        self._owner._prop("items", [])

    def add_command(self, label=None, command=None, **kw):
        self._cmds.append((str(label), command))
        self._owner._prop("items", [c[0] for c in self._cmds])

    entryconfigure = entryconfig = _stub("OptionMenu menu.entryconfigure")

    def index(self, index):
        return len(self._cmds) - 1 if index == "end" else _int(index)


class OptionMenu(_Combobox):
    def __init__(self, master, variable, value=None, *values, **kwargs):
        self._ocmd = kwargs.pop("command", None)
        vals = ([] if value is None else [value]) + list(values)
        _Combobox.__init__(self, master, textvariable=variable, values=vals, state="readonly", **kwargs)
        self._menu = _OMenu(self)

    def cget(self, key):
        if key == "menu":
            return self._menu
        return _Combobox.cget(self, key)

    def __getitem__(self, key):
        return self.cget(key)

    def _selev(self, x):
        for label, cmd in self._menu._cmds:
            if label == self._v and cmd is not None:
                _call(cmd)
                return
        if self._ocmd is not None:
            _call(self._ocmd, self._v)


class _Progressbar(Widget):
    _kind = "Progressbar"

    def _init(self):
        self._p.update({"value": 0.0, "max": 100.0})
        self._timer = None

    def _o_value(self, v):
        self._prop("value", float(v))

    def _o_max(self, v):
        self._prop("max", float(v))

    def _o_mode(self, v):
        self._prop("mode", str(v))

    def _o_variable(self, v):
        self._link("_var", v)

    def _sync(self, var):
        if var is self._var:
            try:
                self._prop("value", float(var._value))
            except (TypeError, ValueError):
                pass

    def cget(self, key):
        if key == "value":
            return self._p["value"]
        return Widget.cget(self, key)

    def __getitem__(self, key):
        return self.cget(key)

    def step(self, amount=1.0):
        v = self._p["value"] + float(amount)
        m = self._p["max"]
        if v >= m:
            v -= m
        if self._var is not None:
            self._var.set(v)
        else:
            self._prop("value", v)

    def start(self, interval=50):
        self.stop()
        if self._p.get("mode") == "indeterminate":
            self._prop("run", 1)
            return

        def tick():
            self.step()
            self._timer = self.after(interval, tick)

        self._timer = self.after(interval, tick)

    def stop(self):
        if self._timer:
            self.after_cancel(self._timer)
            self._timer = None
        if self._p.get("run"):
            self._prop("run", 0)


class _Separator(Widget):
    _kind = "Separator"


class _Notebook(Widget):
    _kind = "Notebook"
    _box = True

    def _init(self):
        self._tabs = []
        self._cur = 0

    def _lay(self):
        L = Misc._lay(self)
        L["n"] = [[t[0]._id, t[1]] for t in self._tabs if t[0]._alive]
        L["cur"] = self._cur
        return L

    def add(self, child, **kw):
        self.insert("end", child, **kw)

    def insert(self, pos, child, **kw):
        for t in self._tabs:
            if t[0] is child:
                if "text" in kw:
                    t[1] = str(kw["text"])
                _dirty_add(self)
                return
        child._forget()
        child._geo = ["nb", {}, self]
        i = len(self._tabs) if pos == "end" else self.index(pos)
        self._tabs.insert(i, [child, str(kw.get("text", ""))])
        _dirty_add(self)

    def index(self, tab_id):
        if tab_id == "end":
            return len(self._tabs)
        if tab_id == "current":
            return self._cur
        if isinstance(tab_id, int):
            return tab_id
        for i, t in enumerate(self._tabs):
            if t[0] is tab_id or str(t[0]) == str(tab_id):
                return i
        raise TclError("bad notebook tab")

    def select(self, tab_id=None):
        if tab_id is None:
            return str(self._tabs[self._cur][0]) if self._tabs else ""
        self._cur = self.index(tab_id)
        _dirty_add(self)
        _virtual(self, "<<NotebookTabChanged>>")

    def tab(self, tab_id, option=None, **kw):
        t = self._tabs[self.index(tab_id)]
        if "text" in kw:
            t[1] = str(kw["text"])
            _dirty_add(self)
        d = {"text": t[1], "state": "normal"}
        return d.get(option) if option else d

    def tabs(self):
        return tuple(str(t[0]) for t in self._tabs)

    def forget(self, tab_id):
        i = self.index(tab_id)
        child = self._tabs[i][0]
        del self._tabs[i]
        child._geo = None
        self._cur = max(0, min(self._cur, len(self._tabs) - 1))
        _dirty_add(self)

    hide = forget
    enable_traversal = _noop()

    def _selev(self, x):
        self._cur = _int(x)
        _virtual(self, "<<NotebookTabChanged>>")


class PanedWindow(Widget):
    _kind = "PanedWindow"
    _box = True

    def _init(self):
        self._panes = []
        self._p["orient"] = "horizontal"

    def _o_sashwidth(self, v):
        self._prop("sash", _px(v))

    _o_sashrelief = _o_sashpad = _o_sashcursor = _o_showhandle = _o_handlesize = _o_handlepad = _noop()
    _o_opaqueresize = _o_proxybackground = _o_proxyborderwidth = _o_proxyrelief = _noop()

    def _lay(self):
        L = Misc._lay(self)
        L["pw"] = [[p[0]._id, p[1]] for p in self._panes if p[0]._alive]
        return L

    def _popts(self, kw):
        o = {}
        for k in kw:
            v = kw[k]
            if k in ("minsize", "width", "height", "padx", "pady"):
                o[k] = _px(v) if v not in ("", None) else 0
            elif k == "weight":
                o[k] = _int(v)
            elif k == "hide":
                o[k] = 1 if _bool(v) else 0
            elif k in ("stretch", "sticky"):
                o[k] = str(v)
        return o

    def _pane(self, child):
        for p in self._panes:
            if p[0] is child or str(p[0]) == str(child):
                return p
        raise TclError("%s is not managed by %s" % (child, self))

    def add(self, child, **kw):
        before, after = kw.pop("before", None), kw.pop("after", None)
        for p in self._panes:
            if p[0] is child:
                p[1].update(self._popts(kw))
                _dirty_add(self)
                return
        child._forget()
        child._geo = ["pw", {}, self]
        ref = before if before is not None else after
        i = len(self._panes)
        for j, p in enumerate(self._panes):
            if ref is not None and (p[0] is ref or str(p[0]) == str(ref)):
                i = j + (1 if before is None else 0)
        self._panes.insert(i, [child, self._popts(kw)])
        _dirty_add(self)

    def remove(self, child):
        p = self._pane(child)
        self._panes.remove(p)
        p[0]._geo = None
        _dirty_add(self)

    forget = remove

    def panes(self):
        return tuple(p[0] for p in self._panes)

    def paneconfigure(self, tagOrId, cnf=None, **kw):
        p = self._pane(tagOrId)
        if cnf:
            kw = _merge(cnf, kw)
        if not kw:
            return dict(p[1])
        p[1].update(self._popts(kw))
        _dirty_add(self)

    paneconfig = paneconfigure

    def panecget(self, child, option):
        return self._pane(child)[1].get(option, "")

    def sash_coord(self, index):
        return (0, 0)

    def identify(self, x, y):
        return ""

    sash = sash_mark = sash_place = sash_dragto = proxy = proxy_coord = proxy_forget = proxy_place = _noop()


def _imgsize(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:4] == b"GIF8":
        return "image/gif", data[6] | data[7] << 8, data[8] | data[9] << 8
    i = data.find(b"<svg", 0, 4096)
    if i >= 0:
        # SVG, как в Tk 9: размер из width/height корня, иначе из viewBox
        head = data[i:data.find(b">", i) + 1].decode("utf-8", "replace")
        def attr(k):
            j = head.find(" " + k + "=")
            if j < 0:
                return None
            q = head[j + len(k) + 2]
            return head[j + len(k) + 3:head.find(q, j + len(k) + 3)]
        def num(s):
            s = (s or "").strip().replace("px", "")
            try:
                return float(s)
            except ValueError:
                return 0
        w, h = num(attr("width")), num(attr("height"))
        vb = (attr("viewBox") or "").replace(",", " ").split()
        if (not w or not h) and len(vb) == 4:
            w, h = w or num(vb[2]), h or num(vb[3])
        return "image/svg+xml", int(w or 16), int(h or 16)
    return None, 0, 0


class PhotoImage:
    _count = [0]

    def __init__(self, name=None, cnf=None, master=None, **kw):
        PhotoImage._count[0] += 1
        self.name = name or "pyimage%d" % PhotoImage._count[0]
        self._wh = (0, 0)
        self._url = ""
        self._o = {}
        _images[self.name] = self
        if cnf:
            kw = _merge(cnf, kw)
        if kw:
            self.configure(**kw)

    def configure(self, **kw):
        import binascii
        self._o.update(kw)
        data = kw.get("data")
        if kw.get("file"):
            with open(kw["file"], "rb") as f:
                data = f.read()
        elif isinstance(data, str):
            data = binascii.a2b_base64(data)
        if data:
            mime, w, h = _imgsize(data)
            if mime is None:
                _warn("формат картинки")
                return
            self._wh = (w, h)
            self._url = "data:%s;base64,%s" % (mime, binascii.b2a_base64(data).decode().replace("\n", ""))
        if kw.get("width") or kw.get("height"):
            self._wh = (_int(kw.get("width") or self._wh[0]), _int(kw.get("height") or self._wh[1]))
        self._send()

    config = configure

    def _send(self):
        _op("img", self.name, self._url, self._wh[0], self._wh[1])

    def cget(self, option):
        return self._o.get(option, "")

    __getitem__ = cget

    def width(self):
        return self._wh[0]

    def height(self):
        return self._wh[1]

    def __str__(self):
        return self.name

    def _derived(self, w, h):
        img = PhotoImage()
        img._url = self._url
        img._wh = (max(1, int(w)), max(1, int(h)))
        img._send()
        return img

    def copy(self):
        return self._derived(*self._wh)

    def zoom(self, x, y=""):
        y = x if y == "" else y
        return self._derived(self._wh[0] * x, self._wh[1] * y)

    def subsample(self, x, y=""):
        y = x if y == "" else y
        return self._derived(self._wh[0] // x, self._wh[1] // y)

    type = _noop("photo")
    blank = _noop()
    put = write = transparency_set = _stub("PhotoImage: пиксели")
    get = _stub("PhotoImage: пиксели", (0, 0, 0))
    transparency_get = _stub("PhotoImage: пиксели", False)


class BitmapImage(PhotoImage):
    __init__ = _stub("BitmapImage")

try:
    _kt.poll()
except OSError:
    pass

try:
    _sys.atexit(_bye)
except AttributeError:
    import atexit as _atexit
    _atexit.register(_bye)
