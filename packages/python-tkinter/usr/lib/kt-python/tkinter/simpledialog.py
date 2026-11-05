from tkinter import _dialog, _stub, _noop, Toplevel
from tkinter import messagebox


def askstring(title, prompt, **kw):
    init = kw.get("initialvalue")
    r = _dialog(title, prompt, [["ok", "ОК"], ["cancel", "Отмена"]], inp="" if init is None else str(init),
                show=kw.get("show"))
    return r["v"] if r["k"] == "ok" else None


def _num(conv, what, title, prompt, kw):
    lo, hi = kw.pop("minvalue", None), kw.pop("maxvalue", None)
    while True:
        s = askstring(title, prompt, **kw)
        if s is None:
            return None
        try:
            v = conv(s.strip())
        except ValueError:
            err = "Нужно " + what
        else:
            if lo is not None and v < lo:
                err = "Не меньше %s" % lo
            elif hi is not None and v > hi:
                err = "Не больше %s" % hi
            else:
                return v
        _dialog(title, err, [["ok", "ОК"]])
        kw["initialvalue"] = s


def askinteger(title, prompt, **kw):
    return _num(int, "целое число", title, prompt, kw)


def askfloat(title, prompt, **kw):
    return _num(float, "число", title, prompt, kw)


class Dialog(Toplevel):
    __init__ = _stub("simpledialog.Dialog")


class SimpleDialog:
    __init__ = _stub("simpledialog.SimpleDialog")
    go = _stub("simpledialog.SimpleDialog")


_setup_dialog = _noop()
_place_window = _noop()
