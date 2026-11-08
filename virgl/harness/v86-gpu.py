#!/usr/bin/env python3
"""virtio-gpu в машине: видит ли ядро устройство, X на нём, снимки страницы (CDP, холст WebGL
через toDataURL не снять) - build/virgl/gpu-ИМЯ.png, сообщения virglrenderer со страницы.
  python3 virgl/harness/v86-gpu.py БАНДЛ ['sh: команда' | 'js: выражение' | 'shot: имя' | 'sleep: с' | 'reload: ' ...]
'cpu: метка' - процессорное время своего Chrome (все процессы и потоки, в т.ч. фоновая компиляция
wasm) с прошлого cpu:. 'prof: секунд' - профиль процессора вкладки (CDP Profiler): доли модулей JIT (код гостя), v86.wasm,
virgl.wasm, JS, сборки мусора, (program) - нативное, в т.ч. WebGL. 'mem: метка' - RssAnon процессов своего Chrome по типам (renderer - страница и v86, gpu-process -
WebGL), МБ. Без шагов: сведения о DRM, startx, снимок."""
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
  console[k] = (...a) => { const t = a.map(String).join(" "); if (/virgl|virtio|gpu|panic|assert/i.test(t)) window.__virglLog.push(k + ": " + t); f.apply(console, a); }; } })()"""
DEFAULT = [
    "sh: dmesg | grep -iE 'virtio|drm|fb0|gpu' | tail -15; ls /dev/dri; cat /sys/class/drm/card0/device/uevent 2>/dev/null | head -3",
    "js: send('startx\\r')",
    "sh: for i in $(seq 90); do test -S /tmp/.X11-unix/X0 && break; sleep 1; done; sleep 3; grep -E 'modeset|EE|virtio|Output' /var/log/Xorg.0.log | tail -12",
    "shot: x",
]


def chrome_mem(profile):
    """RssAnon (МБ) процессов своего Chrome по --type: браузер ищется по профилю, остальные - его
    потомки (у них профиля в командной строке нет)"""
    procs = {}
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            # дочерние процессы Chrome переписывают cmdline одной строкой (setproctitle): делить и по пробелам
            cmd = open("/proc/%s/cmdline" % pid, "rb").read().decode(errors="replace").replace("\0", " ").split()
            ppid = int(open("/proc/%s/stat" % pid).read().rsplit(")", 1)[1].split()[1])
            rss = next((int(l.split()[1]) for l in open("/proc/%s/status" % pid) if l.startswith("RssAnon:")), 0)
            st = open("/proc/%s/stat" % pid).read().rsplit(")", 1)[1].split()
            ticks = int(st[11]) + int(st[12])  # utime + stime всех потоков (и фоновой компиляции wasm)
        except (OSError, ValueError, IndexError):
            continue
        procs[int(pid)] = (ppid, cmd, rss, ticks)
    mine = {p for p, (_, cmd, _, _) in procs.items() if any(profile in a for a in cmd)}
    grew = True
    while grew:
        more = {p for p, (pp, _, _, _) in procs.items() if pp in mine and p not in mine}
        mine |= more
        grew = bool(more)
    out, cpu = {}, 0
    for p in mine:
        _, cmd, rss, ticks = procs[p]
        kind = next((a[7:] for a in cmd if a.startswith("--type=")), "browser")
        out[kind] = out.get(kind, 0) + rss / 1024
        cpu += ticks
    out["cpu_s"] = cpu / os.sysconf("SC_CLK_TCK")
    return out


def prof(secs):
    """Профиль основного потока вкладки за secs: собственное время по модулям wasm и скриптам"""
    s.c.call("Profiler.enable")
    s.c.call("Profiler.setSamplingInterval", interval=200)
    s.c.call("Profiler.start")
    time.sleep(secs)
    p = s.c.call("Profiler.stop")["profile"]
    nodes = {n["id"]: n for n in p["nodes"]}
    self_us = {}
    for sid, dt in zip(p["samples"], p["timeDeltas"]):
        self_us[sid] = self_us.get(sid, 0) + dt
    # wasm-модули: у модуля JIT (страница кода гостя) одна-две функции, у v86.wasm и virgl.wasm - сотни
    funcs = {}
    for n in p["nodes"]:
        url = n["callFrame"]["url"]
        if url.startswith("wasm://"):
            funcs.setdefault(url, set()).add(n["callFrame"]["functionName"])
    groups, top = {}, {}
    total = sum(self_us.values()) or 1
    for nid, us in self_us.items():
        cf = nodes[nid]["callFrame"]
        url, fn = cf["url"], cf["functionName"]
        if url.startswith("wasm://"):
            g = "JIT (код гостя)" if len(funcs[url]) <= 3 else "wasm " + url[-8:] + " (%d функций)" % len(funcs[url])
        elif url:
            g = "JS " + url.rsplit("/", 1)[-1][:40]
        else:
            g = fn or "?"
        groups[g] = groups.get(g, 0) + us
        if not g.startswith("JIT"):
            k = "%s | %s" % (g[:28], fn[:40])
            top[k] = top.get(k, 0) + us
    print("профиль %.0f с:" % secs, flush=True)
    for g, us in sorted(groups.items(), key=lambda kv: -kv[1])[:12]:
        print("  %-48s %5.1f%%" % (g, 100 * us / total))
    print("  функции:")
    for k, us in sorted(top.items(), key=lambda kv: -kv[1])[:15]:
        print("    %-72s %5.1f%%" % (k, 100 * us / total))


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
last_cpu = [chrome_mem(tmp)["cpu_s"]]
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
        elif kind == "prof":
            prof(float(what))
        elif kind == "cpu":
            # процессорное время своего Chrome (все процессы и потоки) с прошлого cpu:
            c = chrome_mem(tmp)["cpu_s"]
            print("процессор %s: %.1f с" % (what, c - last_cpu[0]), flush=True)
            last_cpu[0] = c
        elif kind == "mem":
            m = chrome_mem(tmp)
            m.pop("cpu_s", None)
            print("память %s: %s" % (what, ", ".join("%s %.0f" % kv for kv in sorted(m.items()))), flush=True)
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
