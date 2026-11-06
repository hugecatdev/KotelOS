# python -m ktdesktop desktop|files|notepad|imgview|cfgedit|open [путь]; второй ли это стол, решает /usr/libexec/ktdesktop
import sys


def main(argv):
    cmd = argv[0] if argv else "desktop"
    arg = argv[1] if len(argv) > 1 else None
    if cmd not in ("desktop", "files", "notepad", "imgview", "cfgedit", "open"):
        print("ktdesktop: desktop | files [папка] | notepad [файл] | imgview файл | cfgedit | open путь")
        return 2
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
