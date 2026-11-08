// KotelOS на своём сайте: окна tkinter из машины плавают поверх страницы, терминала не видно.
//
//   <script src="embed.js"></script>
//   <script>
//     const vm = KotelOS.embed("app.html", { cmd: "python3 app.py" });
//     vm.ready.then(() => vm.exec("uname -a")).then((r) => console.log(r.out));
//   </script>
//
// app.html - бандл, собранный с bundle.py --embed (и python-tkinter). Он лежит в прозрачном iframe во весь
// экран поверх сайта, а клики iframe получает только над окнами: clip-path по прямоугольникам, которые
// присылает страница машины. Мимо окон сайт работает как обычно.
//
// Ключи: cmd - команда в новой машине (как ?cmd=); save - брать сохранение машины и сохранять её саму (по
// умолчанию нет: каждый раз со снимка бандла, ?fresh); z - z-index (по умолчанию поверх всего); title.
// Методы - как у API страницы через postMessage: exec, read, write, type, emit, save, cfg; call(метод,
// ...аргументы) - любой из них. on("rects", fn) - окна поменялись (fn получает [[x, y, w, h], ...]),
// on("ready", fn); remove() - убрать машину со страницы.
(() => {
  "use strict";
  const METHODS = ["exec", "read", "write", "type", "emit", "save", "cfg"];
  // совсем без окон - один пиксель в углу, а не пусто: iframe, обрезанный целиком, Chrome считает
  // невидимым и усыпляет - таймеры раз в секунду, и машина почти стоит
  const NONE = 'path("M0 0h1v1h-1z")';

  function embed(src, o = {}) {
    const url = new URL(src, location.href);
    if (!o.save) url.searchParams.set("fresh", "");
    if (o.cmd) url.searchParams.set("cmd", o.cmd);
    const f = document.createElement("iframe");
    f.src = url.href;
    f.title = o.title || "KotelOS";
    f.allow = "clipboard-read; clipboard-write";
    // color-scheme как у страницы машины: при разных Chrome кладёт под iframe непрозрачный фон
    f.style.cssText = "position:fixed;left:0;top:0;width:100%;height:100%;border:0;margin:0;padding:0;" +
      "background:transparent;color-scheme:normal;z-index:" + (o.z ?? 2147483000) + ";clip-path:" + NONE;
    document.body.append(f);

    const subs = { rects: [], ready: [] };
    const fire = (type, v) => { for (const fn of subs[type]) fn(v); };
    const wait = new Map();
    let n = 0, up;
    const ready = new Promise((r) => (up = r));
    const onMessage = (e) => {
      const m = e.data;
      if (e.source !== f.contentWindow || !m || typeof m !== "object" || m.kt === undefined) return;
      if (m.kt === "ready") {
        up();
        fire("ready");
      } else if (m.kt === "rects") {
        const d = m.rects.map(([x, y, w, h]) => `M${x} ${y}h${w}v${h}h${-w}z`).join("");
        f.style.clipPath = d ? `path("${d}")` : NONE;
        fire("rects", m.rects);
      } else if (wait.has(m.kt)) {
        const [ok, no] = wait.get(m.kt);
        wait.delete(m.kt);
        if ("error" in m) no(new Error(m.error));
        else ok(m.result);
      }
    };
    window.addEventListener("message", onMessage);

    // клавиатура телефона: сайт обычно не сжимается под неё (interactive-widget по умолчанию), и окно
    // ушло бы под клавиатуру - iframe идёт за видимой областью, окна tk следуют за ним сами. Под
    // увеличением пальцами iframe остаётся во весь слой, как прочие fixed-элементы
    const vv = window.visualViewport;
    const follow = () => {
      const on = Math.abs(vv.scale - 1) < 0.01;
      f.style.left = (on ? vv.offsetLeft : 0) + "px";
      f.style.top = (on ? vv.offsetTop : 0) + "px";
      f.style.width = on ? vv.width + "px" : "100%";
      f.style.height = on ? vv.height + "px" : "100%";
    };
    if (vv) {
      vv.addEventListener("resize", follow);
      vv.addEventListener("scroll", follow);
    }

    const call = (method, ...args) => ready.then(() => new Promise((ok, no) => {
      const id = ++n;
      wait.set(id, [ok, no]);
      f.contentWindow.postMessage({ kt: id, method, args }, "*");
    }));
    const vm = {
      frame: f,
      ready,
      call,
      on(type, fn) {
        if (!subs[type]) throw new Error("KotelOS: нет события " + type);
        subs[type].push(fn);
        return vm;
      },
      remove() {
        window.removeEventListener("message", onMessage);
        if (vv) {
          vv.removeEventListener("resize", follow);
          vv.removeEventListener("scroll", follow);
        }
        f.remove();
      },
    };
    for (const m of METHODS) vm[m] = (...args) => call(m, ...args);
    return vm;
  }

  window.KotelOS = { embed };
})();
