import argparse
import fnmatch
import gzip
import io
import os
import re
import shutil
import tarfile
import time
import urllib.request

MIRROR = "https://dl-cdn.alpinelinux.org/alpine/v3.22"
KT_MIRRORS = ["https://mirrors.sdu.edu.cn/alpine/v3.22", "https://mirror.xtom.com.hk/alpine/v3.22"]
REPOS = ["main", "community"]
CACHE = ".cache/alpine"
OWN = "packages"  # свои пакеты, в git
GEN = "build/packages"  # скачанные из Alpine и собранные скриптами
BASE_PROVIDES = {"/bin/sh", "busybox", "ca-certificates"}
DROP = [
    "usr/share/man/*", "usr/share/doc/*", "usr/share/info/*", "usr/share/licenses/*",
    "usr/share/locale/*", "usr/share/bash-completion/*", "usr/share/zsh/*", "usr/share/fish/*",
    "usr/lib/pkgconfig/*", "usr/lib/cmake/*", "*.a", "*.la",
    "usr/share/icons/*", "usr/share/pixmaps/*",  # .desktop (usr/share/applications) остаются: их показывает рабочий стол
]


def local_packages():
    """Имена пакетов репозитория: свои и сгенерированные."""
    return {n for d in (OWN, GEN) if os.path.isdir(d) for n in os.listdir(d) if os.path.isdir(os.path.join(d, n))}


def fetch(url, path, max_age=None):
    if not os.path.exists(path) or max_age and time.time() - os.path.getmtime(path) > max_age:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with urllib.request.urlopen(url) as r, open(path + ".tmp", "wb") as f:
            shutil.copyfileobj(r, f)
        os.rename(path + ".tmp", path)
    return path


def index(mirror=MIRROR, tag="", max_age=None):
    pkgs, provides = {}, {}
    for repo in REPOS:
        raw = open(fetch(f"{mirror}/{repo}/x86/APKINDEX.tar.gz", f"{CACHE}/{tag}{repo}.APKINDEX.tar.gz", max_age), "rb").read()
        with tarfile.open(fileobj=io.BytesIO(raw)) as t:
            text = t.extractfile("APKINDEX").read().decode()
        for block in text.split("\n\n"):
            rec = {}
            for line in block.splitlines():
                if len(line) > 2 and line[1] == ":":
                    rec.setdefault(line[0], []).append(line[2:])
            if "P" not in rec:
                continue
            name = rec["P"][0]
            pkg = {"name": name, "ver": rec["V"][0], "repo": repo,
                   "deps": " ".join(rec.get("D", [])).split(), "provides": " ".join(rec.get("p", [])).split(),
                   "size": int(rec.get("S", ["0"])[0]), "isize": int(rec.get("I", ["0"])[0]),
                   "desc": rec.get("T", [""])[0]}
            pkgs.setdefault(name, pkg)
            provides.setdefault(name, name)
            for p in " ".join(rec.get("p", [])).split():
                provides.setdefault(p.split("=")[0], name)
    return pkgs, provides


def resolve(names, pkgs, provides, skip, stop=()):
    out, todo = [], list(names)
    while todo:
        dep = todo.pop(0)
        if dep.startswith("!"):
            continue
        key = dep.split("=")[0].split(">")[0].split("<")[0].split("~")[0]
        if key not in names and (key in BASE_PROVIDES or key in skip):
            continue
        name = key if key in pkgs else provides.get(key)
        if not name or name in skip or name in out:
            continue
        out.append(name)
        if name not in stop:
            todo.extend(pkgs[name]["deps"])
    return out


def extract(apk, dest, drop, keep):
    with gzip.open(apk) as gz, tarfile.open(fileobj=gz, mode="r|") as t:
        for m in t:
            name = m.name[2:] if m.name.startswith("./") else m.name
            if not name or name.startswith("."):
                continue
            if any(fnmatch.fnmatchcase(name, p) for p in drop) and not any(fnmatch.fnmatchcase(name, p) for p in keep):
                continue
            path = os.path.join(dest, name)
            if m.isdir():
                os.makedirs(path, exist_ok=True)
            elif m.issym():
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if os.path.lexists(path):
                    os.remove(path)
                os.symlink(m.linkname, path)
            elif m.islnk():
                src = os.path.join(dest, m.linkname[2:] if m.linkname.startswith("./") else m.linkname)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if os.path.lexists(path):
                    os.remove(path)
                if os.path.exists(src):
                    os.link(src, path)
            elif m.isfile():
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    shutil.copyfileobj(t.extractfile(m), f)
                os.chmod(path, m.mode & 0o7777)


def kt_index(out, mirrors, ours_names, alias, old, new, desc=None):
    for i, mirror in enumerate(mirrors):
        try:
            pkgs, provides = index(mirror, "kt-", 86400)
            break
        except OSError:
            if i == len(mirrors) - 1:
                raise

    def ours(n):
        if n in alias:
            return alias[n]
        return new + n[len(old):] if old and n.startswith(old) else n

    junk = re.compile(r"-(doc|dbg|lang|pyc|tests|openrc|bash-completion|zsh-completion|fish-completion|nftrace)$")
    base = {"busybox", "busybox-binsh", "alpine-baselayout", "alpine-baselayout-data", "alpine-keys", "alpine-release", "apk-tools"}
    rows, found = {}, {}
    for n, p in sorted(pkgs.items()):
        name = ours(n)
        if name in ours_names and n not in alias:
            found.setdefault(name, p["desc"].replace("\t", " "))
        if junk.search(n) or n in base or n in alias or name in ours_names:
            continue
        deps = [ours(d) for d in p_direct(p, pkgs, provides, base | {n})]
        rows[name] = [name, "%d/%d" % (p["size"] // 1024 + 1, p["isize"] // 1024 + 1), deps,
                      p["desc"].replace("\t", " "), "", "%s/x86/%s-%s.apk" % (p["repo"], n, p["ver"])]
    known = set(rows) | ours_names
    with gzip.open(out, "wt", compresslevel=9) as f:
        for m in mirrors:
            f.write("#mirror\t%s\n" % m)
        for r in rows.values():
            r[2] = " ".join(d for d in r[2] if d in known)
            f.write("\t".join(r) + "\n")
    print("alpine: %d пакетов -> %s (%d КБ)" % (len(rows), out, os.path.getsize(out) // 1024))
    if desc:
        lines = []
        with open(desc, encoding="utf-8") as f:
            for line in f:
                r = line.rstrip("\n").split("\t")
                if len(r) > 3 and not r[3] and r[0] in found:
                    r[3] = found[r[0]]
                lines.append("\t".join(r) + "\n")
        with open(desc + ".tmp", "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.replace(desc + ".tmp", desc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("packages", nargs="*")
    ap.add_argument("--kt-index", metavar="FILE", help="индекс Alpine для kt pkg (gzip), без импорта")
    ap.add_argument("--mirror", action="append", help="зеркало с CORS для --kt-index, несколько - по порядку")
    ap.add_argument("--desc", metavar="FILE", help="index.txt: пустые описания пакетов взять из Alpine")
    ap.add_argument("--skip", action="append", default=[])
    ap.add_argument("--drop", action="append", default=[])
    ap.add_argument("--keep", action="append", default=[])
    ap.add_argument("--alias", action="append", default=[], help="ALPINE=OURS: не импортировать, в зависимостях писать OURS")
    ap.add_argument("--rename", default="", help="OLD-:NEW-: приставка имён")
    ap.add_argument("--keep-existing", action="store_true", help="уже существующие packages/<имя> не трогать")
    a = ap.parse_args()

    alias = dict(x.split("=", 1) for x in a.alias)
    old, _, new = a.rename.partition(":")
    if a.kt_index:
        mirrors = [m.rstrip("/") for m in a.mirror or KT_MIRRORS]
        kt_index(a.kt_index, mirrors, local_packages(), alias, old, new, a.desc)
        return
    if not a.packages:
        ap.error("нужны пакеты")
    pkgs, provides = index()
    skip = set(a.skip)

    def ours(n):
        if n in alias:
            return alias[n]
        return new + n[len(old):] if old and n.startswith(old) else n

    have = local_packages() if a.keep_existing else set()
    existing = {n for n in pkgs if ours(n) in have}
    for n in resolve(a.packages, pkgs, provides, skip, set(alias) | existing):
        if n in alias or n in existing:
            continue
        p = pkgs[n]
        dest = os.path.join(GEN, ours(n))
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest)
        fname = f"{n}-{p['ver']}.apk"
        extract(fetch(f"{MIRROR}/{p['repo']}/x86/{fname}", f"{CACHE}/apk/{fname}"), dest, DROP + a.drop, a.keep)
        deps = [ours(d) for d in p_direct(p, pkgs, provides, skip | {n})]
        with open(os.path.join(dest, ".deps"), "w") as f:
            f.write(" ".join(deps) + "\n")
        print(f"  {ours(n)} {p['ver']} <- {' '.join(deps)}")


def p_direct(p, pkgs, provides, skip):
    out = []
    for dep in p["deps"]:
        if dep.startswith("!"):
            continue
        key = dep.split("=")[0].split(">")[0].split("<")[0].split("~")[0]
        if key in BASE_PROVIDES or key in skip:
            continue
        name = key if key in pkgs else provides.get(key)
        if name and name not in skip and name not in out:
            out.append(name)
    return out


if __name__ == "__main__":
    main()
