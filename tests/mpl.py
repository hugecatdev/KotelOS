import argparse
import filecmp
import glob
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = ROOT + "/packages"
SITE = "usr/lib/python3.12/site-packages"
PATCH = ROOT + "/matplotlib.patch"


def tree(dst, original):
    os.makedirs(dst + "/usr")
    for p in ("python-matplotlib", "python-matplotlib-data", "python-matplotlib-fonts"):
        subprocess.run(["cp", "-as", "%s/%s/usr/." % (PKG, p), dst + "/usr/"], check=True)
    if not original:
        return
    for line in open(PATCH):
        if line.startswith("+++ b/"):
            path = os.path.join(dst, SITE, line[6:].strip())
            real = os.path.realpath(path)
            os.remove(path)
            shutil.copy(real, path)
    with open(PATCH) as f:
        subprocess.run(["patch", "-R", "-s", "-p1", "-d", os.path.join(dst, SITE)], stdin=f, check=True)


def render(top, out, extra):
    std = sorted(glob.glob(PKG + "/python3*/usr/lib/python3.12"))
    path = [os.path.join(top, SITE)] + std + [d + "/lib-dynload" for d in std] + sorted(glob.glob(PKG + "/python-*/" + SITE))
    libs = ":".join(glob.glob(PKG + "/*/usr/lib") + glob.glob(PKG + "/*/lib"))
    env = dict(os.environ, PYTHONHOME=PKG + "/minipython/usr", PYTHONPATH=":".join(path), PYTHONDONTWRITEBYTECODE="1",
               MPLCONFIGDIR=top + "/cfg")
    r = subprocess.run([PKG + "/musl/lib/ld-musl-i386.so.1", "--library-path", libs, PKG + "/minipython/usr/bin/python3.12",
                        ROOT + "/tests/mplfigs.py", out] + extra, env=env)
    if r.returncode:
        sys.exit("не отрисовалось: " + top)


def main():
    ap = argparse.ArgumentParser(description="matplotlib с matplotlib.patch против исходного: те же картинки побайтно")
    ap.add_argument("--time", action="store_true", help="показать время кадра на хосте")
    ap.add_argument("--keep", metavar="ПАПКА", help="оставить деревья и картинки в этой папке")
    a = ap.parse_args()
    tmp = a.keep or tempfile.mkdtemp(prefix="kt-mpl-")
    try:
        outs = []
        for name in ("orig", "new"):
            top = os.path.join(tmp, name)
            shutil.rmtree(top, ignore_errors=True)
            tree(top, name == "orig")
            print("исходный:" if name == "orig" else "с правками:")
            sys.stdout.flush()
            outs.append(top + "/out")
            render(top, outs[-1], ["--time"] if a.time else [])
        names = sorted(os.listdir(outs[0]))
        if names != sorted(os.listdir(outs[1])):
            sys.exit("наборы файлов разные")
        bad = [n for n in names if not filecmp.cmp(os.path.join(outs[0], n), os.path.join(outs[1], n), shallow=False)]
        print("файлов %d, расхождений %d%s" % (len(names), len(bad), ": " + " ".join(bad) if bad else ""))
        sys.exit(1 if bad else 0)
    finally:
        if not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
