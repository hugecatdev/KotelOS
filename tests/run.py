import argparse
import base64
import gzip
import hashlib
import io
import http.server
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import traceback
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bundle

PKGS = ["fun", "micropython", "python3", "python-requests", "pip", "curl", "pack", "sync", "notify", "ai"]
# KT_WORKER=1: бандлы с boot.worker on (v86 в Web Worker)
WORKER = os.environ.get("KT_WORKER") == "1"
AGENTS = r"""n=0
for d in /proc/[0-9]*; do
  read -r pid comm st ppid pgrp sid rest < $d/stat 2>/dev/null || continue
  [ "$pid" = "$sid" ] && [ "$(tr '\0' ' ' < $d/cmdline 2>/dev/null)" = "/bin/sh /usr/sbin/kt-agent " ] && n=$((n + 1))
done
echo $n"""
SLOW = r"""import binascii, socket, time
s = socket.socket()
s.connect(("192.168.86.1", 7771))
s.sendall(b"js 77 0 " + binascii.b2a_base64(b"'x'.repeat(600000)").strip() + b"\n")
time.sleep(7)
n = 0
while True:
    b = s.recv(65536)
    if not b:
        break
    n += len(b)
print(n)
"""


class Chrome(bundle.Chrome):
    def __init__(self, profile):
        super().__init__(profile)
        self.events = []

    def call(self, method, session=True, **params):
        self.id += 1
        msg = {"id": self.id, "method": method, "params": params}
        if session and self.session:
            msg["sessionId"] = self.session
        self.proc.stdin.write(json.dumps(msg).encode() + b"\0")
        self.proc.stdin.flush()
        while True:
            while b"\0" not in self.buf:
                chunk = os.read(self.proc.stdout.fileno(), 1 << 20)
                if not chunk:
                    raise RuntimeError("chromium закрылся")
                self.buf += chunk
            raw, self.buf = self.buf.split(b"\0", 1)
            m = json.loads(raw)
            if m.get("id") == self.id:
                if "error" in m:
                    raise RuntimeError(m["error"].get("message"))
                return m.get("result", {})
            if "method" in m:
                self.events.append(m)

    def pump(self):
        self.call("Target.getTargets", session=False)

    def event(self, name, timeout=20):
        t = time.time()
        while time.time() - t < timeout:
            self.pump()
            for e in self.events:
                if e["method"] == name:
                    self.events.remove(e)
                    return e["params"]
            time.sleep(0.2)
        raise AssertionError("не было события " + name)


class Server(http.server.SimpleHTTPRequestHandler):
    ai_log = []
    ai_tokens = 0
    SCRIPTS = {
        "выполни команду": [("sh", {"command": "cd /tmp && echo привет-$((2+3))"})],
        "файлом": [("write", {"path": "/tmp/ai-f/t.txt", "content": "a\nb\n"}),
                   ("edit", {"path": "/tmp/ai-f/t.txt", "old": "b", "new": "c"}),
                   ("read", {"path": "/tmp/ai-f/t.txt"})],
    }
    cha_log = []
    CHA = {
        "/cha/sub/page.html": ("<html><head><link rel=stylesheet href=s.css></head>"
                               "<body><h1>Привет, chawan</h1></body></html>", "text/html; charset=utf-8"),
        "/cha/sub/s.css": ("h1 { color: red }", "text/css"),
    }

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/cha/"):
            Server.cha_log.append((self.path, dict(self.headers)))
            if self.path == "/cha/start":
                self.send_response(302)
                self.send_header("Location", "sub/page.html")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path in self.CHA:
                body, ctype = self.CHA[self.path]
                return self.answer(body.encode(), ctype)
        if self.path == "/hello":
            return self.answer(b"hi from test server", "text/plain")
        if self.path == "/v1/models":
            if self.headers.get("Authorization") != "Bearer test-key":
                return self.answer(json.dumps({"error": {"message": "bad key"}}).encode(), "application/json", 401)
            return self.answer(json.dumps({"data": [{"id": "other"}, {"id": "mock"}]}).encode(), "application/json")
        return super().do_GET()

    def chat(self, body):
        if self.headers.get("Authorization") != "Bearer test-key":
            return self.answer(json.dumps({"error": {"message": "bad key"}}).encode(), "application/json", 401)
        req = json.loads(body)
        Server.ai_log.append(req)
        if req["model"] == "luna" and "tools" in req:
            return self.answer(json.dumps({"error": {"message": "Function tools with reasoning_effort are not supported for luna in "
                                                                "/v1/chat/completions. To use function tools, use /v1/responses or "
                                                                "set reasoning_effort to 'none'."}}).encode(), "application/json", 400)
        msgs = req["messages"]
        last = max(i for i, m in enumerate(msgs) if m["role"] == "user")
        ask = msgs[last]["content"]
        done = sum(1 for m in msgs[last:] if m["role"] == "tool")
        steps = next((v for k, v in self.SCRIPTS.items() if k in ask), [])
        if "tools" not in req:
            msg = {"role": "assistant", "content": "сводка %d" % len(ask)}
        elif done < len(steps):
            name, args = steps[done]
            msg = {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c%d" % done, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
        elif done:
            msg = {"role": "assistant", "content": "готово: " + msgs[-1]["content"].replace("\n", " ")}
        else:
            msg = {"role": "assistant", "content": "эхо %s: %s%s" % (req["model"], ask.replace("\n", " "),
                                                                   " [%s]" % req["reasoning_effort"] if "reasoning_effort" in req else "")}
        out = {"choices": [{"message": msg, "finish_reason": "stop"}]}
        if Server.ai_tokens:
            out["usage"] = {"total_tokens": Server.ai_tokens}
        self.answer(json.dumps(out).encode(), "application/json")

    def respond(self, body):
        if self.headers.get("Authorization") != "Bearer test-key":
            return self.answer(json.dumps({"error": {"message": "bad key"}}).encode(), "application/json", 401)
        req = json.loads(body)
        Server.ai_log.append(req)
        items = req["input"]
        calls = set()
        for it in items:
            if it.get("type") == "function_call":
                if "id" in it:
                    return self.answer(b'{"error": {"message": "Item with id not found, store is false"}}', "application/json", 400)
                calls.add(it["call_id"])
            if it.get("type") == "function_call_output" and it["call_id"] not in calls:
                return self.answer(b'{"error": {"message": "No tool call found for function call output"}}', "application/json", 400)
        last = max(i for i, it in enumerate(items) if it.get("role") == "user")
        ask = items[last]["content"]
        done = sum(1 for it in items[last:] if it.get("type") == "function_call_output")
        steps = next((v for k, v in self.SCRIPTS.items() if k in ask), [])
        say = None
        if "tools" not in req:
            say = "сводка %d" % len(ask)
        elif done < len(steps):
            name, args = steps[done]
            output = [{"type": "reasoning", "id": "rs_%d" % done, "summary": []},
                      {"type": "function_call", "id": "fc_%d" % done, "call_id": "call_%d" % done, "name": name,
                       "arguments": json.dumps(args), "status": "completed"}]
        elif done:
            say = "готово: " + items[-1]["output"].replace("\n", " ")
        else:
            say = "эхо %s: %s%s" % (req["model"], ask.replace("\n", " "),
                                    " [%s]" % req["reasoning"]["effort"] if "reasoning" in req else "")
        if say is not None:
            output = [{"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
                       "content": [{"type": "output_text", "text": say, "annotations": []}]}]
        out = {"object": "response", "status": "completed", "output": output, "error": None,
               "usage": {"total_tokens": Server.ai_tokens or 100}}
        self.answer(json.dumps(out).encode(), "application/json")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path == "/echo":
            return self.answer(json.dumps({"len": len(body), "type": self.headers.get("Content-Type", ""),
                                           "md5": hashlib.md5(body).hexdigest()}).encode(), "application/json")
        if self.path == "/v1/chat/completions":
            return self.chat(body)
        if self.path == "/v1/responses":
            return self.respond(body)
        self.send_error(404)

    def answer(self, data, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class Suite:
    def __init__(self, tmp, url):
        self.tmp = tmp
        self.url = url
        self.c = None
        self.results = []

    def open(self, url):
        if self.c:
            self.c.close()
        self.c = Chrome(tempfile.mkdtemp(dir=self.tmp))
        self.c.open(url)
        self.c.call("Page.enable")
        return self.wait_ready()

    def wait_ready(self, timeout=90):
        t = time.time()
        while time.time() - t < timeout:
            try:
                if self.ev("typeof agentReady !== 'undefined' && agentReady"):
                    time.sleep(0.5)
                    return time.time() - t
            except RuntimeError:
                pass
            time.sleep(0.3)
        raise AssertionError("машина не ответила за %d с" % timeout)

    def ev(self, expr):
        return self.c.eval(expr)

    def sh(self, cmd, timeout=60):
        r = self.ev("Promise.race([kt.exec(%s).then((r) => ({ code: r.code, out: r.out, err: r.err })),"
                    " new Promise((_, no) => setTimeout(() => no(new Error('exec завис')), %d))])" % (json.dumps(cmd), timeout * 1000))
        return r["code"], r["out"], r["err"]

    def ok(self, cmd, timeout=60):
        code, out, err = self.sh(cmd, timeout)
        assert code == 0, "%s -> код %s: %s%s" % (cmd, code, out, err)
        return out

    def start(self, cmd):
        self.ev("window.__job = kt.exec(%s).then((r) => ({ code: r.code, out: r.out, err: r.err })); 0" % json.dumps(cmd))

    def finish(self):
        r = self.ev("window.__job")
        return r["code"], r["out"], r["err"]

    def typed(self, cmd):
        self.ev("term.focus()")
        self.ev("send(%s)" % json.dumps(cmd))
        for t in ("keyDown", "keyUp"):
            self.c.call("Input.dispatchKeyEvent", type=t, key="Enter", code="Enter", windowsVirtualKeyCode=13,
                        **({"text": "\r"} if t == "keyDown" else {}))

    def screen(self):
        return self.ev("screenText()")

    def click_ok(self):
        box = self.ev("""(() => { const b = document.querySelector('#ask [data-m="ok"]').getBoundingClientRect();
          return [b.x + b.width / 2, b.y + b.height / 2]; })()""")
        for t in ("mousePressed", "mouseReleased"):
            self.c.call("Input.dispatchMouseEvent", type=t, x=box[0], y=box[1], button="left", clickCount=1)

    def check(self, name, fn):
        t = time.time()
        try:
            note = fn()
            self.results.append((name, True, ""))
            print("ok    %-34s %5.1f с  %s" % (name, time.time() - t, note or ""))
        except Exception as e:
            self.results.append((name, False, str(e)))
            print("FAIL  %-34s %5.1f с  %s" % (name, time.time() - t, str(e).strip().replace("\n", " | ")[:300]))
            if os.environ.get("TRACE"):
                traceback.print_exc()
                # падения процессов в госте: адрес и код из ядра
                try:
                    print(self.sh("dmesg | grep -i -E 'segfault|trap|protection|oops|bug:' | tail -n 20", 10)[1])
                except Exception as e2:
                    print("dmesg не получить: %s" % e2)


def md5(data):
    return hashlib.md5(data).hexdigest()


def fake_pypi(www, base):
    def wheel(name, ver, files, requires=(), scripts=""):
        fn = "%s-%s-py3-none-any.whl" % (name, ver)
        info = "%s-%s.dist-info/" % (name, ver)
        with zipfile.ZipFile(os.path.join(www, "files", fn), "w") as z:
            for path, body in files.items():
                z.writestr(path, body)
            z.writestr(info + "METADATA", "Metadata-Version: 2.1\nName: %s\nVersion: %s\n%s\n" % (
                name, ver, "".join("Requires-Dist: %s\n" % r for r in requires)))
            if scripts:
                z.writestr(info + "entry_points.txt", "[console_scripts]\n" + scripts)
            z.writestr(info + "RECORD", "")
        return {"filename": fn, "url": base + "files/" + fn, "requires_python": ">=3.8", "size": os.path.getsize(os.path.join(www, "files", fn)), "yanked": False}

    os.makedirs(os.path.join(www, "files"))
    projects = {
        "kthello": {"1.0": [wheel("kthello", "1.0", {"kthello/__init__.py": "def main():\n    print('hello from kthello')\n"},
                                  ["ktdep>=2", "ktwin; sys_platform == 'win32'", "requests>=2"], "kthello = kthello:main\n")]},
        "ktdep": {v: [wheel("ktdep", v, {"ktdep/__init__.py": "V = %r\n" % v})] for v in ("1.0", "2.1", "3.0a1")},
        "ktbin": {"1.0": [{"filename": "ktbin-1.0-cp312-cp312-manylinux_2_17_i686.whl", "url": base + "files/none", "size": 1, "yanked": False}]},
        "ktsrc": {"1.0": [{"filename": "ktsrc-1.0.tar.gz", "url": base + "files/none", "size": 1, "yanked": False}]},
        "pyyaml": {"6.0.2": [{"filename": "pyyaml-6.0.2.tar.gz", "url": base + "files/none", "size": 1, "yanked": False}]},
    }
    repo = os.path.join(www, "repo")
    os.makedirs(repo)
    for f in ("index.txt", "pypi.txt", "python-yaml.tar.xz", "yaml.tar.xz", "chawan.tar.xz", "chawan-fetch.tar.xz"):
        shutil.copy(os.path.join(ROOT, "site", "repo", f), repo)
    apks = os.path.join(www, "alpine", "main", "x86")
    os.makedirs(apks)
    for name, files in (("ktapk", {".PKGINFO": "pkgname = ktapk\n", "usr/bin/ktapk": "#!/bin/sh\ncat /usr/share/ktapklib/msg\n"}),
                        ("ktapklib", {".PKGINFO": "pkgname = ktapklib\ntriggers = /usr/bin\n", "usr/share/ktapklib/msg": "hello from alpine\n",
                                      ".trigger": "#!/bin/sh\n[ -x /usr/bin/ktapk ] && ln -sf ktapk /usr/bin/ktapk-trig\n"}),
                        ("ktold", {".PKGINFO": "pkgname = ktold\n", "usr/bin/ktold": "#!/bin/sh\necho new\n",
                                   "opt/ktold/x": "x\n", "etc/shells": "/bin/sh\n"}),
                        ("ktlib2", {".PKGINFO": "pkgname = ktlib2\n", "usr/share/ktlib2/x": "x\n"})):
        with tarfile.open(os.path.join(apks, name + "-1.0-r0.apk"), "w:gz") as t:
            dirs = sorted({"/".join(p.split("/")[:i]) for p in files if "/" in p for i in range(1, p.count("/") + 1)})
            for d in dirs:
                info = tarfile.TarInfo(d)
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                t.addfile(info)
            for path, body in files.items():
                info = tarfile.TarInfo(path)
                info.size = len(body.encode())
                info.mode = 0o755
                t.addfile(info, io.BytesIO(body.encode()))
    body = "".join("P:%s\nV:1.0-r0\n\n" % n for n in ("ktapk", "ktapklib", "ktold", "ktlib2")).encode()
    with tarfile.open(os.path.join(apks, "APKINDEX.tar.gz"), "w:gz") as t:
        info = tarfile.TarInfo("APKINDEX")
        info.size = len(body)
        t.addfile(info, io.BytesIO(body))
    with gzip.open(os.path.join(repo, "alpine.txt.gz"), "wt") as f:
        f.write("#mirror\thttp://127.0.0.1:1/alpine\n")
        f.write("#mirror\t%salpine\n" % base)
        f.write("ktapk\t1/1\tktapklib musl\ttest apk\t\tmain/x86/ktapk-1.0-r0.apk\n")
        f.write("ktapklib\t1/1\t\ttest lib\t\tmain/x86/ktapklib-1.0-r0.apk\n")
        f.write("ktold\t1/1\t\ttest stale\t\tmain/x86/ktold-0.9-r0.apk\n")
        f.write("ktlib2\t1/1\t\ttest lib2\t\tmain/x86/ktlib2-1.0-r0.apk\n")
        f.write("ktgone\t1/1\tktlib2\ttest gone\t\tmain/x86/ktgone-1.0-r0.apk\n")
    for name, rel in projects.items():
        os.makedirs(os.path.join(www, "pypi", name))
        with open(os.path.join(www, "pypi", name, "json"), "w") as f:
            json.dump({"info": {"name": name}, "releases": rel}, f)


def main():
    ap = argparse.ArgumentParser(description="тесты моста kt в headless Chromium")
    ap.add_argument("--build", action="store_true", help="сначала ./build.sh")
    ap.add_argument("-k", default="", help="только тесты, в имени которых есть эта строка (несколько через запятую)")
    a = ap.parse_args()
    os.chdir(ROOT)
    if a.build:
        subprocess.run(["./build.sh"], check=True)
    os.environ["TZ"] = "America/New_York"
    tmp = tempfile.mkdtemp(prefix="kt-tests-")
    www = os.path.join(tmp, "www")
    os.makedirs(www)
    worker = ["--worker"] if WORKER else []
    for args in (["-o", www + "/t.html", "-n", "test"] + worker + PKGS,
                 ["-o", www + "/snap.html", "-n", "snap", "fun", "--snap", "--version", "t1"] + worker,
                 ["-o", www + "/vga.html", "-n", "vga", "--vga", "doom", "xorg", "xclip"] + worker):
        r = subprocess.run([sys.executable, "bundle.py"] + args, capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stdout + r.stderr)
        print(r.stdout.strip().splitlines()[-1][:100])
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *x: Server(*x, directory=www))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d/" % httpd.server_port
    s = Suite(tmp, base)
    up = os.urandom(1500000)
    with open(os.path.join(tmp, "up.bin"), "wb") as f:
        f.write(up)
    dl = os.path.join(tmp, "dl")
    os.makedirs(dl)
    fake_pypi(www, base)

    def boot():
        t = s.open(base + "t.html")
        s.ev("kt.write('/tmp/agents.sh', %s)" % json.dumps(AGENTS))
        return "загрузка %.1f с" % t

    def vga_clean():
        if WORKER:
            return "видеопамять в воркере; проверяется без воркера"
        n = s.ev("emulator.v86.cpu.devices.vga.svga_memory.reduce((a, b) => a + (b ? 1 : 0), 0)")
        assert n == 0, "в видеопамяти %d ненулевых байт, снимки раздуются" % n

    def bundle_memory():
        n = s.ev("document.querySelectorAll('script[type=\"application/base64\"]').length")
        assert n == 0, "в DOM остались данные бандла: %d" % n
        assert s.ev("!!emulator.worker") == WORKER, "boot.worker не тот: ждали %s" % WORKER
        if WORKER:
            return "v86 в воркере; zero_memory проверяется без воркера"
        r = s.ev("""(() => {
          const cpu = emulator.v86.cpu, P = 4096, zero = (p) => cpu.is_memory_zeroed(p * P, P);
          let p = cpu.mem8.length / P - 8;
          while (p > 8 && !(zero(p) && zero(p + 1) && zero(p + 2) && !zero(p - 1))) p--;
          const before = cpu.mem8.slice((p - 1) * P, p * P);
          cpu.mem8[p * P + 5] = 1;
          cpu.mem8[(p + 2) * P + 4095] = 2;
          cpu.zero_memory(p * P, 3 * P);
          const pages = zero(p) && zero(p + 1) && zero(p + 2);
          cpu.mem8[p * P + 9] = 3;
          cpu.zero_memory(p * P + 8, 8);
          return { p, pages, bytes: zero(p), kept: cpu.mem8.subarray((p - 1) * P, p * P).every((b, i) => b === before[i]) };
        })()""")
        assert r["p"] > 8 and r["pages"] and r["bytes"] and r["kept"], r

    def render():
        canvases = "document.querySelectorAll('#term canvas').length"
        assert s.ev(canvases) == 0, "по умолчанию не DOM-рендер"
        assert s.ev("term.options.cursorBlink") is False, "курсор по умолчанию мигает"
        s.ok("kt cfg term.render canvas")
        assert s.ev(canvases) > 0, "canvas-рендер не включился"
        assert s.ok("echo canvas").strip() == "canvas"
        s.ok("kt cfg term.render dom")
        assert s.ev(canvases) == 0, "после term.render dom остались canvas"

    def one_agent():
        n = s.ok("sh /tmp/agents.sh").strip()
        assert n == "1", "агентов: " + n
        assert s.ok("pidof kt-netd | wc -w").strip() == "1", "серверов kt-netd не один"

    def clean_screen():
        bad = [w for w in ("signal", "Terminated", "Killed", "kt-net", "kt-agent") if w in s.screen()]
        assert not bad, "в терминале: " + ", ".join(bad)

    def kt_js():
        assert s.ok("kt js 6*7").strip() == "42"
        assert s.ok("kt js '(a, b) => a + b' 2 3").strip() == "23"
        assert s.ok("kt js '(a, b) => +a + +b' 2 3").strip() == "5"
        assert s.ok("kt js '() => kt.bundle'").strip() == "test"
        s.ok("printf '(x) => x.toUpperCase()' > /tmp/f.js")
        assert s.ok("kt js -f /tmp/f.js привет").strip() == "ПРИВЕТ"
        assert s.ok("echo '[1,2].length' | kt js").strip() == "2"
        code, out, err = s.sh("kt js 'throw new Error(\"бум\")'")
        assert (code, out, err) == (1, "", "kt js: бум\n"), (code, out, err)
        # аргументы - только у функции: код, разбитый на слова, не склеивается молча
        code, out, err = s.sh("kt js 1 + 2")
        assert code == 1 and "только у функции" in err, (code, out, err)
        code, out, err = s.sh("kt help nosuch")
        assert code == 1 and "нет модуля nosuch" in err, (code, out, err)
        big = "x" * 100000
        assert s.ok("kt js '(s) => s.length' %s" % big).strip() == "100000"

    def kt_list_x():
        def mods(cmd):
            out = re.sub(r"\x1b\[[0-9;]*m", "", s.ok(cmd))
            return {l.split()[1] for l in out.splitlines() if l.startswith("* ")}
        con, x11 = mods("kt"), mods("DISPLAY=:0 kt")
        assert con - x11 == {"theme", "font"}, (con - x11, x11 - con)
        assert "kt font" in s.ok("DISPLAY=:0 kt help font")

    def kt_js_background():
        out = s.ok("(setsid kt js '\"bg-\" + 7' > /tmp/bg 2>&1 < /dev/null &); sleep 3; cat /tmp/bg")
        assert out.strip() == "bg-7", out

    def latency():
        r = s.ev("""(async () => { const m = async (c) => { const t = performance.now(); for (let i = 0; i < 10; i++) await kt.exec(c); return (performance.now() - t) / 10 };
          const a = await m('true'), b = await m('kt js 1'); return [a, b - a] })()""")
        return "kt.exec %.0f мс, kt js из шелла +%.0f мс" % tuple(r)

    def exec_codes():
        code, out, err = s.sh("echo out; echo err >&2; exit 3")
        assert (code, out, err) == (3, "out\n", "err\n"), (code, out, err)
        r = s.ev("kt.exec('cat', { stdin: 'вход' }).then((r) => r.out)")
        assert r == "вход", r

    def read_write():
        data = os.urandom(2 << 20)
        s.ev("window.__d = Uint8Array.from(atob(%s), (c) => c.charCodeAt(0)); 0" % json.dumps(__import__("base64").b64encode(data).decode()))
        w = s.ev("(async () => { const t = performance.now(); await kt.write('/tmp/rw.bin', __d); return performance.now() - t })()")
        assert s.ok("md5sum /tmp/rw.bin").split()[0] == md5(data)
        r = s.ev("(async () => { const t = performance.now(); const b = await kt.read('/tmp/rw.bin'); return [performance.now() - t, b.length, Array.from(b.subarray(0, 16))] })()")
        assert r[1] == len(data) and bytes(r[2]) == data[:16], r[1:]
        return "2 МБ: в машину %.1f МБ/с, из машины %.1f МБ/с" % (2000 / w, 2000 / r[0])

    def kt_dl():
        s.c.call("Browser.setDownloadBehavior", session=False, behavior="allow", downloadPath=dl)
        data = os.urandom(1000000)
        s.ev("kt.write('/tmp/dl.bin', Uint8Array.from(atob(%s), (c) => c.charCodeAt(0)))" % json.dumps(__import__("base64").b64encode(data).decode()))
        s.ok("kt dl /tmp/dl.bin; mkdir -p /tmp/d/sub; echo a > /tmp/d/sub/a; kt dl /tmp/d; echo text | kt dl note.txt")
        t = time.time()
        while time.time() - t < 10 and len(os.listdir(dl)) < 3:
            time.sleep(0.3)
        got = {f: open(os.path.join(dl, f), "rb").read() for f in os.listdir(dl) if not f.endswith(".crdownload")}
        bins = [v for k, v in got.items() if k.startswith("dl.bin")]
        assert bins and md5(bins[0]) == md5(data), sorted(got)
        assert any(k.startswith("d.tar.gz") for k in got), sorted(got)
        assert got.get("note.txt") == b"text\n", sorted(got)

    def kt_up():
        s.c.call("Page.setInterceptFileChooserDialog", enabled=True)
        s.c.events.clear()
        s.start("cd /tmp && kt up && md5sum up.bin")
        time.sleep(1.5)
        assert s.ev("$('#ask').classList.contains('open')"), "нет кнопки выбора"
        s.click_ok()
        e = s.c.event("Page.fileChooserOpened")
        s.c.call("DOM.enable")
        s.c.call("DOM.setFileInputFiles", files=[os.path.join(tmp, "up.bin")], backendNodeId=e["backendNodeId"])
        code, out, err = s.finish()
        assert code == 0 and md5(up) in out, (code, out, err)

    def kt_up_typed():
        s.c.events.clear()
        s.typed("cd /tmp && kt up && md5sum up.bin && cd")
        e = s.c.event("Page.fileChooserOpened")
        assert not s.ev("$('#ask').classList.contains('open')"), "кнопка, хотя только что нажали Enter"
        s.c.call("DOM.setFileInputFiles", files=[os.path.join(tmp, "up.bin")], backendNodeId=e["backendNodeId"])
        time.sleep(4)
        assert md5(up) in s.screen(), s.screen()[-300:]

    def drop():
        # файл, брошенный на страницу снаружи, уходит в машину (в /root); картинка, которую тащат по самой
        # странице (значок в окне tkinter), - нет, хотя браузер отдаёт при отпускании и её файлом
        s.ok("rm -f /root/up.bin /root/svg+xml")
        data = {"items": [], "files": [os.path.join(tmp, "up.bin")], "dragOperationsMask": 1}
        for t in ("dragEnter", "dragOver", "drop"):
            s.c.call("Input.dispatchDragEvent", type=t, x=200, y=200, data=data)
        t = time.time()
        while s.sh("test -f /root/up.bin")[0] and time.time() - t < 20:
            time.sleep(0.5)
        out = s.ok("md5sum /root/up.bin && rm /root/up.bin")
        assert md5(up) in out, out
        s.ev("""(() => { const i = document.createElement('img'); i.id = 'dragimg';
          i.src = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48"><rect width="48" height="48" fill="red"/></svg>');
          i.style = 'position:fixed;left:300px;top:300px;width:48px;height:48px;z-index:99'; document.body.append(i);
          window.__drags = 0; addEventListener('dragstart', () => window.__drags++, true); })()""")
        time.sleep(0.5)
        m = lambda t, x, y, **k: s.c.call("Input.dispatchMouseEvent", type=t, x=x, y=y, **k)  # noqa: E731
        m("mouseMoved", 324, 324)
        m("mousePressed", 324, 324, button="left", buttons=1, clickCount=1)
        for i in range(1, 11):
            m("mouseMoved", 324 + 30 * i, 324 + 10 * i, button="left", buttons=1)
            time.sleep(0.05)
        m("mouseReleased", 624, 424, button="left", buttons=0, clickCount=1)
        time.sleep(3)
        s.ev("document.getElementById('dragimg').remove()")
        assert s.ev("window.__drags"), "браузер не начал перетаскивание картинки - проверять нечего"
        out = s.ok("ls /root")
        assert "svg+xml" not in out, "картинка со страницы ушла в машину: " + out

    def clipboard():
        s.c.call("Browser.grantPermissions", session=False, origin=base.rstrip("/"), permissions=["clipboardReadWrite", "clipboardSanitizedWrite"])
        s.c.call("Emulation.setFocusEmulationEnabled", enabled=True)
        s.ok("kt copy 'буфер 1'")
        assert s.ev("navigator.clipboard.readText()") == "буфер 1"
        s.ev("navigator.clipboard.writeText('из браузера')")
        out = s.ok("kt paste")
        assert out.strip() == "из браузера", out

    def run_left(*kinds):
        return [n for n in s.ok("ls /run/kt").split() if n.startswith(kinds)]

    def run_clean():
        left = run_left("events", "ev.", "reply.")
        assert not left, "в /run/kt остались %s" % left

    def events():
        s.ev("kt.emit('ping', { n: 1 })")
        time.sleep(1)
        run_clean()
        for py in ("micropython", "python3"):
            s.start(py + " -c 'import kt; print(kt.wait(\"ping\", timeout=40)[\"n\"])'")
            t = time.time()
            while not run_left("ev."):
                assert time.time() - t < 30, py + " не начал слушать"
                time.sleep(0.5)
            s.ev("kt.emit('ping', { n: 5 })")
            code, out, err = s.finish()
            assert code == 0 and out.strip() == "5", (py, code, out, err)
            run_clean()

    def micropython():
        out = s.ok("micropython -c 'import kt; print(kt.js(\"(a, b) => a * b\", 6, 7)); print(kt.cfg[\"term.theme\"]); print(kt.info()[\"bundle\"])'")
        assert out.split()[:3] == ["42", "dark", "test,"], out

    def cpython_threads():
        code = ("import kt, threading\n"
                "res = []\n"
                "def w(i):\n"
                "    for j in range(10):\n"
                "        res.append(kt.js('(a, b) => a * 100 + b', i, j) == i * 100 + j)\n"
                "ts = [threading.Thread(target=w, args=(i,)) for i in range(8)]\n"
                "[t.start() for t in ts]; [t.join() for t in ts]\n"
                "print(len(res), all(res))\n")
        s.ev("kt.write('/tmp/th.py', %s)" % json.dumps(code))
        out = s.ok("python3 /tmp/th.py", 180)
        assert out.split() == ["80", "True"], out

    def requests_shim():
        out = s.ok("micropython -c 'import requests; r = requests.get(\"/hello\"); print(r.status_code, r.text)'")
        assert out.strip() == "200 hi from test server", out
        code = ("import requests, io\n"
                "r = requests.post('/echo', data={'a': 'б'}, files={'f': ('x.bin', b'\\x00\\x01' * 1000)})\n"
                "print(r.json()['len'], r.json()['type'].split(';')[0])\n")
        s.ev("kt.write('/tmp/rq.py', %s)" % json.dumps(code))
        n, ctype = s.ok("python3 /tmp/rq.py", 120).split()
        assert int(n) > 2000 and ctype == "multipart/form-data", (n, ctype)
        assert s.ok("curl -s %shello" % base).strip() == "hi from test server"
        big = os.urandom(1200000)
        with open(os.path.join(www, "big.bin"), "wb") as f:
            f.write(big)
        assert s.ok("curl -s %sbig.bin | md5sum" % base, 120).split()[0] == md5(big), "curl: большое тело побилось"
        out = s.ok("curl -s -o /dev/null -D /tmp/h -w '%%{http_code} %%{num_redirects} %%{url_effective}' %scha/start && head -n 1 /tmp/h" % base)
        assert out == "200 1 %scha/sub/page.html" % base + "HTTP/1.1 200 OK\r\n", out

    def dialogs():
        for cmd, accept, text, want in (('kt prompt "Имя?" Вася', True, "Петя", (0, "Петя")),
                                        ('kt prompt "Имя?"', False, None, (1, "")),
                                        ('kt confirm "Да?"', True, None, (0, "")),
                                        ('kt confirm "Да?"', False, None, (1, "")),
                                        ("kt alert привет", True, None, (0, ""))):
            s.c.events.clear()
            s.start(cmd)
            e = s.c.event("Page.javascriptDialogOpening")
            s.c.call("Page.handleJavaScriptDialog", accept=accept, **({"promptText": text} if text is not None else {}))
            code, out, err = s.finish()
            assert (code, out.strip()) == want, (cmd, code, out, err, e["type"])

    def notify():
        s.c.call("Browser.grantPermissions", session=False, origin=base.rstrip("/"), permissions=["notifications"])
        s.ev("""window.__notes = []; (() => { const N = window.Notification;
          window.Notification = class extends N { constructor(t, o) { super(t, o); __notes.push(o.body); } }; })(); 0""")
        s.ok("kt notify готово-тест")
        assert s.ev("__notes") == ["готово-тест"], s.ev("__notes")

    def pack():
        out = s.ok("mkdir -p /tmp/p/a && echo 1 > /tmp/p/a/x && kt pack tp /tmp/p/a && rm -rf /tmp/p && kt unpack tp && cat /tmp/p/a/x && kt unpack tp /tmp/q && cat /tmp/q/a/x && kt pack rm -y tp")
        assert out.count("1\n") >= 2 and out.endswith("- tp\n"), out
        code, out, err = s.sh("kt pack rm tp")
        assert code == 1 and "нет архива tp" in err, (code, out, err)

    def sync():
        s.ev("""(async () => {
          const root = await navigator.storage.getDirectory();
          await root.removeEntry('proj', { recursive: true }).catch(() => {});
          const d = await root.getDirectoryHandle('proj', { create: true });
          const w = await (await d.getFileHandle('a.txt', { create: true })).createWritable();
          await w.write('hello'); await w.close();
          window.showDirectoryPicker = async () => d;
        })()""")
        s.start("kt sync add /mnt/proj")
        time.sleep(1.5)
        if s.ev("$('#ask').classList.contains('open')"):
            s.click_ok()
        code, out, err = s.finish()
        assert code == 0, (code, out, err)
        s.ok("echo changed > /mnt/proj/a.txt; echo new > /mnt/proj/b.txt; sleep 6")
        files = s.ev("""(async () => { const d = await (await navigator.storage.getDirectory()).getDirectoryHandle('proj'); const o = [];
          for await (const [n, h] of d.entries()) o.push(n + '=' + (await (await h.getFile()).text()).trim()); return o.sort().join(' ') })()""")
        assert files == "a.txt=changed b.txt=new", files
        assert s.ok("kt sync").strip() == "/mnt/proj <- proj"
        s.ok("kt sync rm /mnt/proj")
        assert s.ok("kt sync").strip() == ""

    def wait_screen(text, timeout=60):
        t = time.time()
        while time.time() - t < timeout:
            if text in s.screen():
                return
            time.sleep(0.5)
        raise AssertionError("на экране нет %r: %s" % (text, s.screen()[-300:]))

    def cfg_custom():
        def rows():
            # «* ключ значение  описание»: * - не по умолчанию
            lst = re.sub(r"\x1b\[[0-9;]*m", "", s.ok("kt cfg"))
            out = {}
            for line in lst.splitlines():
                f = line[2:].split(None, 2) + [""]
                out[f[0]] = (line[0], f[1], f[2].strip())
            return out

        assert s.ok("kt cfg ai.key test-key") == "test-key\n"
        assert s.ok("kt cfg boot.mem 128") == "128\n"
        assert s.ok("kt cfg term.scroll 100") == "100\n"
        r = rows()
        assert list(r)[0] == "save.auto" and r["save.auto"][:2] == (" ", "on"), r
        assert r["ai.key"] == ("*", "test-key", "ключ API, хранится только в браузере"), r["ai.key"]
        # умолчание ключа пакета - из его описания (ai.ctx=32), у изменённого ключа страницы - в скобках
        assert r["ai.ctx"] == (" ", "32", "предел контекста, тыс. токенов"), r["ai.ctx"]
        assert r["term.scroll"] == ("*", "100", "строк в прокрутке (5000)"), r["term.scroll"]
        assert r["term.render"][2] and r["boot.worker"][2] and "screen.scale" not in r, r
        assert s.ok("kt cfg ai.ctx") == "32\n"
        code, out, err = s.sh("kt cfg rm")
        assert code == 1 and "[y/N]" in err, (code, out, err)
        assert s.ok("kt cfg rm -y") == "- term.scroll\n"
        assert s.ok("kt cfg rm -y") == ""
        assert s.ok("kt cfg ai.key").strip() == "test-key", "kt cfg rm задел свой ключ пакета"
        assert s.ok("kt js 'kt.cfg[\"ai.key\"]'").strip() == "test-key"
        code, out, err = s.sh("kt cfg x.y")
        assert (code, out, err) == (1, "", ""), (code, out, err)
        for bad in ("kt cfg term.fnt 1", "kt cfg nodot 1"):
            code, out, err = s.sh(bad)
            assert code == 1 and "нет ключа" in err, (bad, code, out, err)
        s.ok("kt cfg x.y 'a  b'")
        assert s.ok("kt cfg x.y") == "a  b\n"
        out = s.ok("micropython -c 'import kt; print(kt.cfg[\"x.y\"]); kt.cfg[\"x.z\"] = 5; print(kt.cfg[\"x.z\"], \"x.q\" in kt.cfg)'")
        assert out == "a  b\n5 False\n", repr(out)
        assert s.ok("kt cfg rm x.y x.q") == "- x.y\n"
        s.ok("kt cfg x.z ''")
        assert "x." not in s.ok("kt cfg")

    def ai_tool():
        s.ok("kt cfg ai.url %sv1 && kt cfg ai.model mock && kt cfg ai.key test-key" % base)
        out = s.ok("cd /root && ai 'выполни команду'", 120)
        assert out.strip() == "готово: exit 0 привет-5 (cwd: /tmp)", out
        out = s.ok("rm -rf /tmp/ai-f && ai 'поработай с файлом' && cat /tmp/ai-f/t.txt", 120)
        assert out == "готово: 1\ta 2\tc\na\nc\n", repr(out)
        out = s.ok("echo 123 | ai 'скажи'", 120)
        assert out.strip() == "эхо mock: скажи  123", out
        code, out, err = s.sh("kt cfg ai.auto off >/dev/null && ai 'выполни команду'", 120)
        s.ok("kt cfg rm ai.auto")
        assert code == 1 and "ai.auto on" in err, (code, out, err)
        assert s.ok("ai -l").split() == ["*", "mock", "other"]
        s.ok("mkdir -p /tmp/pj/.ai/skills/demo && echo 'Проект X' > /tmp/pj/AGENTS.md")
        s.ok("printf '%s\\n' --- 'name: demo' 'description: Demo skill.' --- text > /tmp/pj/.ai/skills/demo/SKILL.md")
        s.ok("cd /tmp/pj && ai 'скажи'", 120)
        sysmsg = Server.ai_log[-1]["messages"][0]["content"]
        assert sysmsg.startswith("Проект X\n\nCurrent directory: /tmp/pj.\n\nSkills:"), sysmsg
        assert sysmsg.endswith("\n- demo: Demo skill. (/tmp/pj/.ai/skills/demo/SKILL.md)"), sysmsg
        s.ok("cd /tmp && ai 'скажи'", 120)
        sysmsg = Server.ai_log[-1]["messages"][0]["content"]
        assert sysmsg.startswith("You are an assistant in the KotelOS terminal") and sysmsg.endswith("\n\nCurrent directory: /tmp."), sysmsg
        code, out, err = s.sh("kt cfg ai.key bad >/dev/null && ai hi", 120)
        s.ok("kt cfg ai.key test-key")
        assert code == 1 and "401 bad key" in err, (code, out, err)

    def ai_context():
        Server.ai_tokens = 5000
        s.ok("kt cfg ai.ctx 4")
        try:
            code, out, err = s.sh("ai 'выполни команду'", 120)
        finally:
            Server.ai_tokens = 0
            s.ok("kt cfg rm ai.ctx")
        assert code == 0 and "сжат" in err, (code, out, err)
        packed = Server.ai_log[-2]
        assert "tools" not in packed and "User: выполни команду" in packed["messages"][1]["content"], packed
        assert out.strip().startswith("эхо mock: Summary of the conversation"), out
        out = s.ok("ai -c 'ещё'", 120)
        assert out.strip() == "эхо mock: ещё" and len(Server.ai_log[-1]["messages"]) == 4, (out, Server.ai_log[-1])

    def ai_proto():
        s.ok("rm -f /root/.ai/proto.json && kt cfg ai.model luna")
        try:
            n = len(Server.ai_log)
            out = s.ok("ai 'выполни команду'", 120)
            assert out.strip() == "готово: exit 0 привет-5 (cwd: /tmp)", out
            kinds = ["input" in r for r in Server.ai_log[n:]]
            assert kinds == [False, True, True], kinds
            assert '"responses"' in s.ok("cat /root/.ai/proto.json")
            n = len(Server.ai_log)
            out = s.ok("ai 'поработай с файлом' && ai 'скажи'", 120)
            assert out.split("\n")[-2] == "эхо luna: скажи", out
            assert all("input" in r for r in Server.ai_log[n:]), "снова chat"
            r = Server.ai_log[-2]
            assert r["store"] is False and r["tools"][0]["name"] == "sh" and r["instructions"].startswith("You are an assistant"), r
        finally:
            s.ok("kt cfg ai.model mock")

    def ai_model():
        s.ev("term.clear()")
        s.typed("ai")
        wait_screen("mock\n>")
        s.ev("send('/model\\r')")
        wait_screen("рассуждение: <")
        s.ev("send('oth')")
        s.ev("send('\\x1b[C\\x1b[C\\x1b[C\\x1b[C\\x1b[C')")
        wait_screen("< high >")
        s.ev("send('\\r')")
        wait_screen("other (high)")
        s.ev("send('скажи\\r')")
        wait_screen("эхо other: скажи [high]")
        s.ev("send('/model mock default\\r')")
        time.sleep(1)
        s.ev("send('\\x04')")
        time.sleep(1)
        assert s.ok("kt cfg ai.model").strip() == "mock"
        # описанный ключ пакета без умолчания: пустая строка, а на странице ключа нет
        assert s.ok("kt cfg ai.effort") == ""
        assert s.ok("kt js 'kt.cfg[\"ai.effort\"] === undefined'").strip() == "true"

    def pip_shim():
        idx = "-i %spypi" % base
        out = s.ok("pip install %s kthello" % idx, 120)
        assert "установлено: kthello-1.0 ktdep-2.1" in out, out
        assert s.ok("kthello").strip() == "hello from kthello"
        assert s.ok("python3 -c 'import ktdep; print(ktdep.V)'").strip() == "2.1"
        assert "requests                 2.32.0+kt  (kt pkg)" in s.ok("pip list")
        for name, want in (("ktbin", "musllinux_i686"), ("ktsrc", "sdist"), ("ktnone", "нет на PyPI")):
            code, out, err = s.sh("pip install %s %s" % (idx, name), 120)
            assert code == 1 and want in err, (name, code, out, err)
        code, out, err = s.sh("pip uninstall -y requests")
        assert code == 1 and "kt pkg rm" in err, (code, out, err)
        assert s.ok("pip install %s 'ktdep<2'" % idx, 120).strip().endswith("ktdep-1.0")
        s.ok("pip uninstall -y kthello ktdep")
        assert s.sh("command -v kthello")[0] != 0
        left = s.ok("ls /usr/lib/python3.12/site-packages")
        assert "kthello" not in left and "ktdep" not in left, left

    def pip_repo():
        out = s.ok("pip install -i %spypi pyyaml" % base, 180)
        assert "из репозитория kt: python-yaml" in out, out
        assert s.ok("python3 -c 'import yaml; print(yaml.safe_dump({\"a\": 1}).strip())'").strip() == "a: 1"
        assert "PyYAML                   6.0.2  (kt pkg)" in s.ok("pip list")
        code, out, err = s.sh("pip uninstall -y pyyaml")
        assert code == 1 and "kt pkg rm python-yaml" in err, (code, out, err)
        s.ok("kt pkg rm -y python-yaml")

    def pkg_alpine():
        assert "ktapk" in s.ok("kt pkg search ktap", 60)
        assert "ktapk" not in s.ok("kt pkg search -r ktap", 60)
        out = s.ok("kt pkg add ktapk", 120)
        assert "ktapk" in out and "(apk)" in out, out
        assert s.ok("ktapk").strip() == "hello from alpine"
        assert s.ok("ktapk-trig").strip() == "hello from alpine", "триггер не сработал"
        assert s.sh("ls /.PKGINFO")[0] != 0, "мусор .PKGINFO в /"
        assert s.ok("cat /var/lib/kt/mirror").strip() == base + "alpine"
        out = s.ok("kt pkg")
        assert re.search(r"^\* ktapk .*test apk  \(apk\)$", out, re.M) and "ktapklib" not in out, out
        out = s.ok("kt pkg -a")
        assert re.search(r"^\* ktapk ", out, re.M) and re.search(r"^  ktapklib ", out, re.M) and not re.search(r"^. base ", out, re.M), out
        s.ok("kt pkg add ktold", 120)
        assert s.ok("ktold").strip() == "new"
        code, out, err = s.sh("kt pkg add ktgone", 120)
        assert code == 1 and "не скачать ktgone" in err, (code, out, err)
        assert s.sh("ls /var/lib/kt/pkg/ktlib2")[0] != 0, "ktlib2 поставлен без ktgone"
        out = s.ok("kt pkg rm -y ktapk ktapk", 60)
        assert re.findall(r"^- \S+$", out, re.M) == ["- ktapk"], out
        assert s.ok("cat /usr/share/ktapklib/msg").strip() == "hello from alpine", "ktapklib удалён без -d"
        assert re.search(r"^\* ktapklib ", s.ok("kt pkg"), re.M), "ktapklib не попал в world"
        s.ok("kt pkg rm -y ktapklib", 60)
        s.ok("kt pkg add ktapk", 120)
        code, out, err = s.sh("kt pkg rm ktapklib ktapklib", 60)
        assert err.count("ktapklib нужен для ktapk") == 1 and "- " not in out, (out, err)
        out = s.ok("kt pkg rm -dy ktapk ktold", 60)
        assert sorted(re.findall(r"^- (\S+)$", out, re.M)) == ["ktapk", "ktapklib", "ktold"], out
        assert s.sh("command -v ktapk")[0] != 0 and s.sh("ls /usr/share/ktapklib")[0] != 0
        assert s.ok("ls -A /opt").strip() == "", "после ktold в /opt остался мусор"
        assert s.ok("cat /etc/shells").strip(), "kt pkg rm удалил файл базы"

    def pkg_base():
        code, out, err = s.sh("kt pkg rm fun base")
        assert code == 1 and "base удалить нельзя" in err and "- " not in out, (code, out, err)
        assert s.ok("command -v about").strip(), "fun удалён, хотя команда отказала"
        for flag in ("", "-d "):
            s.ok("printf 'ktonbase\\t1/1\\tbase\\n' >> /var/lib/kt/index && : > /var/lib/kt/pkg/ktonbase")
            out = s.ok("kt pkg rm -y %sktonbase" % flag)
            assert re.findall(r"^- (\S+)$", out, re.M) == ["ktonbase"], out
        db = s.ok("cat /var/lib/kt/pkg/base").split("\n")
        lost = {"bin/busybox", "opt/", "root/", "usr/lib/kt/pkg", "usr/lib/os-release", "var/lib/kt/pkg/base"} - set(db)
        assert not lost, "в base нет " + " ".join(sorted(lost))
        assert not re.search(r"^\* base ", s.ok("kt pkg"), re.M), "base среди поставленных явно"
        assert re.search(r"^\* base .*базовая система", s.ok("kt pkg search -r base"), re.M), "поиск не видит base"

    def pkg_cascade():
        def gone(cmd):
            return re.findall(r"^- (\S+)$", s.ok(cmd), re.M)

        s.ok("printf 'kta\\t1/1\\nktb\\t1/1\\nktuser\\t1/1\\tkta|ktb\\nkttop\\t1/1\\tktuser\\n' >> /var/lib/kt/index")
        s.ok("cd /var/lib/kt/pkg && printf 'usr/\\nusr/bin/\\nusr/bin/kta\\n' > kta && : > ktb && : > ktuser && : > kttop")
        assert s.ok("kt pkg files kta").split() == ["/usr/bin/kta"], "files показывает не только файлы"
        code, out, err = s.sh("kt pkg files kta ktnone")
        assert code == 1 and "ktnone не установлен" in err and not out, (code, out, err)
        code, out, err = s.sh("kt pkg rm ktuser")
        assert "ktuser нужен для kttop" in err and "- " not in out, (out, err)
        for answer in ("", "echo n | "):
            code, out, err = s.sh(answer + "kt pkg rm -c kta")
            assert code == 1 and err.startswith("удалить kta? [y/N] ") and "- " not in out, (code, out, err)
            assert s.sh("ls /var/lib/kt/pkg/kta")[0] == 0, "kta удалён без согласия"
        code, out, err = s.sh("echo y | kt pkg rm -c kta")
        assert (code, out, err) == (0, "- kta\n", "удалить kta? [y/N] "), "ktuser хватает ktb, а удалено: %r" % ((code, out, err),)
        assert gone("kt pkg rm -cy ktb") == ["ktb", "ktuser", "kttop"]
        assert "/bin/busybox" in s.ok("kt pkg files base"), "каскад задел base"

    def chawan():
        s.ok("kt pkg add chawan", 180)
        Server.cha_log.clear()
        out = s.ok("cha -d %scha/start" % base, 120)
        assert "Привет, chawan" in out, out
        paths = [p for p, h in Server.cha_log]
        assert paths.count("/cha/sub/page.html") == 1, "редирект: страница скачана не один раз: %s" % paths
        assert "/cha/sub/s.css" in paths, "стиль не от конечного адреса: %s" % paths
        h = dict(Server.cha_log)["/cha/sub/page.html"]
        assert "chawan" not in h.get("User-Agent", "") and h.get("Cache-Control") == "no-cache", h
        post = ("printf %%s 'a=1&b=%%D0%%B1' | REQUEST_METHOD=POST CONTENT_TYPE=application/x-www-form-urlencoded CONTENT_LENGTH=12"
                " MAPPED_URI_SCHEME=http MAPPED_URI_HOST=127.0.0.1 MAPPED_URI_PORT=%s MAPPED_URI_PATH=/echo"
                " REQUEST_HEADERS=\"$(printf 'Accept: */*\\r\\nPragma: no-cache\\r\\n')\" /usr/libexec/chawan/cgi-bin/curl"
                % base.split(":")[2].strip("/"))
        out = s.ok(post)
        assert out.startswith("Status: 200\r\nCha-Control: ControlDone\r\n"), out
        r = json.loads(out.split("\r\n\r\n", 1)[1])
        assert (r["len"], r["type"], r["md5"]) == (12, "application/x-www-form-urlencoded", md5(b"a=1&b=%D0%B1")), r
        code, out, err = s.sh("cha -d http://127.0.0.1:1/", 60)
        assert "Can't load" in err and "CORS" in err, (code, out, err)
        s.ok("kt pkg rm -dy chawan", 60)

    def ai_repl():
        s.ev("term.clear()")
        s.typed("cd /root && ai")
        wait_screen("mock\n>")
        s.ev("send('/au\\t\\r')")
        wait_screen("с подтверждением")
        s.ev("send('выполни командуЖ\\x7f\\r')")
        wait_screen("выполнить?")
        s.ev("send('y\\r')")
        wait_screen("готово: exit 0")
        assert Server.ai_log[-1]["messages"][1]["content"] == "выполни команду", Server.ai_log[-1]["messages"][1]
        s.ev("send('/auto\\r')")
        wait_screen("без подтверждения")
        # on - объявленное умолчание (ai.auto=on): ключ снят, а не записан
        assert s.ok("kt cfg ai.auto") == "on\n"
        assert s.ok("kt js 'kt.cfg[\"ai.auto\"] === undefined'").strip() == "true"
        s.ev("send('/he\\t\\r')")
        wait_screen("системный промпт")
        s.ev("send('!echo hi-$((1+1))\\r')")
        wait_screen("hi-2")
        n = len(Server.ai_log)
        s.ev("send('скажи\\r')")
        wait_screen("эхо mock: I ran a command")
        ask = Server.ai_log[-1]["messages"][-1]["content"]
        assert ask == "I ran a command:\n$ echo hi-$((1+1))\nexit 0\nhi-2\n\nскажи", ask
        s.ev("send('/retry\\r')")
        time.sleep(2)
        assert len(Server.ai_log) == n + 2 and Server.ai_log[-1]["messages"] == Server.ai_log[-2]["messages"]
        s.ev("send('/copy\\r')")
        # без жеста браузер просит подтвердить: kt.copy ждёт кнопку «Копировать» внизу страницы
        t = time.time()
        while "скопировано" not in s.screen() and time.time() - t < 5:
            if s.ev("$('#toast').classList.contains('open')"):
                s.ev("$('#toast button').click()")
            time.sleep(0.3)
        wait_screen("скопировано", 10)
        s.ev("send('/ctx\\r')")
        wait_screen("контекст ~")
        s.ev("send('/nope\\r')")
        wait_screen("нет команды /nope")
        s.ev("send('\\x04')")
        time.sleep(1)
        assert s.ok("pidof micropython || true").strip() == ""

    def save_restore():
        s.ok("rm -f /tmp/rw.bin /tmp/dl.bin /tmp/up.bin")
        s.ev("term.clear()")
        s.typed("kt save; echo SAVED-OK")
        # не 8 с наугад: под нагрузкой сохранение идёт дольше. SAVED-OK дважды - команда и её вывод
        t0 = time.time()
        while s.screen().count("SAVED-OK") < 2 and time.time() - t0 < 60:
            time.sleep(0.5)
        assert s.screen().count("SAVED-OK") >= 2, s.screen()[-200:]
        s.c.call("Page.reload")
        time.sleep(1)
        t = s.wait_ready()
        time.sleep(2)
        scr = s.screen()
        assert "восстановлено сохранение" in scr and scr.count("SAVED-OK") >= 2, scr[-300:]
        assert s.ok("kt js 1+1").strip() == "2"
        return "восстановление %.1f с" % t

    def snap_rules():
        # ошибка и отмена - код 1: kt export без снимка, kt load/reset без -y и без ответа
        code, out, err = s.sh("kt export nosuch")
        assert (code, out, err) == (1, "", "kt export: нет снимка nosuch\n"), (code, out, err)
        for cmd in ("kt load", "kt reset", "kt save 'bad name'"):
            code, out, err = s.sh(cmd)
            assert code == 1 and not out, (cmd, code, out, err)
        assert "сохранён" in s.ok("kt save tsnap", 120)
        assert "tsnap" in s.ok("kt snap")
        code, out, err = s.sh("kt snap rm tsnap nosuch")
        assert code == 1 and "нет снимка nosuch" in err and "[y/N]" not in err, (code, out, err)
        assert s.ok("kt snap rm -y tsnap") == "- tsnap\n"
        assert "tsnap" not in s.ok("kt snap")

    def reset():
        s.typed("kt reset -y")
        time.sleep(2)
        s.wait_ready()
        assert "save: нет" in s.ok("kt info")

    def end_keys():
        for t in ("rawKeyDown", "keyUp"):
            s.c.call("Input.dispatchKeyEvent", type=t, key="End", code="End", windowsVirtualKeyCode=35, modifiers=3)

    def tap(label):
        box = s.ev("""(() => { const b = [...document.querySelectorAll('#keys button')].find((b) => b.textContent === %s)
          .getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; })()""" % json.dumps(label))
        for t in ("mousePressed", "mouseReleased"):
            s.c.call("Input.dispatchMouseEvent", type=t, x=box[0], y=box[1], button="left", clickCount=1)

    def wiped(**want):
        time.sleep(2)
        s.wait_ready()
        assert "save: нет" in s.ok("kt info"), "сохранение осталось"
        for k, v in want.items():
            assert s.ok("kt cfg " + k.replace("_", ".")).strip() == v, k
        # как kt cfg rm: сбрасываются ключи страницы, свои ключи пакетов (ai.key) остаются
        assert s.ok("kt cfg test.key").strip() == "1", "свой ключ пропал"
        s.ok("kt cfg rm test.key")

    def secret_reset():
        s.ok("kt cfg term.theme amber && kt cfg test.key 1 && kt save")
        s.ev("window.__sent = []; { const o = emulator.serial_send_bytes.bind(emulator); emulator.serial_send_bytes = (p, d) => (__sent.push(...d), o(p, d)); } 0")
        end_keys()
        time.sleep(4)
        assert s.ev("__sent.length") == 0, "нажатие ушло в гостя"
        assert "save: нет" not in s.ok("kt info"), "сброс от одного нажатия"
        s.typed("kill -STOP $(cat /run/kt/agent.pid) $(pidof kt-netd)")
        time.sleep(1)
        end_keys()
        end_keys()
        wiped(term_theme="dark")

    def secret_reset_keys():
        s.ok("kt cfg term.mobile on && kt cfg test.key 1 && kt save")
        for _ in range(2):
            for k in ("CTRL", "ALT", "END"):
                tap(k)
        wiped(term_mobile="off")

    def kill_server():
        s.typed("kill $(pidof kt-netd)")
        time.sleep(4)
        assert s.ok("kt js 3+3").strip() == "6"
        s.typed("kill $(cat /run/kt/agent.pid)")
        time.sleep(4)
        s.wait_ready(30)
        assert s.ok("kt js 4+4").strip() == "8"

    def tcp_resend():
        # Читатель в госте встаёт, окно закрывается. Отправитель TCP в v86
        # (patches/v86/01-tcp-window.patch) ждёт окна, а не шлёт в никуда, и
        # повторяет то, что гость отбросил; поток должен дойти целиком.
        def closed():
            names, values = (line.split() for line in s.ok("grep TcpExt /proc/net/netstat").splitlines()[:2])
            return sum(int(values[names.index(k)]) for k in ("TCPToZeroWindowAdv", "TCPZeroWindowDrop"))

        n = closed()
        s.ok("(sleep 1; kill -STOP $(cat /run/kt/agent.pid); sleep 7; kill -CONT $(cat /run/kt/agent.pid)) > /dev/null 2>&1 &")
        time.sleep(2)
        s.ev("(() => { const line = 'NOP ' + 'x'.repeat(995); for (let i = 0; i < 160; i++) ctl(line); return 0 })()")
        assert s.ok("echo жив", 60).strip() == "жив"
        assert closed() > n, "агент: окно гостя не закрывалось, проверять нечего"
        s.ev("kt.write('/tmp/slow.py', %s)" % json.dumps(SLOW))
        n = closed()
        out = s.ok("python3 /tmp/slow.py", 60)
        assert out.strip() == "600002", out
        assert closed() > n, "ответ: окно гостя не закрывалось, проверять нечего"

    def no_screen():
        assert s.sh("test -e /dev/fb0")[0] != 0, "/dev/fb0 есть без boot.vga"
        assert s.sh("kt screen")[0] != 0, "kt screen есть без пакета kt-screen"
        # бандл без --vga: код экрана на странице вырезан при сборке (/* #if vga */)
        assert s.ev("typeof kt.screen") == "undefined", "kt.screen есть в бандле без экрана"
        assert not s.ev("document.querySelector('#screen')"), "#screen есть в бандле без экрана"
        assert s.sh("kt cfg screen.scale")[0] != 0, "screen.scale есть в бандле без экрана"
        assert s.ev("'vgabios' in BUNDLE.files") is False, "VGA BIOS в бандле без экрана"
        assert "vga: нет" in s.ok("kt info")

    def keys_in(cmd):
        """evdev-события клавиатуры (код, нажата), пока страница делает cmd."""
        s.ok("(cat /dev/input/event0 > /tmp/k.bin &)")
        time.sleep(0.5)
        cmd()
        time.sleep(1)
        raw = base64.b64decode(s.ok("killall cat; base64 /tmp/k.bin"))
        ev = [struct.unpack("<IIHHi", raw[i:i + 16])[2:] for i in range(0, len(raw) - 15, 16)]
        return [(code, v) for t, code, v in ev if t == 1 and v != 2]

    def screen_doom():
        t = s.open(base + "vga.html")
        assert s.ev("!!emulator.worker") == WORKER, "boot.worker не тот: ждали %s" % WORKER
        s.ok("test -c /dev/fb0 && test -c /dev/dri/card0")
        assert "vga: 8.0 МБ, спрятан" in s.ok("kt info")
        s.ok("kt screen on")
        assert s.ev("document.querySelector('#screen').classList.contains('on')"), "экран не показан"
        assert s.ev("emulator.keyboard_adapter.emu_enabled"), "клавиатура не ушла в машину"

        def press():
            for t_ in ("rawKeyDown", "keyUp"):
                s.c.call("Input.dispatchKeyEvent", type=t_, key="Enter", code="Enter", windowsVirtualKeyCode=13)
            s.ev("screenKey('UP', true)")
            time.sleep(0.3)
            s.ev("screenKey('UP', false); screenKey('Y', true); screenKey('Y', false); screenType('A')")
        got = keys_in(press)
        # Enter клавиатурой, ↑ кнопкой ряда (держится), Y кнопкой (без Shift), «A» набором (с Shift)
        assert got == [(28, 1), (28, 0), (103, 1), (103, 0), (21, 1), (21, 0), (42, 1), (30, 1), (30, 0), (42, 0)], got

        # CTRL, ALT и SHIFT ряда залипают: касание - на следующую клавишу, два - пока не коснёшься
        typed = lambda ch: s.ev("kbd.value = %s; kbd.dispatchEvent(new Event('input')); 0" % json.dumps(ch))
        cls = lambda label: s.ev("[...document.querySelectorAll('#keys button')].find((b) => b.textContent === %s).className" % json.dumps(label))
        seen = []

        def sticky():
            tap("ALT")
            tap("SHIFT")
            seen.append(cls("ALT"))
            typed("x")
            seen.append(cls("ALT"))
            tap("CTRL")
            tap("CTRL")
            seen.append(cls("CTRL"))
            typed("c")
            tap("CTRL")
            typed("d")
        s.ok("kt cfg term.mobile on")  # ряд клавиш - только на телефоне
        try:
            got = keys_in(sticky)
        finally:
            s.ok("kt cfg term.mobile off")
        assert seen == ["on", "", "lock"], seen
        assert got == [(56, 1), (56, 0), (42, 1), (42, 0), (56, 1), (42, 1), (45, 1), (45, 0), (56, 0), (42, 0),
                       (29, 1), (29, 0), (29, 1), (46, 1), (46, 0), (29, 0), (32, 1), (32, 0)], got
        s.ok("kt screen off")
        assert not s.ev("document.querySelector('#screen').classList.contains('on')")
        assert not s.ev("emulator.keyboard_adapter.emu_enabled")
        # консоль на виду - экран долой, как по Ctrl+Alt+N (kt tty N из X)
        s.ok("kt screen on")
        assert s.ok("kt js 'kt.tty.go(1)'").strip() == "true"
        assert s.ok("kt screen").strip() == "off", "kt.tty.go не спрятал экран"
        assert not s.ev("emulator.keyboard_adapter.emu_enabled"), "клавиатура осталась в машине"

        # хеш показанного кадра - по пикселям холста: и без воркера, и с ним (кадр пришёл копией)
        frame = """(() => { const c = document.querySelector('#screen canvas'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          let h = 0; for (let i = 0; i < d.length; i += 997) h = (h * 31 + d[i]) | 0; return h; })()"""
        s.start("doom")
        t0 = time.time()
        while not s.ev("document.querySelector('#screen').classList.contains('on')"):
            assert time.time() - t0 < 20, "doom не показал экран"
            time.sleep(0.3)
        time.sleep(2)
        size = s.ev("[document.querySelector('#screen canvas').width, document.querySelector('#screen canvas').height]")
        assert size == [640, 480], size
        a, t0 = s.ev(frame), time.time()
        while s.ev(frame) == a:  # титульная картинка стоит несколько секунд, потом демо
            assert time.time() - t0 < 15, "кадр не меняется"
            time.sleep(0.5)
        # pkill -f нашёл бы и свой шелл: движок - по exe
        s.ok("for p in /proc/[0-9]*; do [ \"$(readlink $p/exe)\" = /usr/lib/doom/doom ] && kill ${p#/proc/}; done; true")
        t0 = time.time()
        while s.ev("document.querySelector('#screen').classList.contains('on')"):
            assert time.time() - t0 < 10, "экран не спрятался после выхода doom"
            time.sleep(0.3)
        assert s.ev("document.activeElement === term.textarea"), "фокус не вернулся в терминал"
        return "загрузка %.1f с" % t

    def screen_x():
        def typing(text):
            for ch in text:
                code = {" ": "Space", "/": "Slash", "-": "Minus", "\r": "Enter"}.get(ch, "Key" + ch.upper())
                for t_ in ("rawKeyDown", "keyUp"):
                    s.c.call("Input.dispatchKeyEvent", type=t_, code=code, key=code, windowsVirtualKeyCode=ord(ch.upper()) if ch.isalpha() else 0)
                time.sleep(0.1)

        t0 = time.time()
        s.ev("send('startx\\r')")
        # окно xterm нарисовано: белый фон внутри него (+20+20 на экране 800x600)
        white = """(() => { const d = document.querySelector('#screen canvas').getContext('2d').getImageData(200, 150, 1, 1).data;
          return d[0] === 255 && d[1] === 255 && d[2] === 255; })()"""
        while not s.ev(white):
            assert time.time() - t0 < 60, "окно xterm не появилось: %s" % s.sh("tail -5 /var/log/Xorg.0.log")[1]
            time.sleep(0.5)
        ready = time.time() - t0
        # размер - тот, что считает страница (screenSize: место, видеопамять, screen.scale)
        canvas = "document.querySelector('#screen canvas').width + 'x' + document.querySelector('#screen canvas').height"
        assert s.ev(canvas) == s.ev("screenSize()"), (s.ev(canvas), s.ev("screenSize()"))
        bad = s.sh("grep '(EE)' /var/log/Xorg.0.log")[1]
        assert "keymap" not in bad, "раскладка не загрузилась: %s" % bad
        typing("touch /tmp/x-ok\r")
        t1 = time.time()
        while s.sh("test -e /tmp/x-ok")[0]:
            assert time.time() - t1 < 10, "набранное в xterm не выполнилось"
            time.sleep(0.5)
        # строка разом (слово с клавиатуры телефона, вставка): очередь evdev в ядре - 64 события, X
        # терял такую целиком, страница отдаёт клавиши порциями
        s.ev("screenType(%s)" % json.dumps("echo 'Hello, World' > /tmp/x-long\n"))
        t1 = time.time()
        while s.sh("cat /tmp/x-long")[1] != "Hello, World\n":
            assert time.time() - t1 < 15, "строка разом не дошла до xterm: %r" % s.sh("cat /tmp/x-long")[1]
            time.sleep(0.5)
        # окно браузера стало меньше - X идёт за ним (событие screen-size -> xrandr)
        s.c.call("Emulation.setDeviceMetricsOverride", width=640, height=480, deviceScaleFactor=1, mobile=False)
        t1 = time.time()
        while s.ev(canvas) != s.ev("screenSize()"):
            assert time.time() - t1 < 20, "X не пошёл за размером страницы: %s, а надо %s" % (s.ev(canvas), s.ev("screenSize()"))
            time.sleep(0.5)
        resized = s.ev(canvas)
        # сохранение с запущенным X: после перезагрузки экран снова на виду, а X идёт за новым местом
        s.ok("kt save", 120)
        s.c.call("Emulation.clearDeviceMetricsOverride")
        s.c.call("Page.reload")
        time.sleep(1)
        s.wait_ready()
        assert s.ev("document.querySelector('#screen').classList.contains('on')"), "после kt save экран не показан"
        t1 = time.time()
        while s.ev(canvas) != s.ev("screenSize()"):
            assert time.time() - t1 < 20, "после kt save X не пошёл за размером: %s, а надо %s" % (s.ev(canvas), s.ev("screenSize()"))
            time.sleep(0.5)
        typing("exit\r")
        t1 = time.time()
        while s.ev("document.querySelector('#screen').classList.contains('on')"):
            assert time.time() - t1 < 15, "экран не спрятался после выхода из сессии"
            time.sleep(0.3)
        assert s.sh("pgrep Xorg")[0] != 0, "Xorg остался"
        assert s.sh("pgrep tail")[0] != 0, "слушатель размера остался"
        return "окно xterm через %.1f с, потом %s" % (ready, resized)

    def screen_clip():
        # общий буфер обмена X и браузера (kt-xclipd из xorg, его запускает startx); xclip - программа X
        # со своим буфером
        if s.ev("typeof kt.screen") == "undefined":  # запущен один, без «экран и doom»
            s.open(base + "vga.html")
        s.c.call("Browser.grantPermissions", session=False, origin=base.rstrip("/"), permissions=["clipboardReadWrite", "clipboardSanitizedWrite"])
        s.c.call("Emulation.setFocusEmulationEnabled", enabled=True)
        s.ev("send('startx\\r')")
        # демон готов, когда слушает порт 7703 (0x1E17): тогда буфер X уже под присмотром
        t0 = time.time()
        while s.sh("grep -q ':1E17 00000000:0000 0A' /proc/net/tcp")[0]:
            assert time.time() - t0 < 60, "kt-xclipd не запустился: %s" % s.sh("tail -5 /var/log/Xorg.0.log")[1]
            time.sleep(0.5)
        # X -> браузер
        s.ok("printf 'из X\\nвторая' | DISPLAY=:0 xclip -selection clipboard")
        t1 = time.time()
        while s.ev("navigator.clipboard.readText()") != "из X\nвторая":
            assert time.time() - t1 < 10, "скопированное в X не попало в браузер: %r" % s.ev("navigator.clipboard.readText()")
            time.sleep(0.3)
        copied = time.time() - t1
        # браузер -> X: Ctrl+V на экране ждёт, пока текст уйдёт в X, нажатое следом (x) - за ним
        s.ev("navigator.clipboard.writeText('из браузера ё')")
        key = lambda t_, code, k, vk, m=0: s.c.call("Input.dispatchKeyEvent", type=t_, modifiers=m, code=code, key=k, windowsVirtualKeyCode=vk)

        def ctrl_v():
            key("rawKeyDown", "ControlLeft", "Control", 17, 2)
            key("rawKeyDown", "KeyV", "v", 86, 2)
            key("keyUp", "KeyV", "v", 86, 2)
            key("keyUp", "ControlLeft", "Control", 17)
            key("rawKeyDown", "KeyX", "x", 88)
            key("keyUp", "KeyX", "x", 88)
        got = keys_in(ctrl_v)
        assert got == [(29, 1), (47, 1), (47, 0), (29, 0), (45, 1), (45, 0)], got
        out = s.ok("DISPLAY=:0 xclip -o -selection clipboard")
        assert out == "из браузера ё", out
        # то же в браузере - в X не уходит: буфер X снова у xclip и остаётся у него
        s.ok("printf 'снова X' | DISPLAY=:0 xclip -selection clipboard")
        t1 = time.time()
        while s.ev("navigator.clipboard.readText()") != "снова X":
            assert time.time() - t1 < 10, "второе скопированное в X не попало в браузер"
            time.sleep(0.3)
        keys_in(ctrl_v)
        assert s.ok("pgrep -x xclip").strip(), "буфер X забрали, хотя в браузере то же"
        # программа с буфером закрылась - текст остаётся у демона
        s.ok("killall xclip")
        time.sleep(1)
        out = s.ok("DISPLAY=:0 xclip -o -selection clipboard")
        assert out == "снова X", out
        s.ok("killall xterm")
        t1 = time.time()
        while s.ev("document.querySelector('#screen').classList.contains('on')"):
            assert time.time() - t1 < 15, "экран не спрятался после выхода из сессии"
            time.sleep(0.3)
        t1 = time.time()
        while not s.sh("pgrep -x kt-xclipd")[0]:
            assert time.time() - t1 < 5, "kt-xclipd остался после X"
            time.sleep(0.3)
        # экран без демона (doom): соединение сразу закрыто, Ctrl+V уходит как есть
        s.ok("kt screen on")
        s.ev("navigator.clipboard.writeText('без демона')")
        try:
            got = keys_in(ctrl_v)
        finally:
            s.ok("kt screen off")
        assert got == [(29, 1), (47, 1), (47, 0), (29, 0), (45, 1), (45, 0)], got
        return "из X в браузер за %.1f с" % copied

    def snap_bundle():
        t = s.open(base + "snap.html")
        tz = s.ok("date +%z").strip()
        want = s.ev("(() => { const o = -new Date().getTimezoneOffset(); return (o < 0 ? '-' : '+') + String(Math.floor(Math.abs(o) / 60)).padStart(2, '0') + String(Math.abs(o) % 60).padStart(2, '0') })()")
        assert tz == want, (tz, want)
        r1 = s.ok("head -c 16 /dev/urandom | od -An -tx1")
        s.open(base + "snap.html")
        r2 = s.ok("head -c 16 /dev/urandom | od -An -tx1")
        assert r1 != r2, "одинаковые случайные числа"
        assert "version: t1" in s.ok("kt info"), "в kt info нет версии"
        return "восстановление %.1f с, пояс %s" % (t, tz)

    tests = [
        ("загрузка", boot), ("видеопамять пустая", vga_clean), ("без экрана", no_screen), ("память бандла", bundle_memory), ("один агент", one_agent), ("чистый терминал", clean_screen),
        ("kt js", kt_js), ("kt js из фона", kt_js_background), ("kt в X без консолей", kt_list_x), ("задержки", latency),
        ("kt.exec коды и stdin", exec_codes), ("kt.read/kt.write 2 МБ", read_write),
        ("kt dl файл, папка, stdin", kt_dl), ("kt up через кнопку", kt_up), ("kt up сразу после Enter", kt_up_typed), ("файл брошен на страницу", drop),
        ("kt copy/paste", clipboard), ("события kt.emit", events), ("micropython kt", micropython),
        ("cpython 8 потоков", cpython_threads), ("requests и curl", requests_shim),
        ("alert/confirm/prompt", dialogs), ("kt notify", notify), ("pack/unpack", pack), ("sync", sync),
        ("kt cfg свои ключи", cfg_custom), ("рендер терминала", render), ("ai инструменты", ai_tool), ("ai сжатие контекста", ai_context),
        ("ai диалог", ai_repl), ("ai протокол responses", ai_proto), ("ai /model", ai_model), ("pip", pip_shim), ("pip из репозитория", pip_repo), ("kt pkg из Alpine", pkg_alpine), ("kt pkg base", pkg_base), ("kt pkg rm -c, -y и files", pkg_cascade),
        ("chawan", chawan), ("в /run/kt нет мусора", run_clean),
        ("kt save + перезагрузка", save_restore), ("один агент после восстановления", one_agent),
        ("чистый терминал после восстановления", clean_screen), ("kill kt-netd и агента", kill_server),
        ("один агент после kill", one_agent), ("повтор сегмента TCP", tcp_resend), ("снимки и коды выхода", snap_rules), ("kt reset", reset),
        ("Ctrl+Alt+End при мёртвом агенте", secret_reset), ("CTRL ALT END кнопками", secret_reset_keys), ("экран и doom", screen_doom), ("X на экране", screen_x), ("буфер обмена X", screen_clip), ("бандл со снимком", snap_bundle),
        ("память бандла со снимком", bundle_memory),
    ]
    try:
        for name, fn in tests:
            if fn is boot or any(k in name for k in a.k.split(",")):
                s.check(name, fn)
    finally:
        if s.c:
            s.c.close()
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [r for r in s.results if not r[1]]
    print("\n%d из %d прошли" % (len(s.results) - len(bad), len(s.results)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
