#!/usr/bin/env python3
"""Снимки бандлов сайта для README: свежий headless Chromium на каждую сцену, бандл с локального
сервера (site/), шаги в машине, снимок страницы -> docs/img/СЦЕНА.png.

  python3 tests/shots.py              # все сцены
  python3 tests/shots.py dwm python-pc  # по имени сцены или бандла
  python3 tests/shots.py -l           # список сцен

Шаги: 'sh: команда' (kt.exec, ждёт конца), 'bg: команда' (в фоне, без ожидания), 'type: строка'
(набрать в терминал с Enter), 'js: выражение', 'wait: команда' (повторять, пока не код 0, до 180 с),
'sleep: с', 'tap: x y' (касание или щелчок в точках страницы), 'place: Заголовок | x y [w h]' (окно
tkinter перетащить за заголовок и растянуть за уголок, как мышью), 'windows: ' (вывести окна и их места).
Снимок - в конце сцены."""
import argparse
import base64
import functools
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, ROOT)
from run import Suite  # noqa: E402
from bundle import Chrome  # noqa: E402

PC = dict(width=1280, height=800, deviceScaleFactor=1, mobile=False)
PHONE = dict(width=412, height=915, deviceScaleFactor=2.625, mobile=True)
X = "DISPLAY=:0 "  # программы X из kt.exec: у агента своего DISPLAY нет
XUP = "wait: pgrep -x %s"  # бандл с --cmd startx: X поднимается при открытии
LONG = 'setsid sh -c "%s" >/dev/null 2>&1 < /dev/null &'  # окно живёт после выхода kt.exec

# сцена: (бандл, экран, шаги)
SCENES = {
    # рабочий стол на tkinter: окна вразброс, последнее - сверху
    "python-desk": ("python", PC, ["bg: tk-files /root", "bg: tk-term -e htop", "bg: idle /root/examples/python/weather.py",
                                   "bg: tk-cfgedit", "sleep: 35",
                                   "place: Реестр | 920 440 330 300", "place: Терминал | 650 105 600 300",
                                   "place: Файлы | 40 130 520 310", "place: weather.py | 210 380 590 360",
                                   # htop после смены размера окна - заново целиком
                                   "sh: kill -WINCH $(pgrep -x htop)", "sleep: 3"]),
    "python-pc": ("python", PC, ["bg: python3 -m turtledemo.yinyang", "sleep: 10", "bg: mpldemo surface", "sleep: 45",
                                 "place: Python Turtle | 30 110", "place: matplotlib | 640 170", "sleep: 3"]),
    "python-phone": ("python", PHONE, ["bg: mpldemo bars", "sleep: 15"]),
    "xorg": ("xorg", PC, [XUP % "xterm", "sleep: 5"]),
    "xorg-phone": ("xorg", PHONE, [XUP % "xterm", "sleep: 5"]),
    "dwm": ("dwm", PC, [XUP % "st", "sleep: 25"]),
    "dwm-phone": ("dwm", PHONE, [XUP % "st", "sleep: 25"]),
    # первый кадр README: шахматы главным окном (последнее открытое), рядом gloss, htop и neofetch; первый,
    # пустой st - закрыть
    "dwm-gl": ("dwm", PC, [XUP % "st", "sleep: 10", "sh: kill $(pgrep -x st | head -1)", "bg: " + X + "st -e htop", "sleep: 5",
                           "bg: cd /usr/share/mesa-demos && " + X + "gloss", "sleep: 15",
                           "bg: " + X + "xboard -fcp gnuchess", "sleep: 40"]),
    "qt": ("qt", PC, ["sleep: 8"]),
    "sqlite": ("sqlite", PC, ["sleep: 8"]),
}


def serve(site):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = functools.partial(Quiet, directory=site)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


WIN_JS = """((t) => { const all = [...document.querySelectorAll('.tk-win')].filter((e) => !e.hidden),
  name = (e) => (e.querySelector('.tk-bar > span') || {}).textContent || '';
  const w = all.find((e) => name(e) === t) || all.find((e) => name(e).includes(t));
  if (!w) return null;
  const r = w.getBoundingClientRect(), bar = w.querySelector('.tk-bar'), b = bar.getBoundingClientRect(),
    g = w.querySelector('.tk-grip').getBoundingClientRect(), at = (x, y, el) => el.contains(document.elementFromPoint(x, y));
  // точка заголовка, которую не закрывают другие окна; нет такой - видимая точка окна (щелчок поднимет его)
  let bx = null, vx = null, vy = null;
  for (let x = b.left + 10; x < b.right - 70 && bx === null; x += 10) if (at(x, b.top + b.height / 2, bar)) bx = x;
  for (let y = r.top + 5; y < r.bottom && vx === null; y += 15)
    for (let x = r.left + 5; x < r.right; x += 15) if (at(x, y, w)) { vx = x; vy = y; break; }
  return { x: r.left, y: r.top, r: r.right, b: r.bottom, bx, by: b.top + b.height / 2, vx, vy,
    gx: g.left + g.width / 2, gy: g.top + g.height / 2 }; })(%s)"""
LIST_JS = """[...document.querySelectorAll('.tk-win')].filter((e) => !e.hidden).map((e) => { const r = e.getBoundingClientRect();
  return ((e.querySelector('.tk-bar > span') || {}).textContent || '?') + ' ' + [r.left, r.top, r.width, r.height].map(Math.round).join(' '); })"""


def drag(s, x1, y1, x2, y2, steps=8):
    """мышью: нажать, протащить шагами, отпустить - как человек за заголовок или уголок"""
    m = lambda t, x, y, **k: s.c.call("Input.dispatchMouseEvent", type=t, x=x, y=y, **k)  # noqa: E731
    m("mouseMoved", x1, y1)
    m("mousePressed", x1, y1, button="left", buttons=1, clickCount=1)
    for i in range(1, steps + 1):
        m("mouseMoved", x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps, button="left", buttons=1)
        time.sleep(0.05)
    m("mouseReleased", x2, y2, button="left", buttons=0, clickCount=1)
    time.sleep(0.6)


def place(s, what):
    """'Заголовок | x y [w h]': окно - в размер и на место (заголовок - целиком или частью). Сначала окно
    поднимается щелчком (по заголовку, а если его закрывают другие окна - по видимой части), уголок
    тянется на старом месте (там он точно на экране), потом окно едет за заголовок"""
    title, _, geo = what.rpartition("|")
    x, y, w, h = (list(map(float, geo.split())) + [0, 0])[:4]
    title = title.strip()
    r = s.ev(WIN_JS % json.dumps(title))
    if not r:
        raise RuntimeError("нет окна " + title)
    px, py = (r["bx"], r["by"]) if r["bx"] is not None else (r["vx"], r["vy"])
    if px is None:
        raise RuntimeError("окно %s не видно" % title)
    for t in ("mousePressed", "mouseReleased"):
        s.c.call("Input.dispatchMouseEvent", type=t, x=px, y=py, button="left", clickCount=1)
    time.sleep(0.6)
    r = s.ev(WIN_JS % json.dumps(title))
    if w and h:
        drag(s, r["gx"], r["gy"], r["x"] + w - (r["r"] - r["gx"]), r["y"] + h - (r["b"] - r["gy"]))
        time.sleep(1)
        r = s.ev(WIN_JS % json.dumps(title))
    if r["bx"] is None:
        raise RuntimeError("заголовок окна %s закрыт" % title)
    # за заголовок - одним движением: окно, которое перекладывается (реестр с сотнями полей), иногда
    # отпускало заголовок после первого шага
    drag(s, r["bx"], r["by"], r["bx"] + x - r["x"], r["by"] + y - r["y"], 1)


def tap(s, x, y, phone):
    if phone:
        for t, pts in (("touchStart", [{"x": x, "y": y}]), ("touchEnd", [])):
            s.c.call("Input.dispatchTouchEvent", type=t, touchPoints=pts)
    else:
        for t in ("mousePressed", "mouseReleased"):
            s.c.call("Input.dispatchMouseEvent", type=t, x=x, y=y, button="left", clickCount=1)


def scene(name, base, out, tmp):
    bundle, metrics, steps = SCENES[name]
    phone = metrics["mobile"]
    s = Suite(tmp, None)
    # окно сразу своего размера: подмена размера (setDeviceMetricsOverride) действует не с первой
    # раскладки, и startx из boot.cmd успевал взять размер окна 800x600
    s.c = Chrome(tempfile.mkdtemp(dir=tmp), "%d,%d" % (metrics["width"], metrics["height"]))
    try:
        s.c.open("about:blank")
        s.c.call("Page.enable")
        s.c.call("Emulation.setDeviceMetricsOverride", **metrics)
        if phone:
            s.c.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
        s.c.call("Page.navigate", url="%s/%s/" % (base, bundle))
        print("%-14s машина готова за %.1f с" % (name, s.wait_ready(180)), flush=True)
        for step in steps:
            kind, _, what = step.partition(": ")
            if kind == "sh":
                code, o, e = s.sh(what, 300)
                if code:
                    print("  %s -> %s %s%s" % (what, code, o, e), flush=True)
            elif kind == "bg":
                s.sh(LONG % what.replace('"', '\\"'), 30)
            elif kind == "type":
                s.typed(what)
            elif kind == "js":
                s.ev(what)
            elif kind == "wait":
                t = time.time()
                while s.sh(what, 60)[0] and time.time() - t < 180:
                    time.sleep(1)
            elif kind == "sleep":
                time.sleep(float(what))
            elif kind == "tap":
                tap(s, *map(float, what.split()), phone)
            elif kind == "place":
                place(s, what)
            elif kind == "windows":
                print("  окна:", *s.ev(LIST_JS), sep="\n    ", flush=True)
        png = base64.b64decode(s.c.call("Page.captureScreenshot", format="png")["data"])
        path = os.path.join(out, name + ".png")
        open(path, "wb").write(png)
        print("  -> %s (%d КБ)" % (os.path.relpath(path, ROOT), len(png) // 1024), flush=True)
    finally:
        s.c.close()


def main():
    ap = argparse.ArgumentParser(description="снимки бандлов сайта для README")
    ap.add_argument("names", nargs="*", help="сцены или бандлы (по умолчанию все)")
    ap.add_argument("-l", action="store_true", help="список сцен")
    ap.add_argument("--site", default=os.path.join(ROOT, "site"), help="откуда бандлы (по умолчанию site/)")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs/img"), help="куда снимки (по умолчанию docs/img/)")
    a = ap.parse_args()
    if a.l:
        for n, (b, m, st) in SCENES.items():
            print("%-14s %-9s %-6s %s" % (n, b, "phone" if m["mobile"] else "pc", "; ".join(st)))
        return
    names = [n for n in SCENES if not a.names or n in a.names or SCENES[n][0] in a.names]
    if not names:
        sys.exit("нет таких сцен: " + " ".join(a.names))
    os.makedirs(a.out, exist_ok=True)
    srv = serve(a.site)
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    tmp = tempfile.mkdtemp(prefix="kt-shots-")  # профили Chrome: удаляются в конце
    failed = []
    try:
        for n in names:
            try:
                scene(n, base, a.out, tmp)
            except Exception as e:  # noqa: BLE001 - одна сцена не останавливает остальные
                print("  %s: %s" % (n, e), flush=True)
                failed.append(n)
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    if failed:
        sys.exit("не снялись: " + " ".join(failed))


if __name__ == "__main__":
    main()
