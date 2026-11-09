#!/usr/bin/env python3
"""XML в пакетах без комментариев и отступов: в машине каждый байт лежит в памяти и в снимке.
xmlmin.py ПАПКА...  - все файлы <?xml ... и *.dtd в папках, кроме root/ (домашняя папка - как есть).
Отступ - пробелы с переводом строки между тегами; пробелы внутри <тег> </тег> и в тексте не трогаются.
XML после правки разбирается и сравнивается с исходным: если отличается не только комментариями и
отступами (xsl:text, xml:space, смешанное содержимое), файл остаётся как был."""
import os
import re
import sys
import xml.etree.ElementTree as ET

COMMENT = re.compile(rb"<!--.*?-->", re.S)
CDATA = re.compile(rb"(<!\[CDATA\[.*?\]\]>)", re.S)
GAP = re.compile(rb"(<[^<>]*>)([ \t\r]*\n[ \t\r\n]*)(?=<(/?))")


def gap(m):
    tag, ws, close = m.group(1), m.group(2), m.group(3)
    leaf = close == b"/" and not tag.startswith((b"</", b"<?", b"<!")) and not tag.endswith(b"/>")
    return m.group(0) if leaf else tag  # <a>\n</a> - значение a, его не трогать


PRESERVE = re.compile(rb"<[\w:.-]+\s[^<>]*xml:space\s*=\s*[\"']preserve")


def minify_xml(data):
    keep = PRESERVE.search(COMMENT.sub(b"", data))  # xml:space="preserve" у элемента - пробелы как есть
    parts = CDATA.split(data)
    for i in range(0, len(parts), 2):
        parts[i] = COMMENT.sub(b"", parts[i])
        if not keep:
            parts[i] = GAP.sub(gap, parts[i])
    return b"".join(parts).strip() + b"\n"


def minify_dtd(data):
    data = COMMENT.sub(b"", data)
    return b"\n".join(l.strip() for l in data.split(b"\n") if l.strip()) + b"\n"


def tree(data):
    def norm(e):
        kids = list(e)
        text, tails = e.text or "", [c.tail or "" for c in kids]
        # пробелы между детьми незначимы, только если у элемента нет своего текста (не смешанное содержимое)
        if kids and not text.strip() and not any(t.strip() for t in tails):
            text, tails = "", [""] * len(kids)
        return (e.tag, sorted(e.attrib.items()), text, [(norm(c), t) for c, t in zip(kids, tails)])

    # внешние DTD не грузятся: сущность из них - ошибка разбора, и файл остаётся как был
    return norm(ET.fromstring(data))


def same(a, b):
    try:
        return tree(a) == tree(b)
    except ET.ParseError:
        return False


def is_xml(path, head):
    return head.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<?xml")


def main():
    saved = 0
    for top in sys.argv[1:]:
        for dp, dn, fn in os.walk(top):
            if os.path.relpath(dp, top) == ".":
                dn[:] = [d for d in dn if d != "root"]
            for f in fn:
                p = os.path.join(dp, f)
                if os.path.islink(p) or not os.path.isfile(p):
                    continue
                with open(p, "rb") as fh:
                    data = fh.read()
                if f.endswith(".dtd"):
                    new = minify_dtd(data)
                elif is_xml(p, data[:64]):
                    new = minify_xml(data)
                    if new != data and not same(data, new):
                        continue
                else:
                    continue
                if len(new) < len(data):
                    st = os.stat(p)
                    with open(p, "wb") as fh:
                        fh.write(new)
                    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
                    saved += len(data) - len(new)
    if os.environ.get("XMLMIN_VERBOSE"):
        print("xmlmin: -%d байт" % saved, file=sys.stderr)


if __name__ == "__main__":
    main()
