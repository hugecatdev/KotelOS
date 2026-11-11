"""Выборочный профиль гостя: где работает процессор машины во время сессии X.

python3 tests/gprof.py [--kernel bzImage --map System.map] [--sym ИМЯ=ФАЙЛ_С_СИМВОЛАМИ ...] [ключи bundle.py]

Страница между отрезками главного цикла v86 (раз в ~4 мс) читает EIP, CR3 и CPL процессора. Сессия -
tests/bench/x-maps.xinitrc (как x-twm, но печатает /proc/PID/maps Xorg, twm и xterm), прогоняется
дважды, выборки берутся со второй (прогретой). Адресные пространства (CR3) сопоставляются с процессами по
картам; ядро раскладывается по System.map, программы - по файлам из карт, а внутри файла - по символам
(--sym Xorg=.cache/xorg-build/hw/xfree86/Xorg: файл до strip; иначе только доля файла).
"""
import argparse
import bisect
import collections
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bundle  # noqa: E402

SAMPLER = """(() => { const c = emulator.v86.cpu; window.gprof = [];
  window.gprofTimer = setInterval(() => gprof.push(c.instruction_pointer[0] >>> 0, c.cr[3] >>> 0, c.cpl[0]), 1); })()"""


def symbols(path):
    out = subprocess.run(["nm", "-n", "--defined-only", path], capture_output=True, text=True).stdout
    if not out.strip():
        out = subprocess.run(["nm", "-D", "-n", "--defined-only", path], capture_output=True, text=True).stdout
    syms = []
    for line in out.splitlines():
        f = line.split()
        if len(f) == 3 and f[1] in "tTwW":
            syms.append((int(f[0], 16), f[2]))
    return syms


def lookup(syms, addr):
    i = bisect.bisect_right(syms, (addr, "\xff")) - 1
    return syms[i][1] if i >= 0 else "?"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--kernel")
    ap.add_argument("--map", help="System.map ядра")
    ap.add_argument("--sym", action="append", default=[], metavar="ИМЯ=ФАЙЛ")
    ap.add_argument("--top", type=int, default=25)
    a, rest = ap.parse_known_args()
    tmp = tempfile.mkdtemp(prefix="kt-gprof-")
    try:
        page = tmp + "/b.html"
        cmd = [sys.executable, os.path.join(ROOT, "bundle.py"), "-o", page, "-n", "gprof", "--cfg", "boot.mem=256", "--vga", "8", "--no-3d",
               "--file", os.path.join(ROOT, "tests/bench/x-maps.xinitrc") + ":/root/.xinitrc"]
        if a.kernel:
            cmd += ["--kernel", a.kernel]
        r = subprocess.run(cmd + (rest or ["xorg", "xeyes", "xcalc"]), cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stdout + r.stderr)
        c = bundle.Chrome(tmp + "/prof")
        try:
            c.open("file://" + page)
            t0 = time.time()
            while not c.eval("typeof agentReady !== 'undefined' && agentReady"):
                if time.time() - t0 > 240:
                    sys.exit("не загрузилась")
                time.sleep(0.1)
            c.eval("exec('timeout 200 startx 800x600').then(() => 1)")
            c.eval(SAMPLER)
            out = c.eval("exec('timeout 200 startx 800x600').then((r) => r.out)")
            raw = c.eval("(clearInterval(gprofTimer), gprof)")
        finally:
            c.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # карты процессов из вывода сессии
    maps, name = {}, None
    for line in out.splitlines():
        if line.startswith("MAPS "):
            name = line[5:]
            maps[name] = []
        elif name and "-" in line[:18]:
            f = line.split()
            lo, hi = (int(x, 16) for x in f[0].split("-"))
            if "x" in f[1]:
                maps[name].append((lo, hi, int(f[2], 16), os.path.basename(f[5]) if len(f) > 5 else "[анонимная]"))
    samples = list(zip(raw[0::3], raw[1::3], raw[2::3]))
    n = len(samples)
    kern = [s for s in samples if s[0] >= 0xC0000000]
    user = collections.defaultdict(list)
    for eip, cr3, cpl in samples:
        if eip < 0xC0000000:
            user[cr3].append(eip)
    print("выборок %d: ядро %.1f%%, программы %.1f%%" % (n, 100 * len(kern) / n, 100 * (n - len(kern)) / n))

    def where(m, eip):
        for lo, hi, off, f in m:
            if lo <= eip < hi:
                return f, eip - lo + off
        return None

    syms = {k: symbols(v) for k, v in (s.split("=", 1) for s in a.sym)}
    by_file = collections.Counter()
    by_sym = collections.Counter()
    for cr3, eips in sorted(user.items(), key=lambda kv: -len(kv[1])):
        best = max(maps, key=lambda p: sum(1 for e in eips if where(maps[p], e)), default=None)
        hit = sum(1 for e in eips if where(maps[best], e)) if best else 0
        proc = best if best and hit > len(eips) * 0.7 else "другие"
        print("  cr3 %08x: %5.1f%% - %s" % (cr3, 100 * len(eips) / n, proc))
        for e in eips:
            w = where(maps[best], e) if proc != "другие" else None
            f = w[0] if w else "?"
            by_file[proc + ": " + f] += 1
            if w and f in syms and syms[f]:
                # программа без PIE - адреса символов абсолютные, библиотека - от начала файла
                by_sym[f + ": " + lookup(syms[f], e if syms[f][0][0] >= 0x8000000 else w[1])] += 1
    print("\nпо файлам, % всех выборок")
    for k, v in by_file.most_common(a.top):
        print("  %5.1f  %s" % (100 * v / n, k))
    if by_sym:
        print("\nпо функциям программ, % всех выборок")
        for k, v in by_sym.most_common(a.top):
            print("  %5.1f  %s" % (100 * v / n, k))
    if a.map and kern:
        ks = sorted((int(f[0], 16), f[2]) for f in (line.split() for line in open(a.map)) if len(f) == 3 and f[1] in "tT")
        cnt = collections.Counter(lookup(ks, e) for e, _, _ in kern)
        print("\nядро по функциям, % всех выборок")
        for k, v in cnt.most_common(a.top):
            print("  %5.1f  %s" % (100 * v / n, k))
    json.dump({"samples": raw, "out": out}, open(os.path.join(ROOT, "build", "gprof.json"), "w"))


if __name__ == "__main__":
    main()
