from tkinter import _dialog
from tkinter.commondialog import Dialog


class Chooser(Dialog):
    command = "tk_chooseColor"


def askcolor(color=None, **options):
    init = "" if color is None else str(color)
    r = _dialog(options.get("title") or "Цвет", "#rrggbb", [["ok", "ОК"], ["cancel", "Отмена"]], inp=init)
    v = (r.get("v") or "").strip()
    if r["k"] != "ok" or len(v) != 7 or v[0] != "#":
        return (None, None)
    try:
        rgb = (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
    except ValueError:
        return (None, None)
    return (rgb, v)
