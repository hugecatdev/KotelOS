#!/usr/bin/env python3
"""Условные блоки, как #if в C, но в комментариях - файл и без обработки остаётся JS или HTML:

    /* #if имя */ ... /* #endif */     в HTML: <!-- #if имя --> ... <!-- #endif -->
    /* #if !имя */ ... /* #endif */    если имени нет

Вложенные можно. Блок остаётся, если имя есть в наборе; пометки уходят, пометка одна
на строке - вместе со строкой. Так собираются page.html (функции бандла, bundle.py)
и v86 (устройства, scripts/build-v86.sh).

    python3 cond.py "имя имя ..." файл ...   обработать файлы на месте
"""
import re
import sys

COND = re.compile(r"(?:/\*|<!--)\s*#(?:if\s+(!?)([\w-]+)|(endif))\s*(?:\*/|-->)")


def preprocess(text, have, name="?"):
    out, stack, pos = [], [], 0
    for m in COND.finditer(text):
        start, end = m.start(), m.end()
        line = text.rfind("\n", 0, start) + 1
        eol = text.find("\n", end)
        eol = len(text) if eol < 0 else eol + 1
        if not text[line:start].strip() and not text[end:eol].strip():
            start, end = line, eol
        if all(stack):
            out.append(text[pos:start])
        if m.group(3):
            if not stack:
                sys.exit("%s:%d: #endif без #if" % (name, text.count("\n", 0, m.start()) + 1))
            stack.pop()
        else:
            stack.append((m.group(2) in have) != bool(m.group(1)))
        pos = end
    if stack:
        sys.exit("%s: #if без #endif" % name)
    out.append(text[pos:])
    return "".join(out)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    have = set(sys.argv[1].split())
    for path in sys.argv[2:]:
        text = open(path, encoding="utf-8").read()
        new = preprocess(text, have, path)
        if new != text:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)


if __name__ == "__main__":
    main()
