// node --no-liftoff --no-wasm-lazy-compilation --perf-basic-prof tests/jitasm.mjs МОДУЛЬ.wasm КУДА.bin
// Компилирует модуль JIT v86 (из tests/jitasm.py) или сам v86.wasm оптимизатором V8 и сохраняет машинный код его
// функций: адреса - из /tmp/perf-PID.map, байты - из /proc/self/mem. Импорты модуля - заглушки,
// код не выполняется.
import fs from "fs";
const [file, out] = process.argv.slice(2);
const bytes = fs.readFileSync(file);
const mod = new WebAssembly.Module(bytes);
const imports = {};
for (const imp of WebAssembly.Module.imports(mod)) {
  const e = imports[imp.module] ||= {};
  if (imp.kind === "memory") e[imp.name] = new WebAssembly.Memory({ initial: 64 });
  else if (imp.kind === "table") e[imp.name] = new WebAssembly.Table({ element: "anyfunc", initial: 4096 });
  else if (imp.kind === "function") e[imp.name] = () => 0;
}
const inst = new WebAssembly.Instance(mod, imports);
globalThis.keep = inst;
const map = fs.readFileSync(`/tmp/perf-${process.pid}.map`, "utf8").split("\n").filter((l) => /-turbofan$|-liftoff$/.test(l));
const fd = fs.openSync("/proc/self/mem", "r");
let total = 0;
const parts = [];
for (const l of map) {
  const [addr, size, ...name] = l.split(" ");
  const n = parseInt(size, 16);
  const buf = Buffer.alloc(n);
  fs.readSync(fd, buf, 0, n, BigInt("0x" + addr));
  parts.push(buf);
  total += n;
  console.log(name.join(" "), n, "байт машинного кода");
}
fs.writeFileSync(out, Buffer.concat(parts));
fs.unlinkSync(`/tmp/perf-${process.pid}.map`);
console.log("wasm", bytes.length, "байт -> машинный код", total, "байт");
