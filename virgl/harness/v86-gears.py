#!/usr/bin/env python3
"""Этап 0 в машине: glxgears в X v86 через VirGL (virpipe -> vtest-bridge -> страница -> WebGL2)
и для сравнения через softpipe. Бандл - с --virgl, --vga и деревом build/virgl-guest/fs:

  python3 bundle.py -o build/virgl/kt-virgl.html -n virgl --vga 8 --cfg boot.mem=256 --virgl \\
    --file build/virgl-guest/fs:/ fun nano kt-ttyd xorg xeyes libstdc++ libgcc libx11 libxext zlib
  python3 virgl/harness/v86-gears.py [build/virgl/kt-virgl.html]

Снимки экрана - build/virgl/gears-*.png.
"""
import base64
import os
import re
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from run import Suite  # noqa: E402

page = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build/virgl-serve/index.html"))
s = Suite(tempfile.mkdtemp(prefix="virgl-v86-"), None)
print("машина готова за %.1f с" % s.open("file://" + page), flush=True)


def shot(name):
    url = s.ev("document.querySelector('#screen canvas').toDataURL('image/png')")
    path = os.path.join(ROOT, "build/virgl", "gears-%s.png" % name)
    open(path, "wb").write(base64.b64decode(url.split(",", 1)[1]))
    return path


def fps(out):
    return [float(x) for x in re.findall(r"=\s*([\d.]+) FPS", out)]


try:
    s.ev("send('startx\\r')")
    t = time.time()
    while s.sh("test -S /tmp/.X11-unix/X0")[0]:
        assert time.time() - t < 90, "X не поднялся: %s" % s.sh("tail -5 /var/log/Xorg.0.log")[1]
        time.sleep(1)
    print("X за %.1f с" % (time.time() - t), flush=True)
    s.ok("(vtest-bridge > /tmp/vtest-bridge.log 2>&1 &)")

    code, out, err = s.sh("DISPLAY=:0 GALLIUM_DRIVER=virpipe glxinfo -B", 180)
    print("glxinfo -B (virpipe), код %s:\n%s%s" % (code, out, err[-2000:]), flush=True)

    for drv in ("virpipe", "softpipe"):
        s.start("DISPLAY=:0 GALLIUM_DRIVER=%s timeout 32 glxgears -geometry 290x290+505+20 2>&1; true" % drv)
        time.sleep(15)
        print("снимок", shot(drv), flush=True)
        code, out, err = s.finish()  # ждёт конца команды
        print("glxgears %s: %s\n%s" % (drv, fps(out), out[-600:]), flush=True)
    print("мост:", s.sh("cat /tmp/vtest-bridge.log")[1], flush=True)
    print("консоль страницы virgl:", s.ev("JSON.stringify(window.__virglLog || null)"), flush=True)
finally:
    s.c.close()
