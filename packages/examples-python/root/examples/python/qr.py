import os
import sys
import kt

text = " ".join(sys.argv[1:])
if not text and os.stat("/dev/stdin")[0] & 0o170000 != 0o020000:
    text = sys.stdin.read().strip()
if not text:
    print("usage: qr.py <текст> | echo текст | qr.py", file=sys.stderr)
    sys.exit(1)

try:
    r = kt.js("""async (text) => {
  const QR = (await import("https://esm.sh/qrcode@1.5.4")).default;
  const m = QR.create(text, { errorCorrectionLevel: "M" }).modules;
  return { size: m.size, bits: Array.from(m.data, (b) => (b ? "1" : "0")).join("") };
}""", text, timeout=60)
except kt.JSError as e:
    print("qr: " + str(e).split(": ", 1)[-1], file=sys.stderr)
    sys.exit(1)

size, bits = r["size"], r["bits"]


def dark(x, y):
    return 0 <= x < size and 0 <= y < size and bits[y * size + x] == "1"


BLACK, WHITE = "\x1b[48;2;0;0;0m ", "\x1b[48;2;255;255;255m "
HALF = "\x1b[38;2;0;0;0;48;2;255;255;255m"
for y in range(-2, size + 2, 2):
    row = []
    for x in range(-2, size + 2):
        t, b = dark(x, y), dark(x, y + 1)
        row.append((BLACK if t else WHITE) if t == b else HALF + ("▀" if t else "▄"))
    print("".join(row) + "\x1b[0m")
