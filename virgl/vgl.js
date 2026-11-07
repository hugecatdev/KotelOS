// Виртуальные GL-контексты поверх одного WebGL2 (подключается к модулю через --pre-js).
//
// vrend заводит по GL-контексту на каждый контекст гостя и ещё служебный (ctx0 - передачи
// данных, заборы) и рассчитывает на разделяемые контексты: объекты общие, состояние у каждого
// своё. В WebGL контексты объектов не делят, поэтому контекст настоящий один, а обёртка помнит
// состояние каждого виртуального и при makeCurrent доводит до него настоящее - так же
// «виртуализирует» контексты Chrome на части платформ. Emscripten работает с обёрткой как с
// обычным WebGL2RenderingContext (GL.registerContext).
//
// Что не виртуализируется: VAO по умолчанию (vrend всегда привязывает свой), активные запросы и
// transform feedback через переключение (их vrend не держит открытыми между командами).

Module.createVGL = function (gl) {
  const G = WebGL2RenderingContext;
  // как у GLES: всё, что поддерживается, включено (Emscripten включает не всё)
  for (const e of gl.getSupportedExtensions() || []) gl.getExtension(e);

  const CAPS = [G.BLEND, G.CULL_FACE, G.DEPTH_TEST, G.DITHER, G.POLYGON_OFFSET_FILL,
    G.SAMPLE_ALPHA_TO_COVERAGE, G.SAMPLE_COVERAGE, G.SCISSOR_TEST, G.STENCIL_TEST,
    G.RASTERIZER_DISCARD];
  const PIXEL = [[G.PACK_ALIGNMENT, 4], [G.UNPACK_ALIGNMENT, 4], [G.UNPACK_FLIP_Y_WEBGL, false],
    [G.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false],
    [G.UNPACK_COLORSPACE_CONVERSION_WEBGL, G.BROWSER_DEFAULT_WEBGL],
    [G.PACK_ROW_LENGTH, 0], [G.PACK_SKIP_PIXELS, 0], [G.PACK_SKIP_ROWS, 0],
    [G.UNPACK_ROW_LENGTH, 0], [G.UNPACK_IMAGE_HEIGHT, 0], [G.UNPACK_SKIP_PIXELS, 0],
    [G.UNPACK_SKIP_ROWS, 0], [G.UNPACK_SKIP_IMAGES, 0]];
  const BUFFERS = [G.ARRAY_BUFFER, G.COPY_READ_BUFFER, G.COPY_WRITE_BUFFER, G.PIXEL_PACK_BUFFER,
    G.PIXEL_UNPACK_BUFFER, G.TRANSFORM_FEEDBACK_BUFFER, G.UNIFORM_BUFFER];
  const TEXTURES = [G.TEXTURE_2D, G.TEXTURE_CUBE_MAP, G.TEXTURE_3D, G.TEXTURE_2D_ARRAY];
  const HINTS = [G.GENERATE_MIPMAP_HINT, G.FRAGMENT_SHADER_DERIVATIVE_HINT];
  // поля, которые Emscripten сам пишет в GLctx: у каждого контекста свои
  const EMU = ["currentArrayBufferBinding", "currentElementArrayBufferBinding",
    "currentPixelPackBufferBinding", "currentPixelUnpackBufferBinding", "currentProgram"];

  function fresh() {
    const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
    const s = {
      caps: new Map(CAPS.map((c) => [c, c === G.DITHER])),
      blendColor: [0, 0, 0, 0], blendEq: [G.FUNC_ADD, G.FUNC_ADD],
      blendFunc: [G.ONE, G.ZERO, G.ONE, G.ZERO], colorMask: [true, true, true, true],
      depthMask: true, depthFunc: G.LESS, depthRange: [0, 1],
      stencilFunc: [[G.ALWAYS, 0, 0xffffffff], [G.ALWAYS, 0, 0xffffffff]], // перед, зад
      stencilOp: [[G.KEEP, G.KEEP, G.KEEP], [G.KEEP, G.KEEP, G.KEEP]],
      stencilMask: [0xffffffff, 0xffffffff],
      cullFace: G.BACK, frontFace: G.CCW, lineWidth: 1, polygonOffset: [0, 0],
      sampleCoverage: [1, false], scissor: [0, 0, w, h], viewport: [0, 0, w, h],
      clearColor: [0, 0, 0, 0], clearDepth: 1, clearStencil: 0,
      hints: new Map(HINTS.map((t) => [t, G.DONT_CARE])),
      pixel: new Map(PIXEL),
      buffers: new Map(BUFFERS.map((t) => [t, null])),
      ubo: new Map(), // индекс -> [буфер, смещение, размер или -1]
      drawFb: null, readFb: null, rb: null, tf: null, vao: null, program: null,
      active: G.TEXTURE0, tex: new Map(), samplers: new Map(), // блок -> ...
      attribs: new Map(), // индекс -> [имя функции, аргументы...]
      emu: {},
    };
    for (const k of EMU) s.emu[k] = k === "currentProgram" ? null : 0;
    return s;
  }

  const contexts = new Map();
  let nextId = 1;
  let cur = fresh(); // состояние, которому сейчас равен настоящий WebGL

  // обёртка: те же методы и константы, состояние пишется в cur
  const W = {};
  for (let p = Object.getPrototypeOf(gl); p && p !== Object.prototype; p = Object.getPrototypeOf(p)) {
    for (const k of Object.getOwnPropertyNames(p)) {
      if (k === "constructor" || k in W) continue;
      const d = Object.getOwnPropertyDescriptor(p, k);
      if (d.get) Object.defineProperty(W, k, { get: () => gl[k] });
      else if (typeof d.value === "function") W[k] = d.value.bind(gl);
      else W[k] = d.value;
    }
  }
  for (const k of EMU) {
    Object.defineProperty(W, k, { get: () => cur.emu[k], set: (v) => { cur.emu[k] = v; } });
  }

  const real = {};
  function track(name, fn) {
    real[name] = gl[name].bind(gl);
    W[name] = function (...a) { fn(...a); return real[name](...a); };
  }
  const faces = (face) => face === G.FRONT ? [0] : face === G.BACK ? [1] : [0, 1];

  track("enable", (c) => { if (cur.caps.has(c)) cur.caps.set(c, true); });
  track("disable", (c) => { if (cur.caps.has(c)) cur.caps.set(c, false); });
  track("blendColor", (...a) => { cur.blendColor = a; });
  track("blendEquation", (m) => { cur.blendEq = [m, m]; });
  track("blendEquationSeparate", (...a) => { cur.blendEq = a; });
  track("blendFunc", (s, d) => { cur.blendFunc = [s, d, s, d]; });
  track("blendFuncSeparate", (...a) => { cur.blendFunc = a; });
  track("colorMask", (...a) => { cur.colorMask = a; });
  track("depthMask", (m) => { cur.depthMask = m; });
  track("depthFunc", (f) => { cur.depthFunc = f; });
  track("depthRange", (...a) => { cur.depthRange = a; });
  track("stencilFunc", (...a) => { cur.stencilFunc = [a, a]; });
  track("stencilFuncSeparate", (face, ...a) => { for (const i of faces(face)) cur.stencilFunc[i] = a; });
  track("stencilOp", (...a) => { cur.stencilOp = [a, a]; });
  track("stencilOpSeparate", (face, ...a) => { for (const i of faces(face)) cur.stencilOp[i] = a; });
  track("stencilMask", (m) => { cur.stencilMask = [m, m]; });
  track("stencilMaskSeparate", (face, m) => { for (const i of faces(face)) cur.stencilMask[i] = m; });
  track("cullFace", (m) => { cur.cullFace = m; });
  track("frontFace", (m) => { cur.frontFace = m; });
  track("lineWidth", (w) => { cur.lineWidth = w; });
  track("polygonOffset", (...a) => { cur.polygonOffset = a; });
  track("sampleCoverage", (...a) => { cur.sampleCoverage = a; });
  track("scissor", (...a) => { cur.scissor = a; });
  track("viewport", (...a) => { cur.viewport = a; });
  track("clearColor", (...a) => { cur.clearColor = a; });
  track("clearDepth", (d) => { cur.clearDepth = d; });
  track("clearStencil", (s) => { cur.clearStencil = s; });
  track("hint", (t, m) => { if (cur.hints.has(t)) cur.hints.set(t, m); });
  track("pixelStorei", (p, v) => { if (cur.pixel.has(p)) cur.pixel.set(p, v); });
  track("bindBuffer", (t, b) => { if (cur.buffers.has(t)) cur.buffers.set(t, b); });
  track("bindBufferBase", (t, i, b) => {
    if (t === G.UNIFORM_BUFFER) cur.ubo.set(i, [b, 0, -1]);
    if (cur.buffers.has(t)) cur.buffers.set(t, b);
  });
  track("bindBufferRange", (t, i, b, off, size) => {
    if (t === G.UNIFORM_BUFFER) cur.ubo.set(i, [b, off, size]);
    if (cur.buffers.has(t)) cur.buffers.set(t, b);
  });
  track("bindFramebuffer", (t, fb) => {
    if (t !== G.READ_FRAMEBUFFER) cur.drawFb = fb;
    if (t !== G.DRAW_FRAMEBUFFER) cur.readFb = fb;
  });
  track("bindRenderbuffer", (t, rb) => { cur.rb = rb; });
  track("bindTransformFeedback", (t, tf) => { cur.tf = tf; });
  track("bindVertexArray", (vao) => { cur.vao = vao; });
  track("useProgram", (p) => { cur.program = p; });
  track("activeTexture", (u) => { cur.active = u; });
  track("bindTexture", (t, tex) => {
    const u = cur.active - G.TEXTURE0;
    if (!cur.tex.has(u)) cur.tex.set(u, new Map());
    cur.tex.get(u).set(t, tex);
  });
  track("bindSampler", (u, s) => { cur.samplers.set(u, s); });
  for (const n of [1, 2, 3, 4]) {
    for (const f of [`vertexAttrib${n}f`, `vertexAttrib${n}fv`]) {
      track(f, (i, ...v) => { cur.attribs.set(i, [f, ...v.map((x) => x && x.slice ? x.slice() : x)]); });
    }
  }
  for (const f of ["vertexAttribI4i", "vertexAttribI4ui", "vertexAttribI4iv", "vertexAttribI4uiv"]) {
    track(f, (i, ...v) => { cur.attribs.set(i, [f, ...v.map((x) => x && x.slice ? x.slice() : x)]); });
  }

  // удалённый объект отвязывается во всех контекстах: в WebGL привязка удалённого - ошибка
  function purge(obj) {
    const tw = twins.get(obj);
    if (tw) {
      gl.deleteBuffer(tw.e);
      twins.delete(obj);
    }
    elemBound.delete(obj);
    for (const [vao, b] of elemBound) if (b === obj) elemBound.set(vao, null);
    for (const s of [cur, ...contexts.values()]) {
      for (const [k, v] of s.buffers) if (v === obj) s.buffers.set(k, null);
      for (const [k, v] of s.ubo) if (v[0] === obj) s.ubo.delete(k);
      for (const k of ["drawFb", "readFb", "rb", "tf", "vao", "program"]) if (s[k] === obj) s[k] = null;
      for (const m of s.tex.values()) for (const [k, v] of m) if (v === obj) m.set(k, null);
      for (const [k, v] of s.samplers) if (v === obj) s.samplers.set(k, null);
    }
  }
  for (const f of ["deleteBuffer", "deleteTexture", "deleteFramebuffer", "deleteRenderbuffer",
    "deleteVertexArray", "deleteTransformFeedback", "deleteSampler", "deleteProgram"]) {
    track(f, (obj) => { if (obj) purge(obj); });
  }

  // Индексы и вершины в одном буфере. WebGL2 закрепляет тип буфера при первой привязке: бывший
  // ELEMENT_ARRAY_BUFFER нельзя привязать к другим точкам и наоборот, копировать между ними тоже
  // нельзя, а Gallium кладёт индексы и вершины в общий буфер выгрузки. Поэтому у буфера, который
  // бывает индексным, есть двойник только для ELEMENT_ARRAY_BUFFER: запись с процессора идёт в
  // оба, запись GPU в основной (копирование, PBO, transform feedback) делает двойника устаревшим,
  // и он перечитывается при следующей привязке. Чтение индексного буфера - из основного.
  const twins = new Map(); // основной буфер -> { e: двойник, stale }
  const elemBound = new Map(); // VAO (null - по умолчанию) -> основной буфер на ELEMENT_ARRAY_BUFFER
  const elemNow = () => {
    const b = elemBound.get(cur.vao);
    return b ? twins.get(b).e : null;
  };
  const via = (target, buf, f) => {
    real.bindBuffer(target, buf);
    try { return f(target); } finally { real.bindBuffer(target, cur.buffers.get(target)); }
  };
  function newTwin() {
    const e = gl.createBuffer();
    real.bindBuffer(G.ELEMENT_ARRAY_BUFFER, e); // тип «индексы» - до любой другой привязки
    real.bindBuffer(G.ELEMENT_ARRAY_BUFFER, elemNow());
    return { e, stale: true };
  }
  function syncTwin(b, t) {
    const data = via(G.COPY_READ_BUFFER, b, (tg) => {
      const d = new Uint8Array(gl.getBufferParameter(tg, G.BUFFER_SIZE) || 0);
      if (d.length) gl.getBufferSubData(tg, 0, d);
      return d;
    });
    via(G.COPY_WRITE_BUFFER, t.e, (tg) => gl.bufferData(tg, data, G.DYNAMIC_DRAW));
    t.stale = false;
  }
  const bufferAt = (t) => t === G.ELEMENT_ARRAY_BUFFER ? elemBound.get(cur.vao) || null : cur.buffers.get(t) || null;
  const staleTwin = (b) => { const t = b && twins.get(b); if (t) t.stale = true; };

  W.bindBuffer = (t, b) => {
    if (t !== G.ELEMENT_ARRAY_BUFFER) {
      if (cur.buffers.has(t)) cur.buffers.set(t, b);
      return real.bindBuffer(t, b);
    }
    if (b) {
      let tw = twins.get(b);
      if (!tw) twins.set(b, tw = newTwin());
      if (tw.stale) syncTwin(b, tw);
    }
    elemBound.set(cur.vao, b || null);
    return real.bindBuffer(t, b ? twins.get(b).e : null);
  };
  for (const name of ["bufferData", "bufferSubData"]) {
    real[name] = gl[name].bind(gl);
    W[name] = (t, ...a) => {
      const b = bufferAt(t);
      if (t === G.ELEMENT_ARRAY_BUFFER) {
        if (b) via(G.COPY_WRITE_BUFFER, b, (tg) => real[name](tg, ...a));
        return real[name](t, ...a);
      }
      const r = real[name](t, ...a);
      const tw = b && twins.get(b);
      if (tw && !tw.stale) via(G.COPY_WRITE_BUFFER, tw.e, (tg) => real[name](tg, ...a));
      return r;
    };
  }
  real.getBufferSubData = gl.getBufferSubData.bind(gl);
  W.getBufferSubData = (t, ...a) => t !== G.ELEMENT_ARRAY_BUFFER ? real.getBufferSubData(t, ...a) :
    via(G.COPY_READ_BUFFER, bufferAt(t), (tg) => real.getBufferSubData(tg, ...a));
  real.copyBufferSubData = gl.copyBufferSubData.bind(gl);
  W.copyBufferSubData = (rt, wt, ...a) => {
    const rb = bufferAt(rt), wb = bufferAt(wt);
    via(G.COPY_READ_BUFFER, rb, () => via(G.COPY_WRITE_BUFFER, wb, () =>
      real.copyBufferSubData(G.COPY_READ_BUFFER, G.COPY_WRITE_BUFFER, ...a)));
    staleTwin(wb);
  };
  real.readPixels = gl.readPixels.bind(gl);
  W.readPixels = (...a) => {
    const r = real.readPixels(...a);
    if (typeof a[6] === "number") staleTwin(cur.buffers.get(G.PIXEL_PACK_BUFFER)); // в PBO
    return r;
  };
  real.endTransformFeedback = gl.endTransformFeedback.bind(gl);
  W.endTransformFeedback = () => {
    real.endTransformFeedback();
    for (const t of twins.values()) t.stale = true;
  };

  // отладка: globalThis.VIRGL_GL_DEBUG - после каждого вызова getError, ошибки - в консоль с
  // именем функции (ошибки при этом не доходят до vrend; первые 50 разных)
  if (globalThis.VIRGL_GL_DEBUG) {
    const seen = new Map();
    for (const k of Object.keys(W)) {
      const f = W[k];
      if (typeof f !== "function" || k === "getError") continue;
      W[k] = function (...a) {
        const r = f.apply(this, a);
        const e = gl.getError();
        if (e) {
          const key = k + ":" + e;
          const n = (seen.get(key) || 0) + 1;
          seen.set(key, n);
          if (seen.size <= 50 && (n === 1 || n === 100)) {
            const args = a.map((x) => typeof x === "number" ? "0x" + x.toString(16) : x && x.constructor ? x.constructor.name : String(x));
            console.warn("virgl: GL", "0x" + e.toString(16), k + "(" + args.join(", ") + ")", n > 1 ? "x" + n : "");
          }
        }
        return r;
      };
    }
  }

  const same = (a, b) => a === b || (Array.isArray(a) && Array.isArray(b) &&
    a.length === b.length && a.every((x, i) => same(x, b[i])));
  const keys = (a, b) => new Set([...a.keys(), ...b.keys()]);

  // довести настоящий WebGL от состояния a до состояния b
  function apply(a, b) {
    for (const c of CAPS) if (a.caps.get(c) !== b.caps.get(c)) (b.caps.get(c) ? real.enable : real.disable)(c);
    if (!same(a.blendColor, b.blendColor)) real.blendColor(...b.blendColor);
    if (!same(a.blendEq, b.blendEq)) real.blendEquationSeparate(...b.blendEq);
    if (!same(a.blendFunc, b.blendFunc)) real.blendFuncSeparate(...b.blendFunc);
    if (!same(a.colorMask, b.colorMask)) real.colorMask(...b.colorMask);
    if (a.depthMask !== b.depthMask) real.depthMask(b.depthMask);
    if (a.depthFunc !== b.depthFunc) real.depthFunc(b.depthFunc);
    if (!same(a.depthRange, b.depthRange)) real.depthRange(...b.depthRange);
    [G.FRONT, G.BACK].forEach((face, i) => {
      if (!same(a.stencilFunc[i], b.stencilFunc[i])) real.stencilFuncSeparate(face, ...b.stencilFunc[i]);
      if (!same(a.stencilOp[i], b.stencilOp[i])) real.stencilOpSeparate(face, ...b.stencilOp[i]);
      if (a.stencilMask[i] !== b.stencilMask[i]) real.stencilMaskSeparate(face, b.stencilMask[i]);
    });
    if (a.cullFace !== b.cullFace) real.cullFace(b.cullFace);
    if (a.frontFace !== b.frontFace) real.frontFace(b.frontFace);
    if (a.lineWidth !== b.lineWidth) real.lineWidth(b.lineWidth);
    if (!same(a.polygonOffset, b.polygonOffset)) real.polygonOffset(...b.polygonOffset);
    if (!same(a.sampleCoverage, b.sampleCoverage)) real.sampleCoverage(...b.sampleCoverage);
    if (!same(a.scissor, b.scissor)) real.scissor(...b.scissor);
    if (!same(a.viewport, b.viewport)) real.viewport(...b.viewport);
    if (!same(a.clearColor, b.clearColor)) real.clearColor(...b.clearColor);
    if (a.clearDepth !== b.clearDepth) real.clearDepth(b.clearDepth);
    if (a.clearStencil !== b.clearStencil) real.clearStencil(b.clearStencil);
    for (const t of HINTS) if (a.hints.get(t) !== b.hints.get(t)) real.hint(t, b.hints.get(t));
    for (const [p] of PIXEL) if (a.pixel.get(p) !== b.pixel.get(p)) real.pixelStorei(p, b.pixel.get(p));

    // индексные привязки UBO меняют и общую привязку UNIFORM_BUFFER - сначала они
    for (const i of keys(a.ubo, b.ubo)) {
      const x = a.ubo.get(i), y = b.ubo.get(i);
      if (same(x, y)) continue;
      if (!y) real.bindBufferBase(G.UNIFORM_BUFFER, i, null);
      else if (y[2] < 0) real.bindBufferBase(G.UNIFORM_BUFFER, i, y[0]);
      else real.bindBufferRange(G.UNIFORM_BUFFER, i, y[0], y[1], y[2]);
    }
    for (const t of BUFFERS) real.bindBuffer(t, b.buffers.get(t));
    if (a.tf !== b.tf) real.bindTransformFeedback(G.TRANSFORM_FEEDBACK, b.tf);
    if (a.drawFb !== b.drawFb) real.bindFramebuffer(G.DRAW_FRAMEBUFFER, b.drawFb);
    if (a.readFb !== b.readFb) real.bindFramebuffer(G.READ_FRAMEBUFFER, b.readFb);
    if (a.rb !== b.rb) real.bindRenderbuffer(G.RENDERBUFFER, b.rb);
    if (a.vao !== b.vao) real.bindVertexArray(b.vao);
    if (a.program !== b.program) real.useProgram(b.program);

    for (const u of keys(a.tex, b.tex)) {
      const x = a.tex.get(u) || new Map(), y = b.tex.get(u) || new Map();
      for (const t of TEXTURES) {
        const tex = y.get(t) || null;
        if ((x.get(t) || null) === tex) continue;
        real.activeTexture(G.TEXTURE0 + u);
        real.bindTexture(t, tex);
      }
    }
    real.activeTexture(b.active);
    for (const u of keys(a.samplers, b.samplers)) {
      const s = b.samplers.get(u) || null;
      if ((a.samplers.get(u) || null) !== s) real.bindSampler(u, s);
    }
    for (const i of keys(a.attribs, b.attribs)) {
      const x = a.attribs.get(i), y = b.attribs.get(i);
      if (same(x, y)) continue;
      if (y) real[y[0]](i, ...y.slice(1));
      else real.vertexAttrib4f(i, 0, 0, 0, 1);
    }
  }

  return {
    gl: W,
    create() {
      const id = nextId++;
      contexts.set(id, contexts.size ? fresh() : cur); // первый получает уже настоящее состояние
      return id;
    },
    destroy(id) {
      contexts.delete(id);
    },
    makeCurrent(id) {
      if (!id) return 0; // «без контекста»: настоящий остаётся как есть
      const s = contexts.get(id);
      if (!s) return -1;
      if (s !== cur) {
        apply(cur, s);
        cur = s;
      }
      return 0;
    },
  };
};
