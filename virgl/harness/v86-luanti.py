#!/usr/bin/env python3
"""luanti (бывший Minetest) в машине через VirGL: запуск сразу в мир devtest, снимки экрана по ходу
(build/virgl/luanti-ДРАЙВЕР-СЕКУНДА.png), конец журнала ~/.minetest/debug.txt и сообщения vrend.
  python3 virgl/harness/v86-luanti.py БАНДЛ [драйвер] [секунд]"""
import base64
import os
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from run import Suite  # noqa: E402

HOOK = """(() => { window.__virglLog = []; for (const k of ["log", "warn", "error"]) { const f = console[k];
  console[k] = (...a) => { if (String(a[0]).startsWith("virgl")) window.__virglLog.push(a.map(String).join(" ")); f.apply(console, a); }; } })()"""

page = os.path.abspath(sys.argv[1])
drv = sys.argv[2] if len(sys.argv) > 2 else "virpipe"
secs = int(sys.argv[3]) if len(sys.argv) > 3 else 180
s = Suite(tempfile.mkdtemp(prefix="virgl-luanti-"), None)
s.open("file://" + page)
s.ev(HOOK)
try:
    s.ev("send('startx\\r')")
    t = time.time()
    while s.sh("test -S /tmp/.X11-unix/X0")[0]:
        assert time.time() - t < 90
        time.sleep(1)
    time.sleep(2)
    s.ok("(cd /root && DISPLAY=:0 GALLIUM_DRIVER=%s timeout %d luanti --go --world /root/.minetest/worlds/w --name kt > /tmp/luanti.log 2>&1 &)" % (drv, secs))
    t0 = time.time()
    for at in (30, 60, 90, 120, 150, 180, 240, 300):
        if at > secs:
            break
        time.sleep(max(0, at - (time.time() - t0)))
        url = s.ev("document.querySelector('#screen canvas').toDataURL('image/png')")
        open(os.path.join(ROOT, "build/virgl", "luanti-%s-%03d.png" % (drv, at)), "wb").write(base64.b64decode(url.split(",", 1)[1]))
        alive = s.sh("pidof luanti")[1].strip()
        print("%3d с: luanti %s" % (at, "идёт" if alive else "закончился"), flush=True)
        if not alive:
            break
    print("--- вывод:\n" + s.sh("tail -15 /tmp/luanti.log")[1])
    print("--- debug.txt:\n" + s.sh("grep -iE 'error|warn|opengl|shader|renderer|driver' /root/.minetest/debug.txt | tail -20")[1])
    log = [line for line in (s.ev("window.__virglLog") or []) if "Shared memory" not in line]
    print("--- vrend (%d):" % len(log))
    for line in sorted(set(log), key=log.index)[:20]:
        print("   ", line[:200])
finally:
    s.c.close()
