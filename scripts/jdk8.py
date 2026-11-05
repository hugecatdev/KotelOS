import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import alpine  # noqa: E402

DEST = os.path.join(alpine.GEN, "jdk8")

J = "usr/lib/jvm/java-1.8-openjdk"
JSA = J + "/jre/lib/i386/server/classes.jsa"
OPTS = "-XX:TieredStopAtLevel=1 -Xshare:auto"
DROP = alpine.DROP + [
    J + "/lib/ct.sym", J + "/lib/sa-jdi.jar", J + "/jre/lib/ext/cldrdata.jar", J + "/jre/lib/ext/nashorn.jar",
    J + "/jre/lib/ext/localedata.jar", J + "/bin/jjs", J + "/jre/bin/jjs", J + "/man/*", J + "/ASSEMBLY_EXCEPTION",
    J + "/THIRD_PARTY_README", J + "/LICENSE", J + "/bin/hsdb", J + "/bin/clhsdb", J + "/bin/jsadebugd",
]


def main():
    pkgs, _ = alpine.index()
    dest = DEST
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    for n in ("openjdk8-jre-lib", "openjdk8-jre-base", "openjdk8-jdk"):
        p = pkgs[n]
        apk = alpine.fetch(f"{alpine.MIRROR}/{p['repo']}/x86/{n}-{p['ver']}.apk", f"{alpine.CACHE}/apk/{n}-{p['ver']}.apk")
        alpine.extract(apk, dest, DROP, [])
    os.symlink("java-1.8-openjdk", os.path.join(dest, "usr/lib/jvm/default-jvm"))
    os.makedirs(os.path.join(dest, "usr/bin"), exist_ok=True)
    for b in sorted(os.listdir(os.path.join(dest, J, "bin"))):
        target = os.path.join(dest, "usr/bin", b)
        if b in ("java", "javac"):
            opts = " ".join(("-J" if b == "javac" else "") + o for o in OPTS.split())
            with open(target, "w") as f:
                f.write('#!/bin/sh\nexec /usr/lib/jvm/default-jvm/bin/%s %s "$@"\n' % (b, opts))
            os.chmod(target, 0o755)
        else:
            os.symlink("../lib/jvm/default-jvm/bin/" + b, target)
    with open(os.path.join(dest, ".deps"), "w") as f:
        f.write("musl libgcc libstdc++ zlib libjpeg-turbo lcms2\n")
    print("jdk8 <- " + " ".join(pkgs[n]["ver"] for n in ("openjdk8-jdk",)))


def cds():
    import bundle
    with tempfile.TemporaryDirectory() as tmp:
        html = os.path.join(tmp, "cds.html")
        subprocess.run([sys.executable, "bundle.py", "-o", html, "-n", "cds", "--mem", "384", "jdk8"], check=True,
                       stdout=subprocess.DEVNULL)
        c = bundle.Chrome(os.path.join(tmp, "profile"))
        try:
            c.open("file://" + html)
            t = time.time()
            while not c.eval("typeof agentReady !== 'undefined' && agentReady"):
                if time.time() - t > 180:
                    sys.exit("машина не загрузилась за 3 минуты")
                time.sleep(0.5)
            r = c.eval("kt.exec('/usr/lib/jvm/default-jvm/bin/java -Xshare:dump').then((r) => [r.code, r.err.slice(-400)])")
            if r[0]:
                sys.exit("java -Xshare:dump: " + r[1])
            data = c.eval("""kt.read(%s).then((b) => { let s = "";
              for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode.apply(null, b.subarray(i, i + 32768));
              return btoa(s); })""" % json.dumps("/" + JSA))
        finally:
            c.close()
    raw = base64.b64decode(data)
    with open(os.path.join(DEST, JSA), "wb") as f:
        f.write(raw)
    print("classes.jsa %.1f МБ -> %s/%s (пересобери ./build.sh)" % (len(raw) / 1048576, DEST, JSA))


if __name__ == "__main__":
    os.chdir(ROOT)
    cds() if sys.argv[1:] == ["--cds"] else main()
