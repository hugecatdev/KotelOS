import binascii
import sys
import kt

TYPES = {b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg", b"GIF8": "image/gif", b"RIFF": "image/webp", b"BM": "image/bmp"}

if len(sys.argv) < 2:
    print("usage: show.py <png|jpg|gif|bmp|svg>", file=sys.stderr)
    sys.exit(1)

with open(sys.argv[1], "rb") as f:
    data = f.read()

mime = "image/svg+xml"
for magic, m in TYPES.items():
    if data.startswith(magic):
        mime = m

url = "data:%s;base64,%s" % (mime, binascii.b2a_base64(data).decode().replace("\n", ""))
kt.js("""
document.getElementById("show")?.remove();
const d = document.createElement("div");
d.id = "show";
d.style.cssText = "position:fixed;inset:24px;z-index:9;display:grid;place-items:center;background:#000c;cursor:pointer";
d.innerHTML = '<img style="max-width:100%%;max-height:100%%;image-rendering:pixelated">';
d.firstChild.src = %s;
d.onclick = () => d.remove();
document.body.append(d);
""" % kt.q(url))
