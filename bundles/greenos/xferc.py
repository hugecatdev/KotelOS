#!/usr/bin/env python3
"""xferc Xfe + xferc-greenos -> xferc GreenOS, без комментариев: наши ключи заменяют одноимённые в секции, новые
добавляются в её начало, секции, которых нет у Xfe, - в конец. xferc.py XFERC НАШ КУДА"""
import sys


def parse(path):
    secs, sect = {}, None
    for line in open(path):
        s = line.strip()
        if s.startswith("["):
            sect = s
            secs.setdefault(sect, [])
        elif "=" in s and not s.startswith("#"):
            secs.setdefault(sect, []).append(s)
    return secs


def main():
    base, ours, out = sys.argv[1:]
    mine = parse(ours)
    keys = {sect: {line.split("=")[0].strip() for line in lines} for sect, lines in mine.items()}
    res, sect, seen = [], None, set()
    for line in open(base).read().splitlines():
        s = line.strip()
        if s.startswith("["):
            sect = s
            seen.add(sect)
            res.append(line)
            res += mine.get(sect, [])
            continue
        if not s or s.startswith("#"):  # в машине всё в памяти - без комментариев
            continue
        if "=" in s and s.split("=")[0].strip() in keys.get(sect, ()):
            continue
        res.append(s)
    for sect, lines in mine.items():
        if sect not in seen:
            res += ["", sect] + lines
    open(out, "w").write("\n".join(res) + "\n")


if __name__ == "__main__":
    main()
