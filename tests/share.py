"""kt share (пакет kt-share) между двумя людьми: два профиля headless Chromium, A -> B -> A -> B.

Бандл - голая машина со снимком, файлы пакета прямо из packages/kt-share (без build.sh и site/repo).
Проверяет: копия открывается у другого с машиной отправителя; kt share, который застал снимок, у
получателя заканчивается; ревизии идут цепочкой; новая чужая ревизия побеждает, своё - в снимок, kt load
его возвращает; файл, от которого пошло сохранение, его продолжает; обычный бандл не задет.
"""
import glob
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bundle  # noqa: E402


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


class Person(bundle.Chrome):
    def __init__(self, tmp, name, url):
        self.dl = os.path.join(tmp, "dl-" + name)
        os.makedirs(self.dl)
        super().__init__(os.path.join(tmp, "prof-" + name))
        self.call("Browser.setDownloadBehavior", session=False, behavior="allow", downloadPath=self.dl)
        self.name, self.url, self.target = name, url, None

    def go(self, page):
        if self.target:
            self.call("Target.closeTarget", session=False, targetId=self.target)
            time.sleep(0.5)
        self.target = self.call("Target.createTarget", session=False, url=self.url + page)["targetId"]
        self.session = self.call("Target.attachToTarget", session=False, targetId=self.target, flatten=True)["sessionId"]
        self.ready()

    def ready(self, t=120):
        t0 = time.time()
        while True:
            try:
                if self.eval("typeof agentReady !== 'undefined' && agentReady && !!document.getElementById('kt-share')"):
                    break
            except RuntimeError:
                pass
            if time.time() - t0 > t:
                raise SystemExit("%s: страница не готова за %d с" % (self.name, t))
            time.sleep(0.3)
        self.eval("kt.cfg('save.auto', 'off')")  # в слоты пишут только kt save и kt share
        time.sleep(1.5)  # хук page.d и REDRAW

    def sh(self, cmd):
        return self.eval("exec(%s).then((r) => [r.code, r.out, r.err])" % json.dumps(cmd))

    def screen(self):
        return self.eval("screenText()")

    def click(self):
        # как человек: мышь на язычок (раскрывается), нажать и отпустить
        x, y = self.eval("(() => { const r = document.getElementById('kt-share').getBoundingClientRect(); "
                         "return [r.right - 3, r.top + r.height / 2]; })()")
        self.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
        time.sleep(0.3)
        for t in ("mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent", type=t, x=x, y=y, button="left", clickCount=1)

    def take(self, www, as_name, t=120):
        t0 = time.time()
        while time.time() - t0 < t:
            files = glob.glob(self.dl + "/*.html")
            if files and not glob.glob(self.dl + "/*.crdownload"):
                time.sleep(0.5)
                dst = os.path.join(www, as_name)
                shutil.move(files[0], dst)
                return dst
            time.sleep(0.3)
        raise SystemExit("%s: файл не скачался за %d с\n%s" % (self.name, t, self.screen()[-600:]))


def meta(path):
    h = open(path, errors="replace").read()
    m = json.loads(re.search(r"<script>window\.KT_BUNDLE = (.*?);</script>", h).group(1))
    return m, re.search(r"<title>(.*?)</title>", h).group(1)


def main():
    os.chdir(ROOT)
    tmp = tempfile.mkdtemp(prefix="kt-share-")
    www = os.path.join(tmp, "www")
    os.makedirs(www)
    r = subprocess.run([sys.executable, "bundle.py", "--bare", "--snap", "-n", "kst", "-o", www + "/t.html",
                        "--file", "packages/kt-share/usr:/usr", "--file", "packages/kt-share/etc:/etc"],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    print(r.stdout.strip().splitlines()[-1])
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *x: Quiet(*x, directory=www))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/" % httpd.server_port
    fails = []

    def check(what, ok, info=""):
        print(("ok   " if ok else "FAIL ") + what + ("" if ok else "\n     " + str(info)[-500:]))
        if not ok:
            fails.append(what)

    A = B = None
    try:
        A, B = Person(tmp, "A", url), Person(tmp, "B", url)

        A.go("t.html")
        A.sh("echo A1 > /root/a.txt")
        A.eval("send('kt share proj\\r')")
        p1 = A.take(www, "p1.html")
        time.sleep(2)
        m1, title = meta(p1)
        s1 = m1["state"]
        check("A: p1 - имя proj-*, gzip, ревизия, без cmd, полный repo, заголовок",
              re.fullmatch(r"proj-[a-z2-9]{6}", m1["name"]) and s1["gz"] and s1["revs"] == [s1["rev"]] and "cmd" not in m1
              and m1["repo"] == url + "repo" and title == "KotelOS proj" and m1["id"] == A.eval("BUNDLE.id"),
              (m1["name"], s1.get("revs"), m1.get("repo"), title))
        check("A: kt share в шелле закончился с итогом", "proj.html," in A.screen() and "скачивается" in A.screen(), A.screen())
        print("     t.html %.1f МБ, p1 %.1f МБ" % (os.path.getsize(www + "/t.html") / 1048576, os.path.getsize(p1) / 1048576))
        pid = m1["name"]

        B.go("p1.html")
        check("B: машина A", B.sh("cat /root/a.txt")[1] == "A1\n", B.sh("cat /root/a.txt"))
        check("B: kt share из снимка закончился", "это копия машины из kt share" in B.screen(), B.screen())
        check("B: слот проекта", B.eval("kt.bundle") == pid, B.eval("kt.bundle"))
        B.sh("echo B2 > /root/b.txt")
        B.click()
        m2 = meta(B.take(www, "p2.html"))[0]
        check("B: p2 - тот же проект, ревизия от p1", m2["name"] == pid and m2["state"]["revs"][:-1] == s1["revs"], m2["state"]["revs"])
        B.sh("echo B3 > /root/b3.txt")
        B.eval("kt.save()")

        A.go("p2.html")
        check("A: правка B есть, сделанного после отправки - нет",
              A.sh("cat /root/b.txt")[1] == "B2\n" and A.sh("test -f /root/b3.txt")[0] != 0)
        A.sh("echo A4 > /root/a4.txt")
        A.click()
        A.take(www, "p3.html")

        B.go("p3.html")
        check("B: p3 побеждает своё", B.sh("cat /root/a4.txt")[1] == "A4\n" and B.sh("test -f /root/b3.txt")[0] != 0)
        check("B: сказано про снимок", "прежнее сохранение - снимок " + pid in B.screen(), B.screen()[-400:])
        check("B: kt snap показывает отложенное", pid in B.sh("kt snap")[1], B.sh("kt snap"))
        time.sleep(6)  # kt load сразу после восстановления страница пропускает
        B.eval("send('kt load %s\\r')" % pid)
        time.sleep(3)
        B.ready()
        check("B: kt load вернул своё и не отдал его в снимок снова",
              B.sh("cat /root/b3.txt")[1] == "B3\n" and "прежнее сохранение" not in B.screen(), B.screen()[-400:])
        B.call("Page.reload")
        time.sleep(2)
        B.ready()
        check("B: перезагрузка p3 - продолжение своего", B.sh("cat /root/b3.txt")[1] == "B3\n")
        B.go("p1.html")
        check("B: старый p1 - тоже продолжение своего", B.sh("cat /root/b3.txt")[1] == "B3\n")

        A.go("t.html")
        check("A: обычный бандл - своё сохранение", A.sh("cat /root/a.txt")[1] == "A1\n" and A.eval("kt.bundle") == "kst")
    finally:
        for x in (A, B):
            if x:
                x.close()
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + ("всё прошло" if not fails else "упало: %d" % len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
