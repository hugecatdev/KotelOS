"""Скорость v86: одни и те же нагрузки в госте с разными сборками libv86.js/v86.wasm.

python3 tests/bench.py vendor/v86 ДРУГАЯ_ПАПКА... [-n 3] [-k имя] [--x]

Для каждой папки собирается бандл (bundle.py --v86, загрузка с ядра), потом
круги: в каждом круге каждый вариант по разу, в свежем headless Chromium, и
порядок в каждом круге сдвигается (A B C, B C A, C A B) - так шум от соседей
по хосту и место в круге делятся поровну; кругов лучше не меньше вариантов. Три числа на
нагрузку: время по часам страницы вокруг exec() (то, что видит пользователь,
включая мост), процессорное время всей вкладки (с фоновой компиляцией wasm в
V8) и её основного потока (сам v86) - эти два почти не зависят от занятости
хоста. В конце медианы и отношение к первому варианту
(меньше 1 - быстрее).
"""
import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bundle

PKGS = ["python3", "lua5.4", "micropython"]
LOAD = [
    ("fork", "i=0; while [ $i -lt 400 ]; do /bin/true; i=$((i+1)); done"),
    ("sh", "i=0; s=0; while [ $i -lt 60000 ]; do s=$((s+i*i%7)); i=$((i+1)); done; echo $s"),
    ("sha256", "dd if=/dev/zero bs=1M count=24 2>/dev/null | sha256sum"),
    ("gzip", "seq 1 300000 | gzip -6 | wc -c"),
    ("memcpy", "dd if=/dev/zero of=/dev/null bs=64k count=40000 2>/dev/null"),
    ("lua", "lua5.4 -e 'local t = {} for i = 1, 800000 do t[i % 1000 + 1] = (t[i % 1000 + 1] or 0) + i end print(#t)'"),
    ("lua-fp", "lua5.4 -e 'local s = 0 for i = 1, 400000 do s = s + math.sin(i) * math.sqrt(i) / i end print(s)'"),
    ("mpy", "micropython -c 'd = {}\nfor i in range(200000): d[i % 977] = d.get(i % 977, 0) + i\nprint(len(d))'"),
    ("py-start", "for i in 1 2 3; do python3.12 -c pass; done"),
    ("py-import", "python3.12 -c 'import json, re, decimal, fractions, statistics, email.parser, urllib.request, asyncio'"),
    ("py-loop", "python3.12 -c 'print(sum(i * i % 7 for i in range(600000)))'"),
    ("py-float", "python3.12 -c 'import math\nprint(sum(math.sin(i) * math.sqrt(i) for i in range(400000)))'"),
]
# --x: сессия X целиком (tests/bench/xinitrc): сервер, twm, xeyes, xcalc, xterm с прокруткой. Три раза
# подряд в одной машине: первый - холодный (страницы кода ещё не скомпилированы), дальше - прогретые
XPKGS = ["xorg", "xeyes", "xcalc"]
XLOAD = [("x-1", "startx 800x600"), ("x-2", "startx 800x600"), ("x-3", "startx 800x600")]
NET = [
    ("net-in", "(async () => { const d = new Uint8Array(4 << 20).fill(97); const t = performance.now(); "
               "await writeFile('/tmp/net.bin', d); return performance.now() - t; })()"),
    ("net-out", "(async () => { await exec(\"[ -s /tmp/net.bin ] || head -c 4194304 /dev/zero | tr '\\\\0' a > /tmp/net.bin\"); "
                "const t = performance.now(); const b = await readFile('/tmp/net.bin'); "
                "if (b.length !== 4 << 20) throw new Error('длина ' + b.length); return performance.now() - t; })()"),
]


def build(v86, out, mem, x=False, worker=False):
    args = [sys.executable, os.path.join(ROOT, "bundle.py"), "--v86", v86, "-o", out, "-n", "bench", "--cfg", "boot.mem=%d" % mem]
    if worker:
        args += ["--cfg", "boot.worker=on"]
    if x:
        args += ["--vga", "8", "--no-3d", "--file", os.path.join(ROOT, "tests/bench/xinitrc") + ":/root/.xinitrc"] + XPKGS
    else:
        args += PKGS
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit("bundle.py %s:\n%s%s" % (v86, r.stdout, r.stderr))


def renderers(profile):
    out = []
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            cmd = open("/proc/%s/cmdline" % pid, "rb").read().decode(errors="replace")
        except OSError:
            continue
        if "--type=renderer" in cmd and profile in cmd:
            out.append(pid)
    return out


def cpu(pids):
    """процессорное время процессов, с: все потоки (и закончившиеся) и основной поток (там JS и v86)"""
    t = m = 0
    for pid in pids:
        try:
            f = open("/proc/%s/stat" % pid).read().rsplit(")", 1)[1].split()
            g = open("/proc/%s/task/%s/stat" % (pid, pid)).read().rsplit(")", 1)[1].split()
        except OSError:
            continue
        t += int(f[11]) + int(f[12])
        m += int(g[11]) + int(g[12])
    hz = os.sysconf("SC_CLK_TCK")
    return t / hz, m / hz


def since(c0, pids):
    c1 = cpu(pids)
    return c1[0] - c0[0], c1[1] - c0[1]


CHROME_LOCK = threading.Lock()


def run_once(page, names, tmp, load=LOAD, cfg=(), chrome=None, sync=None):
    prof = tempfile.mkdtemp(dir=tmp)
    with CHROME_LOCK:
        # chrome - свой запускатель Chromium у варианта (скрипт с ключами V8): bundle.Chrome берёт его из CHROME
        old = os.environ.get("CHROME")
        if chrome:
            os.environ["CHROME"] = chrome
        try:
            c = bundle.Chrome(prof)
        finally:
            if chrome:
                os.environ.pop("CHROME")
                if old:
                    os.environ["CHROME"] = old
    res = {}
    try:
        t0 = time.time()
        c.open("file://" + page)
        while not c.eval("typeof agentReady !== 'undefined' && agentReady"):
            if time.time() - t0 > 240:
                raise RuntimeError("не загрузилась за 4 минуты")
            time.sleep(0.05)
        pids = renderers(prof)
        res["boot"] = (time.time() - t0, *cpu(pids))
        c.eval(bundle.SETTLE % (1000, 60000))
        for k, v in cfg:
            c.eval("emulator.v86.cpu.wm.exports.set_jit_config(%d, %d)" % (k, v))
        for name, cmd in load:
            if name not in names:
                continue
            if sync:
                sync()  # парный замер: нагрузка начинается у всех вариантов разом
            c0 = cpu(pids)
            r = c.eval("(async () => { const t = performance.now(); const r = await exec(%s); "
                       "return [performance.now() - t, r.code, r.err]; })()" % json.dumps(cmd))
            if r[1]:
                raise RuntimeError("%s: код %s %s" % (name, r[1], r[2][-300:]))
            res[name] = (r[0] / 1000, *since(c0, pids))
        for name, expr in NET:
            if name in names:
                c0 = cpu(pids)
                res[name] = (c.eval(expr) / 1000, *since(c0, pids))
    finally:
        c.close()
        shutil.rmtree(prof, ignore_errors=True)
    return res


def table(title, names, labels, med):
    w = max(len(n) for n in names)
    print("\n" + title + "".join("  %14s" % x[:14] for x in labels))
    for n in names:
        line = "%-*s" % (w + 1, n) + "  %14.2f" % med[0][n]
        for m in med[1:]:
            line += "  %7.2f (%.2f)" % (m[n], m[n] / med[0][n])
        print(line)
    for j, m in enumerate(med[1:], 1):
        g = statistics.geometric_mean([m[n] / med[0][n] for n in names])
        print("  среднее геом. %s / %s: %.3f" % (labels[j], labels[0], g))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("v86", nargs="+", help="папки с libv86.js, v86.wasm и BIOS; ПАПКА#5=100000 - с настройкой JIT (set_jit_config)")
    ap.add_argument("-n", type=int, default=3, help="кругов (по умолчанию 3)")
    ap.add_argument("-k", action="append", help="только эти нагрузки (можно несколько)")
    ap.add_argument("--mem", type=int, default=256, help="память машины, МБ")
    ap.add_argument("--json", help="сырые замеры сюда")
    ap.add_argument("--x", action="store_true", help="нагрузка - сессии X (Xorg, twm, xterm...), бандл с экраном")
    ap.add_argument("--worker", action="store_true", help="v86 в Web Worker (boot.worker): смотреть время, основной поток тут - только страница")
    a = ap.parse_args()
    load = XLOAD if a.x else LOAD
    names = ["boot"] + [n for n, _ in (load if a.x else load + NET)]
    if a.k:
        names = ["boot"] + [n for n in names if n in a.k]
    tmp = tempfile.mkdtemp(prefix="kt-bench-")
    try:
        pages = []
        cfgs = []
        for i, v in enumerate(a.v86):
            # ПАПКА#5=100000,6=0 - после загрузки set_jit_config(номер, значение): порог JIT и т.п.
            v, _, cfg = v.partition("#")
            cfgs.append([tuple(map(int, kv.split("="))) for kv in cfg.split(",") if kv])
            page = os.path.join(tmp, "b%d.html" % i)
            build(os.path.abspath(v), page, a.mem, a.x, a.worker)
            pages.append(page)
        runs = [[] for _ in a.v86]
        for k in range(a.n):
            print("круг %d/%d, load %s" % (k + 1, a.n, open("/proc/loadavg").read().split()[0]), flush=True)
            # порядок сдвигается каждый круг: место в круге делится поровну
            for i in [(j + k) % len(pages) for j in range(len(pages))]:
                r = run_once(pages[i], names, tmp, load, cfgs[i])
                runs[i].append(r)
                print("  %-28s %s" % (a.v86[i][-28:], " ".join("%s=%.2f/%.2f/%.2f" % (n, *r[n]) for n in names if n in r)), flush=True)
        if a.json:
            with open(a.json, "w") as f:
                json.dump({"v86": a.v86, "runs": runs}, f, indent=1)
        labels = [os.path.basename(os.path.normpath(v.partition("#")[0])) + v.partition("#")[2][-9:] for v in a.v86]
        for col, title in ((2, "основной поток (эмуляция), медианы, с"), (1, "весь процессор вкладки (с компиляцией V8), медианы, с"),
                           (0, "время, медианы, с")):
            table(title, names, labels, [{n: statistics.median(r[n][col] for r in rr) for n in names} for rr in runs])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
