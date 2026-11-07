#!/usr/bin/env python3
"""Стенд VirGL без v86: нативный клиент Mesa (GALLIUM_DRIVER=virpipe) -> unix-сокет -> этот мост
-> WebSocket -> страница virgl/harness/index.html с virglrenderer в wasm.

  python3 virgl/harness/bridge.py --sock /tmp/vt.sock --port 8790 [--chrome]
  VTEST_SOCKET_NAME=/tmp/vt.sock LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=virpipe <программа>

Отдаёт файлы проекта по HTTP, страница подключается к /vtest. Журнал страницы (текстовые кадры
"log ...") печатается сюда. --chrome запускает headless Chromium со страницей сам.
"""
import argparse
import asyncio
import base64
import hashlib
import mimetypes
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("text/javascript", ".js")

page = None      # (reader, writer) страницы
client = None    # writer клиента vtest
ready = asyncio.Event()


async def ws_read(reader):
    """следующий кадр WebSocket: (opcode, данные); склеивает продолжения"""
    data, op = b"", None
    while True:
        b0, b1 = await reader.readexactly(2)
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", await reader.readexactly(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", await reader.readexactly(8))[0]
        mask = await reader.readexactly(4) if b1 & 0x80 else None
        chunk = await reader.readexactly(n)
        if mask:
            chunk = bytes(c ^ mask[i & 3] for i, c in enumerate(chunk)) if n < 64 else \
                (int.from_bytes(chunk, "little") ^ int.from_bytes((mask * (n // 4 + 1))[:n], "little")).to_bytes(n, "little")
        if b0 & 0x0F:
            op = b0 & 0x0F
        data += chunk
        if b0 & 0x80:
            return op, data


def ws_frame(op, data):
    n = len(data)
    if n < 126:
        head = struct.pack(">BB", 0x80 | op, n)
    elif n < 65536:
        head = struct.pack(">BBH", 0x80 | op, 126, n)
    else:
        head = struct.pack(">BBQ", 0x80 | op, 127, n)
    return head + data


async def send_page(op, data):
    if page:
        page[1].write(ws_frame(op, data))
        await page[1].drain()


async def serve_page(reader, writer, headers):
    global page
    key = headers.get("sec-websocket-key", "")
    accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
    await writer.drain()
    page = (reader, writer)
    print("страница подключилась", flush=True)
    try:
        while True:
            op, data = await ws_read(reader)
            if op == 8:
                break
            if op == 1:
                text = data.decode(errors="replace")
                if text == "ready":
                    ready.set()
                else:
                    print(text, flush=True)
            elif op == 2 and client:
                client.write(data)
                await client.drain()
    except (asyncio.IncompleteReadError, ConnectionError):
        pass
    print("страница отключилась", flush=True)
    page = None
    ready.clear()


async def http(reader, writer):
    try:
        req = (await reader.readuntil(b"\r\n\r\n")).decode(errors="replace").split("\r\n")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        writer.close()
        return
    method, path, _ = (req[0].split(" ") + ["", ""])[:3]
    headers = {k.strip().lower(): v.strip() for k, _, v in (h.partition(":") for h in req[1:] if h)}
    path = path.split("?")[0]
    if path == "/vtest":
        await serve_page(reader, writer, headers)
        writer.close()
        return
    f = os.path.normpath(os.path.join(ROOT, path.lstrip("/")))
    if method != "GET" or not f.startswith(ROOT) or not os.path.isfile(f):
        writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
    else:
        body = open(f, "rb").read()
        ctype = mimetypes.guess_type(f)[0] or "application/octet-stream"
        writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: {ctype}\r\nContent-Length: {len(body)}\r\n"
                     "Cache-Control: no-store\r\nConnection: close\r\n\r\n".encode() + body)
    await writer.drain()
    writer.close()


async def vtest_client(reader, writer):
    global client
    await ready.wait()
    if client:
        client.close()
    client = writer
    print("клиент vtest подключился", flush=True)
    await send_page(1, b"connect")
    try:
        while data := await reader.read(1 << 20):
            await send_page(2, data)
    except ConnectionError:
        pass
    if client is writer:
        client = None
        await send_page(1, b"disconnect")
    print("клиент vtest отключился", flush=True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sock", default="/tmp/.virgl_test")
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--chrome", action="store_true", help="запустить headless Chromium со страницей")
    ap.add_argument("--debug", action="store_true", help="страница пишет размеры команд и ответов")
    a = ap.parse_args()
    if os.path.exists(a.sock):
        os.unlink(a.sock)
    await asyncio.start_server(http, "127.0.0.1", a.port, limit=1 << 16)
    await asyncio.start_unix_server(vtest_client, a.sock)
    url = f"http://127.0.0.1:{a.port}/virgl/harness/index.html" + ("?debug" if a.debug else "")
    print(f"страница {url}, сокет {a.sock}", flush=True)
    if a.chrome:
        exe = os.environ.get("CHROME") or shutil.which("chromium")
        prof = tempfile.mkdtemp(prefix="virgl-chrome-")
        chrome = subprocess.Popen([exe, "--headless=new", f"--user-data-dir={prof}", "--no-first-run",
                                   "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", url],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    stop = asyncio.Event()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop.set)
    asyncio.get_running_loop().add_signal_handler(signal.SIGINT, stop.set)
    await stop.wait()
    if a.chrome:
        chrome.terminate()
        chrome.wait(10)
        shutil.rmtree(prof, ignore_errors=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
