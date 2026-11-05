#!/usr/bin/env python3
import argparse
import glob
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import bundle

VERSIONS = "versions"
DEFS = "bundles"
SITE = "site"
TREE = (["bundle.py", "alpine.py", bundle.PAGE]
        + [bundle.IMG + "/" + f for f in ("bzImage", "rootfs.cpio", "build.json")]
        + [bundle.V86 + "/" + f for f in ("libv86.js", "v86.wasm", "seabios.bin", "vgabios.bin")])


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def plan():
    defs = sorted(glob.glob(DEFS + "/*.txt"))
    if not defs:
        sys.exit("нет описаний бандлов: %s/*.txt" % DEFS)
    files = set(TREE) | set(defs) | {bundle.REPO + "/index.txt"}
    if os.path.exists(bundle.REPO + "/alpine.txt.gz"):
        files.add(bundle.REPO + "/alpine.txt.gz")
    for url in re.findall(r'<(?:link|script) [^>]*?(?:href|src)="(https://[^"]+)"', open(bundle.PAGE).read()):
        bundle.fetch(url)
        files.add(os.path.join(bundle.CACHE, hashlib.sha1(url.encode()).hexdigest()))
    bundles = {}
    for d in defs:
        args = shlex.split(open(d).read(), comments=True)
        a = bundle.options(args)
        names = bundle.closure(a.packages)
        alien = [n for n in names if n in bundle.APK]
        if alien:
            sys.exit("%s: пакеты из Alpine качаются при сборке и не замораживаются: %s" % (d, " ".join(alien)))
        extra = [spec.partition(":")[0] for spec in a.file]
        outside = [f for f in extra if os.path.isabs(f) or ".." in f.split("/")]
        if outside:
            sys.exit("%s: --file только из папки проекта: %s" % (d, " ".join(outside)))
        files |= {"%s/%s.tar.xz" % (bundle.REPO, n) for n in names} | set(extra)
        bundles[os.path.basename(d)[:-4]] = {"args": args, "packages": names}
    return sorted(files), bundles


def freeze(ver):
    dst = os.path.join(VERSIONS, ver)
    tmp = dst + ".tmp"
    for _ in range(3):
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            files, bundles = plan()
            stamp = [os.stat(f).st_mtime_ns for f in files]
            sums = {}
            for f in files:
                to = os.path.join(tmp, "src", f)
                os.makedirs(os.path.dirname(to), exist_ok=True)
                shutil.copy2(f, to)
                sums[f] = sha(to)
            if stamp == [os.stat(f).st_mtime_ns for f in files]:
                break
        except OSError as e:
            print("  %s" % e, file=sys.stderr)
        print("исходники менялись во время заморозки, повторяю", file=sys.stderr)
        time.sleep(2)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit("исходники всё время меняются (идёт сборка?), заморозить не вышло")
    lock = {"version": ver, "created": time.strftime("%Y-%m-%d %H:%M"), "bundles": bundles, "files": sums, "built": {},
            "image": json.load(open(os.path.join(tmp, "src", bundle.IMG, "build.json")))["build"]}
    save(tmp, lock)
    os.rename(tmp, dst)
    size = sum(os.path.getsize(os.path.join(dst, "src", f)) for f in files)
    print("версия %s заморожена: образ %s, %d файлов, %.1f МБ, бандлы: %s" % (
        ver, lock["image"], len(files), size / 1048576, " ".join(bundles)))


def save(dst, lock):
    with open(os.path.join(dst, "lock.json"), "w") as f:
        json.dump(lock, f, ensure_ascii=False, indent=1)
        f.write("\n")


def build(ver, names, publish):
    dst = os.path.join(VERSIONS, ver)
    lock = json.load(open(os.path.join(dst, "lock.json")))
    names = names or list(lock["bundles"])
    unknown = [n for n in names if n not in lock["bundles"]]
    if unknown:
        sys.exit("в версии %s нет бандла %s (есть: %s)" % (ver, " ".join(unknown), " ".join(lock["bundles"])))
    src = os.path.join(dst, "src")
    bad = [f for f, s in lock["files"].items() if not os.path.exists(os.path.join(src, f)) or sha(os.path.join(src, f)) != s]
    if bad:
        sys.exit("версия %s испорчена, файлы не те, что при заморозке: %s" % (ver, " ".join(bad)))
    for name in names:
        out = os.path.abspath(os.path.join(dst, name + ".html"))
        r = subprocess.run([sys.executable, "-B", "bundle.py"] + lock["bundles"][name]["args"] +
                           ["-n", name, "-o", out, "--version", ver], cwd=src)
        if r.returncode:
            sys.exit("%s не собрался" % name)
        lock["built"][name] = {"sha256": sha(out), "size": os.path.getsize(out)}
        save(dst, lock)
        if publish:
            to = os.path.join(SITE, name, "index.html")
            os.makedirs(os.path.dirname(to), exist_ok=True)
            shutil.copy(out, to + ".tmp")
            os.replace(to + ".tmp", to)
            print("  выложен в %s" % to)


def show():
    locks = [json.load(open(p)) for p in glob.glob(VERSIONS + "/*/lock.json")]
    if not locks:
        print("версий пока нет: ./release.py ИМЯ заморозит текущее состояние и соберёт бандлы")
    for lock in sorted(locks, key=lambda x: x["created"]):
        built = []
        for name, b in lock["built"].items():
            live = os.path.join(SITE, name, "index.html")
            on = os.path.exists(live) and os.path.getsize(live) == b["size"] and sha(live) == b["sha256"]
            built.append("%s %.1f МБ%s" % (name, b["size"] / 1048576, " (в site)" if on else ""))
        print("%-12s %s  образ %s  %s" % (lock["version"], lock["created"], lock["image"], ", ".join(built) or "не собрана"))


def main():
    ap = argparse.ArgumentParser(description="заморозить версию KotelOS и собрать её бандлы")
    ap.add_argument("version", nargs="?", help="имя версии; без имени - список версий")
    ap.add_argument("bundles", nargs="*", help="какие бандлы собрать (по умолчанию все из версии)")
    ap.add_argument("--build", action="store_true", help="перед заморозкой запустить ./build.sh")
    ap.add_argument("--no-publish", action="store_true", help="не копировать бандлы в site/")
    a = ap.parse_args()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.stdout.reconfigure(line_buffering=True)
    if not a.version:
        return show()
    if not re.fullmatch(r"[\w.-]{1,32}", a.version):
        sys.exit("имя версии: буквы, цифры, . _ -")
    if os.path.isdir(os.path.join(VERSIONS, a.version)):
        if a.build:
            sys.exit("версия %s уже заморожена, --build её не изменит: возьми новое имя" % a.version)
        print("версия %s уже заморожена, собираю из неё" % a.version)
    else:
        if a.build:
            subprocess.run(["./build.sh"], check=True)
        freeze(a.version)
    build(a.version, a.bundles, not a.no_publish)


if __name__ == "__main__":
    main()
