#!/usr/bin/env python3
"""Собрать бандлы сайта по описаниям bundles/ИМЯ.txt в site/ИМЯ/index.html."""
import argparse
import glob
import os
import shlex
import subprocess
import sys

DEFS = "bundles"
SITE = "site"


def main():
    ap = argparse.ArgumentParser(description="собрать бандлы по описаниям %s/ИМЯ.txt в %s/ИМЯ/index.html" % (DEFS, SITE))
    ap.add_argument("bundles", nargs="*", help="какие бандлы собрать (по умолчанию все)")
    ap.add_argument("--build", action="store_true", help="сначала пересобрать образ и пакеты: ./build.sh")
    a = ap.parse_args()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.stdout.reconfigure(line_buffering=True)
    defs = {os.path.basename(p)[:-4]: p for p in sorted(glob.glob(DEFS + "/*.txt"))}
    names = a.bundles or list(defs)
    unknown = [n for n in names if n not in defs]
    if unknown:
        sys.exit("нет описания %s (есть: %s)" % (" ".join(unknown), " ".join(defs)))
    if a.build:
        subprocess.run(["./build.sh"], check=True)
    for name in names:
        args = shlex.split(open(defs[name]).read(), comments=True)
        # бандл лежит в ИМЯ/, репозиторий - рядом: относительный адрес годится и для корня сайта, и
        # для github.io/<репозиторий>/, где /repo указал бы мимо
        if "--repo" not in args:
            args += ["--repo", "../repo"]
        out = os.path.join(SITE, name, "index.html")
        tmp = out + ".tmp"
        # сайт может раздаваться прямо сейчас: старый бандл заменяется только готовым новым
        if os.path.exists(tmp):
            os.remove(tmp)
        r = subprocess.run([sys.executable, "-B", "bundle.py"] + args + ["-n", name, "-o", tmp])
        if r.returncode:
            sys.exit("%s не собрался, в %s осталось как было" % (name, out))
        os.replace(tmp, out)
        print("  выложен в %s" % out)


if __name__ == "__main__":
    main()
