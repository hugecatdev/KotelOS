#!/usr/bin/env python3
"""Отладка VirGL в машине: открыть бандл, выполнить команды в госте и выражения на странице.
  python3 virgl/harness/v86-probe.py БАНДЛ 'sh: команда' 'js: выражение' ...
Сообщения консоли страницы с префиксом virgl собираются в window.__virglLog."""
import json
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from run import Suite  # noqa: E402

HOOK = """(() => { window.__virglLog = []; for (const k of ["log", "warn", "error"]) { const f = console[k];
  console[k] = (...a) => { if (String(a[0]).startsWith("virgl")) window.__virglLog.push(k + ": " + a.map(String).join(" ")); f.apply(console, a); }; } })()"""

s = Suite(tempfile.mkdtemp(prefix="virgl-probe-"), None)
print("машина готова за %.1f с" % s.open("file://" + os.path.abspath(sys.argv[1])), flush=True)
s.ev(HOOK)
try:
    for a in sys.argv[2:]:
        kind, _, what = a.partition(": ")
        if kind == "sh":
            code, out, err = s.sh(what, 300)
            print("$ %s -> %s\n%s%s" % (what, code, out, err), flush=True)
        else:
            print("js %s -> %s" % (what, json.dumps(s.ev(what), ensure_ascii=False)), flush=True)
    print("журнал virgl:", "\n".join(s.ev("window.__virglLog") or []), flush=True)
finally:
    s.c.close()
