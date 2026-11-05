# python -m ktdesktop desktop|files|notepad|imgview|open [путь]
import sys

from . import running


def main(argv):
    cmd = argv[0] if argv else "desktop"
    arg = argv[1] if len(argv) > 1 else None
    if cmd not in ("desktop", "files", "notepad", "imgview", "open"):
        print("ktdesktop: desktop | files [папка] | notepad [файл] | imgview файл | open путь")
        return 2
    if cmd == "desktop" and running():
        print("рабочий стол уже запущен")
        return 0
    from .app import App
    app = App()
    if cmd == "desktop":
        from .desk import Desktop
        Desktop(app)
    elif cmd == "open":
        if not arg:
            return 2
        app.open_path(arg)
    else:
        getattr(app, cmd)(arg)
    if app.desk is None and not app.wins:
        return 0
    app.tick()
    app.root.mainloop()
    return 0


sys.exit(main(sys.argv[1:]))
