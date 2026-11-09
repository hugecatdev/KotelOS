#!/usr/bin/env python3
"""Мёртвые библиотеки бандла: ELF в образе, до которых не дойти по DT_NEEDED ни от одной программы.
Корни - всё в */bin, */sbin, */libexec, модули Xorg и imlib2, SDL2 (её грузит sdl12-compat через dlopen);
остальной dlopen скрипт не видит - список проверять в машине. Уже убранное ключами --drop не показывается.
python3 -B scripts/deadlibs.py bundles/greenos/greenos.txt  (из корня репозитория)"""
import collections
import os
import shlex
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, ".")
import bundle  # noqa: E402

DLOPEN = {"libSDL2-2.0.so.0"}  # sdl12-compat


def dyn(b):
    if b[:4] != b"\x7fELF":
        return None
    phoff, = struct.unpack_from("<I", b, 0x1c)
    phentsize, phnum = struct.unpack_from("<HH", b, 0x2a)
    ph = [struct.unpack_from("<IIIIIIII", b, phoff + i * phentsize) for i in range(phnum)]
    d = [p for p in ph if p[0] == 2]
    interp = any(p[0] == 3 for p in ph)
    if not d:
        return [], interp, None
    ents = [struct.unpack_from("<iI", b, d[0][1] + i * 8) for i in range(d[0][4] // 8)]

    def v2o(v):
        for p in ph:
            if p[0] == 1 and p[2] <= v < p[2] + p[4]:
                return v - p[2] + p[1]
    st = v2o([v for t, v in ents if t == 5][0])
    s = lambda o: b[st + o:b.index(b"\0", st + o)].decode()  # noqa: E731
    son = [s(v) for t, v in ents if t == 14]
    return [s(v) for t, v in ents if t == 1], interp, son[0] if son else None


def main():
    args = shlex.split(open(sys.argv[1]).read(), comments=True)
    a = bundle.options(args + ["-o", "/dev/null"])
    names = bundle.closure(a.packages)
    with tempfile.TemporaryDirectory() as tmp:
        cpio = bundle.packages_cpio(names, a.packages, a.file, a.drop)
        open(tmp + "/p.cpio", "wb").write(cpio)
        os.makedirs(tmp + "/r")
        subprocess.run(["cpio", "-idm", "--quiet", "-F", tmp + "/p.cpio"], cwd=tmp + "/r", check=True)
        root = tmp + "/r"
        info, size = {}, {}
        for dp, dn, fn in os.walk(root):
            for f in fn:
                p = os.path.join(dp, f)
                if os.path.islink(p):
                    continue
                b = open(p, "rb").read()
                d = dyn(b)
                if d is not None:
                    rel = "/" + os.path.relpath(p, root)
                    info[rel], size[rel] = d, len(b)
    libs = collections.defaultdict(set)
    for f, (n, i, s) in info.items():
        libs[os.path.basename(f)].add(f)
        if s:
            libs[s].add(f)
    libs["libc.musl-x86.so.1"].add("/lib/ld-musl-i386.so.1")
    roots = [f for f, (n, i, s) in info.items() if i or "/bin/" in f or "/sbin/" in f or "/libexec/" in f
             or "/xorg/modules/" in f or "/imlib2/" in f or os.path.basename(f) in DLOPEN or (s in DLOPEN)]
    seen, st = set(), list(roots)
    while st:
        f = st.pop()
        if f in seen:
            continue
        seen.add(f)
        for n in info[f][0]:
            st.extend(libs.get(n, ()))
    dead = sorted((f for f in info if f not in seen), key=lambda f: -size[f])
    print("мёртвые: %.0f КБ" % (sum(size[f] for f in dead) / 1024))
    for f in dead:
        print("  %4.0f КБ %s" % (size[f] / 1024, f))


if __name__ == "__main__":
    main()
