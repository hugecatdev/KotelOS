import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import alpine
from cond import preprocess

IMG = "images"  # собирают build.sh и scripts/build-kernel.sh
V86 = "vendor/v86"  # libv86.js, v86.wasm и BIOS из проекта v86 (scripts/build-v86.sh)
v86_dir = V86  # откуда их брать на самом деле: --v86
REPO = "site/repo"
PAGE = "page.html"
CACHE = ".cache/cdn"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
DEFAULT = ["fun", "nano", "htop", "minipython", "lua5.4", "pyzygote",
           "curl", "wget", "python-requests", "pack", "notify", "ai", "examples-python", "examples-lua", "kt-ttyd", "tk-desktop", "tk-term"]


def fetch(url):
    path = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest())
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
    return open(path, "rb").read()


APK = {}
APK_MIRROR = [alpine.MIRROR]


def closure(names):
    deps = {}
    for line in open(REPO + "/index.txt"):
        f = line.rstrip("\n").split("\t")
        deps[f[0]] = f[2].split() if len(f) > 2 else []
    if os.path.exists(REPO + "/alpine.txt.gz"):
        with gzip.open(REPO + "/alpine.txt.gz", "rt") as idx:
            for line in idx:
                f = line.rstrip("\n").split("\t")
                if line.startswith("#mirror"):
                    APK_MIRROR.append(f[1])
                elif f[0] not in deps and len(f) > 5:
                    deps[f[0]] = f[2].split()
                    APK[f[0]] = f[5]
    out = []

    def pick(d):
        alts = d.split("|")
        return next((x for x in alts if x in names or x in out), alts[0])

    def visit(n):
        if n in out:
            return
        if n not in deps:
            sys.exit("нет пакета " + n)
        for d in deps[n]:
            visit(pick(d))
        out.append(n)

    for n in names:
        visit(n)
    return out


def packages_cpio(names, world, extra=()):
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "root")
        db = os.path.join(root, "var/lib/kt/pkg")
        os.makedirs(db)
        for spec in extra:
            src, _, dest = spec.partition(":")
            dest = dest or "/root/" + os.path.basename(src)
            if os.path.isdir(src):  # папка - её содержимое в ПУТЬ с правами (данные бандла, мимо kt pkg)
                shutil.copytree(src, os.path.join(root, dest.lstrip("/")), dirs_exist_ok=True)
                continue
            if dest.endswith("/"):
                dest += os.path.basename(src)
            target = os.path.join(root, dest.lstrip("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy(src, target)
        triggers = []
        for n in names:
            if n in APK:
                if apk_into(n, root):
                    triggers.append(n)
                continue
            archive = "%s/%s.tar.xz" % (REPO, n)
            subprocess.run(["tar", "-xJpf", archive, "-C", root], check=True)
            with open(os.path.join(db, n), "w") as f:
                subprocess.run(["tar", "-tJf", archive], stdout=f, check=True)
        if os.path.isdir(os.path.join(root, "root")):
            os.chmod(os.path.join(root, "root"), 0o700)
        if triggers:
            with open(os.path.join(root, "var/lib/kt/trigger.pending"), "w") as f:
                f.write(" ".join(triggers) + "\n")
        with open(os.path.join(root, "var/lib/kt/world"), "w") as f:
            f.write("".join(n + "\n" for n in world))
        with open(REPO + "/index.txt", "rb") as src, open(os.path.join(root, "var/lib/kt/index"), "wb") as dst:
            dst.write(src.read())
        post = [n for n in names if os.path.exists(os.path.join(root, "var/lib/kt/post", n))]
        if post:
            with open(os.path.join(root, "var/lib/kt/post.pending"), "w") as f:
                f.write(" ".join(post) + "\n")
        files = subprocess.run(["find", ".", "-mindepth", "1", "-printf", "%P\\n"], cwd=root,
                               capture_output=True, check=True).stdout
        files = b"\n".join(sorted(files.split(b"\n"))).strip() + b"\n"
        return subprocess.run(["cpio", "-o", "-H", "newc", "-R", "0:0", "--quiet"], cwd=root,
                              input=files, capture_output=True, check=True).stdout


def apk_into(name, root):
    path = APK[name]
    for i, mirror in enumerate(APK_MIRROR):
        try:
            apk = alpine.fetch(mirror + "/" + path, alpine.CACHE + "/apk/" + os.path.basename(path))
            break
        except OSError:
            if i == len(APK_MIRROR) - 1:
                raise
    alpine.extract(apk, root, [], [])
    files, trigger, dirs = [], None, ""
    with gzip.open(apk) as gz, tarfile.open(fileobj=gz, mode="r|") as t:
        for m in t:
            n = m.name[2:] if m.name.startswith("./") else m.name
            if n == ".trigger":
                trigger = t.extractfile(m).read()
            elif n == ".PKGINFO":
                for line in t.extractfile(m).read().decode().splitlines():
                    if line.startswith("triggers = "):
                        dirs = line[len("triggers = "):]
            elif n and not n.startswith("."):
                files.append(n + ("/" if m.isdir() else ""))
    with open(os.path.join(root, "var/lib/kt/pkg", name), "w") as f:
        f.write("".join(x + "\n" for x in files))
    if trigger is None:
        return False
    tdir = os.path.join(root, "var/lib/kt/trigger")
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(tdir, name), "wb") as f:
        f.write(trigger)
    with open(os.path.join(tdir, name + ".dirs"), "w") as f:
        f.write(dirs + "\n")
    return True


def b64(data):
    return base64.b64encode(data).decode()


def blob(data, gz=True):
    if gz:
        data = gzip.compress(data, 9)
    return {"gz": gz, "data": b64(data)}


def zstd(data):
    return subprocess.run(["zstd", "-19", "-q", "-c"], input=data, capture_output=True, check=True).stdout


def terser(js):
    try:
        r = subprocess.run(["npx", "--yes", "terser@5", "-c", "-m"], input=js.encode(), capture_output=True, check=True, timeout=300)
        return r.stdout.decode()
    except (OSError, subprocess.SubprocessError) as e:
        print("terser не сработал, скрипт без минификации:", e, file=sys.stderr)
        return js


def script(js):
    return "<script>%s</script>" % js.replace("</script", "<\\/script")


def local(src):
    """src из page.html: vendor/v86/* берётся из --v86"""
    if src.startswith(V86 + "/"):
        src = os.path.join(v86_dir, src[len(V86) + 1:])
    return open(src).read()


def template(have=()):
    # функции бандла (have): блоки /* #if имя */ ... /* #endif */ без них вырезаются, см. cond.py
    html = preprocess(open(PAGE).read(), set(have), PAGE)
    html = re.sub(r'<link (?:rel="stylesheet" )?href="(https://[^"]+)"(?: rel="stylesheet")?>',
                  lambda m: "<style>%s</style>" % fetch(m.group(1)).decode(), html)
    src = lambda u: fetch(u).decode() if u.startswith("https://") else local(u)
    # data-lazy: скрипт - текстом, страница запустит его сама, когда понадобится (lazyScript)
    html = re.sub(r'<script src="([^"]+)" data-lazy="([\w-]+)"></script>',
                  lambda m: '<script type="text/plain" id="%s">%s</script>' % (m.group(2), src(m.group(1)).replace("</script", "<\\/script")), html)
    # id: текст выполненного скрипта страница берёт по нему (libv86 - исходник для воркера, boot.worker)
    html = re.sub(r'<script src="([^"]+)" id="([\w-]+)"></script>',
                  lambda m: '<script id="%s">%s</script>' % (m.group(2), src(m.group(1)).replace("</script", "<\\/script")), html)
    html = re.sub(r'<script src="([^"]+)"></script>', lambda m: script(src(m.group(1))), html)
    return html


def nodata(d):
    return d and {k: v for k, v in d.items() if k != "data"}


def assemble(html, bundle, minify):
    parts = dict(bundle["files"], **({"state": bundle["state"]} if bundle["state"] else {}))
    blocks = "".join('<script type="application/base64" id="kt-%s">%s</script>' % (k, v["data"]) for k, v in parts.items())
    meta = dict(bundle, files={k: nodata(v) for k, v in bundle["files"].items()}, state=nodata(bundle["state"]))
    data = "window.KT_BUNDLE = %s;" % json.dumps(meta, separators=(",", ":"))
    i = html.index('<script>\n    "use strict";')
    j = html.index("</script>", i)
    main = html[i + 8:j]
    html = html[:i] + blocks + script(data) + script(terser(main) if minify else main) + html[j + 9:]
    if bundle["name"] != "kotelos":
        html = html.replace("<title>KotelOS</title>", "<title>KotelOS %s</title>" % bundle["name"])
    if minify:
        html = re.sub(r"<style>\n(.*?)</style>", lambda m: "<style>" + re.sub(r"\s*\n\s*", "", m.group(1)) + "</style>", html, flags=re.S)
        html = re.sub(r">\n\s*<", "><", html)
    return html


class Chrome:
    def __init__(self, profile):
        exe = os.environ.get("CHROME") or next(
            (x for x in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable") if shutil.which(x)), None)
        if not exe:
            sys.exit("для снимка нужен chromium (или CHROME=путь)")
        args = [exe, "--headless=new", "--remote-debugging-pipe", "--user-data-dir=" + profile,
                "--no-first-run", "--no-default-browser-check", "--window-size=800,600"]
        self.proc = subprocess.Popen(["sh", "-c", 'exec "$@" 3<&0 4>&1 </dev/null >/dev/null', "sh"] + args,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.id = 0
        self.buf = b""
        self.session = None

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
                    raise RuntimeError(m["error"].get("message", str(m["error"])))
                return m["result"]

    def open(self, url):
        target = self.call("Target.createTarget", session=False, url=url)["targetId"]
        self.session = self.call("Target.attachToTarget", session=False, targetId=target, flatten=True)["sessionId"]

    def eval(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise RuntimeError(d.get("exception", {}).get("description") or d.get("text"))
        return r["result"].get("value")

    def close(self):
        try:
            self.call("Browser.close", session=False)
        except (RuntimeError, OSError):
            pass
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


SETTLE = """(async (quiet, max) => {
  const t0 = Date.now();
  while (Date.now() - t0 < max) {
    const r = await exec('read a < /proc/stat; sleep 1; read b < /proc/stat; echo "$a"; echo "$b"');
    const [a, b] = r.out.trim().split("\\n").map((l) => l.split(/\\s+/).slice(1).map(Number));
    const d = b.map((x, i) => x - a[i]), total = d.reduce((x, y) => x + y, 0);
    if ((total ? (d[3] + (d[4] || 0)) / total : 1) > 0.9 && Date.now() - lastOutput > quiet) return true;
  }
  return false;
})(%d, %d)"""

SNAP = """(async () => {
  const raw = await emulator.save_state();
  const gz = await new Response(new Blob([raw]).stream().pipeThrough(new CompressionStream("gzip"))).arrayBuffer();
  return { state: toB64(new Uint8Array(gz)), screen: serializer.serialize({ scrollback: 300 }), mem: memSize, vga: vgaSize,
           screen_on: screenOn, screen_size: screenSent };
})()"""


def snapshot(html, cmds, timeout, prep=()):
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "bundle.html")
        with open(page, "w") as f:
            f.write(html)
        chrome = Chrome(os.path.join(tmp, "profile"))
        try:
            chrome.open("file://" + page)
            t0 = time.time()
            while not chrome.eval("typeof agentReady !== 'undefined' && agentReady"):
                if time.time() - t0 > 180:
                    sys.exit("машина не загрузилась за 3 минуты")
                time.sleep(0.5)
            chrome.eval(SETTLE % (1500, 60000))
            print("загрузилась за %.0f с" % (time.time() - t0))
            for cmd in prep:
                t1 = time.time()
                code, err = chrome.eval("exec(%s).then((r) => [r.code, r.err])" % json.dumps(cmd))
                if code:
                    sys.exit("%s: код %s\n%s" % (cmd, code, err))
                chrome.eval(SETTLE % (1500, timeout * 1000))
                print("  %s: %.0f с" % (cmd, time.time() - t1))
            for cmd in cmds:
                t1 = time.time()
                chrome.eval("send(%s)" % json.dumps(cmd + "\r"))
                time.sleep(1)
                if not chrome.eval(SETTLE % (1500, timeout * 1000)):
                    print("  %s: не успокоилась за %d с, снимаю как есть" % (cmd, timeout), file=sys.stderr)
                print("  %s: %.0f с" % (cmd, time.time() - t1))
            r = chrome.eval(SNAP)
        finally:
            chrome.close()
    out = {"data": b64(zstd(gzip.decompress(base64.b64decode(r["state"])))), "mem": r["mem"], "vga": r["vga"], "screen": r["screen"]}
    if r.get("screen_on"):  # снимок с запущенным X (--run startx): страница сразу покажет экран
        out.update(screen_on=True, screen_size=r["screen_size"])
    return out


def options(argv=None):
    ap = argparse.ArgumentParser(description="KotelOS в один html-файл")
    ap.add_argument("packages", nargs="*", default=DEFAULT, help="пакеты (по умолчанию: %s)" % " ".join(DEFAULT))
    ap.add_argument("-o", "--out", default="site/index.html", help="куда (по умолчанию site/index.html)")
    ap.add_argument("-n", "--name", default="kotelos", help="имя: своё сохранение у каждого имени")
    ap.add_argument("--repo", default="/repo", help="откуда kt pkg add качает пакеты (по умолчанию /repo)")
    ap.add_argument("--snap", action="store_true", help="загрузить машину при сборке и положить снимок")
    ap.add_argument("--run", action="append", default=[], metavar="CMD", help="перед снимком набрать команду (можно несколько)")
    ap.add_argument("--prep", action="append", default=[], metavar="CMD",
                    help="перед снимком выполнить команду мимо терминала: прогреть кэши (можно несколько)")
    ap.add_argument("--keep-boot", action="store_true", help="оставить ядро рядом со снимком (kt reset -b)")
    ap.add_argument("--timeout", type=int, default=300, help="сколько ждать каждую --run, с")
    ap.add_argument("--bare", action="store_true", help="без пакетов: только busybox и kt")
    ap.add_argument("--mem", type=int, help="память машины по умолчанию, МБ (иначе 128)")
    ap.add_argument("--worker", action="store_true",
                    help="boot.worker по умолчанию on: процессор и устройства v86 в Web Worker")
    ap.add_argument("--vga", type=int, choices=[4, 8, 16], metavar="МБ",
                    help="экран (boot.vga): видеопамять 4, 8 или 16 МБ (без числа - 8), /dev/fb0")
    ap.add_argument("--virgl", action="store_true",
                    help="VirGL: сервер vtest с virglrenderer в wasm (build/virgl, scripts/build-virgl.sh) на 192.168.86.1:7790")
    ap.add_argument("--phone-scale", type=float, metavar="CSS",
                    help="экран на телефоне при screen.scale auto: точек страницы на точку X (иначе 1); на ПК не действует")
    ap.add_argument("--save-timer", type=int, metavar="МИН", help="save.timer по умолчанию: сохранять машину каждые N минут (иначе 0 - нет)")
    ap.add_argument("--cmd", help="команда при загрузке по умолчанию (boot.cmd)")
    ap.add_argument("--file", action="append", default=[], metavar="ФАЙЛ[:ПУТЬ]",
                    help="положить файл в образ (по умолчанию в /root/); папку - её содержимое в ПУТЬ")
    ap.add_argument("--version", help="метка бандла: видна в kt info")
    ap.add_argument("--v86", default=V86, metavar="ПАПКА", help="libv86.js, v86.wasm и BIOS (по умолчанию %s)" % V86)
    # --vga [МБ]: число - только если оно следом, иначе (--vga doom) 8; argparse с nargs="?" съел бы пакет
    argv = list(sys.argv[1:] if argv is None else argv)
    for i, x in enumerate(argv):
        if x == "--vga":
            argv[i] = "--vga=" + (argv.pop(i + 1) if i + 1 < len(argv) and argv[i + 1].isdigit() else "8")
    a = ap.parse_args(argv)
    if a.bare:
        a.packages = []
    for v in (a.name, a.version or "0"):
        if not re.fullmatch(r"[\w.-]{1,32}", v):
            sys.exit("имя и метка: буквы, цифры, . _ -")
    return a


def main():
    global v86_dir
    a = options()
    v86_dir = a.v86
    snap = a.snap or bool(a.run) or bool(a.prep)
    if os.path.exists(a.out) and "window.KT_BUNDLE" not in open(a.out, errors="replace").read():
        sys.exit("%s есть и это не бандл, не перезаписываю" % a.out)

    names = closure(a.packages)
    initrd = open(IMG + "/rootfs.cpio", "rb").read() + packages_cpio(names, a.packages, a.file)
    files = {
        "wasm": blob(open(v86_dir + "/v86.wasm", "rb").read()),
        "bios": blob(open(v86_dir + "/seabios.bin", "rb").read()),
    }
    # VGA BIOS нужен только экрану: ядро грузится через fw_cfg, консоль - ttyS0
    if a.vga:
        files["vgabios"] = blob(open(v86_dir + "/vgabios.bin", "rb").read())
    if a.virgl:
        files["virgl"] = blob(open("build/virgl/virgl.wasm", "rb").read())
    boot = {
        "bzimage": blob(open(IMG + "/bzImage", "rb").read(), gz=False),
        "initrd": {"size": len(initrd), "data": b64(zstd(initrd))},
    }
    bundle = {"name": a.name, "build": json.load(open(IMG + "/build.json")), "repo": a.repo, "files": {**files, **boot}, "state": None}
    if a.mem:
        bundle["mem"] = a.mem
    if a.vga:
        bundle["vga"] = a.vga
    if a.phone_scale:
        bundle["phone_scale"] = a.phone_scale
    if a.save_timer:
        bundle["save_timer"] = a.save_timer
    if a.worker:
        bundle["worker"] = True
    if a.cmd:
        bundle["cmd"] = a.cmd
    if a.version:
        bundle["version"] = a.version
    # функции бандла: блоки страницы /* #if имя */ без них вырезаются
    page = template({x for x in ("vga", "virgl") if getattr(a, x)})

    if snap:
        bundle["state"] = snapshot(assemble(page, bundle, False), a.run, a.timeout, a.prep)
        if not a.keep_boot:
            bundle["files"] = files

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as f:
        f.write(assemble(page, bundle, True))
    what = ["снимок %.1f МБ" % (len(bundle["state"]["data"]) * 3 / 4 / 1048576)] if snap else []
    if "bzimage" in bundle["files"]:
        what.append("ядро")
    print("%s %.1f МБ, %s, пакеты: %s" % (a.out, os.path.getsize(a.out) / 1048576, " + ".join(what), " ".join(names)))


if __name__ == "__main__":
    main()
