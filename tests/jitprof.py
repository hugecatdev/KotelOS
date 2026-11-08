#!/usr/bin/env python3
"""Профиль JIT v86 на нагрузке в госте: счётчики profiler_stat_get (компиляции, выходы в
интерпретатор, медленные пути памяти...) и опкоды (выполнено, выходы из JIT) за время команды.
v86 - сборка со счётчиками (PROFILER=1 OUT=build/v86-prof scripts/build-v86.sh), бандл - с
--v86 build/v86-prof и без --worker (счётчики читаются со страницы).
  python3 tests/jitprof.py БАНДЛ [--js ВЫРАЖЕНИЕ] [--x] [--pre КОМАНДА] НАГРУЗКА [--top N]
--js - выражение на странице до замера (send('startx\\r')), --x - ждать сервер X, --pre - команда в
машине до замера (несколько можно), НАГРУЗКА - команда в машине, за время которой меряем."""
import argparse
import glob
import os
import re
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, ROOT)
from run import Suite  # noqa: E402
from bundle import Chrome  # noqa: E402

# группы: у них g (reg в modrm) - другая инструкция
GROUPS = {0x80, 0x81, 0x83, 0xC0, 0xC1, 0xD0, 0xD1, 0xD2, 0xD3, 0xF6, 0xF7, 0xFE, 0xFF,
          0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF}
GROUPS_0F = {0x00, 0x01, 0x71, 0x72, 0x73, 0xAE, 0xBA, 0xC7}
PREFIXES = {0x26, 0x2E, 0x36, 0x3E, 0x64, 0x65, 0x66, 0x67, 0xF0, 0xF2, 0xF3}

SNAP = """(() => { const c = emulator.v86.cpu, e = c.wm.exports;
  if (!e.profiler_is_enabled()) return null;
  const st = []; for (let i = 0; i < %d; i++) st.push(e.profiler_stat_get(i));
  const ops = {};
  for (const [k, a] of [["exec", [0, 0, 0]], ["exit", [0, 1, 0]], ["wasm", [0, 0, 1]], ["compiled", [1, 0, 0]]]) {
    const r = [];
    for (let op = 0; op < 256; op++) for (const f of [0, 1]) for (const m of [0, 1]) for (let g = 0; g < 8; g++)
      r.push(e.get_opstats_buffer(a[0], a[1], 0, a[2], op, f, m, g));
    ops[k] = r;
  }
  return { st, ops, t: performance.now() };
})()"""


def stat_names(path=None):
    # имена счётчиков - по порядку enum stat в profiler.rs той сборки, что в бандле
    src = [path] if path else sorted(glob.glob(os.path.join(ROOT, ".cache/v86-*/src/rust/profiler.rs")))
    if not src:
        sys.exit("нет .cache/v86-*/src/rust/profiler.rs - сначала scripts/build-v86.sh")
    text = open(src[-1]).read()
    body = text[text.index("pub enum stat {"):]
    body = body[:body.index("}")]
    return re.findall(r"^\s+([A-Z][A-Z0-9_]*),", body, re.M)


def opname(op, f, m, g):
    s = ("0F %02X" % op) if f else ("%02X" % op)
    if (f and op in GROUPS_0F) or (not f and op in GROUPS):
        s += "/%d" % g
    return s + (" mem" if m else "")


def ops_table(arr):
    out = {}
    i = 0
    for op in range(256):
        for f in (0, 1):
            for m in (0, 1):
                for g in range(8):
                    n = arr[i]
                    i += 1
                    if n and not (not f and op in PREFIXES):
                        k = opname(op, f, m, g)
                        out[k] = out.get(k, 0) + n
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle")
    ap.add_argument("load", help="команда в машине, за время которой меряем")
    ap.add_argument("--js", action="append", default=[])
    ap.add_argument("--x", action="store_true", help="ждать сервер X после --js")
    ap.add_argument("--pre", action="append", default=[])
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--stats", metavar="PROFILER_RS", help="profiler.rs сборки в бандле, если не из .cache/v86-*")
    a = ap.parse_args()

    names = stat_names(a.stats)
    page = a.bundle if a.bundle.startswith("http") else "file://" + os.path.abspath(a.bundle)
    tmp = tempfile.mkdtemp(prefix="jitprof-")  # профиль Chrome, /tmp - в памяти: удаляется в конце
    s = Suite(tmp, None)
    s.c = Chrome(tempfile.mkdtemp(dir=tmp))
    try:
        s.c.open("about:blank")
        s.c.call("Page.navigate", url=page)
        print("машина готова за %.1f с" % s.wait_ready(), flush=True)
        for js in a.js:
            s.ev(js)
        if a.x:
            t = time.time()
            while s.sh("test -S /tmp/.X11-unix/X0")[0]:
                assert time.time() - t < 120, "нет X"
                time.sleep(1)
            time.sleep(5)
        for cmd in a.pre:
            code, out, err = s.sh(cmd, a.timeout)
            print("$ %s -> %s %s" % (cmd[:80], code, (out + err).strip()[-200:]), flush=True)
        b = s.ev(SNAP % len(names))
        if b is None:
            sys.exit("v86 без счётчиков: PROFILER=1 scripts/build-v86.sh, бандл с --v86 этой папкой")
        code, out, err = s.sh(a.load, a.timeout)
        e = s.ev(SNAP % len(names))
        print("$ %s -> %s\n%s" % (a.load[:100], code, (out + err).strip()[-600:]), flush=True)

        secs = (e["t"] - b["t"]) / 1000
        # счётчик инструкций v86 32-битный (переполняется за ~40 с) - сумма выполненных опкодов
        instr = sum(e["ops"]["exec"]) - sum(b["ops"]["exec"])
        print("\n%.1f с, инструкций %.0f млн (%.0f MIPS)" % (secs, instr / 1e6, instr / 1e6 / secs if secs else 0))
        print("\nсчётчики JIT (разница):")
        for i, n in enumerate(names):
            d = e["st"][i] - b["st"][i]
            if d:
                print("  %-55s %14.0f" % (n, d))
        for kind, title in (("exec", "выполнено"), ("exit", "выходы из JIT"), ("compiled", "скомпилировано"),
                            ("wasm", "байт wasm на них")):
            tb, te = ops_table(b["ops"][kind]), ops_table(e["ops"][kind])
            diff = {k: te.get(k, 0) - tb.get(k, 0) for k in te}
            total = sum(v for v in diff.values() if v > 0)
            print("\nопкоды, %s: всего %.0f" % (title, total))
            for k, v in sorted(diff.items(), key=lambda kv: -kv[1])[:a.top]:
                if v > 0:
                    print("  %-12s %14.0f  %5.1f%%" % (k, v, 100 * v / total if total else 0))
    finally:
        s.c.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
