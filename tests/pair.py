"""Парный замер v86: варианты работают одновременно, каждый в своём Chromium, - занятость хоста,
нагрев и частота у них общие, поэтому отношение времён держится и там, где прогоны по очереди
(tests/bench.py) расходятся на 10-15%. Нагрузки и бандлы - как в bench.py.

python3 tests/pair.py ПАПКА ДРУГАЯ_ПАПКА... [-n 4] [-k имя] [--x] [--worker]

Варианты задаются как в bench.py (ПАПКА#5=100000 - с настройкой JIT); ПАПКА%СКРИПТ - со своим
запускателем Chromium (скрипт, который зовёт chromium с ключами V8 и "$@"). Число вариантов - не больше
числа свободных ядер / 3: у каждого свой основной поток и фоновая компиляция. В конце - медианы
отношений к первому варианту по кругам (меньше 1 - быстрее)."""
import argparse
import os
import shutil
import statistics
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import bench  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("v86", nargs="+")
    ap.add_argument("-n", type=int, default=4, help="кругов (по умолчанию 4)")
    ap.add_argument("-k", action="append", help="только эти нагрузки")
    ap.add_argument("--mem", type=int, default=256)
    ap.add_argument("--x", action="store_true", help="нагрузка - сессии X")
    ap.add_argument("--worker", action="store_true", help="v86 в Web Worker: смотреть время и процессор вкладки")
    a = ap.parse_args()
    load = bench.XLOAD if a.x else bench.LOAD
    names = ["boot"] + [n for n, _ in load]
    if a.k:
        names = ["boot"] + [n for n in names if n in a.k]
    tmp = tempfile.mkdtemp(prefix="kt-pair-")
    try:
        pages, cfgs, chromes = [], [], []
        for i, v in enumerate(a.v86):
            # ПАПКА%СКРИПТ - вариант со своим запускателем Chromium (ключи V8)
            v, _, chrome = v.partition("%")
            chromes.append(chrome or None)
            v, _, cfg = v.partition("#")
            cfgs.append([tuple(map(int, kv.split("="))) for kv in cfg.split(",") if kv])
            pages.append(os.path.join(tmp, "b%d.html" % i))
            bench.build(os.path.abspath(v), pages[-1], a.mem, a.x, a.worker)
        rounds = []
        for k in range(a.n):
            res = [None] * len(pages)
            # каждая нагрузка начинается у всех разом: иначе быстрый вариант уходит вперёд и
            # делит ядра уже с другой нагрузкой соседей
            barrier = threading.Barrier(len(pages), timeout=900)

            def one(i):
                try:
                    res[i] = bench.run_once(pages[i], names, tmp, load, cfgs[i], chromes[i], barrier.wait)
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
                print("  %-28s %s" % (a.v86[i][-28:], " ".join("%s=%.2f/%.2f/%.2f" % (n, *r[n]) for n in names)), flush=True)
        for col, title in ((2, "основной поток (эмуляция)"), (1, "весь процессор вкладки (с компиляцией V8)"), (0, "время")):
            print("\n%s: медиана отношения к %s по кругам" % (title, a.v86[0]))
            for i in range(1, len(pages)):
                ratios = {n: statistics.median(r[i][n][col] / r[0][n][col] for r in rounds) for n in names}
                print("  %-28s %s  среднее геом. %.3f" % (a.v86[i][-28:], " ".join("%s=%.2f" % (n, ratios[n]) for n in names),
                                                         statistics.geometric_mean(ratios.values())))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
