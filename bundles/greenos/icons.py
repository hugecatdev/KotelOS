#!/usr/bin/env python3
"""Значки GreenOS -> fs/usr/share/greenos/:
- свой только логотип: четыре ровных квадрата (кнопка «Пуск» - icons/greenos.png, ровно в размер значка
  на панели JWM, чтобы не размывался; окно «О системе» - logo.png);
- остальное - оригинальные значки KDE Breeze (пакет breeze-icons Alpine) для программ без своего
  значка и пунктов меню, SVG -> PNG (у JWM здесь нет librsvg). Родные значки программ (xterm, feh)
  меню берёт прямо из их пакетов.
Нужны Pillow и rsvg-convert; PNG лежат в git: python3 bundles/greenos/icons.py"""
import io
import os
import subprocess
import sys
import tarfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fs/usr/share/greenos")
GREEN = (43, 191, 32)
TRAY_ICON = 28  # Tray height=36 в /etc/system.jwmrc: кнопка 34 (без рамки панели), значок - на 6 меньше

# имя у нас <- путь в breeze-icons (usr/share/icons/breeze/...)
BREEZE = {
    "calc": "apps/48/accessories-calculator.svg",
    "clock": "preferences/32/preferences-system-time.svg",
    "monitor": "apps/48/utilities-system-monitor.svg",
    "eyes": "actions/24/view-visible.svg",
    "kill": "actions/32/window-close.svg",
    "appearance": "preferences/32/preferences-desktop-color.svg",
    "utilities": "categories/32/applications-utilities.svg",
    "games": "categories/32/applications-games.svg",
    "system": "categories/32/applications-system.svg",
    "office": "categories/32/applications-office.svg",
    "graphics": "categories/32/applications-graphics.svg",
    "development": "categories/32/applications-development.svg",
    "python": "mimetypes/64/text-x-python.svg",
    "folder": "places/48/folder-green.svg",
    "home": "places/48/user-home.svg",
    "trash": "places/48/user-trash.svg",
    "about": "actions/32/help-about.svg",
    "restart": "actions/32/view-refresh.svg",
    "exit": "actions/32/system-log-out.svg",
    "desktop": "places/48/user-desktop.svg",
    "executable": "mimetypes/64/application-x-executable.svg",
}


def squares(size, gap):
    """четыре квадрата с ровными гранями, без сглаживания: размер и зазор - в целых точках"""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    a = (size - gap) // 2
    for x in (0, size - a):
        for y in (0, size - a):
            d.rectangle([x, y, x + a - 1, y + a - 1], fill=GREEN)
    return im


def breeze():
    sys.path.insert(0, os.path.join(HERE, "../.."))
    import alpine
    pkgs, _ = alpine.index(tag="xorg-", max_age=30 * 86400)
    f = "breeze-icons-%s.apk" % pkgs["breeze-icons"]["ver"]
    apk = alpine.fetch("%s/%s/x86/%s" % (alpine.MIRROR, pkgs["breeze-icons"]["repo"], f), "%s/apk/%s" % (alpine.CACHE, f))
    want = {"usr/share/icons/breeze/" + v: k for k, v in BREEZE.items()}
    with tarfile.open(apk, "r:gz") as t:
        members = {m.name: m for m in t.getmembers()}
        for name in list(want):
            m = members.get(name)
            while m is not None and m.issym():  # многие значки Breeze - ссылки на соседние
                m = members.get(os.path.normpath(os.path.join(os.path.dirname(m.name), m.linkname)))
            if m is None or not m.isfile():
                continue
            png = subprocess.run(["rsvg-convert", "-w", "48", "-h", "48"], input=t.extractfile(m).read(),
                                 capture_output=True, check=True).stdout
            Image.open(io.BytesIO(png)).save(os.path.join(OUT, "icons", want.pop(name) + ".png"), optimize=True)
    if want:
        sys.exit("нет в breeze-icons: " + " ".join(want))


if __name__ == "__main__":
    os.makedirs(os.path.join(OUT, "icons"), exist_ok=True)
    squares(TRAY_ICON, 2).save(os.path.join(OUT, "icons/greenos.png"), optimize=True)
    squares(96, 6).save(os.path.join(OUT, "logo.png"), optimize=True)
    breeze()
    print("значки ->", OUT)
