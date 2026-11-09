#!/usr/bin/env python3
"""Конфиг без комментариев, пустых строк и отступов - в машине каждый байт в памяти. minify.py ВИД ИЗ КУДА:
xml - <!-- --> и пробелы между тегами; xres - строки «!» (ресурсы X; продолжения строк «\\» сохраняются);
ini - строки «#»"""
import re
import sys


def main():
    kind, src, dst = sys.argv[1:]
    s = open(src, encoding="utf-8").read()
    if kind == "xml":
        s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
        s = re.sub(r">\s+<", "><", s).strip() + "\n"
    else:
        mark = "!" if kind == "xres" else "#"
        lines = [line.strip() for line in s.splitlines()]
        s = "\n".join(line for line in lines if line and not line.startswith(mark)) + "\n"
        if kind == "xres":
            s = s.replace("\\n\\\n", "\\n\\\n    ")
    open(dst, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    main()
