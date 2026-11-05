import fnmatch
import os
import sys


def entries(data):
    i = 0
    while data[i:i + 6] == b"070701":
        h = data[i:i + 110]
        mode = int(h[14:22], 16)
        filesize = int(h[54:62], 16)
        namesize = int(h[94:102], 16)
        name = data[i + 110:i + 110 + namesize - 1].decode()
        body = i + 110 + namesize
        body += -body % 4
        end = body + filesize
        end += -end % 4
        yield name, mode, data[body:body + filesize], data[i:end]
        if name == "TRAILER!!!":
            return
        i = end


def minify(body):
    lines = body.decode().split("\n")
    keep = [lines[0]] + [l.lstrip() for l in lines[1:] if l.strip() and not l.lstrip().startswith("#")]
    return ("\n".join(keep) + "\n").encode()


def repack(raw, body):
    namesize = int(raw[94:102], 16)
    head = raw[:110 + namesize]
    head = head[:54] + b"%08X" % len(body) + head[62:]
    head += b"\0" * (-len(head) % 4)
    return head + body + b"\0" * (-len(body) % 4)


def filter_cpio(src, patterns, applets=None):
    pats = [p.strip() for p in open(patterns) if p.strip()]
    keep = {a.strip() for a in open(applets)} if applets else None
    out = sys.stdout.buffer
    for name, mode, body, raw in entries(open(src, "rb").read()):
        if name != "TRAILER!!!" and any(fnmatch.fnmatchcase(name, p) for p in pats):
            continue
        if keep is not None and mode & 0o170000 == 0o120000 and body.endswith(b"busybox") and name not in keep:
            continue
        if mode & 0o170000 == 0o100000 and body.startswith(b"#!/bin/sh"):
            raw = repack(raw, minify(body))
        out.write(raw)


def listing(srcs):
    names = set()
    for src in srcs:
        for name, mode, body, raw in entries(open(src, "rb").read()):
            if name not in (".", "TRAILER!!!"):
                names.add(name + ("/" if mode & 0o170000 == 0o040000 else ""))
    sys.stdout.write("".join(n + "\n" for n in sorted(names)))


def extract(src, dest, names):
    for name, mode, body, raw in entries(open(src, "rb").read()):
        if not any(fnmatch.fnmatchcase(name, p) for p in names):
            continue
        path = os.path.join(dest, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        kind = mode & 0o170000
        if kind == 0o040000:
            os.makedirs(path, exist_ok=True)
        elif kind == 0o120000:
            if os.path.lexists(path):
                os.remove(path)
            os.symlink(body.decode(), path)
        elif kind == 0o100000:
            with open(path, "wb") as f:
                f.write(body)
            os.chmod(path, mode & 0o7777)


if __name__ == "__main__":
    if sys.argv[1] == "filter":
        filter_cpio(*sys.argv[2:5])
    elif sys.argv[1] == "list":
        listing(sys.argv[2:])
    elif sys.argv[1] == "extract":
        extract(sys.argv[2], sys.argv[3], sys.argv[4:])
