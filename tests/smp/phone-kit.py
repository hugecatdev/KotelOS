#!/usr/bin/env python3
"""Набор для телефона: python3 tests/smp/phone-kit.py ПАПКА V86_BASE V86_ATOMIC

В ПАПКУ кладутся base.html и atomic.html (бандлы bundle.py --v86 с python3, lua5.4,
micropython, как в tests/bench.py, без снимка) и index.html (tests/smp/phone.html).
Раздать: python3 -m http.server 8090 --bind 0.0.0.0 -d ПАПКА, открыть на телефоне
http://IP-компьютера:8090/. KT_ROOT - где images/ (по умолчанию корень репозитория).
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("KT_ROOT") or os.path.dirname(os.path.dirname(HERE))


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    out, base, atomic = (os.path.abspath(x) for x in sys.argv[1:])
    os.makedirs(out, exist_ok=True)
    for name, v86 in (("base", base), ("atomic", atomic)):
        r = subprocess.run([sys.executable, "bundle.py", "--v86", v86, "-o", os.path.join(out, name + ".html"),
                            "-n", "smp" + name, "--mem", "256", "python3", "lua5.4", "micropython"],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stdout + r.stderr)
        print(r.stdout.strip().splitlines()[-1][:120])
    shutil.copy(os.path.join(HERE, "phone.html"), os.path.join(out, "index.html"))
    print("готово:", out)


if __name__ == "__main__":
    main()
