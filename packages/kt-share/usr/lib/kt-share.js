async (cmd = "", arg = "") => {
  // kt share: та же страница с v86 одним html, только снимок - машина как сейчас. Получатель открывает файл,
  // правит, шлёт своим kt share обратно. См. docs/packages.md
  const B = window.KT_BUNDLE, W = window.ktShare || (window.ktShare = { busy: false });
  const PROJ = "/var/lib/kt/share", WAIT = "/run/kt/share.wait", DONE = "/run/kt/share.done";
  const STATE = '<script type="application/base64" id="kt-state">', META = "<script>window.KT_BUNDLE = ", END = "</script>";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const mb = (n) => (n / 1048576).toFixed(1) + " МБ";
  const rand = (n) => [...crypto.getRandomValues(new Uint8Array(n))].map((b) => "abcdefghijkmnpqrstuvwxyz23456789"[b & 31]).join("");
  const sh = async (c) => {
    const r = await kt.exec(c);
    if (r.code) throw new Error(r.err.trim() || c);
    return r.out;
  };

  // машина-проект: id - имя бандла у копий (у получателя свой слот сохранения), name - имя файла. Лежит в
  // самой машине и уезжает со снимком: следующий kt share - та же машина новой ревизией
  async function project(name) {
    if (name) {
      // как kt_name в госте; 24 - чтобы с «-xxxxxx» вышло имя снимка, до 32 знаков
      if (!/^(?!-)[\w.-]{1,24}$/.test(name)) throw new Error("имя - латинские буквы, цифры, . _ -, до 24 знаков: " + name);
    } else {
      const [id, n] = (await sh(`cat ${PROJ} 2>/dev/null; true`)).split("\n");
      if (id && n) return { id, name: n };
      name = (B.name || "kotelos").slice(0, 24);
    }
    const p = { id: name + "-" + rand(6), name };
    await sh(`mkdir -p /var/lib/kt && printf '%s\\n%s\\n' ${p.id} ${p.name} > ${PROJ}`);
    return p;
  }

  // свой файл: части страницы после загрузки удалены - взять у сервера (обычно из кэша) или у пользователя
  const pick = () => new Promise((ok) => {
    const i = document.createElement("input");
    i.type = "file";
    i.accept = ".html,text/html";
    i.onchange = () => ok([...i.files]);
    i.oncancel = () => ok([]);
    i.click();
  });
  async function source() {
    if (/^https?:$/.test(location.protocol)) {
      try {
        const r = await fetch(location.href, { cache: "force-cache" });
        if (r.ok) return await r.blob();
      } catch {}
    }
    const [f] = await kt.gesture("Выбери файл этой страницы: копия собирается из него", "Выбрать", pick);
    if (!f) throw new Error("файл не выбран");
    return f;
  }

  // где в файле заголовок, блок снимка и KT_BUNDLE. Файл - в хранилище браузера (Blob), читаются только
  // нужные места кусками по 64 КБ, по байту на символ (latin1): индексы - смещения в байтах, а мелкие куски
  // убирает сборка мусора молодого поколения, большие копились бы поверх снимка машины. Порядок от
  // bundle.py: шаблон, мелкие части (wasm, bios), блок снимка, KT_BUNDLE, код страницы
  const CH = 65536, LAP = 128, dec = new TextDecoder("latin1");
  const read = async (blob, a, b) => dec.decode(new Uint8Array(await blob.slice(a, b).arrayBuffer()));
  async function find(blob, needles, from) { // первая из строк после from: [индекс, какая] или [-1]
    for (let off = from; off < blob.size; off += CH) {
      const text = await read(blob, off, off + CH + LAP);
      let best = [-1];
      for (const s of needles) {
        const i = text.indexOf(s);
        if (i >= 0 && i < CH && (best[0] < 0 || i < best[0] - off)) best = [off + i, s];
      }
      if (best[0] >= 0) return best;
    }
    return [-1];
  }
  async function findLast(blob, s) {
    for (let end = blob.size; end > 0; end -= CH) {
      const a = Math.max(0, end - CH - LAP), i = (await read(blob, a, end)).lastIndexOf(s);
      if (i >= 0) return a + i;
    }
    return -1;
  }
  async function scan(blob) {
    const at = {};
    at.title = (await find(blob, ["<title>"], 0))[0];
    at.titleEnd = at.title < 0 ? -1 : (await find(blob, ["</title>"], at.title))[0];
    // блока снимка нет (бандл только с ядром) - на его месте KT_BUNDLE
    const [s, which] = at.titleEnd < 0 ? [-1] : await find(blob, [STATE, META], at.titleEnd);
    at.state = s;
    at.meta = which === META ? s : s < 0 ? -1 : await findLast(blob, META);
    at.metaEnd = at.meta < 0 ? -1 : (await find(blob, [END], at.meta))[0];
    if (Object.values(at).some((x) => x < 0) || at.meta < at.state) throw new Error("это не файл KotelOS");
    const meta = JSON.parse((await blob.slice(at.meta + META.length, at.metaEnd).text()).replace(/;\s*$/, ""));
    if (meta.id !== B.id) throw new Error("файл не от этой страницы" + (/^https?:$/.test(location.protocol) ? " - сайт обновился, открой страницу заново" : ""));
    return at;
  }

  // base64 потоком, кусками по 48 КБ - кратно 3, так куски стыкуются без '=' (и мусор мелкий, см. выше)
  async function b64(blob) {
    const parts = [], rd = blob.stream().getReader(), N = 49152;
    const enc = (u) => u.toBase64 ? u.toBase64() : btoa(String.fromCharCode.apply(null, u));
    let rest = new Uint8Array(0);
    for (;;) {
      const { done, value } = await rd.read();
      if (done) break;
      let u = value;
      if (rest.length) {
        u = new Uint8Array(rest.length + value.length);
        u.set(rest);
        u.set(value, rest.length);
      }
      const n = u.length - (u.length % 3);
      for (let o = 0; o < n; o += N) parts.push(new Blob([enc(u.subarray(o, Math.min(n, o + N)))]));
      rest = u.slice(n);
    }
    if (rest.length) parts.push(new Blob([enc(rest)]));
    return new Blob(parts);
  }

  // файл: всё до блока снимка - как было (заголовок - имя машины), новый снимок, новый KT_BUNDLE, дальше как было
  async function build(src, at, rec, p, rev) {
    const meta = JSON.parse(JSON.stringify(B));
    meta.name = p.id;
    delete meta.cmd; // startx бандлов xorg и dwm уже отработал
    if (/^https?:$/.test(location.protocol)) meta.repo = new URL(B.repo || "/repo", location.href).href;
    meta.state = { mem: rec.memory_size, vga: rec.vga_memory_size, screen: rec.screen || "", gz: true, rev, revs: rec.revs };
    if (rec.screen_on) Object.assign(meta.state, { screen_on: true, screen_size: rec.screen_size });
    return new File([
      src.slice(0, at.title), `<title>KotelOS ${p.name}</title>`, src.slice(at.titleEnd + 8, at.state),
      STATE, await b64(rec.blob), END,
      META, JSON.stringify(meta).replace(/</g, "\\u003c"), ";" + END,
      src.slice(at.metaEnd + END.length),
    ], p.name + ".html", { type: "text/html" });
  }

  // на телефоне - «Поделиться» системы, иначе (и если браузер не даёт) - скачать
  async function give(file) {
    if (kt.cfg["term.mobile"] && navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await kt.gesture(`${file.name} готов, ${mb(file.size)}`, "Поделиться", () => navigator.share({ files: [file] }));
        return "отправлен";
      } catch (e) {
        if (e.name === "AbortError" || e.message === "отменено") return "не отправлен";
      }
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(file);
    a.download = file.name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
    return "скачивается";
  }

  function busy(on) {
    W.busy = on;
    const b = document.getElementById("kt-share");
    if (b) {
      b.disabled = on;
      b.style.opacity = on ? "1" : "";
    }
  }

  async function share(shell, name) {
    if (W.busy) throw new Error("уже собираю");
    if (typeof kt.share !== "function" || !B || !B.id) throw new Error("страница собрана без kt share, нужен бандл новее");
    busy(true);
    try {
      const p = await project(name);
      const src = await source();
      const at = await scan(src);
      // команда kt share в шелле ждёт ответа в своём цикле (share.wait), а не в запросе к странице: снимок с
      // открытым запросом у получателя завис бы
      if (shell) for (let i = 0; i < 50 && (await kt.exec(`test -f ${WAIT}`)).code; i++) await sleep(100);
      const rev = rand(8);
      const rec = await kt.share(rev);
      const file = await build(src, at, rec, p, rev);
      return `${file.name}, ${mb(file.size)}: ${await give(file)}`;
    } finally {
      busy(false);
    }
  }

  if (cmd === "share") {
    // через mv: команда ждёт появления файла и не должна прочитать его недописанным
    const done = (s) => kt.exec(`cat > ${DONE}.part && mv ${DONE}.part ${DONE}`, { stdin: s + "\n" }).catch(() => {});
    share(true, arg).then((m) => done("0" + m), (e) => done("1" + e.message));
    return "";
  }

  if (cmd === "button") {
    document.getElementById("kt-share")?.remove();
    const b = document.createElement("button");
    b.id = "kt-share";
    b.setAttribute("aria-label", "kt share");
    b.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V3M7 8l5-5 5 5"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/></svg>';
    b.style.cssText = "position:absolute;top:6px;right:6px;z-index:15;width:30px;height:30px;padding:0;display:flex;" +
      "align-items:center;justify-content:center;background:var(--bg);color:var(--text);border:1px solid var(--line);" +
      "border-radius:6px;opacity:.35;cursor:pointer";
    b.onmouseenter = () => { if (!W.busy) b.style.opacity = ".9"; };
    b.onmouseleave = () => { if (!W.busy) b.style.opacity = ""; };
    b.addEventListener("mousedown", (e) => e.preventDefault());
    // без функции gesture показывает окно всегда (с функцией сразу после нажатия - только вызывает её)
    b.onclick = () => share(false).catch((e) => kt.gesture("kt share: " + e.message, "OK").catch(() => {}));
    document.getElementById("app").append(b);
    busy(W.busy);
    return W.busy ? "busy" : "";
  }

  throw new Error("kt-share.js: share [имя] | button");
}
