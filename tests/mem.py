import argparse
import os
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bundle


def anon(pid):
    try:
        for line in open("/proc/%s/status" % pid):
            if line.startswith("RssAnon:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0


def renderer(profile):
    best = (0, None)
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            cmd = open("/proc/%s/cmdline" % pid, "rb").read().decode(errors="replace")
        except OSError:
            continue
        if "--type=renderer" in cmd and profile in cmd:
            best = max(best, (anon(pid), pid))
    return best


def main():
    ap = argparse.ArgumentParser(description="анонимная память вкладки с бандлом в headless Chromium, МБ (нужен Linux)")
    ap.add_argument("bundle", help="html-файл бандла")
    ap.add_argument("--save", action="store_true", help="после загрузки сделать kt save и показать всплеск")
    ap.add_argument("--profile", help="папка профиля: повторный запуск с ней - возврат из сохранения")
    ap.add_argument("--wait", type=float, default=4, help="пауза после загрузки, с (по умолчанию 4)")
    a = ap.parse_args()
    tmp = None if a.profile else tempfile.mkdtemp(prefix="kt-mem-")
    profile = os.path.abspath(a.profile or tmp)
    c = bundle.Chrome(profile)
    peak = [0.0]
    stop = threading.Event()

    def watch():
        while not stop.is_set():
            peak[0] = max(peak[0], renderer(profile)[0])
            time.sleep(0.01)

    def settled():
        for _ in range(3):
            c.call("HeapProfiler.collectGarbage")
            time.sleep(0.7)
        return renderer(profile)[0]

    try:
        threading.Thread(target=watch, daemon=True).start()
        t0 = time.time()
        c.open("file://" + os.path.abspath(a.bundle))
        while not c.eval("typeof agentReady !== 'undefined' && agentReady"):
            if time.time() - t0 > 180:
                sys.exit("машина не загрузилась за 3 минуты")
            time.sleep(0.2)
        t = time.time() - t0
        time.sleep(a.wait)
        how = c.eval("kv.get(SLOT).then((s) => s ? 'из сохранения' : BUNDLE.state && !coldBoot ? 'со снимка' : 'с ядра', () => '?')")
        print("%s, %s: загрузка %.1f с, пик %.0f МБ, после загрузки %.0f МБ" % (a.bundle, how, t, peak[0], settled()))
        if a.save:
            peak[0] = 0
            size = c.eval("kt.save()")
            time.sleep(1)
            print("kt save %.1f МБ: пик %.0f МБ, после %.0f МБ" % ((size or 0) / 1048576, peak[0], settled()))
    finally:
        stop.set()
        c.close()
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
