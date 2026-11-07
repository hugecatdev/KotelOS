#!/usr/bin/env python3
"""Края кадра GLX через VirGL: glxcolor заливает окно цветом, меняя его каждый кадр; по снимку
экрана видно, что лежит в крайних столбцах и строках окна. Бандл - с glxcolor в дереве гостя.
  python3 virgl/harness/v86-edges.py [БАНДЛ] [ШxВ ...]"""
import base64
import io
import os
import sys
import tempfile
import time

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from run import Suite  # noqa: E402

page = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build/virgl-serve/index.html"))
sizes = [tuple(map(int, a.split("x"))) for a in sys.argv[2:]] or [(290, 290), (452, 446)]
NAMES = {(255, 0, 0): "R", (0, 255, 0): "G", (0, 0, 255): "B", (0, 0, 0): "."}

s = Suite(tempfile.mkdtemp(prefix="virgl-edges-"), None)
s.open("file://" + page)
try:
    s.ev("send('startx\\r')")
    t = time.time()
    while s.sh("test -S /tmp/.X11-unix/X0")[0]:
        assert time.time() - t < 90
        time.sleep(1)
    time.sleep(2)
    for w, h in sizes:
        s.ok("(DISPLAY=:0 GALLIUM_DRIVER=virpipe glxcolor %d %d 30 300 40 > /tmp/glxcolor.log 2>&1 &)" % (w, h))
        t = time.time()
        while "последний" not in s.sh("cat /tmp/glxcolor.log")[1]:
            assert time.time() - t < 60, s.sh("cat /tmp/glxcolor.log")[1]
            time.sleep(0.5)
        time.sleep(1)
        url = s.ev("document.querySelector('#screen canvas').toDataURL('image/png')")
        im = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")
        im.save(os.path.join(ROOT, "build/virgl", "edges-%dx%d.png" % (w, h)))
        # окно ставится в 300,40; рамку twm ищем по первому синему пикселю
        y = 40 + h // 2
        xs = [x for x in range(im.width) if im.getpixel((x, y)) == (0, 0, 255)]
        x0, x1 = xs[0], xs[-1]
        print("%dx%d: синих в строке %d - столбцы %d..%d (%d)" % (w, h, y, x0, x1, x1 - x0 + 1), flush=True)
        for yy in (y - h // 3, y, y + h // 3):
            row = "".join(NAMES.get(im.getpixel((x, yy)), "?") for x in range(x1 - 3, x1 + 12))
            print("  строка %d, от столбца %d: %s" % (yy, x1 - 3, row), flush=True)
        s.sh("killall glxcolor")
        time.sleep(1)
finally:
    s.c.close()
