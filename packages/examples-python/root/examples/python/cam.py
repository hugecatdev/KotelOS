import binascii
import sys
import time
import kt

cols, rows = kt.js("() => [kt.term.cols, kt.term.rows]")
w = min(cols - 1, int(sys.argv[1]) if len(sys.argv) > 1 else 64)
h = min(rows - 2, w * 3 // 8)

try:
    kt.js("""async () => {
  if (window.ktCam) return;
  const v = document.createElement("video");
  v.muted = true;
  v.playsInline = true;
  v.srcObject = await navigator.mediaDevices.getUserMedia({ video: true });
  await v.play();
  const c = document.createElement("canvas");
  window.ktCam = { v, c, g: c.getContext("2d", { willReadFrequently: true }) };
}""", timeout=60)
except kt.JSError as e:
    print("cam: нет доступа к камере (%s)" % str(e).split(": ", 1)[-1], file=sys.stderr)
    sys.exit(1)

GRAB = """(w, h) => {
  const { v, c, g } = window.ktCam;
  c.width = w;
  c.height = h;
  g.setTransform(-1, 0, 0, 1, w, 0);
  g.drawImage(v, 0, 0, w, h);
  const d = g.getImageData(0, 0, w, h).data;
  const q = (x) => Math.round(x / 51);
  let s = "";
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i], gr = d[i + 1], b = d[i + 2];
    const n = Math.max(r, gr, b) - Math.min(r, gr, b) < 12
      ? 232 + Math.round((r + gr + b) / 3 / 255 * 23)
      : 16 + 36 * q(r) + 6 * q(gr) + q(b);
    s += n.toString(16).padStart(2, "0");
  }
  return s;
}"""


def frame(px):
    out = []
    for y in range(h):
        top, bot = 2 * y * w, (2 * y + 1) * w
        pf = pb = -1
        for x in range(w):
            f, b = px[top + x], px[bot + x]
            if f != pf and b != pb:
                out.append("\x1b[38;5;%d;48;5;%dm▀" % (f, b))
            elif f != pf:
                out.append("\x1b[38;5;%dm▀" % f)
            elif b != pb:
                out.append("\x1b[48;5;%dm▀" % b)
            else:
                out.append("▀")
            pf, pb = f, b
        out.append("\x1b[0m\n")
    return "".join(out)


sys.stdout.write("\x1b[?1049h\x1b[2J\x1b[?25l")
frames, start = 0, time.time()
try:
    while True:
        px = binascii.unhexlify(kt.js(GRAB, w, h * 2))
        frames += 1
        fps = frames / max(0.001, time.time() - start)
        sys.stdout.write("\x1b[H" + frame(px) + "%dx%d %.1f fps" % (w, h * 2, fps))
except KeyboardInterrupt:
    pass
finally:
    kt.js("() => { window.ktCam?.v.srcObject.getTracks().forEach((t) => t.stop()); delete window.ktCam; }")
    sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
