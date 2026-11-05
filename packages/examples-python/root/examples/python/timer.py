import sys
import time
import kt

FONT = {
    "0": ["███", "█ █", "█ █", "█ █", "███"],
    "1": [" █ ", "██ ", " █ ", " █ ", "███"],
    "2": ["███", "  █", "███", "█  ", "███"],
    "3": ["███", "  █", "███", "  █", "███"],
    "4": ["█ █", "█ █", "███", "  █", "  █"],
    "5": ["███", "█  ", "███", "  █", "███"],
    "6": ["███", "█  ", "███", "█ █", "███"],
    "7": ["███", "  █", "  █", "  █", "  █"],
    "8": ["███", "█ █", "███", "█ █", "███"],
    "9": ["███", "█ █", "███", "  █", "███"],
    ":": ["   ", " █ ", "   ", " █ ", "   "],
}


def seconds(s):
    if ":" in s:
        m, sec = s.split(":")
        return int(m) * 60 + int(sec)
    unit = {"s": 1, "m": 60, "h": 3600}.get(s[-1:])
    return int(s[:-1]) * unit if unit else int(s) * 60


def clock(left):
    if left >= 3600:
        return "%d:%02d:%02d" % (left // 3600, left // 60 % 60, left % 60)
    return "%02d:%02d" % (left // 60, left % 60)


try:
    total = seconds(sys.argv[1]) if len(sys.argv) > 1 else 60
except ValueError:
    print("usage: timer.py [25m|90s|1h|5:00] [текст]", file=sys.stderr)
    sys.exit(1)
text = " ".join(sys.argv[2:])
title = kt.js("() => document.title")
end = time.time() + total
try:
    while True:
        left = max(0, int(end - time.time() + 0.99))
        for row in range(5):
            print(" ".join(FONT[ch][row] for ch in clock(left)) + "\x1b[K")
        kt.js("(t) => { document.title = t }", (clock(left) + " " + text).strip())
        if not left:
            break
        time.sleep(1)
        sys.stdout.write("\x1b[5A")
    print("\a" + (text or "время вышло"))
except KeyboardInterrupt:
    pass
finally:
    kt.js("(t) => { document.title = t }", title)
