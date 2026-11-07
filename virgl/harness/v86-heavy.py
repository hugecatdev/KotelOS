#!/usr/bin/env python3
"""Тяжёлые GL-программы в машине через VirGL и для сравнения через softpipe: каждая идёт N секунд,
снимок экрана посередине (build/virgl/heavy-ИМЯ-ДРАЙВЕР.png), строки с FPS из её вывода и
сообщения vrend со страницы.
  DRIVERS="virpipe" python3 virgl/harness/v86-heavy.py БАНДЛ [секунд] [программа ...]"""
import base64
import os
import re
import shutil
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from run import Suite  # noqa: E402

HOOK = """(() => { window.__virglLog = []; for (const k of ["log", "warn", "error"]) { const f = console[k];
  console[k] = (...a) => { if (String(a[0]).startsWith("virgl")) window.__virglLog.push(a.map(String).join(" ")); f.apply(console, a); }; } })()"""
DEMOS = ["gears", "gloss", "fire", "ipers", "isosurf", "teapot", "engine", "fsraytrace", "fbo_firecube", "terrain"]

page = os.path.abspath(sys.argv[1])
secs = int(sys.argv[2]) if len(sys.argv) > 2 else 20
demos = sys.argv[3:] or DEMOS
tmp = tempfile.mkdtemp(prefix="virgl-heavy-")  # профили Chrome, /tmp - в памяти: удаляются в конце
s = Suite(tmp, None)
s.open("file://" + page)
s.ev(HOOK)


def shot(name):
    # снимок страницы (CDP): холст WebGL (virtio-gpu) через toDataURL не снять
    png = s.c.call("Page.captureScreenshot", format="png")["data"]
    open(os.path.join(ROOT, "build/virgl", "heavy-%s.png" % name), "wb").write(base64.b64decode(png))


try:
    s.ev("send('startx\\r')")
    t = time.time()
    while s.sh("test -S /tmp/.X11-unix/X0")[0]:
        assert time.time() - t < 90
        time.sleep(1)
    time.sleep(float(os.environ.get("X_SETTLE", "2")))
    for demo in demos:
        # драйвер: virpipe/softpipe - libGL через Xlib (этап 0), virgl/soft - Mesa с DRI (virtio-gpu)
        for drv in os.environ.get("DRIVERS", "virpipe softpipe").split():
            env = {"virgl": "", "soft": "LIBGL_ALWAYS_SOFTWARE=1"}.get(drv, "GALLIUM_DRIVER=" + drv)
            s.ev("window.__virglLog.length = 0")
            s.start("cd /usr/share/mesa-demos 2>/dev/null; DISPLAY=:0 %s timeout %d %s 2>&1; echo код $?" % (env, secs, demo))
            time.sleep(secs * 0.6)
            shot("%s-%s" % (demo, drv))
            code, out, err = s.finish()
            fps = [float(x) for x in re.findall(r"([\d.]+)\s*(?:FPS|fps)", out)]
            tail = [line for line in out.splitlines() if line.strip()][-3:]
            log = [line for line in (s.ev("window.__virglLog") or []) if "Shared memory" not in line][:6]
            print("%-12s %-8s FPS %s | %s%s" % (demo, drv, fps[-4:], " / ".join(tail)[-160:],
                  ("\n    vrend: " + "\n    vrend: ".join(x[:200] for x in log)) if log and drv in ("virpipe", "virgl") else ""), flush=True)
finally:
    s.c.close()
    shutil.rmtree(tmp, ignore_errors=True)
