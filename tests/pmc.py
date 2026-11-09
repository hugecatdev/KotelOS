#!/usr/bin/env python3
"""Аппаратные счётчики процессора на основном потоке вкладки за время нагрузки в госте: такты,
инструкции, промахи предсказателя и кэшей (perf_event_open, только пользовательский код; perf не
нужен, /proc/sys/kernel/perf_event_paranoid <= 2). Сколько машинных инструкций и обращений к памяти
хоста приходится на работу гостя - то, чего не видно ни в профиле вкладки, ни в микротестах.
  python3 tests/pmc.py БАНДЛ [ПРОГРЕВ] [НАГРУЗКА]
БАНДЛ - без --worker (v86 в основном потоке). НАГРУЗКА - команда в машине (по умолчанию
startx 800x600 - бандл как у tests/bench.py --x), ПРОГРЕВ - сколько раз выполнить её до замера (2)."""
import ctypes
import os
import shutil
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, ROOT)
from run import Suite  # noqa: E402
from bundle import Chrome  # noqa: E402
import bench  # noqa: E402

libc = ctypes.CDLL(None, use_errno=True)
HW, CACHE = 0, 3
# (тип, config)
EVENTS = [
    ("такты", HW, 0), ("инструкции", HW, 1), ("ветвления", HW, 4), ("промахи ветвлений", HW, 5),
    ("L1I промахи", CACHE, 1 | 0 << 8 | 1 << 16), ("iTLB промахи", CACHE, 4 | 0 << 8 | 1 << 16),
    ("L1D обращения", CACHE, 0 | 0 << 8 | 0 << 16), ("L1D промахи", CACHE, 0 | 0 << 8 | 1 << 16),
    ("dTLB промахи", CACHE, 3 | 0 << 8 | 1 << 16), ("LLC промахи", CACHE, 2 | 0 << 8 | 1 << 16),
]


def open_counter(typ, config, tid):
    # struct perf_event_attr: type, size, config, sample_period, sample_type, read_format, flags...
    attr = bytearray(128)
    struct.pack_into("IIQQQQ", attr, 0, typ, 128, config, 0, 0, 0)
    flags = 1 << 5 | 1 << 6  # exclude_kernel, exclude_hv
    struct.pack_into("Q", attr, 40, flags)
    buf = (ctypes.c_char * 128).from_buffer(attr)
    fd = libc.syscall(298, buf, tid, -1, -1, 0)
    if fd < 0:
        return None
    return fd


def read(fd):
    return struct.unpack("Q", os.read(fd, 8))[0]


page = "file://" + os.path.abspath(sys.argv[1])
warm = int(sys.argv[2]) if len(sys.argv) > 2 else 2
load = sys.argv[3] if len(sys.argv) > 3 else "startx 800x600"
tmp = tempfile.mkdtemp(prefix="kt-pmc-")
s = Suite(tmp, None)
s.c = Chrome(tempfile.mkdtemp(dir=tmp))
try:
    s.c.open(page)
    s.wait_ready()
    for i in range(warm):
        s.sh(load, 600)
    pids = bench.renderers(tmp)
    # основной поток вкладки с машиной - тот из renderer, что съел больше всего процессора
    pid = max(pids, key=lambda p: bench.cpu([p])[1])
    fds = [(n, open_counter(t, c, int(pid))) for n, t, c in EVENTS]
    a = {n: read(fd) for n, fd in fds if fd is not None}
    c0 = bench.cpu([pid])
    s.sh(load, 600)
    c1 = bench.cpu([pid])
    b = {n: read(fd) for n, fd in fds if fd is not None}
    d = {n: b[n] - a[n] for n in a}
    print("основной поток %.1f с" % (c1[1] - c0[1]))
    for n, _, _ in EVENTS:
        if n in d:
            print("  %-20s %8.0f млн" % (n, d[n] / 1e6))
        else:
            print("  %-20s недоступно" % n)
    if "такты" in d and "инструкции" in d:
        print("  инструкций на такт %.2f; на 1000 инструкций: промахов ветвлений %.1f, L1I %.1f, iTLB %.2f, L1D %.1f, dTLB %.2f, LLC %.2f" % (
            d["инструкции"] / d["такты"], *(1000 * d.get(k, 0) / d["инструкции"] for k in
                                           ("промахи ветвлений", "L1I промахи", "iTLB промахи", "L1D промахи", "dTLB промахи", "LLC промахи"))))
finally:
    s.c.close()
    shutil.rmtree(tmp, ignore_errors=True)
