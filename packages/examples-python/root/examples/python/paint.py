import os
import sys
import kt

name = sys.argv[1] if len(sys.argv) > 1 else "drawing.png"
path = name if name.startswith("/") else os.getcwd() + "/" + name
try:
    os.stat(path)
    exists = True
except OSError:
    exists = False

try:
    kt.js("""async (path, exists) => {
  document.getElementById("kt-paint")?.remove();
  const d = document.createElement("div");
  d.id = "kt-paint";
  d.style.cssText = "position:fixed;inset:12px;z-index:9;display:flex;flex-direction:column;background:#000;color:#ccc;border:1px solid #444;font:12px/1.6 ui-monospace,monospace";
  const colors = ["#111111", "#ffffff", "#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#8e24aa"];
  const btn = "background:none;border:1px solid #333;color:#aaa;font:inherit;padding:2px 10px;cursor:pointer";
  d.innerHTML = `<div style="display:flex;align-items:center;justify-content:space-between;padding:0 0 0 10px;border-bottom:1px solid #222;color:#888">
    <span>${path.split("/").pop()}</span><button data-a="close" style="background:none;border:0;color:#888;font:16px/1 monospace;padding:6px 10px;cursor:pointer">×</button></div>
    <div style="flex:1;min-height:0;display:flex;align-items:center;justify-content:center;background:#111">
      <canvas style="max-width:100%;max-height:100%;touch-action:none;background:#fff;cursor:crosshair"></canvas></div>
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:6px 10px;border-top:1px solid #222">
      ${colors.map((c) => `<button data-c="${c}" style="width:22px;height:22px;border:2px solid #000;outline:1px solid #333;background:${c};cursor:pointer"></button>`).join("")}
      <span style="width:12px"></span>
      ${[2, 6, 14].map((s) => `<button data-s="${s}" style="${btn}">${s}</button>`).join("")}
      <span style="flex:1"></span>
      <button data-a="clear" style="${btn}">очистить</button>
      <button data-a="save" style="${btn}">сохранить</button>
    </div>`;
  document.body.append(d);
  const c = d.querySelector("canvas"), g = c.getContext("2d"), area = c.parentElement;
  const blank = () => { g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height); };
  if (exists) {
    const img = await createImageBitmap(new Blob([await kt.read(path)]));
    c.width = img.width;
    c.height = img.height;
    g.drawImage(img, 0, 0);
  } else {
    c.width = area.clientWidth;
    c.height = area.clientHeight;
    blank();
  }
  g.lineCap = g.lineJoin = "round";
  let color = colors[0], size = 6, last = null;
  const pick = (attr, v) => d.querySelectorAll(`[data-${attr}]`).forEach((b) => {
    const on = b.dataset[attr] === String(v);
    if (attr === "c") b.style.outlineColor = on ? "#ccc" : "#333"; else b.style.color = on ? "#fff" : "#aaa";
  });
  pick("c", color);
  pick("s", size);
  d.onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.c) { color = b.dataset.c; pick("c", color); }
    if (b.dataset.s) { size = +b.dataset.s; pick("s", size); }
    if (b.dataset.a === "clear") blank();
    if (b.dataset.a === "close") { d.remove(); kt.emit("close"); }
    if (b.dataset.a === "save") c.toBlob(async (blob) => { await kt.write(path, blob); kt.emit("saved", blob.size); });
  };
  const at = (e) => {
    const r = c.getBoundingClientRect();
    return [(e.clientX - r.left) * c.width / r.width, (e.clientY - r.top) * c.height / r.height];
  };
  c.onpointerdown = (e) => { last = at(e); c.setPointerCapture(e.pointerId); };
  c.onpointermove = (e) => {
    if (!last) return;
    const p = at(e);
    g.strokeStyle = color;
    g.lineWidth = size * c.width / c.getBoundingClientRect().width;
    g.beginPath(); g.moveTo(...last); g.lineTo(...p); g.stroke();
    last = p;
  };
  c.onpointerup = () => { last = null; };
}""", path, exists)
except kt.JSError as e:
    print("paint: %s" % e, file=sys.stderr)
    sys.exit(1)

for ev in kt.events():
    if ev["name"] == "saved":
        print("%s, %d байт" % (name, ev["data"]))
    elif ev["name"] == "close":
        break
