import os
import time
import kt

kt.js("""() => {
  document.getElementById("kt-monitor")?.remove();
  const d = document.createElement("div");
  d.id = "kt-monitor";
  d.style.cssText = "position:fixed;top:12px;right:12px;z-index:9;width:264px;background:#000;color:#ccc;border:1px solid #444;font:12px/1.6 ui-monospace,monospace";
  d.innerHTML = `<div style="display:flex;align-items:center;justify-content:space-between;padding:0 0 0 10px;border-bottom:1px solid #222;color:#888">
    <span>monitor</span><button style="background:none;border:0;color:#888;font:16px/1 monospace;padding:6px 10px;cursor:pointer">×</button></div>
    <div style="padding:8px 12px 10px"></div>`;
  d.querySelector("button").onclick = () => { d.remove(); kt.emit("close"); };
  document.body.append(d);
  const body = d.lastElementChild;
  const row = (a, b, dim) => `<div style="display:flex;justify-content:space-between${dim ? ";color:#777" : ""}"><span>${a}</span><span>${b}</span></div>`;
  const bar = (v) => `<div style="height:3px;background:#222;margin:3px 0 8px"><div style="height:100%;width:${Math.round(v * 100)}%;background:#bbb"></div></div>`;
  window.ktMonitor = (m) => {
    const pts = m.hist.map((v, i) => `${(i * 240 / 59).toFixed(1)},${(29 - v * 27).toFixed(1)}`).join(" ");
    body.innerHTML = row("процессор", Math.round(m.cpu * 100) + "%") + bar(m.cpu) +
      `<svg width="240" height="30" style="display:block;margin:-2px 0 8px"><polyline points="${pts}" fill="none" stroke="#777" stroke-width="1"/></svg>` +
      row("память", `${m.used} / ${m.total} МБ`) + bar(m.used / m.total) +
      row("процессов " + m.procs, "работает " + m.up, true);
  };
}""")


def cpu():
    with open("/proc/stat") as f:
        v = [int(x) for x in f.readline().split()[1:]]
    return sum(v), v[3]


def mem():
    m = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            m[k] = int(v.split()[0]) // 1024
    return m["MemTotal"], m["MemTotal"] - m["MemAvailable"]


def uptime():
    with open("/proc/uptime") as f:
        s = int(float(f.read().split()[0]))
    return "%d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60) if s >= 3600 else "%d:%02d" % (s // 60, s % 60)


hist = [0] * 60
t0, i0 = cpu()
try:
    while not kt.poll():
        time.sleep(1)
        t1, i1 = cpu()
        load = 1 - (i1 - i0) / max(1, t1 - t0)
        t0, i0 = t1, i1
        total, used = mem()
        hist = hist[1:] + [load]
        kt.js("(m) => ktMonitor(m)", {"cpu": load, "hist": hist, "used": used, "total": total,
                                       "procs": sum(p.isdigit() for p in os.listdir("/proc")), "up": uptime()})
except KeyboardInterrupt:
    pass
finally:
    kt.js("() => document.getElementById('kt-monitor')?.remove()")
