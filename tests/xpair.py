"""Парный замер сессии X с разным содержимым машины: ядро, файлы поверх образа, пакеты, сборка v86.

python3 tests/xpair.py [-n 3] [--load имя] ВАРИАНТ ВАРИАНТ...

ВАРИАНТ - "метка: ключи bundle.py", например
  "base:" "o2: --kernel build/bzImage-o2" "xorg: --file build/Xorg:/usr/bin/Xorg" "jit: --v86 build/v86"
Первый вариант - база. Все варианты идут одновременно, каждый в своём Chromium (как tests/pair.py):
занятость хоста у них общая. Нагрузка - сессия X (tests/bench/x-*.xinitrc) несколько раз подряд в
одной машине: первый раз холодный, дальше прогретые. На нагрузку - время, процессор вкладки, её
основного потока и то, как это время делится в госте (user/sys/idle по /proc/stat, %).
Дальше в строке - кэш JIT v86 (patches/v86/19): сколько раз сброшен целиком, сколько раз выселялись
старые модули, сколько мест свободно, - и память вкладки (RSS). --jit 10=899 в ключах варианта -
set_jit_config после загрузки; --load tk - программы на FOX и GTK; --cmd и --pkgs - своя нагрузка.
"""
import argparse
import json
import os
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import bench  # noqa: E402
import bundle  # noqa: E402

PKGS = {"twm": ["xorg", "xeyes", "xcalc"], "tk": ["xorg", "xdotool", "fox-calculator", "fox-adie", "galculator"]}
STAT = "read a < /proc/stat; echo $a"


def build(args, out, load, mem, pkgs=None):
    cmd = [sys.executable, os.path.join(ROOT, "bundle.py"), "-o", out, "-n", "xpair", "--cfg", "boot.mem=%d" % mem,
           "--vga", "8", "--no-3d", "--file", os.path.join(ROOT, "tests/bench/x-%s.xinitrc" % load) + ":/root/.xinitrc"]
    r = subprocess.run(cmd + args + (pkgs or PKGS.get(load, PKGS["twm"])), cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit("bundle.py %s:\n%s%s" % (args, r.stdout, r.stderr))


def run(page, tmp, times, cmd, sync, jit=()):
    prof = tempfile.mkdtemp(dir=tmp)
    with bench.CHROME_LOCK:
        c = bundle.Chrome(prof)
    res = []
    try:
        t0 = time.time()
        c.open("file://" + page)
        while not c.eval("typeof agentReady !== 'undefined' && agentReady"):
            if time.time() - t0 > 240:
                raise RuntimeError("не загрузилась за 4 минуты")
            time.sleep(0.05)
        pids = bench.renderers(prof)
        c.eval(bundle.SETTLE % (1000, 60000))
        for k, v in jit:
            c.eval("emulator.v86.cpu.wm.exports.set_jit_config(%d, %d)" % (k, v))
        for _ in range(times):
            sync()
            c0 = bench.cpu(pids)
            r = c.eval("(async () => { const a = (await exec(%s)).out; const t = performance.now(); const r = await exec(%s); "
                       "const d = performance.now() - t; return [d, r.code, r.err, r.out, a, (await exec(%s)).out]; })()"
                       % (json.dumps(STAT), json.dumps(cmd), json.dumps(STAT)))
            if r[1]:
                raise RuntimeError("нагрузка: код %s %s\n%s" % (r[1], r[2][-300:], r[3][-1500:]))
            # сборка v86 со счётчиком (patches/v86/19): сколько раз кэш JIT сброшен целиком и сколько мест свободно
            j = c.eval("(() => { const e = emulator.v86.cpu.wm.exports; return e.jit_get_full_clears ? "
                       "[e.jit_get_full_clears(), e.jit_get_wasm_table_index_free_list_count(), "
                       "e.jit_get_evictions ? e.jit_get_evictions() : -1] : [-1, -1, -1]; })()")
            rss = sum(int(open("/proc/%s/statm" % p).read().split()[1]) for p in pids if os.path.exists("/proc/%s/statm" % p)) * 4 // 1024
            a, b = ([int(x) for x in s.split()[1:8]] for s in r[4:6])
            d = [y - x for x, y in zip(a, b)]
            tot = sum(d) or 1
            res.append((r[0] / 1000, *bench.since(c0, pids), 100 * (d[0] + d[1]) / tot, 100 * (d[2] + d[5] + d[6]) / tot,
                        100 * (d[3] + d[4]) / tot, j[0], j[2], j[1], rss, r[3]))
    finally:
        c.close()
        shutil.rmtree(prof, ignore_errors=True)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("variants", nargs="+", help='"метка: ключи bundle.py"')
    ap.add_argument("-n", type=int, default=3, help="кругов (по умолчанию 3)")
    ap.add_argument("--times", type=int, default=3, help="сессий подряд в одной машине (по умолчанию 3)")
    ap.add_argument("--load", default="twm", help="сессия tests/bench/x-ИМЯ.xinitrc (по умолчанию twm)")
    ap.add_argument("--size", default="800x600")
    ap.add_argument("--mem", type=int, default=256)
    ap.add_argument("--cmd", help="вместо сессии X - эта команда шелла (с --pkgs: пакеты бандла)")
    ap.add_argument("--pkgs", help="пакеты бандла через пробел")
    ap.add_argument("--out", action="store_true", help="показать вывод сессий (замеры внутри машины)")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="kt-xpair-")
    try:
        labels, pages, jits = [], [], []
        for i, v in enumerate(a.variants):
            label, _, args = v.partition(":")
            labels.append(label.strip())
            pages.append(os.path.join(tmp, "b%d.html" % i))
            args = shlex.split(args)
            # --jit НОМЕР=ЗНАЧЕНИЕ - не ключ bundle.py: set_jit_config после загрузки (10 - предел модулей JIT)
            jits.append([tuple(map(int, args[i + 1].split("="))) for i, x in enumerate(args) if x == "--jit"])
            args = [x for i, x in enumerate(args) if x != "--jit" and (i == 0 or args[i - 1] != "--jit")]
            build(args, pages[-1], a.load, a.mem, a.pkgs and a.pkgs.split())
        rounds = []
        for k in range(a.n):
            res = [None] * len(pages)
            barrier = threading.Barrier(len(pages), timeout=900)

            def one(i):
                try:
                    res[i] = run(pages[i], tmp, a.times, a.cmd or "timeout 200 startx " + a.size, barrier.wait, jits[i])
                except BaseException:
                    barrier.abort()
                    raise
            threads = [threading.Thread(target=one, args=(i,)) for i in range(len(pages))]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            if any(r is None for r in res):
                sys.exit("круг %d: вариант не отработал" % (k + 1))
            rounds.append(res)
            print("круг %d/%d, load %s" % (k + 1, a.n, open("/proc/loadavg").read().split()[0]), flush=True)
            for i, r in enumerate(res):
                print("  %-10s %s" % (labels[i], "  ".join("%.2f/%.2f/%.2f u%.0f s%.0f i%.0f сброс %d выс %d своб %d %dМБ" % x[:10] for x in r)), flush=True)
                if a.out:
                    print("\n".join("    | " + s for s in r[-1][-1].strip().split("\n")[-12:]), flush=True)
        for col, title in ((0, "время"), (2, "основной поток"), (1, "весь процессор вкладки")):
            print("\n%s: медиана отношения к %s по кругам (сессии 1..%d)" % (title, labels[0], a.times))
            for i in range(1, len(pages)):
                ratios = [statistics.median(r[i][j][col] / r[0][j][col] for r in rounds) for j in range(a.times)]
                print("  %-10s %s  среднее геом. %.3f" % (labels[i], " ".join("%.2f" % x for x in ratios), statistics.geometric_mean(ratios)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
