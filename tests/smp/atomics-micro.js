// Цена атомиков wasm в V8 без v86: node tests/smp/atomics-micro.js
// Цикл записи (или чтения) по 4 КБ, обычные i32.store/load против i32.atomic.*, на обычной и
// на shared памяти - понимает ли V8, что атомики на обычной памяти можно делать простыми.
"use strict";
const leb = (n) => { const o = []; do { let b = n & 0x7f; n >>>= 7; if (n) b |= 0x80; o.push(b); } while (n); return o; };
const sec = (id, b) => [id, ...leb(b.length), ...b];
const vec = (items) => [...leb(items.length), ...items.flat()];
const str = (s) => [...leb(s.length), ...Buffer.from(s)];

function build(kind, atomic, shared) {
  // (func (param n i32) (result i32) (local i i32) (local s i32) loop ... end s)
  const addr = [0x20, 1, 0x41, 2, 0x74, 0x41, 0xfc, 0x1f, 0x71];  // (i << 2) & 0xFFC
  const op = kind === "store"
    ? [...addr, 0x20, 1, ...(atomic ? [0xfe, 0x17, 2, 0] : [0x36, 2, 0])]
    : [0x20, 2, ...addr, ...(atomic ? [0xfe, 0x10, 2, 0] : [0x28, 2, 0]), 0x6a, 0x21, 2];
  const body = [1, 2, 0x7f, 0x03, 0x40, ...op, 0x20, 1, 0x41, 1, 0x6a, 0x22, 1, 0x20, 0, 0x49, 0x0d, 0, 0x0b, 0x20, 2, 0x0b];
  return new Uint8Array([0, 0x61, 0x73, 0x6d, 1, 0, 0, 0,
    ...sec(1, vec([[0x60, 1, 0x7f, 1, 0x7f]])),
    ...sec(2, vec([[...str("e"), ...str("m"), 2, shared ? 3 : 1, 1, 1]])),
    ...sec(3, vec([[0]])),
    ...sec(7, vec([[...str("f"), 0, 0]])),
    ...sec(10, vec([[...leb(body.length), ...body]]))]);
}

const N = 2e8;
for (const kind of ["store", "load"]) {
  for (const shared of [false, true]) {
    const mem = new WebAssembly.Memory({ initial: 1, maximum: 1, shared });
    const res = [];
    for (const atomic of [false, true]) {
      const f = new WebAssembly.Instance(new WebAssembly.Module(build(kind, atomic, shared)), { e: { m: mem } }).exports.f;
      f(1e6);
      let best = Infinity;
      for (let k = 0; k < 3; k++) { const t = process.hrtime.bigint(); f(N); best = Math.min(best, Number(process.hrtime.bigint() - t) / N); }
      res.push(best);
    }
    console.log(`${kind} ${shared ? "shared " : "обычная"}: простая ${res[0].toFixed(2)} нс, атомарная ${res[1].toFixed(2)} нс (x${(res[1] / res[0]).toFixed(2)})`);
  }
}
