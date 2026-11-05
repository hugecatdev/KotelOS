import os as _os
from tkinter import _dialog, _stub
from tkinter.dialog import Dialog
from tkinter import commondialog
from tkinter.simpledialog import _setup_dialog


def _cwd():
    try:
        return _os.getcwd()
    except Exception:
        return "/"


def _ask(title, path):
    r = _dialog(title, "", [["ok", "ОК"], ["cancel", "Отмена"]], inp=path)
    return r["v"].strip() if r["k"] == "ok" and r["v"] else ""


def _start(kw):
    d = kw.get("initialdir") or _cwd()
    if not d.endswith("/"):
        d += "/"
    return d + (kw.get("initialfile") or "")


def askopenfilename(**kw):
    return _ask(kw.get("title") or "Открыть", _start(kw))


def asksaveasfilename(**kw):
    p = _ask(kw.get("title") or "Сохранить как", _start(kw))
    ext = kw.get("defaultextension")
    if p and ext and "." not in p.split("/")[-1]:
        p += ext
    return p


def askopenfilenames(**kw):
    p = askopenfilename(**kw)
    return (p,) if p else ()


def askdirectory(**kw):
    return _ask(kw.get("title") or "Папка", kw.get("initialdir") or _cwd())


def askopenfile(mode="r", **kw):
    p = askopenfilename(**kw)
    return open(p, mode) if p else None


def asksaveasfile(mode="w", **kw):
    p = asksaveasfilename(**kw)
    return open(p, mode) if p else None


class FileDialog:
    __init__ = _stub("filedialog.FileDialog")
    go = _stub("filedialog.FileDialog")


LoadFileDialog = SaveFileDialog = FileDialog


class Open(commondialog.Dialog):
    command = "tk_getOpenFile"

    def show(self, **options):
        return askopenfilename(**dict(self.options, **options))


class SaveAs(commondialog.Dialog):
    command = "tk_getSaveFile"

    def show(self, **options):
        return asksaveasfilename(**dict(self.options, **options))


class Directory(commondialog.Dialog):
    command = "tk_chooseDirectory"

    def show(self, **options):
        return askdirectory(**dict(self.options, **options))
