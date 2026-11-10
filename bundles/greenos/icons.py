#!/usr/bin/env python3
"""Значки GreenOS -> fs/usr/share/greenos/:
- свой только логотип: четыре ровных квадрата (кнопка «Пуск» - icons/greenos.png, ровно в размер значка
  на панели JWM, чтобы не размывался; окно «О системе» - logo.png);
- остальное - оригинальные значки MATE (пакет mate-icon-theme Alpine): тема Menta (зелёные папки), чего
  в ней нет - из mate, как и в самой теме; готовые PNG 48x48. Это значки программ без своего значка,
  разделов и пунктов меню, панели и рабочего стола. Родные значки программ (xterm, feh) меню берёт прямо
  из их пакетов.
Нужен Pillow; PNG лежат в git: python3 bundles/greenos/icons.py"""
import io
import os
import sys
import tarfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fs/usr/share/greenos")
GREEN = (43, 191, 32)
TRAY_ICON = 28  # Tray height=36 в /etc/system.jwmrc: кнопка 34 (без рамки панели), значок - на 6 меньше
THEMES = ("menta", "mate")
SIZE = "48x48"

# имя у нас <- имя значка по freedesktop
ICONS = {
    "save": "document-save",
    "volume": "audio-volume-high",
    "clock": "preferences-system-time",
    "monitor": "utilities-system-monitor",
    "eyes": "face-glasses",
    "kill": "process-stop",
    "appearance": "preferences-desktop-theme",
    "utilities": "applications-utilities",
    "games": "applications-games",
    "system": "applications-system",
    "office": "applications-office",
    "graphics": "applications-graphics",
    "development": "applications-development",
    "internet": "applications-internet",
    "network": "network-workgroup",
    "network-offline": "network-offline",
    "network-relay": "network-transmit-receive",
    "network-browser": "network-idle",
    "python": "text-x-python",
    "folder": "folder",
    "home": "user-home",
    "trash": "user-trash",
    "about": "help-about",
    "restart": "view-refresh",
    "exit": "system-log-out",
    "desktop": "user-desktop",
    "executable": "application-x-executable",
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


def mate():
    sys.path.insert(0, os.path.join(HERE, "../.."))
    import alpine
    pkgs, _ = alpine.index(tag="xorg-", max_age=30 * 86400)
    f = "mate-icon-theme-%s.apk" % pkgs["mate-icon-theme"]["ver"]
    apk = alpine.fetch("%s/%s/x86/%s" % (alpine.MIRROR, pkgs["mate-icon-theme"]["repo"], f), "%s/apk/%s" % (alpine.CACHE, f))
    with tarfile.open(apk, "r:gz") as t:
        members = {m.name: m for m in t.getmembers()}
        # значок темы: usr/share/icons/ТЕМА/48x48/РАЗДЕЛ/ИМЯ.png
        where = {}
        for name in members:
            p = name.split("/")
            if len(p) == 7 and p[:3] == ["usr", "share", "icons"] and p[4] == SIZE and p[6].endswith(".png"):
                where.setdefault((p[3], p[6][:-4]), name)
        missing = []
        for ours, name in ICONS.items():
            path = next((where[(th, name)] for th in THEMES if (th, name) in where), None)
            m = members.get(path)
            while m is not None and m.issym():  # многие значки MATE - ссылки на соседние
                m = members.get(os.path.normpath(os.path.join(os.path.dirname(m.name), m.linkname)))
            if m is None or not m.isfile():
                missing.append(name)
                continue
            Image.open(io.BytesIO(t.extractfile(m).read())).save(os.path.join(OUT, "icons", ours + ".png"), optimize=True)
    if missing:
        sys.exit("нет в mate-icon-theme: " + " ".join(missing))


if __name__ == "__main__":
    os.makedirs(os.path.join(OUT, "icons"), exist_ok=True)
    squares(TRAY_ICON, 2).save(os.path.join(OUT, "icons/greenos.png"), optimize=True)
    squares(96, 6).save(os.path.join(OUT, "logo.png"), optimize=True)
    mate()
    print("значки ->", OUT)
