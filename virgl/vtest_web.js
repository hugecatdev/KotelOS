// Связка сервера vtest (vtest_web.c) со страницей (подключается через --pre-js после vgl.js).
//
//   const v = await createVirgl();
//   v.start(canvas, (bytes) => ws.send(bytes));   // WebGL2 на холсте, ответы - в колбэк
//   v.connect();                                    // новый клиент
//   v.feed(bytes);                                  // команды клиента; ответы приходят сами
//
// Ответы сервер пишет в /dev/vtest (устройство Emscripten FS). Ожидание GPU не блокирует:
// vtw_run() возвращает 1, и разбор продолжается после возврата в цикл событий - только тогда
// WebGL2 отдаёт готовность заборов.

Module.preRun = [].concat(Module.preRun || [], () => {
  const dev = FS.makedev(64, 0);
  FS.registerDevice(dev, {
    open() {},
    close() {},
    read() { return 0; },
    write(stream, buf, off, len) {
      if (Module.onVtestOut) Module.onVtestOut(buf.slice(off, off + len));
      return len;
    },
  });
  FS.mkdev("/dev/vtest", dev);
});

Module.start = function (canvas, onOut) {
  const gl = canvas.getContext("webgl2", {
    alpha: false, depth: false, stencil: false, antialias: false,
    premultipliedAlpha: false, preserveDrawingBuffer: false,
    powerPreference: "high-performance",
  });
  if (!gl) throw new Error("нет WebGL2");
  Module.vgl = Module.createVGL(gl);
  const handle = GL.registerContext(Module.vgl.gl, { majorVersion: 2, minorVersion: 0 });
  GL.makeContextCurrent(handle);
  Module.onVtestOut = onOut;
  if (Module._vtw_init() < 0) throw new Error("virgl_renderer_init не удался");
};

// имена с приставкой: в области модуля Emscripten есть свои run() и т.п.
let vtwWaiting = false;
function vtwRun() {
  const r = Module._vtw_run();
  if (r < 0) {
    if (Module.onVtestError) Module.onVtestError(r);
  } else if (r === 1 && !vtwWaiting) {
    // ждём GPU: заборы WebGL2 готовы только в следующей задаче
    vtwWaiting = true;
    setTimeout(() => { vtwWaiting = false; Module._vtw_poll(); vtwRun(); }, 0);
  }
}

Module.connect = function () {
  const r = Module._vtw_connect();
  if (r < 0) throw new Error("vtw_connect: " + r);
};

Module.disconnect = function () {
  Module._vtw_disconnect();
};

Module.feed = function (bytes) {
  const p = Module._vtw_reserve(bytes.length);
  if (!p) throw new Error("vtest: нет памяти");
  HEAPU8.set(bytes, p);
  Module._vtw_push(bytes.length);
  if (!vtwWaiting) vtwRun();
};
