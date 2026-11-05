from tkinter import _stub


class Dialog:
    command = None

    def __init__(self, master=None, **options):
        self.master = master
        self.options = options

    show = _stub("commondialog.Dialog")
