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
      if (!/^[\w.-]{1,24}$/.test(name)) throw new Error("имя: латинские буквы, цифры, . _ -, до 24 знаков");
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

  // где в файле заголовок, блок снимка и KT_BUNDLE: файл читается кусками по байту на символ (latin1),
  // индексы - смещения в байтах. Блок снимка - последний перед KT_BUNDLE (bundle.py), его может не быть
  async function scan(blob) {
    const dec = new TextDecoder("latin1"), CH = 4 << 20, LAP = 128;
    const marks = [["title", "<title>"], ["titleEnd", "</title>"], ["state", STATE], ["meta", META], ["metaEnd", END]];
    const at = {};
    let i = 0, pos = 0;
    for (let off = 0; off < blob.size && i < marks.length; off += CH) {
      const start = Math.max(0, off - LAP);
      const text = dec.decode(new Uint8Array(await blob.slice(start, off + CH).arrayBuffer()));
      while (i < marks.length) {
        const [k, s] = marks[i], from = Math.max(0, pos - start);
        const j = text.indexOf(s, from);
        if (k === "state") {
          const m = text.indexOf(META, from);
          if (m >= 0 && (j < 0 || m < j)) {
            at.state = start + m;
            i++;
            continue;
          }
        }
        if (j < 0) break;
        at[k] = start + j;
        pos = start + j + s.length;
        i++;
      }
    }
    if (i < marks.length) throw new Error("это не файл KotelOS");
    const meta = JSON.parse((await blob.slice(at.meta + META.length, at.metaEnd).text()).replace(/;\s*$/, ""));
    if (meta.id !== B.id) throw new Error("файл не от этой страницы" + (/^https?:$/.test(location.protocol) ? " - сайт обновился, открой страницу заново" : ""));
    return at;
  }

  async function b64(blob) {
    const parts = [], CH = 3 << 20; // кратно 3: куски base64 стыкуются без '='
    for (let o = 0; o < blob.size; o += CH) {
      const u = new Uint8Array(await blob.slice(o, o + CH).arrayBuffer());
      let s;
      if (u.toBase64) s = u.toBase64();
      else {
        let t = "";
        for (let i = 0; i < u.length; i += 0x8000) t += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
        s = btoa(t);
      }
      parts.push(new Blob([s]));
    }
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
    share(true, arg).then((m) => done("0" + m), (e) => done("1kt share: " + e.message));
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
