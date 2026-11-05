import os
import sys
import kt

text = " ".join(sys.argv[1:])
if not text and os.stat("/dev/stdin")[0] & 0o170000 != 0o020000:
    text = sys.stdin.read().strip()
if not text:
    print("usage: speak.py <текст> | echo текст | speak.py", file=sys.stderr)
    sys.exit(1)

lang = "ru-RU" if any("А" <= c <= "я" or c in "ёЁ" for c in text) else "en-US"
try:
    kt.js("""(text, lang) => new Promise((ok, err) => {
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang;
  u.onend = () => ok();
  u.onerror = (e) => err(new Error(e.error));
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
})""", text, lang, timeout=600)
except kt.JSError as e:
    print("speak: " + str(e).split(": ", 1)[-1], file=sys.stderr)
    sys.exit(1)
