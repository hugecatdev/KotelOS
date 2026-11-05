import argparse
import fnmatch
import os
import shutil
import subprocess

L = "usr/lib/python3.12"
DROP = ["test/*", "tkinter/*", "ensurepip/*", "lib2to3/*", "pydoc_data/*", "msilib/*",
        "__phello__/*", "__hello__.py", "config-3.12-*", "site-packages/*", "encodings/mbcs.py",
        "encodings/oem.py", "*/__pycache__/*", "__pycache__/*"] + [
    "idlelib/" + f for f in "ChangeLog extend.txt HISTORY.txt NEWS2x.txt TODO.txt idle.bat idle.pyw Icons/idle.ico".split()]
ENC = ("__init__ aliases ascii latin_1 utf_8 utf_8_sig utf_7 utf_16 utf_16_be utf_16_le utf_32 utf_32_be utf_32_le "
       "charmap unicode_escape raw_unicode_escape punycode undefined base64_codec hex_codec zlib_codec uu_codec rot_13 "
       "cp1250 cp1251 cp1252 cp866 cp437 cp850 koi8_r koi8_u mac_cyrillic mac_roman iso8859_1 iso8859_2 iso8859_5 "
       "iso8859_15 idna").split()
MODS = {
    "python3-asyncio": ["asyncio/*", "lib-dynload/_asyncio.*"],
    "python3-ctypes": ["ctypes/*", "lib-dynload/_ctypes.*"],
    "python3-html": ["html/*", "_markupbase.py"],
    "python3-http": ["http/*", "wsgiref/*", "mimetypes.py", "urllib/request.py", "urllib/response.py",
                     "urllib/robotparser.py", "urllib/error.py"],
    "python3-venv": ["venv/*"],
    "python3-xml": ["xml/*", "plistlib.py", "lib-dynload/pyexpat.*", "lib-dynload/_elementtree.*"],
    "python3-multiprocessing": ["multiprocessing/*", "lib-dynload/_multiprocessing.*", "lib-dynload/_posixshmem.*"],
}
FULL = ["xmlrpc/*", "lib-dynload/*", "encodings/*"] + [
    m + ".py" for m in (
        "_pydatetime _pyio _aix_support _osx_support aifc antigravity bz2 cgi cgitb chunk crypt ftplib imaplib "
        "imghdr lzma mailbox mailcap modulefinder netrc nntplib nturl2path pickletools pipes poplib pyclbr pydoc "
        "smtplib sndhdr ssl stringprep sunau symtable tabnanny telnetlib this trace uu wave webbrowser xdrlib "
        "zipapp").split()]
# tkinter свой (packages/python-tkinter), а программы на нём берутся из CPython как есть
TK = {"python-idle": ["idlelib/*"], "python-turtle": ["turtle.py"], "python-turtledemo": ["turtledemo/*"]}
BIN = {"python-idle": ("idle", "idlelib"), "python-turtledemo": ("turtledemo", "turtledemo")}
SRC = ["python-turtle", "python-turtledemo"]  # .src: показывают свои исходники, их не сжимать
PARTS = [("python3-sqlite", ["sqlite3/*", "lib-dynload/_sqlite3*"]),
         ("python3-curses", ["curses/*", "lib-dynload/_curses*"]),
         ("minipython", ["lib-dynload/readline.*", "lib-dynload/_lsprof.*"] + ["encodings/%s.py" % m for m in ENC])
         ] + list(MODS.items()) + list(TK.items()) + [("python3", FULL), ("minipython", ["*"])]
DEPS = {"minipython": "musl readline", "python3": " ".join(["minipython"] + list(MODS)),
        "python3-sqlite": "minipython sqlite-libs", "python3-curses": "minipython libncursesw libpanelw",
        **{n: "minipython" for n in MODS}, "python3-http": "minipython python3-html",
        "python3-xml": "minipython python3-http", "python3-multiprocessing": "minipython python3-ctypes",
        "python-idle": "python3 python-tkinter", "python-turtle": "minipython python-tkinter",
        "python-turtledemo": "python-turtle python-idle"}


def main():
    ap = argparse.ArgumentParser(description="раскладка собранного CPython по пакетам minipython, python3 и др.")
    ap.add_argument("stage", help="DESTDIR после make install")
    ap.add_argument("--strip", required=True)
    ap.add_argument("--out", default="build/packages")
    a = ap.parse_args()
    lib = os.path.join(a.stage, L)
    for n in DEPS:
        shutil.rmtree(os.path.join(a.out, n), ignore_errors=True)
        os.makedirs(os.path.join(a.out, n, L))
        with open(os.path.join(a.out, n, ".deps"), "w") as f:
            f.write(DEPS[n] + "\n")
    for root, dirs, files in os.walk(lib):
        for name in files:
            src = os.path.join(root, name)
            rel = os.path.relpath(src, lib)
            if any(fnmatch.fnmatchcase(rel, p) for p in DROP):
                continue
            dest = next(n for n, pats in PARTS if any(fnmatch.fnmatchcase(rel, p) for p in pats))
            out = os.path.join(a.out, dest, L, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copy2(src, out)
            if rel.endswith(".so"):
                subprocess.run([a.strip, "--strip-unneeded", out], check=True)
    b = os.path.join(a.out, "minipython/usr/bin")
    os.makedirs(b)
    shutil.copy2(os.path.join(a.stage, "usr/bin/python3.12"), b)
    subprocess.run([a.strip, os.path.join(b, "python3.12")], check=True)
    os.symlink("python3.12", os.path.join(b, "python3"))
    os.symlink("python3", os.path.join(b, "python"))
    for n, (cmd, mod) in BIN.items():
        b = os.path.join(a.out, n, "usr/bin")
        os.makedirs(b)
        with open(os.path.join(b, cmd), "w") as f:
            f.write('#!/bin/sh\nexec python3 -m %s "$@"\n' % mod)
        os.chmod(os.path.join(b, cmd), 0o755)
    for n in SRC:
        open(os.path.join(a.out, n, ".src"), "w").close()
    for n in DEPS:
        size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(os.path.join(a.out, n)) for f in fs)
        print("%s %d КБ" % (n, size // 1024))


if __name__ == "__main__":
    main()
