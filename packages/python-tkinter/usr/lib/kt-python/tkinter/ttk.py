from tkinter import *
from tkinter import _warn, _stub, _noop, _Combobox, _Progressbar, _Separator, _Notebook
from tkinter import Button as _Button, Label as _Label, Entry as _Entry, Frame as _Frame
from tkinter import Checkbutton as _Checkbutton, Radiobutton as _Radiobutton, Scale as _Scale
from tkinter import Spinbox as _Spinbox, LabelFrame as _LabelFrame, Scrollbar as _Scrollbar
from tkinter import OptionMenu as _OptionMenu, Menubutton as _Menubutton
from tkinter import PanedWindow as _PanedWindow
from tkinter import _widgets, _norm

_styles = {}
_maps = {}
_SOPT = {"foreground": "fg", "background": "bg", "borderwidth": "bd"}
_SKEYS = ("font", "fg", "bg", "padding", "relief", "bd", "anchor", "justify", "width", "wraplength")


def _chain(name):
    out = []
    while name:
        out.append(name)
        name = name.partition(".")[2]
    out.append(".")
    return out


class _State:
    _ts = "."

    def _o_bootstyle(self, v):
        _warn("bootstyle")

    def _stylename(self):
        return self._o.get("style") or self._ts

    def _o_style(self, v):
        if not self._new:
            self._restyle()

    def _restyle(self):
        got = {}
        for s in reversed(_chain(self._stylename())):
            got.update(_styles.get(s, {}))
        for k in got:
            o = _SOPT.get(k, k)
            if o in _SKEYS and o not in self._o:
                self._prop(o, _norm(self, o, got[k]))

    def state(self, statespec=None):
        if statespec is None:
            s = self._o.get("state", "normal")
            return (s,) if s != "normal" else ()
        for s in ([statespec] if isinstance(statespec, str) else statespec):
            if s in ("disabled", "readonly"):
                self.configure(state=s)
            elif s in ("!disabled", "!readonly"):
                self.configure(state="normal")

    def instate(self, statespec, callback=None, *args, **kw):
        cur = self.state()
        ok = all((s[1:] not in cur) if s.startswith("!") else (s in cur) for s in statespec)
        if ok and callback is not None:
            return callback(*args, **kw)
        return ok


class Button(_State, _Button):
    _ts = "TButton"


class Label(_State, _Label):
    _ts = "TLabel"


class Entry(_State, _Entry):
    _ts = "TEntry"


class Frame(_State, _Frame):
    _ts = "TFrame"


class Checkbutton(_State, _Checkbutton):
    _ts = "TCheckbutton"


class Radiobutton(_State, _Radiobutton):
    _ts = "TRadiobutton"


class Spinbox(_State, _Spinbox):
    _ts = "TSpinbox"


class LabelFrame(_State, _LabelFrame):
    _ts = "TLabelframe"


Labelframe = LabelFrame


class Scrollbar(_State, _Scrollbar):
    _ts = "TScrollbar"


class Combobox(_State, _Combobox):
    _ts = "TCombobox"


class Progressbar(_State, _Progressbar):
    _ts = "TProgressbar"


class Separator(_State, _Separator):
    _ts = "TSeparator"


class Notebook(_State, _Notebook):
    _ts = "TNotebook"


class Menubutton(_State, _Menubutton):
    _ts = "TMenubutton"


class PanedWindow(_State, _PanedWindow):
    _ts = "TPanedwindow"

    def _init(self):
        _PanedWindow._init(self)
        self._p["orient"] = "vertical"

    def insert(self, pos, child, **kw):
        if pos != "end":
            kw["before"] = self._panes[pos][0] if isinstance(pos, int) else pos
        self.add(child, **kw)

    def pane(self, pane, option=None, **kw):
        if kw:
            return self.paneconfigure(pane, **kw)
        o = self.paneconfigure(pane)
        return o.get(option, "") if option else o

    def sashpos(self, index, newpos=None):
        return 0


Panedwindow = PanedWindow


class Sizegrip(_State, _Scrollbar):
    _ts = "TSizegrip"


class Scale(_State, _Scale):
    _ts = "TScale"

    def _init(self):
        _Scale._init(self)
        self._p.update({"orient": "horizontal", "showvalue": 0, "res": 0})


class OptionMenu(_State, _OptionMenu):
    _ts = "TMenubutton"

    def __init__(self, master, variable, default=None, *values, **kwargs):
        _OptionMenu.__init__(self, master, variable, *values, **kwargs)
        if default is not None:
            variable.set(default)


class Style:
    def __init__(self, master=None):
        self.master = master

    def configure(self, style, query_opt=None, **kw):
        d = _styles.setdefault(style, {})
        if query_opt is not None:
            return d.get(query_opt, "")
        if not kw:
            return dict(d) or None
        d.update(kw)
        for w in _widgets:
            if w._alive and hasattr(w, "_restyle") and style in _chain(w._stylename()):
                w._restyle()

    def map(self, style, query_opt=None, **kw):
        d = _maps.setdefault(style, {})
        if query_opt is not None:
            return d.get(query_opt, [])
        d.update(kw)
        return dict(d)

    def lookup(self, style, option, state=None, default=None):
        for s in _chain(style):
            if option in _styles.get(s, ()):
                return _styles[s][option]
        return default if default is not None else ""

    def theme_use(self, themename=None):
        return "default" if themename is None else None

    def theme_names(self):
        return ("default",)

    def layout(self, style, layoutspec=None):
        return []

    element_create = element_options = theme_create = theme_settings = _noop()
    element_names = _noop(())
