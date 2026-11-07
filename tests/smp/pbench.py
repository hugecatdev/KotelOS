#!/usr/bin/env python3
"""Сравнение сборок v86 одновременным прогоном: python3 tests/smp/pbench.py БАЗА ВАРИАНТ... [-n 4]

tests/bench.py гоняет варианты по очереди, и на общем хосте (нагрузка 3-7) шум
между кругами доходит до ±12% - больше, чем различия в 5-10%. Здесь в каждом круге
все варианты запущены сразу, каждый в своём headless Chromium, и каждая нагрузка
стартует во всех одновременно: занятость хоста бьёт по всем одинаково, а
отношение «вариант / база» берётся внутри одного окна времени. Мера - процессорное
время основного потока вкладки (там v86), медиана отношений по кругам.
Нагрузки и сборка бандлов - из tests/bench.py. KT_ROOT - где images/.
"""
import argparse
import os
import shutil
import statistics
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("KT_ROOT") or os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, ROOT)
import bench  # noqa: E402
import bundle  # noqa: E402


class Run:
    def __init__(self, page, tmp):
        self.prof = tempfile.mkdtemp(dir=tmp)
        self.c = bundle.Chrome(self.prof)
        self.c.open("file://" + page)
        self.pids = None

    def ready(self):
        t0 = time.time()
        while not self.c.eval("typeof agentReady !== 'undefined' && agentReady"):
            if time.time() - t0 > 300:
                raise RuntimeError("не загрузилась")
            time.sleep(0.1)
        self.pids = bench.renderers(self.prof)
        self.c.eval(bundle.SETTLE % (1000, 60000))

    def load(self, cmd, out, i, barrier):
        import json
        barrier.wait()
        c0 = bench.cpu(self.pids)
        r = self.c.eval("(async () => { const r = await exec(%s); return [r.code, r.err]; })()" % json.dumps(cmd))
        if r[0]:
            raise RuntimeError("код %s: %s" % (r[0], r[1][-200:]))
        out[i] = bench.since(c0, self.pids)[1]

    def close(self):
        self.c.close()
        shutil.rmtree(self.prof, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("v86", nargs="+", help="папки сборок, первая - база")
    ap.add_argument("-n", type=int, default=4, help="кругов")
    ap.add_argument("-k", action="append", help="только эти нагрузки")
    a = ap.parse_args()
    loads = [(n, c) for n, c in bench.LOAD if not a.k or n in a.k]
    tmp = tempfile.mkdtemp(prefix="kt-pbench-")
    labels = [os.path.basename(os.path.normpath(v)) for v in a.v86]
    ratio = {n: [[] for _ in a.v86] for n, _ in loads}
    try:
        pages = []
        for i, v in enumerate(a.v86):
            pages.append(os.path.join(tmp, "b%d.html" % i))
            bench.build(os.path.abspath(v), pages[-1], 256)
        for k in range(a.n):
            print("круг %d/%d, load %s" % (k + 1, a.n, open("/proc/loadavg").read().split()[0]), flush=True)
            runs = [Run(p, tmp) for p in pages]
            try:
                th = [threading.Thread(target=r.ready) for r in runs]
                [t.start() for t in th]
                [t.join() for t in th]
                for name, cmd in loads:
                    out = [None] * len(runs)
                    bar = threading.Barrier(len(runs))
                    th = [threading.Thread(target=r.load, args=(cmd, out, i, bar)) for i, r in enumerate(runs)]
                    [t.start() for t in th]
                    [t.join() for t in th]
                    if None in out:
                        raise RuntimeError("%s не прошла" % name)
                    for i, x in enumerate(out):
                        ratio[name][i].append(x / out[0])
                    print("  %-10s база %.2f с, " % (name, out[0]) + ", ".join(
                        "%s %.2f" % (labels[i], out[i] / out[0]) for i in range(1, len(out))), flush=True)
            finally:
                for r in runs:
                    r.close()
        print("\nмедианы отношений к %s (процессор основного потока, одновременный прогон)" % labels[0])
        print("%-12s" % "" + "".join("%12s" % x[:12] for x in labels[1:]))
        for name, _ in loads:
            print("%-12s" % name + "".join("%12.3f" % statistics.median(ratio[name][i]) for i in range(1, len(a.v86))))
        print("%-12s" % "геом." + "".join("%12.3f" % statistics.geometric_mean(
            [statistics.median(ratio[n][i]) for n, _ in loads]) for i in range(1, len(a.v86))))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
