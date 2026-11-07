#!/usr/bin/env python3
"""virtio-gpu в машине: видит ли ядро устройство, X на нём, снимки страницы (CDP, холст WebGL
через toDataURL не снять) - build/virgl/gpu-ИМЯ.png, сообщения virglrenderer со страницы.
  python3 virgl/harness/v86-gpu.py БАНДЛ ['sh: команда' | 'js: выражение' | 'shot: имя' | 'sleep: с' | 'reload: ' ...]
Без шагов: сведения о DRM, startx, снимок."""
import base64
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from run import Suite  # noqa: E402
from bundle import Chrome  # noqa: E402

HOOK = """(() => { window.__virglLog = []; for (const k of ["log", "warn", "error"]) { const f = console[k];
  console[k] = (...a) => { const t = a.map(String).join(" "); if (/virgl|virtio|gpu/i.test(t)) window.__virglLog.push(k + ": " + t); f.apply(console, a); }; } })()"""
DEFAULT = [
    "sh: dmesg | grep -iE 'virtio|drm|fb0|gpu' | tail -15; ls /dev/dri; cat /sys/class/drm/card0/device/uevent 2>/dev/null | head -3",
    "js: send('startx\\r')",
    "sh: for i in $(seq 90); do test -S /tmp/.X11-unix/X0 && break; sleep 1; done; sleep 3; grep -E 'modeset|EE|virtio|Output' /var/log/Xorg.0.log | tail -12",
    "shot: x",
]

# бандл: файл или адрес http(s) (тогда работает kt pkg add из репозитория того же сервера)
page = sys.argv[1] if sys.argv[1].startswith("http") else "file://" + os.path.abspath(sys.argv[1])
steps = sys.argv[2:] or DEFAULT
tmp = tempfile.mkdtemp(prefix="virgl-gpu-")  # профили Chrome, /tmp - в памяти: удаляются в конце
s = Suite(tmp, None)
# перехват консоли - до скриптов страницы: сообщения загрузки модуля не теряются
s.c = Chrome(tempfile.mkdtemp(dir=tmp))
s.c.open("about:blank")
s.c.call("Page.enable")
s.c.call("Page.addScriptToEvaluateOnNewDocument", source=HOOK)
s.c.call("Page.navigate", url=page)
print("машина готова за %.1f с" % s.wait_ready(), flush=True)
try:
    for step in steps:
        kind, _, what = step.partition(": ")
        if kind == "sh":
            code, out, err = s.sh(what, 300)
            print("$ %s -> %s\n%s%s" % (what[:120], code, out, err), flush=True)
        elif kind == "js":
            print("js %s -> %s" % (what[:120], json.dumps(s.ev(what), ensure_ascii=False)), flush=True)
        elif kind == "reload":
            # та же страница заново: машина восстанавливается из сохранения (kt save)
            s.c.call("Page.navigate", url=page)
            time.sleep(2)
            print("после перезагрузки готова за %.1f с" % s.wait_ready(), flush=True)
        elif kind == "drag":
            # мышью по странице: drag: x1 y1 x2 y2 - нажать, протащить шагами, отпустить
            x1, y1, x2, y2 = map(float, what.split())
            m = lambda t, x, y, **k: s.c.call("Input.dispatchMouseEvent", type=t, x=x, y=y, **k)
            m("mouseMoved", x1, y1)
            time.sleep(0.5)
            m("mousePressed", x1, y1, button="left", buttons=1, clickCount=1)
            time.sleep(1)
            for i in range(1, 11):
                m("mouseMoved", x1 + (x2 - x1) * i / 10, y1 + (y2 - y1) * i / 10, button="left", buttons=1)
                time.sleep(0.4)
            m("mouseReleased", x2, y2, button="left", buttons=0, clickCount=1)
            time.sleep(2)
        elif kind == "sleep":
            time.sleep(float(what))
        elif kind == "shot":
            png = s.c.call("Page.captureScreenshot", format="png")["data"]
            path = os.path.join(ROOT, "build/virgl", "gpu-%s.png" % what)
            open(path, "wb").write(base64.b64decode(png))
            print("снимок", path, flush=True)
    log = s.ev("window.__virglLog") or []
    print("журнал (%d):" % len(log))
    for line in sorted(set(log), key=log.index)[:30]:
        print("   ", line[:240])
finally:
    s.c.close()
    shutil.rmtree(tmp, ignore_errors=True)
