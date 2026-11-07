#!/usr/bin/env python3
"""Принимает ли V8 модули JIT сборки v86 и есть ли в них атомики: python3 tests/smp/jitcheck.py ПАПКА_V86

В release-сборке v86 отказ WebAssembly.instantiate для модуля JIT молча оставляет код в
интерпретаторе (catch только при DEBUG) - без этой проверки замер скорости врёт.
atomic/fence - сколько раз в модулях встретились байты 0xFE 0x10..0x1A / 0xFE 0x03 (это и
константы тоже): сравнивать с обычной сборкой, 2026-11-07 у vendor/v86 было 132/69,
у варианта SMP_PROBE=3 - 63273/62770 на тех же 172 модулях.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.environ.get("KT_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import bundle  # noqa: E402

HOOK = r"""(() => {
  window.__jit = { ok: 0, fail: 0, atomic: 0, fence: 0, err: "" };
  const orig = WebAssembly.instantiate;
  WebAssembly.instantiate = function (code, imp) {
    const p = orig.call(WebAssembly, code, imp);
    if (code instanceof Uint8Array) {
      let a = 0, f = 0;
      for (let i = 0; i + 1 < code.length; i++) if (code[i] === 0xFE) { if (code[i + 1] >= 0x10 && code[i + 1] <= 0x1A) a++; else if (code[i + 1] === 3) f++; }
      p.then(() => { __jit.ok++; __jit.atomic += a; __jit.fence += f; }, (e) => { __jit.fail++; __jit.err = String(e); });
    }
    return p;
  };
  return 1;
})()"""


def main():
    v86 = os.path.abspath(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="kt-jitcheck-")
    page = os.path.join(tmp, "chk.html")
    r = subprocess.run([sys.executable, "bundle.py", "--v86", v86, "-o", page, "-n", "chk", "--mem", "256",
                        "python3", "lua5.4", "micropython"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    c = bundle.Chrome(os.path.join(tmp, "prof"))
    try:
        c.open("about:blank")
        c.call("Page.enable")
        c.call("Page.addScriptToEvaluateOnNewDocument", source=HOOK)
        c.call("Page.navigate", url="file://" + page)
        time.sleep(1)
        t0 = time.time()
        while not c.eval("typeof agentReady !== 'undefined' && agentReady"):
            assert time.time() - t0 < 240
            time.sleep(0.2)
        for cmd in ("seq 1 100000 | gzip -6 | wc -c", "python3.12 -c 'print(sum(i * i % 7 for i in range(300000)))'",
                    "dd if=/dev/zero bs=1M count=8 2>/dev/null | sha256sum"):
            t = time.time()
            r = c.eval("exec(%s)" % json.dumps(cmd))
            print("%-70s код %s, %.1f с, %s" % (cmd[:70], r["code"], time.time() - t, r["out"].strip()[:40]))
        print("модули JIT:", c.eval("JSON.stringify(window.__jit)"))
    finally:
        c.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
