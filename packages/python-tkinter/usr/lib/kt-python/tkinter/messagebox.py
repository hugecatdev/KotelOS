from tkinter import _dialog
from tkinter.commondialog import Dialog

ERROR = "error"
INFO = "info"
QUESTION = "question"
WARNING = "warning"

ABORTRETRYIGNORE = "abortretryignore"
OK = "ok"
OKCANCEL = "okcancel"
RETRYCANCEL = "retrycancel"
YESNO = "yesno"
YESNOCANCEL = "yesnocancel"

ABORT = "abort"
RETRY = "retry"
IGNORE = "ignore"
CANCEL = "cancel"
YES = "yes"
NO = "no"

_L = {"ok": "ОК", "cancel": "Отмена", "yes": "Да", "no": "Нет", "retry": "Повтор", "abort": "Прервать",
      "ignore": "Пропустить"}
_T = {"ok": ["ok"], "okcancel": ["ok", "cancel"], "yesno": ["yes", "no"], "yesnocancel": ["yes", "no", "cancel"],
      "retrycancel": ["retry", "cancel"], "abortretryignore": ["abort", "retry", "ignore"]}


def _show(title, message, btns, options):
    msg = "" if message is None else str(message)
    if options.get("detail"):
        msg += "\n\n" + str(options["detail"])
    btns = _T.get(options.get("type"), btns)
    r = _dialog(title, msg, [[b, _L.get(b, b)] for b in btns], default=options.get("default"))
    return r["k"]


def showinfo(title=None, message=None, **options):
    return _show(title, message, ["ok"], options)


def showwarning(title=None, message=None, **options):
    return _show(title, message, ["ok"], options)


def showerror(title=None, message=None, **options):
    return _show(title, message, ["ok"], options)


def askquestion(title=None, message=None, **options):
    return _show(title, message, ["yes", "no"], options)


def askokcancel(title=None, message=None, **options):
    return _show(title, message, ["ok", "cancel"], options) == "ok"


def askyesno(title=None, message=None, **options):
    return _show(title, message, ["yes", "no"], options) == "yes"


def askyesnocancel(title=None, message=None, **options):
    r = _show(title, message, ["yes", "no", "cancel"], options)
    return None if r == "cancel" else r == "yes"


def askretrycancel(title=None, message=None, **options):
    return _show(title, message, ["retry", "cancel"], options) == "retry"


class Message(Dialog):
    command = "tk_messageBox"
