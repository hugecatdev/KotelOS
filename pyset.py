import argparse
import os
import re
import alpine

GUI = re.compile(r"qt[56]|gtk|webkit|mesa|llvm|clang|wayland|libx11|cairo|pango|gdk|gstreamer|ffmpeg|sdl2|^R$|openjdk|vulkan|xorg|libdrm")


def main():
    ap = argparse.ArgumentParser(description="py3-пакеты Alpine с C-кодом для репозитория")
    ap.add_argument("--limit", type=float, default=10, help="предел на пакет вместе с новыми зависимостями, МБ")
    ap.add_argument("--skip", action="append", default=[])
    a = ap.parse_args()
    pkgs, provides = alpine.index()
    have = set(os.listdir("packages")) | set(a.skip) | {"python3"}

    def deps(n):
        for d in pkgs[n]["deps"]:
            if d.startswith("!"):
                continue
            d = re.split(r"[<>=~]", d)[0]
            m = d if d in pkgs else provides.get(d)
            if m:
                yield m

    def closure(n):
        seen, todo = set(), [n]
        while todo:
            x = todo.pop()
            if x in seen or x in have or "python-" + x[4:] in have:
                continue
            seen.add(x)
            todo.extend(deps(x))
        return seen

    out = []
    for n in sorted(pkgs):
        if not n.startswith("py3-") or re.search(r"-(doc|pyc|tests|dev)$", n) or n in a.skip:
            continue
        if not any(d.startswith("so:libc.musl") for d in pkgs[n]["deps"]):
            continue
        c = closure(n)
        if any(GUI.search(x) for x in c) or sum(pkgs[x]["size"] for x in c) > a.limit * 1e6:
            continue
        out.append(n)
    print(" ".join(out))


if __name__ == "__main__":
    main()
