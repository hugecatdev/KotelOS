#!/usr/bin/env python3
"""Модули wasm, которые JIT v86 собрал за время команды в госте, - в файлы, чтобы посмотреть, какой
машинный код делает из них V8.
  python3 tests/jitasm.py БАНДЛ КОМАНДА КУДА [МАКС_БАЙТ]   -> КУДА/mN.wasm (wasm-dis mN.wasm - текст)
  node --no-liftoff --no-wasm-lazy-compilation --perf-basic-prof tests/jitasm.mjs КУДА/mN.wasm mN.bin
  objdump -D -b binary -m i386:x86-64 -M intel mN.bin      -> код TurboFan этого модуля
БАНДЛ - без --worker. V8 у node и у Chromium разных версий, но картина та же."""
import base64
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, ROOT)
from run import Suite  # noqa: E402
from bundle import Chrome  # noqa: E402

HOOK = """(() => { window.__mods = []; const orig = WebAssembly.instantiate;
  WebAssembly.instantiate = function (code, imp) {
    if (code instanceof Uint8Array && imp && imp.e && window.__keep) window.__mods.push(code.slice());
    return orig.apply(this, arguments);
  }; })()"""

page, cmd, out = sys.argv[1:4]
limit = int(sys.argv[4]) if len(sys.argv) > 4 else 1 << 30
tmp = tempfile.mkdtemp(prefix="kt-jitasm-")
page = os.path.abspath(page)
s = Suite(tmp, None)
s.c = Chrome(tempfile.mkdtemp(dir=tmp))
try:
    s.c.open("about:blank")
    s.c.call("Page.enable")
    s.c.call("Page.addScriptToEvaluateOnNewDocument", source=HOOK)
    s.c.call("Page.navigate", url="file://" + page)
    s.wait_ready()
    s.ev("window.__keep = true")
    print(s.sh(cmd, 600)[0])
    os.makedirs(out, exist_ok=True)
    n = s.ev("__mods.length")
    k = 0
    for i in range(n):
        size = s.ev("__mods[%d].length" % i)
        if size > limit:
            continue
        b64 = s.ev("btoa(String.fromCharCode.apply(null, __mods[%d]))" % i)
        open(os.path.join(out, "m%d.wasm" % i), "wb").write(base64.b64decode(b64))
        k += 1
    print("модулей %d, сохранено %d" % (n, k))
finally:
    s.c.close()
    shutil.rmtree(tmp, ignore_errors=True)
