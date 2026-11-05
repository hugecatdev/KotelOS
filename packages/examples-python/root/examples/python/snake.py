import os
import random
import select
import sys
import termios
import time

try:
    from tty import setraw
except ImportError:
    from termios import setraw

os.system("stty size > /tmp/.kt-size")
with open("/tmp/.kt-size") as f:
    rows, cols = [int(x) for x in f.read().split()]
h, w = min(rows - 2, 22), min(cols // 2, 30)
keys = {b"A": (-1, 0), b"B": (1, 0), b"D": (0, -1), b"C": (0, 1),
        b"w": (-1, 0), b"s": (1, 0), b"a": (0, -1), b"d": (0, 1)}
stdin = sys.stdin.buffer
poll = select.poll()
poll.register(sys.stdin, select.POLLIN)

HEAD, FOOD, EMPTY = "\x1b[38;5;118m██", "\x1b[38;5;203m██", "  "
BODY = ["\x1b[38;5;34m██", "\x1b[38;5;28m██"]


def cell(y, x, s):
    sys.stdout.write("\x1b[%d;%dH%s\x1b[0m" % (y + 2, x * 2 + 2, s))


def frame():
    out = ["\x1b[2;1H┌" + "─" * (w * 2) + "┐"]
    for y in range(h):
        out.append("\x1b[%d;1H│\x1b[%dC│" % (y + 3, w * 2))
    out.append("\x1b[%d;1H└%s┘" % (h + 3, "─" * (w * 2)))
    sys.stdout.write("".join(out))


def status(score, text=""):
    sys.stdout.write("\x1b[1;1H\x1b[2Ksnake %d %s" % (score, text))


def key():
    if not poll.poll(0):
        return None
    c = stdin.read(1)
    if c == b"\x1b":
        if not poll.poll(30):
            return b"q"
        stdin.read(1)
        c = stdin.read(1)
    return c


def place(snake):
    while True:
        p = (random.randint(0, h - 1), random.randint(0, w - 1))
        if p not in snake:
            return p


old = termios.tcgetattr(0)
setraw(0)
sys.stdout.write("\x1b[?1049h\x1b[2J\x1b[?25l")
frame()
snake = [(h // 2, w // 2 + i) for i in range(3)]
for i, p in enumerate(snake):
    cell(p[0] + 1, p[1], HEAD if i == 0 else BODY[i % 2])
step, score, over, moves = (0, -1), 0, False, 0
food = place(snake)
cell(food[0] + 1, food[1], FOOD)
status(score)
try:
    while True:
        k = key()
        if k in (b"q", b"\x03"):
            break
        if k in keys and keys[k] != (-step[0], -step[1]):
            step = keys[k]
        head = (snake[0][0] + step[0], snake[0][1] + step[1])
        if head in snake or not (0 <= head[0] < h and 0 <= head[1] < w):
            over = True
            break
        moves += 1
        cell(snake[0][0] + 1, snake[0][1], BODY[moves % 2])
        snake.insert(0, head)
        cell(head[0] + 1, head[1], HEAD)
        if head == food:
            score += 1
            food = place(snake)
            cell(food[0] + 1, food[1], FOOD)
            status(score)
        else:
            tail = snake.pop()
            cell(tail[0] + 1, tail[1], EMPTY)
        sys.stdout.flush()
        time.sleep(max(0.06, 0.16 - score * 0.005))
    if over:
        status(score, "игра окончена")
        sys.stdout.flush()
        while not key():
            time.sleep(0.05)
finally:
    termios.tcsetattr(0, termios.TCSANOW, old)
    sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
print("счёт: %d" % score)
