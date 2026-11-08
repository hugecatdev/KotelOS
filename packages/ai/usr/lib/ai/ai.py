import json
import os
import select
import socket
import sys
import termios
import kt

try:
    from tty import setraw
except ImportError:
    def setraw(fd, when=None):
        termios.setraw(fd)

# ключи ai.* и их умолчания - в /usr/share/kt/cfg/ai, kt.cfg отдаёт их и для незаданных
SETTINGS = sorted((k, v) for k, v in kt.cfg.describe().items() if k.startswith("ai."))
HOME = os.getenv("HOME") or "/root"
LAST = HOME + "/.ai/last.json"
HIST = HOME + "/.ai/history.json"
BASE = "/etc/ai/AGENTS.md"
SKILLS = (".ai/skills", HOME + "/.ai/skills", "/etc/ai/skills")
PROTO = HOME + "/.ai/proto.json"
OUT_MAX = 12000
STEPS = 40
EFFORTS = ["", "none", "minimal", "low", "medium", "high", "xhigh"]
UP = ("\x1b[A", "\x1bOA", "\x10")
DOWN = ("\x1b[B", "\x1bOB", "\x0e")
LEFT = ("\x1b[D", "\x1bOD", "\x02")
RIGHT = ("\x1b[C", "\x1bOC", "\x06")

HELP = """usage: ai [-c] [текст]
       ai -l | -k
  текст  задание; без текста - диалог; ввод из канала добавляется к тексту
  -c     продолжить прошлый разговор
  -l     список моделей
  -k     ввод ключа API

Настройки kt cfg:
%s

Системный промпт: AGENTS.md из текущей папки, без него /etc/ai/AGENTS.md.
Скиллы: <имя>/SKILL.md в ./.ai/skills, ~/.ai/skills, /etc/ai/skills.
Команды диалога: /help""" % "\n".join("  %-10s %s%s" % (k, d, " (по умолчанию %s)" % v if v else "") for k, (v, d) in SETTINGS)

CMDS = """/model    выбор модели и рассуждения
/auto     подтверждение команд и правок: вкл/выкл
/clear    новый разговор
/retry    повтор последнего запроса
/undo     удаление последнего запроса
/compact  сжатие истории в сводку
/ctx      размер контекста
/copy     последний ответ в буфер обмена
/prompt   системный промпт
/skills   скиллы
/key      ввод ключа API
/exit     выход
!команда  выполнение команды, вывод уходит в следующий запрос
Esc       остановка ответа"""
NAMES = [line.split()[0] for line in CMDS.split("\n") if line.startswith("/")] + ["/help"]

COMPACT = """Summarize the conversation so the work can continue: the user's task, what was done, key facts (paths, commands, results, decisions), what remains. Be brief, output only the summary."""

TOOLS = [
    {"type": "function", "function": {
        "name": "sh",
        "description": "Run a command with /bin/sh (busybox ash) in the current directory. Returns the exit code and combined stdout and stderr. No stdin.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "read",
        "description": "Read a text file with line numbers, or list a directory. Read large files in parts.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer", "description": "first line, 1-based"},
            "limit": {"type": "integer", "description": "number of lines, default 300"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write",
        "description": "Create or overwrite a whole file. Missing directories are created.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "edit",
        "description": "Replace old with new in a file. old must occur in the file exactly once, with exact whitespace and line breaks.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}},
            "required": ["path", "old", "new"]}}},
]

FETCH = """async (url, path, body) => {
  url = url.replace(/\\/+$/, "");
  const key = kt.cfg["ai.key"], h = {}, o = { headers: h };
  if (key) h.Authorization = "Bearer " + key;
  if (body) {
    body.model = kt.cfg["ai.model"];
    h["Content-Type"] = "application/json";
    o.method = "POST";
    o.body = JSON.stringify(body);
  }
  let r;
  try { r = await fetch(url + path, o); }
  catch { throw new Error("нет ответа от " + url + " (сеть, CORS или неверный ключ: ai -k)"); }
  const t = await r.text();
  let j = null;
  try { j = JSON.parse(t); } catch {}
  if (!r.ok) {
    const e = j && j.error;
    throw new Error(r.status + " " + ((e && (e.message || JSON.stringify(e))) || t.slice(0, 300) || r.statusText));
  }
  if (!j) throw new Error("ответ не JSON: " + t.slice(0, 200));
  return j;
}"""


def tty(stream):
    try:
        return os.stat("/dev/" + stream)[0] & 0o170000 == 0o020000
    except OSError:
        return False


COLOR = tty("stderr")


def note(s, end="\n"):
    sys.stderr.write(("\x1b[90m%s\x1b[0m" % s if COLOR else s) + end)


def text(b):
    for i in range(4):
        try:
            return b[:len(b) - i].decode()
        except UnicodeError:
            pass
    return "".join(chr(c) if c < 128 else "?" for c in b)


def clip(s, n):
    if len(s) <= n:
        return s
    return s[:n * 2 // 3] + "\n... %d characters skipped ...\n" % (len(s) - n) + s[len(s) - n // 3:]


def path_of(p):
    if p == "~" or p.startswith("~/"):
        p = HOME + p[1:]
    return p if p.startswith("/") else os.getcwd().rstrip("/") + "/" + p


def is_dir(p):
    try:
        return os.stat(p)[0] & 0o170000 == 0o040000
    except OSError:
        return False


def makedirs(p):
    parts = p.split("/")[:-1]
    cur = ""
    for part in parts:
        if not part:
            continue
        cur += "/" + part
        if not is_dir(cur):
            os.mkdir(cur)


def load(p):
    with open(p, "rb") as f:
        return f.read()


def save(p, data):
    makedirs(p)
    with open(p + ".tmp", "wb") as f:
        f.write(data)
    os.rename(p + ".tmp", p)


class Stop(Exception):
    pass


def skills():
    found = {}
    for d in SKILLS:
        base = path_of(d)
        try:
            names = sorted(os.listdir(base))
        except OSError:
            continue
        for n in names:
            f = base + "/" + n + "/SKILL.md"
            try:
                head = text(load(f)[:4096])
            except OSError:
                continue
            meta = {}
            if head.startswith("---"):
                for line in head.split("\n")[1:]:
                    if line.strip() == "---":
                        break
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
            name = meta.get("name") or n
            if name not in found:
                found[name] = (meta.get("description", ""), f)
    return found


def columns():
    tmp = "/tmp/ai-" + kt._rid()
    os.system("stty size > %s 2>/dev/null" % tmp)
    try:
        return max(10, int(text(load(tmp)).split()[1]))
    except (OSError, ValueError, IndexError):
        return 80
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


class Editor:
    def __init__(self):
        try:
            self.hist = json.loads(load(HIST))
        except (OSError, ValueError):
            self.hist = []
        self.names = []
        self.wait = select.poll()
        self.wait.register(sys.stdin, select.POLLIN)

    def key(self):
        inp = getattr(sys.stdin.buffer, "raw", sys.stdin.buffer)
        b = inp.read(1)
        if not b:
            return "\x04"
        c = b[0]
        if c >= 0xc0:
            b += inp.read(1 if c < 0xe0 else 2 if c < 0xf0 else 3)
        elif c == 0x1b and self.wait.poll(50):
            b += inp.read(1)
            if b[1:] in (b"[", b"O"):
                while True:
                    x = inp.read(1)
                    b += x
                    if not x or 0x40 <= x[0] <= 0x7e:
                        break
        return text(b)

    def draw(self):
        w = self.width
        shown = "".join("↵" if ch == "\n" else ch for ch in self.buf)
        total = len(self.prompt) + len(shown)
        cur = len(self.prompt) + self.pos
        out = ("\x1b[%dA" % self.row if self.row else "") + "\r" + self.prompt + shown + "\x1b[J"
        if total and total % w == 0:
            out += " \b"
        up = total // w - cur // w
        if up:
            out += "\x1b[%dA" % up
        out += "\r" + ("\x1b[%dC" % (cur % w) if cur % w else "")
        self.row = cur // w
        sys.stdout.write(out)

    def raw(self):
        old = termios.tcgetattr(0)
        setraw(0, termios.TCSANOW)
        return old

    def quiet(self):
        old = termios.tcgetattr(0)
        new = old[:6] + [old[6][:]]
        new[3] &= ~(getattr(termios, "ICANON", 2) | getattr(termios, "ECHO", 8))
        new[6][getattr(termios, "VMIN", 6)], new[6][getattr(termios, "VTIME", 5)] = 1, 0
        termios.tcsetattr(0, termios.TCSANOW, new)
        return old

    def pick(self, models, model, effort):
        w = columns()
        rows = max(1, min(8, len(models)))
        q, sel, top = "", models.index(model) if model in models else 0, 0
        e = EFFORTS.index(effort) if effort in EFFORTS else 0
        res = None
        old = self.raw()
        sys.stdout.write("\r\n" * (rows + 1) + "\x1b[%dA" % (rows + 1))
        try:
            while True:
                found = [m for m in models if q.lower() in m.lower()]
                sel = max(0, min(sel, len(found) - 1))
                if sel < top:
                    top = sel
                if sel >= top + rows:
                    top = sel - rows + 1
                lines = ["модель: " + q]
                for i in range(top, top + rows):
                    m = found[i] if i < len(found) else ""
                    lines.append(("> " if i == sel else "  ") + m + (" *" if m == model else "") if m else "")
                lines.append("рассуждение: < %s >" % (EFFORTS[e] or "по умолчанию"))
                col = min(len(lines[0]), w - 1)
                sys.stdout.write("\r" + "\r\n".join(line[:w - 1] + "\x1b[K" for line in lines) +
                                 "\x1b[%dA\r" % (rows + 1) + ("\x1b[%dC" % col if col else ""))
                k = self.key()
                if k in ("\r", "\n"):
                    name = found[sel] if found else q.strip()
                    if name:
                        res = (name, EFFORTS[e])
                    break
                if k in ("\x1b", "\x03", "\x04"):
                    break
                if k in UP:
                    sel -= 1
                elif k in DOWN:
                    sel += 1
                elif k in LEFT:
                    e = (e - 1) % len(EFFORTS)
                elif k in RIGHT:
                    e = (e + 1) % len(EFFORTS)
                elif k in ("\x7f", "\x08"):
                    q, sel, top = q[:-1], 0, 0
                elif k[0] >= " ":
                    q, sel, top = q + k, 0, 0
        finally:
            sys.stdout.write("\r\x1b[J")
            termios.tcsetattr(0, termios.TCSANOW, old)
        return res

    def read(self, prompt):
        self.prompt, self.buf, self.pos, self.row = prompt, [], 0, 0
        self.width = columns()
        hi, draft, paste = len(self.hist), [], False
        old = self.raw()
        sys.stdout.write("\x1b[?2004h")
        try:
            self.draw()
            while True:
                k = self.key()
                buf, pos = self.buf, self.pos
                if paste:
                    if k == "\x1b[201~":
                        paste = False
                    elif k in ("\r", "\n", "\t") or k[0] >= " ":
                        ch = "\n" if k == "\r" else "  " if k == "\t" else k
                        self.buf = buf[:pos] + list(ch) + buf[pos:]
                        self.pos += len(ch)
                elif k == "\x1b[200~":
                    paste = True
                elif k in ("\r", "\n"):
                    self.pos = len(buf)
                    self.draw()
                    sys.stdout.write("\r\n")
                    line = "".join(buf)
                    if line.strip() and (not self.hist or self.hist[-1] != line):
                        self.hist = (self.hist + [line])[-200:]
                        try:
                            save(HIST, json.dumps(self.hist).encode())
                        except OSError:
                            pass
                    return line
                elif k == "\x03":
                    self.pos = len(buf)
                    self.draw()
                    sys.stdout.write("^C\r\n")
                    raise KeyboardInterrupt
                elif k == "\x04":
                    if not buf:
                        sys.stdout.write("\r\n")
                        raise EOFError
                    self.buf = buf[:pos] + buf[pos + 1:]
                elif k in ("\x7f", "\x08"):
                    if pos:
                        self.buf = buf[:pos - 1] + buf[pos:]
                        self.pos -= 1
                elif k == "\x1b[3~":
                    self.buf = buf[:pos] + buf[pos + 1:]
                elif k in ("\x1b[D", "\x1bOD", "\x02"):
                    self.pos = max(0, pos - 1)
                elif k in ("\x1b[C", "\x1bOC", "\x06"):
                    self.pos = min(len(buf), pos + 1)
                elif k in ("\x1b[H", "\x1bOH", "\x1b[1~", "\x01"):
                    self.pos = 0
                elif k in ("\x1b[F", "\x1bOF", "\x1b[4~", "\x05"):
                    self.pos = len(buf)
                elif k == "\x15":
                    self.buf, self.pos = buf[pos:], 0
                elif k == "\x0b":
                    self.buf = buf[:pos]
                elif k == "\x17":
                    i = pos
                    while i and buf[i - 1] == " ":
                        i -= 1
                    while i and buf[i - 1] != " ":
                        i -= 1
                    self.buf, self.pos = buf[:i] + buf[pos:], i
                elif k in ("\x1b[A", "\x1bOA", "\x10", "\x1b[B", "\x1bOB", "\x0e"):
                    step = -1 if k in ("\x1b[A", "\x1bOA", "\x10") else 1
                    if 0 <= hi + step <= len(self.hist):
                        if hi == len(self.hist):
                            draft = buf
                        hi += step
                        self.buf = list(self.hist[hi]) if hi < len(self.hist) else draft
                        self.pos = len(self.buf)
                elif k == "\t":
                    line = "".join(buf)
                    if line.startswith("/") and " " not in line and pos == len(buf):
                        found = [n for n in self.names if n.startswith(line)]
                        if found:
                            common = found[0]
                            for n in found[1:]:
                                while not n.startswith(common):
                                    common = common[:-1]
                            self.buf = list(common + (" " if len(found) == 1 else ""))
                            self.pos = len(self.buf)
                    else:
                        self.buf = buf[:pos] + [" ", " "] + buf[pos:]
                        self.pos += 2
                elif k[0] >= " " and k[0] != "\x7f":
                    self.buf = buf[:pos] + list(k) + buf[pos:]
                    self.pos += len(k)
                self.draw()
        finally:
            sys.stdout.write("\x1b[?2004l")
            termios.tcsetattr(0, termios.TCSANOW, old)


class Agent:
    def __init__(self):
        self.ask_tty = None
        self.ed = None
        self.pending = []
        c = kt.cfg()
        self.yes = c.get("ai.auto") != "off"
        self.url = c.get("ai.url") or ""
        self.model, self.effort = c.get("ai.model", ""), c.get("ai.effort", "")
        try:
            self.limit = max(4, int(c.get("ai.ctx") or 32)) * 1000
        except ValueError:
            self.limit = 32000
        api = c.get("ai.api", "")
        self.fixed = api in ("chat", "responses")
        try:
            self.protos = json.loads(load(PROTO))
        except (OSError, ValueError):
            self.protos = {}
        self.mode = api if self.fixed else self.protos.get(self.url, "chat")
        self.names = None
        self.msgs = [self.system()]
        self.base = (0, 0)

    def system(self):
        self.source = path_of("AGENTS.md")
        try:
            s = text(load(self.source))
        except OSError:
            self.source = BASE
            try:
                s = text(load(BASE))
            except OSError:
                s = ""
        s = (clip(s.strip(), 8000) + "\n\nCurrent directory: %s." % os.getcwd()).strip()
        found = skills()
        if found:
            s += "\n\nSkills: before a matching task, read its SKILL.md with the read tool.\n" + "\n".join(
                "- %s: %s (%s)" % (n, found[n][0], found[n][1]) for n in sorted(found))
        return {"role": "system", "content": s}

    def api(self, path, body=None):
        try:
            r = self.page("(%s)(%s)" % (FETCH, ", ".join(json.dumps(a) for a in (self.url, path, body))))
        except OSError as e:
            raise Stop(str(e))
        out = r[1:].decode().strip()
        if r[:1] != b"0":
            raise Stop(out[7:] if out.startswith("Error: ") else out)
        return json.loads(out) if out else None

    # как kt.js, но Esc с клавиатуры прерывает ожидание: ответа ждёт, пока соединение живо, а сменился
    # агент (машину восстановили) - ещё kt.WAIT секунд, по соединению или файлом от агента
    def page(self, code):
        s = socket.socket()
        old = None
        rid = kt._rid()
        try:
            s.settimeout(kt.WAIT)
            try:
                s.connect(socket.getaddrinfo(kt.PAGE[0], kt.PAGE[1])[0][-1])
                data = ("jsjson %s 0 %s\n" % (rid, kt._b64(code))).encode()
                if hasattr(s, "sendall"):
                    s.sendall(data)
                else:
                    s.write(data)
            except OSError:
                raise OSError("нет связи с браузером")
            wait = select.poll()
            wait.register(s.fileno(), select.POLLIN)
            if self.ed:
                old = self.ed.quiet()
                wait.register(0, select.POLLIN)
            out = []
            agent, lost = kt._agent(), None
            while True:
                got = wait.poll(1000)
                if not got:
                    if lost is None and kt._agent() != agent:
                        lost = kt._ms()
                    if lost is not None:
                        r = kt._take("%s/reply.%s" % (kt.RUN, rid))
                        if r is not None:
                            return r
                        if kt._diff(kt._ms(), lost) > kt.WAIT * 1000:
                            raise OSError("браузер не ответил")
                    continue
                for e in got:
                    if e[0] == 0 and e[1] & (select.POLLHUP | select.POLLERR):
                        wait.unregister(0)
                    elif e[0] == 0 and self.ed.key() == "\x1b":
                        raise KeyboardInterrupt
                if any(e[0] != 0 for e in got):
                    b = s.recv(65536)
                    if not b:
                        return b"".join(out)
                    out.append(b)
        finally:
            if old:
                termios.tcsetattr(0, termios.TCSANOW, old)
            s.close()

    def chat(self, msgs, tools=True):
        if not self.model:
            raise Stop("не задана модель: /model или kt cfg ai.model <имя>")
        if COLOR:
            note("...", "\r")
        try:
            try:
                return self.request(msgs, tools)
            except Stop as e:
                mode = self.other(str(e))
                if not mode:
                    raise
                self.mode = self.protos[self.url] = mode
                try:
                    save(PROTO, json.dumps(self.protos).encode())
                except OSError:
                    pass
                return self.request(msgs, tools)
        finally:
            if COLOR:
                sys.stderr.write("\r\x1b[K")

    def other(self, err):
        if self.fixed:
            return None
        if self.mode == "chat" and "/responses" in err:
            return "responses"
        if self.mode == "responses" and err[:4] in ("404 ", "405 "):
            return "chat"
        return None

    def request(self, msgs, tools):
        if self.mode == "responses":
            return self.responses(msgs, tools)
        body = {"messages": msgs}
        if tools:
            body["tools"] = TOOLS
        if self.effort:
            body["reasoning_effort"] = self.effort
        j = self.api("/chat/completions", body)
        ch = (j.get("choices") or [None])[0]
        if not ch or not ch.get("message"):
            raise Stop("пустой ответ: " + json.dumps(j)[:200])
        return ch, (j.get("usage") or {}).get("total_tokens") or 0

    def responses(self, msgs, tools):
        items = []
        for m in msgs[1:]:
            if m["role"] == "tool":
                items.append({"type": "function_call_output", "call_id": m["tool_call_id"], "output": m["content"]})
                continue
            if m.get("content"):
                items.append({"role": m["role"], "content": m["content"]})
            for c in m.get("tool_calls") or []:
                items.append({"type": "function_call", "call_id": c["id"], "name": c["function"]["name"],
                              "arguments": c["function"]["arguments"]})
        body = {"instructions": msgs[0]["content"], "input": items, "store": False}
        if tools:
            body["tools"] = [{"type": "function", "name": t["function"]["name"], "description": t["function"]["description"],
                              "parameters": t["function"]["parameters"]} for t in TOOLS]
        if self.effort:
            body["reasoning"] = {"effort": self.effort}
        j = self.api("/responses", body)
        if j.get("error"):
            raise Stop(j["error"].get("message") or json.dumps(j["error"]))
        say, calls = [], []
        for it in j.get("output") or []:
            if it.get("type") == "message":
                for c in it.get("content") or []:
                    say.append(c.get("text") or c.get("refusal") or "")
            elif it.get("type") == "function_call":
                calls.append({"id": it.get("call_id") or it.get("id"),
                              "function": {"name": it.get("name"), "arguments": it.get("arguments") or "{}"}})
        msg = {"content": "".join(say) or None}
        if calls:
            msg["tool_calls"] = calls
        ch = {"message": msg, "finish_reason": "length" if j.get("status") == "incomplete" else "stop"}
        return ch, (j.get("usage") or {}).get("total_tokens") or 0

    def models(self):
        if self.names is None:
            j = self.api("/models")
            self.names = sorted(m["id"] for m in j.get("data") or [] if m.get("id"))
        return self.names

    def title(self):
        return (self.model or "модель не задана") + (" (%s)" % self.effort if self.effort else "")

    def size(self):
        n = len(json.dumps(self.msgs))
        return self.base[0] + (n - self.base[1]) // 3 if self.base[0] else n // 3

    def repair(self):
        out = []
        i = 0
        while i < len(self.msgs):
            m = self.msgs[i]
            i += 1
            if m["role"] == "tool":
                continue
            out.append(m)
            if m.get("tool_calls"):
                got = {}
                while i < len(self.msgs) and self.msgs[i]["role"] == "tool":
                    got[self.msgs[i].get("tool_call_id")] = self.msgs[i]
                    i += 1
                for c in m["tool_calls"]:
                    out.append(got.get(c["id"]) or {"role": "tool", "tool_call_id": c["id"], "content": "cancelled"})
        self.msgs = out

    def transcript(self):
        out = []
        for m in self.msgs[1:]:
            r = m["role"]
            if r == "user":
                out.append("User: " + clip(m["content"], 4000))
            elif r == "assistant":
                if m.get("content"):
                    out.append("Assistant: " + clip(m["content"], 4000))
                for c in m.get("tool_calls") or []:
                    out.append("Call %s: %s" % (c["function"]["name"], clip(c["function"]["arguments"], 2000)))
            elif r == "tool":
                out.append("Result: " + clip(m["content"], 2000))
        return "\n\n".join(out)

    def compact(self, going=False):
        if len(self.msgs) < 3:
            return
        before = self.size()
        ch, _ = self.chat([{"role": "system", "content": COMPACT},
                           {"role": "user", "content": self.transcript()}], tools=False)
        summary = (ch["message"].get("content") or "").strip()
        if not summary:
            raise Stop("модель не вернула сводку")
        self.msgs = [self.system(), {"role": "user", "content": "Summary of the conversation so far:\n" + summary +
                                     ("\n\nContinue the task." if going else "")}]
        self.base = (0, 0)
        note("контекст сжат: %dk -> %dk" % (before // 1000, self.size() // 1000))

    def turn(self, prompt):
        if self.pending:
            prompt = "\n\n".join(self.pending + [prompt])
            self.pending = []
        self.msgs.append({"role": "user", "content": prompt})
        for step in range(STEPS):
            self.repair()
            if self.size() > self.limit:
                note("контекст %dk из %dk, сжимаю" % (self.size() // 1000, self.limit // 1000))
                self.compact(True)
            ch, tokens = self.chat(self.msgs)
            m = ch["message"]
            msg = {"role": "assistant", "content": m.get("content")}
            calls = m.get("tool_calls") or []
            if calls:
                msg["tool_calls"] = [{"id": c.get("id") or "call%d_%d" % (step, i), "type": "function",
                                      "function": {"name": c["function"]["name"], "arguments": c["function"].get("arguments") or "{}"}}
                                     for i, c in enumerate(calls)]
            self.msgs.append(msg)
            if tokens:
                self.base = (tokens, len(json.dumps(self.msgs)))
            say = (m.get("content") or m.get("refusal") or "").strip()
            if say:
                print(say)
            if ch.get("finish_reason") == "length":
                note("ответ обрезан по длине")
            if not calls:
                return
            stop = False
            for c in msg["tool_calls"]:
                if stop:
                    res = "cancelled"
                else:
                    res, stop = self.tool(c["function"]["name"], c["function"]["arguments"])
                self.msgs.append({"role": "tool", "tool_call_id": c["id"], "content": res})
            if stop:
                return
        note("остановлено после %d шагов" % STEPS)

    def confirm(self):
        if self.yes:
            return True
        if self.ask_tty is None:
            try:
                self.ask_tty = open("/dev/tty")
            except OSError:
                try:
                    self.ask_tty = open(os.ttyname(2))
                except Exception:
                    raise Stop("нет терминала для подтверждения (kt cfg ai.auto on)")
        sys.stderr.write("выполнить? [y/n/a] ")
        try:
            a = self.ask_tty.readline().strip().lower()
        except KeyboardInterrupt:
            sys.stderr.write("\n")
            a = "n"
        if a in ("a", "ф"):
            self.yes = True
            return True
        return a in ("y", "д", "н", "yes", "да")

    def tool(self, name, raw):
        try:
            a = json.loads(raw)
        except ValueError:
            return "error: arguments are not JSON", False
        try:
            if name == "sh":
                return self.t_sh(a["command"])
            if name == "read":
                return self.t_read(a), False
            if name == "write":
                return self.t_write(a)
            if name == "edit":
                return self.t_edit(a)
            return "error: no tool " + name, False
        except KeyError as e:
            return "error: missing argument %s" % e, False
        except (OSError, ValueError, TypeError) as e:
            return "error: %s" % e, False

    def denied(self):
        return "denied by user", True

    def shell(self, cmd, live=False):
        tmp = "/tmp/ai-" + kt._rid()
        os.putenv("AI_CMD", cmd + "\nai_s=$?\npwd > %s.cwd\nexit $ai_s" % tmp)
        if live:
            os.system('{ sh -c "$AI_CMD"; echo $? > %s.st; } 2>&1 | tee %s.out' % (tmp, tmp))
            try:
                code = int(text(load(tmp + ".st")).strip())
                os.remove(tmp + ".st")
            except (OSError, ValueError):
                code = 130
        else:
            st = os.system('sh -c "$AI_CMD" > %s.out 2>&1 < /dev/null' % tmp)
            code = st & 0x7f and 128 + (st & 0x7f) or st >> 8 & 0xff
        os.unsetenv("AI_CMD")
        try:
            out = load(tmp + ".out")
            os.remove(tmp + ".out")
        except OSError:
            out = b""
        try:
            cwd = text(load(tmp + ".cwd")).strip()
            os.remove(tmp + ".cwd")
        except OSError:
            cwd = ""
        res = clip(text(out), OUT_MAX).rstrip("\n")
        if code:
            note(("  " if not live else "") + "код %d" % code)
        moved = ""
        if cwd and cwd != os.getcwd():
            try:
                os.chdir(cwd)
                moved = "\n(cwd: %s)" % cwd
            except OSError:
                pass
        return code, res, moved

    def t_sh(self, cmd):
        note("$ " + "\n  ".join(cmd.strip().split("\n")))
        if not self.confirm():
            return self.denied()
        code, res, moved = self.shell(cmd)
        shown = res.split("\n") if res else []
        for line in shown[:6]:
            note("  " + line[:200])
        if len(shown) > 6:
            note("  ... ещё %d строк" % (len(shown) - 6))
        if code == 130:
            return "exit 130, interrupted by user\n" + res, True
        return "exit %d\n%s%s" % (code, res, moved), False

    def bang(self, cmd):
        if not cmd:
            return
        code, res, moved = self.shell(cmd, True)
        self.pending.append("I ran a command:\n$ %s\nexit %d\n%s%s" % (cmd, code, res, moved))

    def last_user(self):
        for i in range(len(self.msgs) - 1, 0, -1):
            if self.msgs[i]["role"] == "user":
                return i
        return None

    def t_read(self, a):
        p = path_of(a["path"])
        note("read " + a["path"])
        if is_dir(p):
            names = sorted(os.listdir(p))
            return "\n".join(n + "/" if is_dir(p.rstrip("/") + "/" + n) else n for n in names) or "(empty)"
        data = load(p)
        if b"\0" in data[:4096]:
            return "binary file, %d bytes" % len(data)
        lines = text(data).split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        first = max(1, int(a.get("offset") or 1))
        count = max(1, int(a.get("limit") or 300))
        part = lines[first - 1:first - 1 + count]
        out = "\n".join("%d\t%s" % (first + i, line if len(line) <= 500 else line[:500] + "...") for i, line in enumerate(part))
        if first - 1 + count < len(lines) or first > 1:
            out += "\n(lines %d-%d of %d)" % (first, first + len(part) - 1, len(lines))
        return clip(out, OUT_MAX) or "(empty file)"

    def t_write(self, a):
        p = path_of(a["path"])
        data = a["content"].encode()
        try:
            os.stat(p)
            what = "перезапись"
        except OSError:
            what = "новый файл"
        note("write %s (%s, %d байт)" % (a["path"], what, len(data)))
        if not self.confirm():
            return self.denied()
        save(p, data)
        return "wrote %d bytes" % len(data), False

    def t_edit(self, a):
        p = path_of(a["path"])
        old, new = a["old"], a["new"]
        src = text(load(p))
        n = src.count(old) if old else 0
        if n != 1:
            note("edit %s: фрагмент найден %d раз" % (a["path"], n))
            return ("error: old text not found" if not n else "error: old text occurs %d times, add context" % n), False
        note("edit " + a["path"])
        for sign, part in (("-", old), ("+", new)):
            rows = part.split("\n")
            for line in rows[:8]:
                note("  %s %s" % (sign, line[:200]))
            if len(rows) > 8:
                note("  %s ... ещё %d строк" % (sign, len(rows) - 8))
        if not self.confirm():
            return self.denied()
        save(p, src.replace(old, new).encode())
        return "replaced", False

    def store(self):
        try:
            save(LAST, json.dumps(self.msgs).encode())
        except OSError:
            pass

    def restore(self):
        try:
            msgs = json.loads(load(LAST))
        except (OSError, ValueError):
            return False
        self.msgs = [self.system()] + msgs[1:]
        self.repair()
        return True

    def command(self, line, ed):
        c = line.split()[0]
        if c in ("/exit", "/quit"):
            raise EOFError
        if c == "/model":
            model, effort = self.model, self.effort
            args = line.split()[1:]
            for a in args:
                if a in EFFORTS or a == "default":
                    effort = "" if a == "default" else a
                else:
                    model = a
            if not args:
                try:
                    names = self.models()
                except Stop as e:
                    note(str(e))
                    names = []
                got = ed.pick(names, model, effort)
                if not got:
                    return
                model, effort = got
            kt.js("(m, e) => { kt.cfg['ai.model'] = m; kt.cfg['ai.effort'] = e }", model, effort)
            self.model, self.effort = model, effort
            note(self.title())
            return
        i = self.last_user()
        if c == "/auto":
            self.yes = not self.yes
            kt.cfg["ai.auto"] = "on" if self.yes else "off"
            note("команды и правки " + ("без подтверждения" if self.yes else "с подтверждением"))
        elif c == "/clear":
            self.msgs = [self.system()]
            self.base = (0, 0)
            self.pending = []
            self.store()
            note("новый разговор")
        elif c in ("/retry", "/undo"):
            if i is None:
                note("запросов ещё нет")
                return
            prompt = self.msgs[i]["content"]
            self.msgs = self.msgs[:i]
            self.base = (0, 0)
            self.store()
            if c == "/retry":
                self.run(prompt)
            else:
                note("последний запрос удалён")
        elif c == "/compact":
            self.compact()
            self.store()
        elif c == "/ctx":
            note("контекст ~%dk из %dk токенов, сообщений %d" % (self.size() // 1000, self.limit // 1000, len(self.msgs) - 1))
        elif c == "/copy":
            for m in reversed(self.msgs):
                if m["role"] == "assistant" and m.get("content"):
                    try:
                        kt.copy(m["content"])
                        note("скопировано")
                    except kt.Error as e:
                        note(str(e))
                    break
            else:
                note("ответов ещё нет")
        elif c == "/prompt":
            note(self.source)
            print(self.msgs[0]["content"])
        elif c == "/key":
            set_key()
        elif c == "/skills":
            found = skills()
            for n in sorted(found):
                print("%s  %s" % (n, found[n][0]))
                note("  " + found[n][1])
            if not found:
                note("скиллов нет: ./.ai/skills, ~/.ai/skills, /etc/ai/skills")
        elif c == "/help":
            print(CMDS)
        else:
            note("нет команды %s (/help)" % c)

    def run(self, prompt):
        try:
            self.turn(prompt)
        except KeyboardInterrupt:
            note("\nпрервано")
        except Stop as e:
            print("ai: " + str(e), file=sys.stderr)
            self.store()
            return False
        self.store()
        return True

    def repl(self):
        note(self.title())
        ed = self.ed = Editor()
        ed.names = NAMES
        while True:
            try:
                line = ed.read("> ").strip()
            except KeyboardInterrupt:
                continue
            except EOFError:
                return
            if not line:
                continue
            if line.startswith("/"):
                try:
                    self.command(line, ed)
                except Stop as e:
                    print("ai: " + str(e), file=sys.stderr)
                except KeyboardInterrupt:
                    note("\nпрервано")
                except EOFError:
                    return
                continue
            if line.startswith("!"):
                try:
                    self.bang(line[1:].strip())
                except KeyboardInterrupt:
                    note("\nпрервано")
                continue
            self.run(line)


def set_key():
    hide = tty("stdin")
    if hide:
        os.system("stty -echo")
    try:
        sys.stderr.write("ключ API: ")
        v = sys.stdin.readline().strip()
    finally:
        if hide:
            os.system("stty echo")
            sys.stderr.write("\n")
    kt.js("(v) => { kt.cfg['ai.key'] = v }", v)
    print("ключ сохранён в браузере" if v else "ключ удалён")


def models(agent):
    for i in agent.models():
        print(("* " if i == agent.model else "  ") + i)


def main():
    args = sys.argv[1:]
    flags = []
    while args and args[0].startswith("-") and len(args[0]) > 1:
        flags += list(args.pop(0)[1:])
    if "h" in flags or "-" in flags:
        print(HELP)
        return 0
    if "k" in flags:
        set_key()
        return 0
    agent = Agent()
    if "l" in flags:
        models(agent)
        return 0
    prompt = " ".join(args)
    if not tty("stdin"):
        piped = text(sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode()).strip()
        if piped:
            prompt = (prompt + "\n\n" + piped).strip()
    if "c" in flags and not agent.restore():
        note("прошлого разговора нет")
    if prompt:
        return 0 if agent.run(prompt) else 1
    if not tty("stdin"):
        print(HELP, file=sys.stderr)
        return 1
    agent.repl()
    return 0


try:
    sys.exit(main())
except kt.Error as e:
    print("ai: " + str(e), file=sys.stderr)
    sys.exit(1)
except Stop as e:
    print("ai: " + str(e), file=sys.stderr)
    sys.exit(1)
except OSError as e:
    print("ai: %s" % e, file=sys.stderr)
    sys.exit(1)
except KeyboardInterrupt:
    sys.exit(130)
