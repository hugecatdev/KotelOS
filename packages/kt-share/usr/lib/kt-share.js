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

  // исходник - сама страница без снимка и ядра (kt.source: page.html берёт его при загрузке, пока DOM
  // нетронут); на местах снимка и KT_BUNDLE - комментарии kt-state и kt-meta. Снимка может не быть (бандл
  // только с ядром) - тогда он встаёт перед KT_BUNDLE
  async function source() {
    const html = await kt.source.text(), M = "<!--kt-meta-->", S = "<!--kt-state-->";
    const m = html.indexOf(M);
    if (m < 0) throw new Error("в исходнике страницы нет места KT_BUNDLE");
    const s = html.indexOf(S);
    return s < 0 || s > m ? [html.slice(0, m), html.slice(m + M.length)] : [html.slice(0, s), html.slice(s + S.length, m) + html.slice(m + M.length)];
  }

  // base64 потоком, кусками по 48 КБ - кратно 3, так куски стыкуются без '='; мелкие куски убирает сборка
  // мусора молодого поколения, большие копились бы до полной поверх снимка машины
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

  // файл: страница до места снимка (заголовок - имя машины), новый снимок, новый KT_BUNDLE, остальное
  async function build([pre, post], rec, p, rev) {
    const meta = JSON.parse(JSON.stringify(B));
    meta.name = p.id;
    meta.cfg = Object.assign({}, B.cfg);
    delete meta.cfg["boot.cmd"]; // startx бандлов xorg и dwm уже отработал
    delete meta.id; // отпечаток страницы прежних версий
    meta.share = true; // копия сразу берёт свой исходник: получатель шлёт обратно с первого открытия
    for (const k of ["bzimage", "initrd"]) delete meta.files[k]; // ядро в исходник не взято
    if (/^https?:$/.test(location.protocol)) meta.cfg["pkg.repo"] = new URL(meta.cfg["pkg.repo"] || "/repo", location.href).href;
    meta.state = { mem: rec.memory_size, vga: rec.vga_memory_size, screen: rec.screen || "", gz: true, rev, revs: rec.revs };
    if (rec.screen_on) Object.assign(meta.state, { screen_on: true, screen_size: rec.screen_size });
    return new File([
      pre.replace(/<title>[^<]*<\/title>/, `<title>KotelOS ${p.name}</title>`),
      STATE, await b64(rec.blob), END,
      META, JSON.stringify(meta).replace(/</g, "\\u003c"), ";" + END,
      post,
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
    if (b) b.classList.toggle("busy", on);
  }

  async function share(shell, name) {
    if (W.busy) throw new Error("уже собираю");
    if (typeof kt.share !== "function" || !("source" in kt)) throw new Error("страница собрана без kt share, нужен бандл новее");
    // исходник страница берёт при открытии, и только если kt-share был (бандл с ним или отметка хука)
    if (!kt.source) throw new Error("kt-share поставлен в уже открытой странице: kt save и обнови страницу");
    busy(true);
    try {
      const p = await project(name);
      const src = await source();
      // команда kt share в шелле ждёт ответа в своём цикле (share.wait), а не в запросе к странице: снимок с
      // открытым запросом у получателя завис бы
      if (shell) for (let i = 0; i < 50 && (await kt.exec(`test -f ${WAIT}`)).code; i++) await sleep(100);
      const rev = rand(8);
      const rec = await kt.share(rev);
      const file = await build(src, rec, p, rev);
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

  // кнопка - полупрозрачный значок без фона у правого края над рядом клавиш, поверх терминала и экрана X
  // (у #screen z-index 16); светлый с тёмной тенью - виден и на чёрном терминале, и на белом окне X
  const CSS = `#kt-share { position: absolute; right: 8px; bottom: 8px; z-index: 17; width: 32px; height: 32px; padding: 0;
  border: 0; background: none; color: #ddd; opacity: .45; cursor: pointer; display: flex; align-items: center;
  justify-content: center; filter: drop-shadow(0 0 1px #000) drop-shadow(0 0 2px #000); touch-action: none;
  user-select: none; -webkit-user-select: none; }
#kt-share:hover { opacity: .9; }
#kt-share.busy { cursor: wait; animation: kt-share .8s ease-in-out infinite alternate; }
@keyframes kt-share { from { opacity: .3; } to { opacity: 1; } }
body.mobile #kt-share { width: 40px; height: 40px; }`;

  if (cmd === "button") {
    if (kt.keepSource) kt.keepSource(); // со следующего открытия страница берёт исходник: kt-share здесь есть
    document.getElementById("kt-share")?.remove();
    document.getElementById("kt-share-css")?.remove();
    if (W.keys) W.keys.disconnect();
    const css = document.createElement("style");
    css.id = "kt-share-css";
    css.textContent = CSS;
    document.head.append(css);
    const b = document.createElement("button");
    b.id = "kt-share";
    b.tabIndex = -1;
    b.setAttribute("aria-label", "kt share");
    b.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"><path d="M12 15V3M7 8l5-5 5 5"/><path d="M5 12v9h14v-9"/></svg>';
    // фокус остаётся у терминала или экрана X, клавиатура телефона не закрывается (как у ряда клавиш),
    // поэтому нажатие - по pointerup (click после погашенного touchstart не приходит)
    let down = false;
    b.addEventListener("touchstart", (e) => e.preventDefault(), { passive: false });
    b.addEventListener("mousedown", (e) => e.preventDefault());
    b.onpointerdown = () => { down = true; };
    b.onpointerleave = () => { down = false; };
    // без функции gesture показывает окно всегда (с функцией сразу после нажатия - только вызывает её)
    b.onpointerup = () => {
      if (down && !W.busy) share(false).catch((e) => kt.gesture("kt share: " + e.message, "OK").catch(() => {}));
      down = false;
    };
    const app = document.getElementById("app"), keys = document.getElementById("keys");
    app.append(b);
    // над рядом клавиш телефона (на ПК его нет)
    W.keys = new ResizeObserver(() => { b.style.bottom = (keys ? keys.offsetHeight : 0) + 8 + "px"; });
    if (keys) W.keys.observe(keys);
    else b.style.bottom = "8px";
    busy(W.busy);
    return W.busy ? "busy" : "";
  }

  throw new Error("kt-share.js: share [имя] | button");
}
