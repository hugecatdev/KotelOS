(m) => {
  // терминал в окне: xterm.js страницы в рамке tk-окна; ввод, размер и заголовок - событием ktterm в гостя
  const S = (window.ktTermS ||= {});
  const bytes = (b) => Uint8Array.from(atob(b), (c) => c.charCodeAt(0));
  const send = (id, d) => kt.emit("ktterm", { id, ...d });
  window.ktTerm = (m) => {
    const t = S[m.id];
    if (m.op === "open") {
      if (t) {
        t.ro.disconnect();
        t.mo.disconnect();
        t.x.dispose();
        t.box.remove();
      }
      const host = document.querySelector(`[data-tk="${CSS.escape(m.host)}"]`);
      if (!host) return 0;
      host.style.position = "relative";
      const box = document.createElement("div");
      box.style.cssText = "position:absolute;inset:0;padding:2px;box-sizing:border-box;overflow:hidden";
      host.append(box);
      const o = term.options; // шрифт и цвета - как у основного терминала
      const x = new Terminal({ fontFamily: o.fontFamily, fontSize: o.fontSize, theme: o.theme, cursorStyle: o.cursorStyle, scrollback: 3000 });
      const fit = new FitAddon.FitAddon();
      x.loadAddon(fit);
      x.open(box);
      if (m.tail) x.write(bytes(m.tail));
      x.onData((d) => send(m.id, { d }));
      x.onResize(({ cols, rows }) => send(m.id, { r: [cols, rows] }));
      x.onTitleChange((title) => send(m.id, { t: title }));
      const refit = () => {
        try {
          if (box.clientWidth && box.clientHeight) fit.fit();
        } catch {}
      };
      const ro = new ResizeObserver(refit);
      ro.observe(box);
      // раскладка рамки (tkinter прислал новую) не должна выбросить экран терминала
      const mo = new MutationObserver(() => box.parentNode !== host && host.append(box));
      mo.observe(host, { childList: true });
      S[m.id] = { x, fit, box, ro, mo };
      refit();
      send(m.id, { r: [x.cols, x.rows] });
      x.focus();
      return 1;
    }
    if (!t) return 0;
    if (m.op === "w") t.x.write(bytes(m.d));
    else if (m.op === "focus") t.x.focus();
    else if (m.op === "close") {
      t.ro.disconnect();
      t.mo.disconnect();
      t.x.dispose();
      t.box.remove();
      delete S[m.id];
    }
    return 1;
  };
  return window.ktTerm(m);
}
