#!/usr/bin/env python3
"""Потолок SMP: как процессорное время гостя делится между потоками в живых сценариях.

python3 tests/smp/split.py БАНДЛ [сценарий...] [--site ПАПКА] [--json out.json]

БАНДЛ - имя папки в site/ (dwm, python, qt; собираются release.py). site/ раздаётся на свободном порту
127.0.0.1 (kt pkg add берёт пакеты из /repo), бандл открывается в headless Chromium,
в гостя кладётся ktop (сэмплер /proc), каждый сценарий - запуск ktop, нагрузка,
ожидание, пока гость затихнет. Итог по сценарию: время до последней работы, доля
занятости, самые большие потоки и потолок ускорения на 2 и 4 ядрах:
T_N = простой + max(занято / N, самый большой поток) - оценка сверху, она не знает
о зависимостях (X-клиент ждёт ответа сервера и т. п.).
"""
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("KT_ROOT") or os.path.dirname(os.path.dirname(HERE))  # KT_ROOT - где images/ и site/
# ktop собирается из ktop.c: i686-linux-musl-gcc -O2 -static -s -o tests/smp/ktop tests/smp/ktop.c
KTOP = os.environ.get("KTOP") or os.path.join(HERE, "ktop")
sys.path.insert(0, ROOT)
import bundle  # noqa: E402

KILL = "for p in /proc/[0-9]*; do c=\"$(tr '\\0' ' ' < $p/cmdline 2>/dev/null)\"; case \"$c\" in *'for p in'*) ;; %s) kill ${p#/proc/};; esac; done; true"
X = "export DISPLAY=:0 HOME=/root; "
BG = "setsid sh -c %s </dev/null >/dev/null 2>&1 &"


def sq(s):
    return "'" + s.replace("'", "'\\''") + "'"


# (имя, как запустить: exec - ждать команду, bg - в фоне, tty - набрать в терминале; команда; min_s; max_s; уборка)
SCEN = {
    "dwm": [
        ("startx", "tty", "startx", 8, 180, None),
        ("st-seq", "exec", X + "st -e sh -c 'seq 1 20000'", 2, 180, None),
        ("xcalc", "bg", X + "exec xcalc", 4, 120, KILL % "*xcalc*"),
        ("feh", "bg", X + "exec feh -g 640x480 /tmp/img.ppm", 4, 120, KILL % "*feh\\ *"),
        ("gzip", "exec", "seq 1 300000 | gzip -6 | wc -c", 1, 180, None),
        ("pkg-add", "exec", "kt pkg add python3 >/dev/null 2>&1", 1, 400, None),
    ],
    "python": [
        ("idle", "bg", "exec idle", 8, 180, KILL % "*idlelib*"),
        ("mpldemo", "bg", "exec python3 -m mpldemo", 8, 240, KILL % "*mpldemo*"),
    ],
    "qt": [
        ("pyqt-studio", "bg", X + "cd /root && exec pyqt-studio > /root/.cache/pyqt-studio.log 2>&1", 10, 300, None),
    ],
    # VirGL (ветка virgl: bundle.py --virgl, bundles/virgl/xinitrc): Mesa virpipe -> vtest-bridge -> страница
    "virgl": [
        ("startx", "tty", "startx", 6, 120, None),
        ("glxgears", "bg", X + "GALLIUM_DRIVER=virpipe exec timeout 15 glxgears -geometry 290x290+505+20", 5, 60, None),
        ("glxgears-soft", "bg", X + "GALLIUM_DRIVER=softpipe exec timeout 15 glxgears -geometry 290x290+505+20", 5, 60, None),
    ],
    "virglheavy": [
        ("startx", "tty", "startx", 6, 120, None),
        ("teapot", "bg", X + "cd /usr/share/mesa-demos; GALLIUM_DRIVER=virpipe exec timeout 20 teapot", 5, 80, None),
        ("gloss", "bg", X + "cd /usr/share/mesa-demos; GALLIUM_DRIVER=virpipe exec timeout 20 gloss", 5, 80, None),
        ("engine", "bg", X + "cd /usr/share/mesa-demos; GALLIUM_DRIVER=virpipe exec timeout 20 engine", 5, 80, None),
        ("terrain", "bg", X + "cd /usr/share/mesa-demos; GALLIUM_DRIVER=virpipe exec timeout 20 terrain", 5, 80, None),
        ("fire", "bg", X + "cd /usr/share/mesa-demos; GALLIUM_DRIVER=virpipe exec timeout 20 fire", 5, 80, None),
        ("luanti", "bg", X + "cd /root && GALLIUM_DRIVER=virpipe exec timeout 150 luanti --go --world /root/.minetest/worlds/w --name kt", 140, 260, None),
    ],
}
PREP = {
    "dwm": "{ printf 'P6\\n640 480\\n255\\n'; dd if=/dev/urandom bs=3072 count=300 2>/dev/null; } > /tmp/img.ppm",
    # студия и Designer уже открыты в снимке - закрыть, чтобы сценарий открыл их заново
    "qt": KILL % "*pyqt-studio*|*designer*",
}


def serve(site):
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = functools.partial(Q, directory=site)
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s.server_port


def ex(c, cmd, timeout=600):
    r = c.eval("exec(%s)" % json.dumps(cmd))
    return r


def parse(txt):
    lines = txt.strip().splitlines()
    s = lines[0].split()
    r = dict(busy=int(s[1]), idle=int(s[2]), tlast=float(s[3]), tall=float(s[4]), own=int(s[5]), steps=int(s[6]),
             hist=[0] * 9, threads=[])
    for l in lines[1:]:
        f = l.split()
        if f[0] == "H":
            r["hist"][int(f[1])] = int(f[2])
        elif f[0] == "T":
            r["threads"].append((int(f[-1]), "_".join(f[3:-1]), int(f[1]), int(f[2])))
    r["threads"].sort(reverse=True)
    return r


def ceilings(r, n):
    B = max(sum(r["hist"]), 1)
    I = r["idle"]
    P = r["threads"][0][0] if r["threads"] else 0
    t1 = (B + I) / 100
    runq = (I + sum(h / max(1, min(k, n)) for k, h in enumerate(r["hist"]))) / 100
    big = (I + max(B / n, P)) / 100
    return t1, runq, big


def report(name, r):
    B = max(sum(r["hist"]), 1)
    I = r["idle"]
    attributed = sum(t[0] for t in r["threads"])
    out = ["%s: %.1f с до последней работы, занято %.0f%% (%d тиков; ktop %d), по потокам видно %d%%" % (
        name, r["tlast"], 100 * B / (B + I), B, r["own"], 100 * attributed / B)]
    out.append("    очередь готовых (доля занятого): " + " ".join(
        "%d:%.0f%%" % (k, 100 * h / B) for k, h in enumerate(r["hist"]) if h))
    for t in r["threads"][:7]:
        out.append("    %-16s tid %-5d %5.1f с  %4.0f%%" % (t[1], t[2], t[0] / 100, 100 * t[0] / B))
    for n in (2, 4):
        t1, runq, big = ceilings(r, n)
        out.append("    %d ядра: по очереди готовых %.2fx (%.1f -> %.1f с), сверху по самому большому потоку %.2fx" % (
            n, t1 / runq, t1, runq, t1 / big))
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    opt = {"--json": None, "--site": os.path.join(ROOT, "site")}
    for k in opt:
        if k in args:
            i = args.index(k)
            opt[k] = args[i + 1]
            del args[i:i + 2]
    js = opt["--json"]
    name, only = args[0], args[1:]
    port = serve(opt["--site"])
    tmp = tempfile.mkdtemp(prefix="kt-smp-")
    c = bundle.Chrome(tmp)
    res = {}
    try:
        t0 = time.time()
        c.open("http://127.0.0.1:%d/%s/index.html" % (port, name))
        while not c.eval("typeof agentReady !== 'undefined' && agentReady"):
            if time.time() - t0 > 300:
                raise RuntimeError("не загрузилась")
            time.sleep(0.2)
        print("%s готов за %.1f с, load %s" % (name, time.time() - t0, open("/proc/loadavg").read().split()[0]), flush=True)
        c.eval(bundle.SETTLE % (1000, 60000))
        b64 = base64.b64encode(open(KTOP, "rb").read()).decode()
        c.eval("writeFile('/tmp/ktop', Uint8Array.from(atob('%s'), (ch) => ch.charCodeAt(0)))" % b64)
        assert ex(c, "chmod +x /tmp/ktop && /tmp/ktop 2>&1 | head -1")["out"].startswith("ktop"), "ktop не запускается"
        c.eval("window.__kt = ''; emulator.add_listener('serial0-output-byte', (b) => "
               "{ window.__kt = (window.__kt + String.fromCharCode(b)).slice(-200); }); 1")
        if name in PREP:
            ex(c, PREP[name])
            time.sleep(3)
        for sc, how, cmd, mn, mx, clean in SCEN[name]:
            if only and sc not in only:
                continue
            ex(c, "rm -f /tmp/k.out")
            c.eval("window.__kt = ''")
            ex(c, BG % sq("exec /tmp/ktop /tmp/k.out %d %d" % (mn, mx)))
            ts = time.time()
            if how == "tty":
                c.eval("send(%s)" % json.dumps(cmd + "\r"))
            elif how == "bg":
                ex(c, BG % sq(cmd))
            else:
                r = ex(c, cmd)
                if r["code"]:
                    print("  %s: код %s %s" % (sc, r["code"], r["err"][-300:]), flush=True)
            while not c.eval("window.__kt.includes('KTOP-DONE')"):
                time.sleep(0.5)
                if time.time() - ts > mx + 60:
                    raise RuntimeError("%s: ktop не закончил" % sc)
            r = ex(c, "cat /tmp/k.out")
            res[sc] = parse(r["out"])
            print(report(sc, res[sc]), flush=True)
            if clean:
                ex(c, clean)
                c.eval(bundle.SETTLE % (1000, 30000))
        if js:
            json.dump(res, open(js, "w"), indent=1)
    finally:
        c.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
