// Связка virglrenderer с устройством virtio-gpu v86 (src/virtio_gpu.js, патч v86 10): WebGL2 на
// холсте устройства (HTMLCanvasElement или OffscreenCanvas в воркере), виртуальные контексты
// (vgl.js), доступ к куче модуля для передач с памятью гостя. Подключается через --pre-js.
//
//   const g = await createVirgl({ wasmBinary });
//   g.startGPU(canvas);                 // контекст WebGL2 и virgl_renderer_init
//   g.onFence = (id) => ...;            // заборы (virgl_renderer_create_fence)
//   g._vgw_resource_create(...), g._vgw_transfer_write(...), g._vgw_present(...) - см. vgpu_web.c

Module.startGPU = function (canvas) {
  const gl = canvas.getContext("webgl2", {
    alpha: false, depth: false, stencil: false, antialias: false,
    premultipliedAlpha: false, preserveDrawingBuffer: false,
    powerPreference: "high-performance",
  });
  if (!gl) throw new Error("нет WebGL2");
  Module.vgl = Module.createVGL(gl);
  const handle = GL.registerContext(Module.vgl.gl, { majorVersion: 2, minorVersion: 0 });
  GL.makeContextCurrent(handle);
  const r = Module._vgw_init();
  if (r) throw new Error("virgl_renderer_init: " + r);
};

// виды на кучу - заново после каждого роста памяти
Module.heapU8 = () => HEAPU8;
Module.heapU32 = () => HEAPU32;
