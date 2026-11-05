(m) => {
  const S = (window.ktTkS ||= { w: {}, z: 1, n: 0, q: {} });
  S.term = term;
  S.css ||= document.head.appendChild(document.createElement("style"));
  S.css.textContent = `
.tk-layer{position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:15;pointer-events:none}
.tk-layer>*{pointer-events:auto}
.tk-win{position:absolute;display:flex;flex-direction:column;box-sizing:border-box;width:max-content;background:var(--bg,#000);color:var(--text,#bbb);border:1px solid #444;font:13px/1.4 var(--mono,monospace);max-width:calc(var(--tk-vw,100vw) - 8px);max-height:calc(var(--tk-vh,100vh) - 8px);outline:none}
.tk-win[hidden]{visibility:hidden!important;pointer-events:none!important}
.tk-win [hidden]{display:none!important}
.tk-bar{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:0 0 0 10px;border-bottom:1px solid #222;color:#888;cursor:move;user-select:none;touch-action:none;flex:none;min-height:26px}
.tk-bar span{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.tk-x{background:none;border:0;color:#888;font:16px/1 var(--mono,monospace);padding:5px 10px;cursor:pointer}
.tk-x:hover{color:var(--hi,#eee)}
.tk-fixw>.tk-bar,.tk-fixw>.tk-mb{width:0;min-width:100%;box-sizing:border-box}
.tk-grip{position:absolute;right:0;bottom:0;width:14px;height:14px;z-index:3;cursor:nwse-resize;touch-action:none;background:linear-gradient(135deg,transparent 52%,#777 52%,#777 60%,transparent 60%,transparent 74%,#777 74%,#777 82%,transparent 82%) no-repeat right bottom/12px 12px}
.tk-mb{display:flex;flex-wrap:wrap;border-bottom:1px solid #222;flex:none}
.tk-mb>button,.tk-dd>button{background:none;border:0;color:inherit;font:inherit;padding:2px 10px;cursor:pointer;text-align:left;white-space:pre;flex:none}
.tk-mb>button:hover,.tk-mb>button.on,.tk-dd>button:hover{background:var(--text,#bbb);color:var(--bg,#000)}
.tk-mb>button:disabled,.tk-dd>button:disabled{color:#555;background:none;cursor:default}
.tk-dd{position:absolute;display:flex;flex-direction:column;background:var(--bg,#000);color:var(--text,#bbb);border:1px solid #444;font:13px/1.4 var(--mono,monospace);padding:2px 0;min-width:140px;z-index:100000;box-sizing:border-box;max-width:calc(var(--tk-vw,100vw) - 8px);max-height:calc(var(--tk-vh,100vh) - 8px);overflow:auto}
.tk-dd hr{border:0;border-top:1px solid #333;margin:2px 0;width:100%;flex:none}
.tk-dd .h{color:#777;padding:2px 10px;white-space:pre}
.tk-body{flex:1 1 auto;min-width:0;min-height:0;max-width:100%;overflow:auto;display:flex;flex-direction:column;scrollbar-width:thin}
.tk-empty{min-width:200px;min-height:200px}
.tk-box{position:relative;display:flex;flex-direction:column}
.tk-root{flex:1 1 auto;min-width:min-content}
.tk-cav{display:flex;min-width:min-content}
.tk-vr{flex-direction:column}
.tk-hr{flex-direction:row}
.tk-vr>.tk-pc,.tk-hr>.tk-pc{flex:0 1 auto}
.tk-vr>.tk-cav,.tk-hr>.tk-cav{flex:0 1000 auto}
.tk-vr>.tk-gx,.tk-hr>.tk-gx{flex:1 1000 auto}
.tk-wr{flex-wrap:wrap}
.tk-sash{flex:none;position:relative;background:#555;cursor:col-resize;touch-action:none}
.tk-sash.tk-v{cursor:row-resize}
.tk-sash::after{content:"";position:absolute;inset:-4px}
.tk-wr>.tk-pc,.tk-wr>.tk-cav{flex:1 1 min-content;max-width:max-content}
.tk-wr>.tk-gx{max-width:none}
.tk-pc{display:grid;grid-template-columns:minmax(min-content,auto);box-sizing:border-box;min-width:min-content}
.tk-pc>*{min-width:0;min-height:0;max-height:100%}
.tk-pc>.tk-el{max-width:100%}
.tk-pl{position:absolute;display:flex}
.tk-el{contain:size;contain-intrinsic-size:var(--nw,0px) var(--nh,0px)}
@supports not (contain-intrinsic-size:1px){.tk-el{contain:none;width:var(--nw,auto);height:var(--nh,auto)}}
.tk-probe{max-height:none!important}
.tk-probe>.tk-body{height:auto!important;max-height:none!important;flex:0 0 auto!important}
.tk-probe .tk-cav,.tk-probe .tk-pc,.tk-probe .tk-root{min-height:0!important}
.tk-probe .tk-el{contain-intrinsic-height:var(--pm,var(--nh,0px))!important}
.tk-hid{visibility:hidden;min-width:0!important;overflow:hidden}
.tk-probe .tk-hid{display:none!important}
.tk-label,.tk-btn,.tk-in,.tk-chk,.tk-frame{padding:calc(var(--py) + var(--iy,0px)) calc(var(--px) + var(--ix,0px))}
.tk-frame{--px:0px;--py:0px}
.tk-label{--px:2px;--py:1px;display:flex;align-items:center;justify-content:center;justify-content:safe center;white-space:pre}
.tk-btn{--px:10px;--py:2px;font:inherit;color:var(--hi,#eee);background:var(--bg,#000);border:1px solid #555;cursor:pointer;white-space:pre;display:flex;align-items:center;justify-content:center;border-radius:0}
.tk-btn:hover{border-color:#999}
.tk-btn:active{background:#222}
.tk-btn:disabled{color:#555;border-color:#333;cursor:default}
.tk-in{--px:4px;--py:2px;font:inherit;color:var(--hi,#eee);background:var(--bg,#000);border:1px solid #444;outline:none;border-radius:0;margin:0}
.tk-in:focus{border-color:#888}
.tk-in:disabled,.tk-off{color:#555}
.tk-tx{position:relative;border:1px solid #444;background:var(--bg,#000);color:var(--hi,#eee);--px:4px;--py:2px;overflow:hidden;line-height:1.4}
.tk-tx:focus-within{border-color:#888}
.tk-hl,.tk-ta{position:absolute;inset:0;margin:0;border:0;padding:var(--py) var(--px);font:inherit;line-height:inherit;tab-size:8;white-space:pre-wrap;word-break:break-all;overflow-wrap:anywhere;box-sizing:border-box;scrollbar-gutter:stable;scrollbar-width:thin;overflow:auto;letter-spacing:normal;font-variant-ligatures:none}
.tk-hl{overflow:hidden;pointer-events:none;color:inherit}
.tk-hl>div{min-height:1.4em}
.tk-ta{background:transparent;color:transparent;-webkit-text-fill-color:transparent;caret-color:var(--hi,#eee);resize:none;outline:none}
.tk-ta::selection{background:var(--selbg,rgba(150,150,150,.45))}
.tk-tx.tk-nowrap .tk-hl,.tk-tx.tk-nowrap .tk-ta{white-space:pre;word-break:normal;overflow-wrap:normal}
.tk-tx.tk-wword .tk-hl,.tk-tx.tk-wword .tk-ta{word-break:normal}
.tk-s{background:var(--selbg2,var(--selbg,rgba(150,150,150,.45)))}
.tk-tx:focus-within .tk-s{background:none!important}
.tk-ew{color:transparent}
.tk-emb{position:absolute;z-index:2}
.tk-narrow>.tk-main{left:4px!important;width:calc(var(--tk-vw,100vw) - 8px)}
.tk-narrow>.tk-main>.tk-body{width:auto!important}
.tk-layer>.tk-max{left:0!important;top:0!important;width:var(--tk-vw,100vw);height:var(--tk-vh,100vh);max-width:none;max-height:none}
.tk-max>.tk-body{width:auto!important;height:auto!important}
.tk-max>.tk-grip{display:none}
.tk-chk{--px:2px;--py:1px;display:flex;align-items:center;gap:6px;cursor:pointer;white-space:pre}
.tk-chk input{appearance:none;margin:0;width:11px;height:11px;border:1px solid #888;display:grid;place-content:center;cursor:pointer;flex:none}
.tk-chk input[type=radio]{border-radius:50%}
.tk-chk input:checked::before{content:"";width:5px;height:5px;background:var(--hi,#eee)}
.tk-chk input[type=radio]:checked::before{border-radius:50%}
.tk-noind{border:1px solid transparent}
.tk-noind>input{display:none}
.tk-noind.tk-on{border-color:#888;background:#222}
.tk-scale{display:flex;flex-direction:column;align-items:stretch;padding:1px 2px}
.tk-scale.tk-v{flex-direction:row;align-items:center;gap:4px}
.tk-scale input{accent-color:#999;margin:2px 0}
.tk-scale.tk-v input{writing-mode:vertical-lr;margin:0 2px}
.tk-sv{text-align:center;color:var(--hi,#eee)}
.tk-list{border:1px solid #444;overflow:auto;outline:none;cursor:default;user-select:none;padding:0;scrollbar-width:thin}
.tk-row{padding:0 4px;white-space:pre;min-height:1.4em}
.tk-row.on{background:var(--text,#bbb);color:var(--bg,#000)}
.tk-cv{display:block;position:relative;overflow:auto;scrollbar-width:thin;touch-action:none;user-select:none;-webkit-user-select:none;color:var(--text,#bbb)}
.tk-cv>svg{display:block;position:absolute;left:0;top:0;overflow:hidden;min-width:100%;min-height:100%}
.tk-cvwin{position:absolute;left:0;top:0;width:max-content;display:flex}
.tk-cb{display:flex}
.tk-cb .tk-in{flex:1 1 auto;min-width:0;width:0}
.tk-pg{border:1px solid #444;position:relative;overflow:hidden}
.tk-pg>div{position:absolute;left:0;bottom:0;height:100%;background:var(--text,#bbb)}
.tk-pg.tk-v>div{width:100%}
.tk-pg.tk-run>div{width:30%!important;animation:tk-run 1.2s linear infinite}
@keyframes tk-run{from{left:-30%}to{left:100%}}
.tk-sep{border-top:1px solid #333;margin:3px 0;min-width:1px}
.tk-sep.tk-v{border-top:0;border-left:1px solid #333;margin:0 3px;min-height:1px}
.tk-sb{display:none}
.tk-lf{border:1px solid #333;margin:0;padding:2px 6px 6px;min-width:0;display:flex;flex-direction:column}
.tk-lf>.tk-box{flex:1 1 auto;min-height:0}
.tk-lf>legend{color:#888;padding:0 4px}
.tk-nb{display:flex;flex-direction:column}
.tk-tabs{display:flex;flex-wrap:wrap;border-bottom:1px solid #333}
.tk-tabs>button{background:none;border:0;border-bottom:1px solid transparent;color:#888;font:inherit;padding:2px 12px;cursor:pointer;margin-bottom:-1px}
.tk-tabs>button.on{color:var(--hi,#eee);border-bottom-color:var(--hi,#eee)}
.tk-nbb{flex:1 1 auto;min-height:0;padding:6px 0 0}
.tk-modal{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:#0008;z-index:99999}
.tk-modal>.tk-win{position:relative;min-width:min(260px,calc(var(--tk-vw,100vw) - 16px));max-width:min(480px,calc(var(--tk-vw,100vw) - 16px))}
.tk-modal .tk-bar{cursor:default}
.tk-msg{padding:12px 14px 4px;white-space:pre-wrap}
.tk-din{margin:8px 14px 0}
.tk-btns{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px;padding:12px 14px}
@media (pointer:coarse){.tk-sash::after{inset:-10px}.tk-grip{width:24px;height:24px}.tk-x{padding:8px 14px}.tk-mb>button,.tk-dd>button{padding:6px 12px}.tk-tabs>button{padding:6px 12px}}
`;
  if (!S.layer?.isConnected) S.layer = document.body.appendChild(document.createElement("div"));
  S.layer.className = "tk-layer";
  const NS = "http://www.w3.org/2000/svg";
  const WIN = new Set(["Tk", "Toplevel"]);
  const h = (tag, cls, parent) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (parent) parent.append(e);
    return e;
  };
  const sv = (tag) => document.createElementNS(NS, tag);
  const pair = (v) => (Array.isArray(v) ? v : [v, v]).map((x) => (+x || 0) + "px");
  const hz = (a) => (a === "center" ? "safe center" : a.includes("w") ? "flex-start" : a.includes("e") ? "safe flex-end" : "safe center");
  const vt = (a) => (a === "center" ? "safe center" : a.includes("n") ? "flex-start" : a.includes("s") ? "safe flex-end" : "safe center");
  const al = (st, k, v) => {
    st[k] = v.replace("safe ", "");
    st[k] = v;
  };
  const X11 = "antiquewhite:ffefdb,aquamarine:7fffd4,azure:f0ffff,bisque:ffe4c4,blue:0000ff,brown:ff4040,burlywood:ffd39b,cadetblue:98f5ff,chartreuse:7fff00,chocolate:ff7f24,coral:ff7256,cornsilk:fff8dc,cyan:00ffff,darkgoldenrod:ffb90f,darkolivegreen:caff70,darkorange:ff7f00,darkorchid:bf3eff,darkseagreen:c1ffc1,darkslategray:97ffff,deeppink:ff1493,deepskyblue:00bfff,dodgerblue:1e90ff,firebrick:ff3030,gold:ffd700,goldenrod:ffc125,green:00ff00,honeydew:f0fff0,hotpink:ff6eb4,indianred:ff6a6a,ivory:fffff0,khaki:fff68f,lavenderblush:fff0f5,lemonchiffon:fffacd,lightblue:bfefff,lightcyan:e0ffff,lightgoldenrod:ffec8b,lightpink:ffaeb9,lightsalmon:ffa07a,lightskyblue:b0e2ff,lightsteelblue:cae1ff,lightyellow:ffffe0,magenta:ff00ff,maroon:ff34b3,mediumorchid:e066ff,mediumpurple:ab82ff,mistyrose:ffe4e1,navajowhite:ffdead,olivedrab:c0ff3e,orange:ffa500,orangered:ff4500,orchid:ff83fa,palegreen:9aff9a,paleturquoise:bbffff,palevioletred:ff82ab,peachpuff:ffdab9,pink:ffb5c5,plum:ffbbff,purple:9b30ff,red:ff0000,rosybrown:ffc1c1,royalblue:4876ff,salmon:ff8c69,seagreen:54ff9f,seashell:fff5ee,sienna:ff8247,skyblue:87ceff,slateblue:836fff,slategray:c6e2ff,snow:fffafa,springgreen:00ff7f,steelblue:63b8ff,tan:ffa54f,thistle:ffe1ff,tomato:ff6347,turquoise:00f5ff,violetred:ff3e96,wheat:ffe7ba,yellow:ffff00,lightgoldenrod0:eedd82,lightslateblue0:8470ff,navyblue0:000080,violetred0:d02090";
  const X11M = [1, 0.932, 0.804, 0.545];
  const color = (v) => {
    if (!v) return "";
    v = String(v).replace(/\s+/g, "").toLowerCase();
    const g = v.match(/^gr[ae]y(\d+)$/);
    if (g) return `hsl(0 0% ${g[1]}%)`;
    const m = v.match(/^([a-z]+?)([1-4]?)$/);
    if (m && !CSS.supports("color", v)) {
      S.x11 ||= Object.fromEntries(X11.split(",").map((x) => x.split(":")));
      const h = S.x11[m[1] + (m[2] ? "" : "0")] || (m[2] && S.x11[m[1]]);
      if (h) return "rgb(" + [0, 2, 4].map((i) => Math.round(parseInt(h.substr(i, 2), 16) * X11M[(m[2] || 1) - 1])).join(",") + ")";
    }
    return v.startsWith("system") ? "" : v;
  };
  S.rgb = (v) => {
    const cx = (S.cx ||= document.createElement("canvas").getContext("2d"));
    const sys = /^system/i.test(v) && getComputedStyle(S.layer).getPropertyValue(/text/i.test(v) ? "--hi" : "--bg").trim();
    const c = /^system/i.test(v) ? sys || (/text/i.test(v) ? "#eee" : "#000") : color(v);
    if (!c) return null;
    for (const p of ["#010203", "#030201"]) {
      cx.fillStyle = p;
      cx.fillStyle = c;
      if (cx.fillStyle !== p) break;
      if (p === "#030201") return null;
    }
    const x = /^#(..)(..)(..)$/.exec(cx.fillStyle);
    return x ? x.slice(1).map((h) => parseInt(h, 16)) : null;
  };
  const light = (c) => {
    const cx = (S.cx ||= document.createElement("canvas").getContext("2d"));
    cx.fillStyle = "#000";
    cx.fillStyle = c;
    const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(cx.fillStyle);
    return !!m && 0.299 * parseInt(m[1], 16) + 0.587 * parseInt(m[2], 16) + 0.114 * parseInt(m[3], 16) > 150;
  };
  const FAM = {
    "": "var(--mono,monospace)", tkdefaultfont: "var(--mono,monospace)", tkfixedfont: "var(--mono,monospace)", tktextfont: "var(--mono,monospace)",
    tkheadingfont: "var(--mono,monospace)", tkcaptionfont: "var(--mono,monospace)", courier: '"Courier New",var(--mono,monospace)',
    helvetica: "Helvetica,Arial,sans-serif", arial: "Arial,Helvetica,sans-serif", times: '"Times New Roman",Times,serif',
    monospace: "var(--mono,monospace)", "sans-serif": "sans-serif", serif: "serif",
  };
  const font = (v) => {
    const a = Array.isArray(v) ? v.map(String) : (String(v).match(/\{[^}]*\}|\S+/g) || []).map((x) => x.replace(/^\{|\}$/g, ""));
    const fam = a[0] || "", size = +a[1] || 0, st = a.slice(2).join(" ").toLowerCase();
    const f = FAM[fam.toLowerCase()] ?? `"${fam}",var(--mono,monospace)`;
    const px = size > 0 ? Math.round((size * 4) / 3) : size < 0 ? -size : 13;
    return [`${/italic/.test(st) ? "italic " : ""}${/bold/.test(st) ? "bold " : ""}${px}px ${f}`, /underline/.test(st) ? "underline" : /overstrike/.test(st) ? "line-through" : ""];
  };
  const CUR = { hand1: "pointer", hand2: "pointer", watch: "wait", xterm: "text", cross: "crosshair", crosshair: "crosshair", tcross: "crosshair", fleur: "move", arrow: "default", question_arrow: "help", plus: "cell", sb_h_double_arrow: "ew-resize", sb_v_double_arrow: "ns-resize" };
  const RELIEF = { raised: "outset", sunken: "inset", groove: "groove", ridge: "ridge", solid: "solid" };
  const KEYS = { Enter: "Return", ArrowLeft: "Left", ArrowRight: "Right", ArrowUp: "Up", ArrowDown: "Down", " ": "space", Backspace: "BackSpace", Escape: "Escape", Tab: "Tab", Delete: "Delete", Home: "Home", End: "End", PageUp: "Prior", PageDown: "Next", Insert: "Insert", Shift: "Shift_L", Control: "Control_L", Alt: "Alt_L", Meta: "Meta_L", CapsLock: "Caps_Lock" };
  const CHAR = { Enter: "\r", Tab: "\t", Backspace: "\b", Escape: "\x1b", Delete: "\x7f" };

  const MOVES = 32, STALL = 2000;
  const Q = (s) => (S.q[s] ||= { e: [], v: {}, t: 0, due: 0, k: 0, l: 0, n: 0, w: 0 });
  const mv = (it) => it[1] === "ev" && it[2].t === "move";
  const flush = (s) => {
    const q = Q(s);
    clearTimeout(q.t);
    q.t = 0;
    if (!q.e.length && !Object.keys(q.v).length) return;
    const m = { s, e: q.e, v: q.v };
    if (q.k && q.e.some(mv)) {
      m.n = ++q.n;
      q.w = Date.now();
    }
    kt.emit("tk", m);
    q.e = [];
    q.v = {};
  };
  const ack = (s, n, l) => {
    const q = Q(s);
    q.k = 1;
    q.l = l ? 1 : 0;
    if (!q.w || n !== q.n) return;
    q.w = 0;
    if (q.e.length) later(s, 0);
  };
  const later = (s, ms) => {
    const q = Q(s), due = Date.now() + ms;
    if (q.t && q.due <= due) return;
    clearTimeout(q.t);
    q.due = due;
    q.t = setTimeout(() => flush(s), ms);
  };
  const push = (w, kind, x, co) => {
    const q = Q(w.s), last = q.e[q.e.length - 1], it = x === undefined ? [w.id, kind] : [w.id, kind, x], m = mv(it);
    if (m && q.l) co = true;
    if (co && last && last[0] === w.id && last[1] === kind && (kind !== "ev" || last[2].t === x.t)) q.e.pop();
    q.e.push(it);
    if (m) {
      let i = q.e.length - 1;
      while (i > 0 && q.e[i - 1][0] === w.id && mv(q.e[i - 1])) i--;
      if (q.e.length - i > MOVES) q.e.splice(i, 1);
      if (q.w && Date.now() - q.w < STALL) return;
    }
    later(w.s, co || m ? 30 : 0);
  };
  const dirty = (w, v) => {
    Q(w.s).v[w.id] = v;
    later(w.s, 200);
  };
  const top = (w) => S.w[w.top];
  const want = (w, k) => w.b.has(k) || !!top(w)?.b.has(k);
  const at = (e) => {
    const t = e.target.closest?.("[data-tk]");
    return t && S.w[t.dataset.tk];
  };
  const mods = (e) => (e.shiftKey ? 1 : 0) | (e.getModifierState?.("CapsLock") ? 2 : 0) | (e.ctrlKey ? 4 : 0) | (e.altKey ? 8 : 0) | (e.metaKey ? 32 : 0);
  const keyd = (e, kind) => ({ t: kind, x: 0, y: 0, m: mods(e), k: KEYS[e.key] || e.key, c: e.key.length === 1 ? e.key : CHAR[e.key] || "", kc: e.keyCode });

  const fire = (e, kind) => {
    const w = at(e);
    if (!w) return;
    if (e.tkDone && (kind === "key" || kind === "keyup")) return;
    if (kind === "move") {
      if (!want(w, "move") && !(e.buttons && want(w, "drag"))) return;
    } else if (!want(w, kind)) return;
    const d = kind === "key" || kind === "keyup" ? keyd(e, kind) : { t: kind, x: 0, y: 0, m: mods(e) };
    if (kind !== "key" && kind !== "keyup" && e.clientX !== undefined) {
      const r = w.el.getBoundingClientRect();
      d.x = Math.round(e.clientX - r.left);
      d.y = Math.round(e.clientY - r.top);
      d.X = Math.round(e.clientX);
      d.Y = Math.round(e.clientY);
      d.b = e.buttons || 0;
    }
    if (kind === "down" || kind === "up" || kind === "dbl") d.n = [1, 2, 3][e.button] || 1;
    if (kind === "down" && !w.in && w.k !== "Button" && (want(w, "drag") || want(w, "up"))) {
      try { w.el.setPointerCapture(e.pointerId); } catch {}
    }
    if (kind === "wheel") {
      d.d = e.deltaY < 0 ? 120 : -120;
      if (w.k === "Text") e.preventDefault();
    }
    if (kind === "key" && (e.ctrlKey || e.altKey || e.metaKey) && e.key.length === 1 && !(w.in && "cvxaz".includes(e.key.toLowerCase()))) e.preventDefault();
    const it = e.target.closest?.("[data-ti]");
    if (it) d.i = +it.dataset.ti;
    if (w.k === "Text") txd(w, d);
    if (w.k === "Canvas") {
      d.sx = Math.round(w.el.scrollLeft - w.t[0]);
      d.sy = Math.round(w.el.scrollTop - w.t[1]);
    }
    push(w, "ev", d, kind === "move" && !d.b);
  };
  const hover = (win, e) => {
    const w = e && at(e), o = win.hv;
    if (w === o) return;
    win.hv = w;
    if (o && S.w[o.id] && want(o, "leave")) push(o, "ev", { t: "leave", x: 0, y: 0, m: 0 });
    if (w && want(w, "enter")) push(w, "ev", { t: "enter", x: 0, y: 0, m: 0 });
  };
  const listen = (win, el) => {
    const on = (type, kind) => el.addEventListener(type, (e) => fire(e, kind));
    on("pointerdown", "down");
    on("pointerup", "up");
    on("dblclick", "dbl");
    on("pointermove", "move");
    on("keydown", "key");
    on("keyup", "keyup");
    on("wheel", "wheel");
    on("focusin", "fin");
    on("focusout", "fout");
    el.addEventListener("pointerover", (e) => hover(win, e));
    el.addEventListener("pointerleave", () => hover(win, null));
    el.addEventListener("contextmenu", (e) => {
      const w = at(e);
      if (w && want(w, "down")) e.preventDefault();
    });
  };
  const observe = (w) => {
    if (w.ro || !w.el) return;
    w.ro = new ResizeObserver(() => {
      const r = (w.body || w.el).getBoundingClientRect();
      if (!r.width && !r.height) return;
      push(w, "ev", { t: "conf", x: 0, y: 0, m: 0, w: Math.round(r.width), h: Math.round(r.height) }, true);
    });
    w.ro.observe(w.body || w.el);
  };

  const lift = (el) => {
    if (el.style.zIndex !== "100000") el.style.zIndex = ++S.z;
  };
  const raise = (w, seen = new Set()) => {
    if (!w?.el || seen.has(w)) return;
    seen.add(w);
    lift(w.el);
    for (const t of Object.values(S.w)) {
      if (!WIN.has(t.k) || t.s !== w.s) continue;
      if (t.p.transient === w.id || (t.p.bare && S.w[t.pa]?.top === w.id)) raise(t, seen);
    }
  };
  const vp = () => {
    const v = window.visualViewport;
    return v ? { x: v.offsetLeft, y: v.offsetTop, w: v.width, h: v.height } : { x: 0, y: 0, w: innerWidth, h: innerHeight };
  };
  const fit = (el) => {
    if (!el.isConnected) return;
    const r = el.getBoundingClientRect(), v = vp();
    if (el.offsetLeft + r.width > v.w) el.style.left = Math.max(0, v.w - r.width - 4) + "px";
    if (el.offsetTop + r.height > v.h) el.style.top = Math.max(0, v.h - r.height - 4) + "px";
  };
  S.view = () => {
    const v = vp(), st = S.layer.style;
    st.left = v.x + "px";
    st.top = v.y + "px";
    st.width = v.w + "px";
    st.height = v.h + "px";
    st.setProperty("--tk-vw", v.w + "px");
    st.setProperty("--tk-vh", v.h + "px");
    S.layer.classList.toggle("tk-narrow", v.w <= 520);
    for (const el of S.layer.children) if (el.classList.contains("tk-win") || el.classList.contains("tk-dd")) fit(el);
  };
  if (!S.vl) {
    S.vl = 1;
    const f = () => S.view();
    window.visualViewport?.addEventListener("resize", f);
    window.visualViewport?.addEventListener("scroll", f);
    addEventListener("resize", f);
  }
  S.view();
  const drag = (w) => {
    const { bar, el } = w;
    bar.onpointerdown = (e) => {
      if (e.target.closest("button") || el.classList.contains("tk-max")) return;
      const dx = e.clientX - el.offsetLeft, dy = e.clientY - el.offsetTop;
      bar.setPointerCapture(e.pointerId);
      bar.onpointermove = (e) => {
        const v = vp();
        w.moved = 1;
        el.style.left = Math.max(60 - el.offsetWidth, Math.min(v.w - 60, e.clientX - dx)) + "px";
        el.style.top = Math.max(0, Math.min(v.h - 30, e.clientY - dy)) + "px";
      };
      bar.onpointerup = bar.onpointercancel = () => (bar.onpointermove = null);
    };
  };
  const grip = (w) => {
    const rs = w.p.rs;
    w.grip.hidden = !!w.p.bare || (!!rs && !rs[0] && !rs[1]);
    w.el.classList.toggle("tk-main", !w.p.bare && !w.p.transient && (!rs || !!rs[0]));
  };
  const resize = (w) => {
    const g = w.grip;
    g.onpointerdown = (e) => {
      e.preventDefault();
      e.stopPropagation();
      const r = w.body.getBoundingClientRect(), x = e.clientX, y = e.clientY, rs = w.p.rs || [1, 1];
      g.setPointerCapture(e.pointerId);
      g.onpointermove = (e) => {
        const us = (w.us ||= [null, null]);
        w.moved = 1;
        if (rs[0]) us[0] = Math.max(80, Math.round(r.width + e.clientX - x));
        if (rs[1]) us[1] = Math.max(24, Math.round(r.height + e.clientY - y));
        sizeOf(w);
      };
      g.onpointerup = g.onpointercancel = () => {
        g.onpointermove = null;
        const a = w.body.getBoundingClientRect(), us = w.us;
        if (!us) return;
        if (us[0]) us[0] = Math.min(us[0], Math.round(a.width));
        if (us[1]) us[1] = Math.min(us[1], Math.round(a.height));
        sizeOf(w);
      };
    };
  };
  const refocus = () => {
    if (S.layer.querySelector(".tk-win") || matchMedia("(pointer: coarse)").matches) return;
    S.term?.focus?.();
  };
  const closeDrop = () => {
    S.dd?.remove();
    S.dd = null;
    S.ddb?.classList.remove("on");
    S.ddb = null;
    if (S.ddc) document.removeEventListener("pointerdown", S.ddc, true);
    S.ddc = null;
  };
  const menuFill = (d, m, ind) => {
    for (const [i, it] of (m.p.items || []).entries()) {
      if (it.t === "s") {
        h("hr", "", d);
        continue;
      }
      if (it.t === "m") {
        h("div", "h", d).textContent = ind + (it.label || "");
        if (S.w[it.sub]) menuFill(d, S.w[it.sub], ind + "  ");
        continue;
      }
      const b = h("button", "", d);
      const mark = it.t === "k" ? (it.on ? "✓ " : "  ") : it.t === "r" ? (it.on ? "• " : "  ") : "";
      b.textContent = ind + mark + (it.label || "") + (it.acc ? "   " + it.acc : "");
      b.disabled = it.state === "disabled";
      b.onclick = () => {
        closeDrop();
        push(m, "cmd", i);
      };
    }
  };
  const drop = (m, b, x, y) => {
    closeDrop();
    if (!m) return;
    const d = (S.dd = h("div", "tk-dd", S.layer));
    const r = b?.getBoundingClientRect(), v = vp();
    d.style.left = (r ? r.left : x) - v.x + "px";
    d.style.top = (r ? r.bottom : y) - v.y + "px";
    if (b) b.classList.add("on");
    S.ddb = b;
    menuFill(d, m, "");
    requestAnimationFrame(() => fit(d));
    setTimeout(() => document.addEventListener("pointerdown", (S.ddc = (e) => !d.contains(e.target) && closeDrop()), true));
  };
  const menus = (s) => {
    for (const w of Object.values(S.w)) {
      if (w.s !== s || !WIN.has(w.k)) continue;
      const m = S.w[w.p.menu];
      w.mb.replaceChildren();
      w.mb.hidden = !m;
      if (!m) continue;
      for (const [i, it] of (m.p.items || []).entries()) {
        if (it.t === "s") continue;
        const b = h("button", "", w.mb);
        b.textContent = it.label || "";
        b.disabled = it.state === "disabled";
        b.onclick = () => (it.t === "m" ? (S.ddb === b ? closeDrop() : drop(S.w[it.sub], b)) : push(m, "cmd", i));
      }
    }
  };

  const fmt = (w, v) => {
    const r = +w.p.res || 1, d = (String(r).split(".")[1] || "").length;
    return d ? v.toFixed(d) : String(Math.round(v));
  };
  const prog = (w) => {
    const v = w.p.orient === "vertical", f = (Math.max(0, Math.min(1, (+w.p.value || 0) / (+w.p.max || 100))) * 100).toFixed(2) + "%";
    w.el.classList.toggle("tk-v", v);
    w.fill.style.width = v ? "" : f;
    w.fill.style.height = v ? f : "";
  };
  const rows = (w) => {
    const sel = new Set(w.p.sel || []);
    for (const r of w.el.children) r.classList.toggle("on", sel.has(+r.dataset.i));
  };
  const pick = (w, i, e) => {
    if (w.p.state === "disabled") return;
    const mode = w.p.selectmode || "browse";
    let s = new Set(w.p.sel || []);
    if (mode === "multiple" || (mode === "extended" && (e.ctrlKey || e.metaKey))) s.has(i) ? s.delete(i) : s.add(i);
    else if (mode === "extended" && e.shiftKey && w.anc != null) {
      s = new Set();
      for (let j = Math.min(w.anc, i); j <= Math.max(w.anc, i); j++) s.add(j);
    } else s = new Set([i]);
    if (!e.shiftKey) w.anc = i;
    w.p.sel = [...s].sort((a, b) => a - b);
    rows(w);
    dirty(w, w.p.sel);
    push(w, "sel");
  };
  const combo = (w) => {
    const p = w.p, ro = !!p.ro;
    if (!w.in || w.rdo !== ro) {
      w.el.replaceChildren();
      w.rdo = ro;
      w.in = h(ro ? "select" : "input", "tk-in", w.el);
      if (!ro) {
        w.dl = h("datalist", "", w.el);
        w.dl.id = "tkdl-" + w.id.replace(/\W/g, "-");
        w.in.setAttribute("list", w.dl.id);
        w.in.spellcheck = false;
        w.in.autocomplete = "off";
      }
      w.in.oninput = () => {
        dirty(w, w.in.value);
        if (w.rdo || (w.p.items || []).map(String).includes(w.in.value)) push(w, "sel");
      };
      size(w);
    }
    const opts = (p.items || []).map((v) => {
      const o = h("option");
      o.value = o.textContent = v;
      return o;
    });
    (ro ? w.in : w.dl).replaceChildren(...opts);
    w.in.value = p.value ?? "";
  };
  const val = (w, v) => {
    if (w.k === "Scale") {
      w.in.value = v;
      w.vl.textContent = fmt(w, +w.in.value);
    } else if (w.k === "Progressbar") prog(w);
    else if (w.in && "value" in w.in && w.in.value !== String(v)) w.in.value = v;
  };
  const EL = { Text: [48, 36], Entry: [40, 0], Spinbox: [40, 0], Combobox: [40, 0], Listbox: [40, 36], Canvas: [24, 24], Progressbar: [16, 0] };
  const mins = (w) => {
    const m = EL[w.k];
    if (!m) return [0, 0];
    if (w.k !== "Canvas") return m;
    return [+(w.p.width ?? 378) > 64 ? m[0] : 0, +(w.p.height ?? 265) > 64 ? m[1] : 0];
  };
  const nat = (w, nw, nh) => {
    const st = w.el.style, mh = mins(w)[1];
    w.nw = nw;
    w.nh = nh;
    st.setProperty("--nw", nw);
    st.setProperty("--nh", nh);
    if (mh) st.setProperty("--pm", `min(${nh}, ${mh}px)`);
    else st.removeProperty("--pm");
    w.el.classList.toggle("tk-ve", !!mh);
  };
  const pcMin = (w) => {
    const c = w.pc;
    if (!EL[w.k] || !c?.classList.contains("tk-pc")) return;
    const [mw, mh] = mins(w);
    c.style.gridTemplateColumns = mw ? `minmax(min(${w.nw}, ${mw}px), auto)` : "";
    c.style.minHeight = mh ? `calc(min(${w.nh}, ${mh}px) + ${c.pv})` : "";
  };
  const cvView = (w) => {
    const el = w.el, sr = w.p.sr || [0, 0, 0, 0], t = w.t.slice();
    for (const i of [0, 1]) {
      const a = sr[i], b = sr[i + 2], v = i ? el.clientHeight : el.clientWidth, o = w.org[i];
      if (!v) continue;
      if (b - a > v) {
        t[i] = -a;
        el[i ? "scrollTop" : "scrollLeft"] = Math.max(a, Math.min(b - v, o)) - a;
        continue;
      }
      const left = o - a, right = b - (o + v);
      t[i] = -(b > a && left < 0 && right > 0 ? o + Math.min(-left, right) : b > a && right < 0 && left > 0 ? o - Math.min(left, -right) : o);
    }
    w.t = t;
    w.g.setAttribute("transform", `translate(${t[0]},${t[1]})`);
  };
  const size = (w) => {
    sizeOf(w);
    const el = w.el;
    if (!el || WIN.has(w.k)) return;
    const st = el.style;
    if ((w.fx || w.k === "Button") && st.width) {
      st.minWidth = st.width;
      st.width = "";
    } else st.minWidth = "";
    if (w.fy && st.height) {
      st.minHeight = st.height;
      st.height = "";
    } else st.minHeight = "";
    pcMin(w);
  };
  const sizeOf = (w) => {
    const p = w.p, k = w.k;
    if (WIN.has(k)) {
      const g = p.geo || {}, b = w.body.style, us = w.us || [];
      const bw = us[0] ?? g.w, bh = us[1] ?? g.h;
      b.width = bw ? bw + "px" : "";
      b.height = bh ? bh + "px" : "";
      w.el.classList.toggle("tk-fixw", !!bw);
      w.body.classList.toggle("tk-empty", !w.box.children.length && !bw);
      return;
    }
    if (!w.el) return;
    const st = w.el.style;
    if (k === "Canvas") {
      const cw = +(p.width ?? 378), ch = +(p.height ?? 265), sr = p.sr || [0, 0, 0, 0];
      nat(w, cw + "px", ch + "px");
      w.svg.setAttribute("width", Math.max(1, sr[2] - sr[0]));
      w.svg.setAttribute("height", Math.max(1, sr[3] - sr[1]));
      cvView(w);
      return;
    }
    if (k === "Text") return nat(w, `calc(${p.width || 80}ch + 2 * var(--px, 4px) + 16px)`, `calc(${(p.height || 24) * 1.4}em + 2 * var(--py, 2px))`);
    if (k === "Entry" || k === "Spinbox") return nat(w, (p.width || 20) + "ch", "1.4em");
    if (k === "Combobox") return nat(w, `calc(${p.width || 20}ch + 10px)`, "calc(1.4em + 6px)");
    if (k === "Listbox") return nat(w, (p.width || 20) + "ch", (p.height || 10) * 1.4 + "em");
    if (w.box) {
      const kids = !!w.L && (w.L.p?.length || w.L.g?.length || w.L.n?.length);
      const fix = (!kids || w.L.prop === false) && !!(p.width || p.height);
      w.el.classList.toggle("tk-el", fix);
      if (fix) nat(w, (p.width || 0) + "px", (p.height || 0) + "px");
      st.overflow = fix && kids ? "hidden" : "";
      return;
    }
    if (k === "Scale") {
      const v = p.orient !== "horizontal", n = (p.length || 100) + "px";
      w.el.classList.toggle("tk-v", v);
      w.in.style.width = v ? "" : n;
      w.in.style.height = v ? n : "";
      return;
    }
    if (k === "Progressbar") {
      const n = (p.length || 100) + "px";
      return p.orient === "vertical" ? nat(w, "8px", n) : nat(w, n, "8px");
    }
    if (k === "Separator") return w.el.classList.toggle("tk-v", p.orient === "vertical");
    st.width = p.width ? p.width + "ch" : "";
    st.height = p.height ? p.height * 1.4 + "em" : "";
  };
  const border = (w) => {
    const { relief: r, bd } = w.p, st = (w.body || w.el).style;
    const own = ["Button", "Entry", "Text", "Listbox", "Spinbox", "LabelFrame"].includes(w.k);
    if (r === "flat" || bd === 0) st.border = bd ? `${bd}px solid transparent` : "0";
    else if (RELIEF[r]) st.border = `${Math.max(1, bd ?? 1)}px ${RELIEF[r]} #666`;
    else if (bd != null) {
      if (own) st.borderWidth = bd + "px";
      else st.border = `${bd}px solid transparent`;
    }
  };
  const setImage = (w, name) => {
    const el = w.el;
    if (!el || !["Label", "Button", "Checkbutton", "Radiobutton"].includes(w.k)) return;
    if (!w.tx) {
      const t = h("span");
      t.textContent = el.textContent;
      el.replaceChildren(t);
      w.tx = t;
    }
    if (!name) {
      w.im?.remove();
      w.im = null;
      w.tx.hidden = false;
      return;
    }
    if (!w.im) {
      w.im = document.createElement("img");
      w.im.style.display = "block";
      w.tx.before(w.im);
    }
    const im = (S.img ||= {})[name];
    w.im.dataset.img = name;
    if (im) {
      w.im.src = im.u;
      w.im.width = im.w;
      w.im.height = im.h;
    }
    const c = w.p.compound || "none";
    w.tx.hidden = c === "none";
    el.style.flexDirection = c === "top" ? "column" : c === "bottom" ? "column-reverse" : c === "right" ? "row-reverse" : "";
    el.style.gap = c !== "none" ? "4px" : "";
  };
  const LATE = ["items", "sel", "value", "on"];
  const apply = (w, p) => {
    Object.assign(w.p, p);
    const el = w.el;
    if (!el) return;
    const st = el.style;
    for (const [k, v] of Object.entries(p)) {
      switch (k) {
        case "text":
          if (w.k === "Text") { txSet(w, v); txDirty(w); break; }
          if (w.k === "LabelFrame") w.lg.textContent = v;
          else (w.tx || el).textContent = v;
          break;
        case "title": w.ttl.textContent = v; break;
        case "image": case "compound": setImage(w, w.p.image); break;
        case "bg": {
          const t = w.body || el;
          t.style.background = color(v);
          if (!w.p.fg) t.style.color = v && light(color(v)) ? "#000" : "";
          break;
        }
        case "fg": st.color = color(v); break;
        case "font": {
          const [f, d] = font(v);
          st.font = f;
          st.lineHeight = "1.4";
          st.textDecoration = d;
          if (w.k === "Text") {
            w.cw = 0;
            txDirty(w);
          }
          break;
        }
        case "relief": case "bd": border(w); break;
        case "padx": st.setProperty("--px", (+v || 0) + "px"); break;
        case "pady": st.setProperty("--py", (+v || 0) + "px"); break;
        case "padding": st.padding = (Array.isArray(v) ? v : [v]).map((x) => (+x || 0) + "px").join(" "); break;
        case "anchor": al(st, "justifyContent", hz(v)); al(st, "alignItems", vt(v)); break;
        case "justify": (w.in || el).style.textAlign = v; break;
        case "wraplength": st.whiteSpace = +v ? "pre-wrap" : ""; st.maxWidth = +v ? v + "px" : ""; break;
        case "cursor": st.cursor = CUR[v] || v; break;
        case "state": {
          const t = w.in || el, off = v === "disabled";
          if ("disabled" in t && t.tagName !== "LABEL") t.disabled = off;
          if ("readOnly" in t) t.readOnly = v === "readonly";
          if (w.k === "Combobox" && w.in.tagName === "SELECT") w.in.disabled = off;
          el.classList.toggle("tk-off", off);
          break;
        }
        case "group": w.in.name = v; break;
        case "ind": el.classList.toggle("tk-noind", !v); break;
        case "show": w.in.type = v ? "password" : "text"; break;
        case "wrap":
          if (w.k === "Text") {
            el.classList.toggle("tk-nowrap", v === "none");
            el.classList.toggle("tk-wword", v === "word");
            w.in.wrap = v === "none" ? "off" : "soft";
            txDirty(w);
          } else {
            st.whiteSpace = v === "none" ? "pre" : "pre-wrap";
            el.wrap = v === "none" ? "off" : "soft";
          }
          break;
        case "tags":
          for (const [n, r] of Object.entries(v)) {
            if (r === null) delete w.tg[n];
            else w.tg[n] = r.slice();
          }
          txDirty(w);
          break;
        case "tcfg": w.tc = v; txDirty(w); break;
        case "torder": w.to = v; txDirty(w); break;
        case "sel": case "ins": w[k] = v; break;
        case "ver": w.ver = v; break;
        case "caret": w.in.style.caretColor = color(v); break;
        case "selbg": el.style.setProperty("--selbg", `color-mix(in srgb, ${color(v)} 55%, transparent)`); break;
        case "selbg2": el.style.setProperty("--selbg2", color(v)); break;
        case "wins": w.wins = v; txDirty(w); break;
        case "zoom": el.classList.toggle("tk-max", !!v); break;
        case "from": case "to": case "res": {
          const a = +(w.p.from ?? 0), b = +(w.p.to ?? 100);
          w.in.min = Math.min(a, b);
          w.in.max = Math.max(a, b);
          w.in.step = +w.p.res > 0 ? w.p.res : "any";
          break;
        }
        case "label": w.lb.textContent = v; w.lb.hidden = !v; break;
        case "showvalue": w.vl.hidden = !v; break;
        case "orient": case "length": size(w); if (w.k === "Progressbar") prog(w); if (w.L?.pw) layout(w, w.L); break;
        case "sash": if (w.L?.pw) layout(w, w.L); break;
        case "sr": size(w); break;
        case "max": case "mode": prog(w); break;
        case "run": el.classList.toggle("tk-run", !!v); break;
        case "b": w.b = new Set(v); if (v.includes("conf")) observe(w); break;
        case "geo": {
          if (v?.w || v?.h) w.us = null;
          size(w);
          if (v?.x != null) st.left = v.x + "px";
          if (v?.y != null) st.top = v.y + "px";
          S.fresh?.push(el);
          break;
        }
        case "rs": grip(w); break;
        case "minsize": w.body.style.minWidth = v[0] ? v[0] + "px" : ""; w.body.style.minHeight = v[1] ? v[1] + "px" : ""; break;
        case "maxsize": w.body.style.maxWidth = v[0] ? v[0] + "px" : ""; w.body.style.maxHeight = v[1] ? v[1] + "px" : ""; break;
        case "hide": el.hidden = !!v; if (!v && WIN.has(w.k)) S.fresh?.push(el); break;
        case "bare": w.bar.hidden = !!v; grip(w); break;
        case "topmost": st.zIndex = v ? 100000 : ++S.z; break;
        case "transient": lift(el); grip(w); break;
        case "alpha": st.opacity = v; break;
        case "ro": combo(w); break;
        case "width": case "height": size(w); break;
      }
    }
    if ("items" in p) {
      if (w.k === "Listbox") {
        el.replaceChildren(...p.items.map((t, i) => {
          const r = h("div", "tk-row");
          r.dataset.i = i;
          r.textContent = t;
          return r;
        }));
        rows(w);
      } else if (w.k === "Combobox") combo(w);
    }
    if ("sel" in p && w.k === "Listbox") rows(w);
    if (w.k === "Text" && ("sel" in p || "ins" in p || "text" in p)) txSelApply(w);
    if ("value" in p) val(w, p.value);
    if ("on" in p) {
      w.in.checked = !!p.on;
      el.classList.toggle("tk-on", !!p.on);
    }
  };
  const MODK = new Set(["Shift", "Control", "Alt", "Meta", "CapsLock", "AltGraph", "OS", "Hyper", "Super", "Fn"]);
  const cpMap = (t) => {
    const m = [];
    let u = 0;
    for (const ch of t) {
      m.push(u);
      u += ch.length;
    }
    m.push(u);
    return m;
  };
  const U = (w, p) => {
    if (!w.astral) return Math.max(0, Math.min(p, w.txt.length));
    if (!w.cm) w.cm = cpMap(w.txt);
    return w.cm[Math.max(0, Math.min(p, w.cm.length - 1))];
  };
  const CP = (w, u) => {
    if (!w.astral) return u;
    let c = 0;
    for (let i = 0; i < u && i < w.txt.length; i++) {
      const x = w.txt.charCodeAt(i);
      if (x < 0xdc00 || x > 0xdfff) c++;
    }
    return c;
  };
  const txd = (w, d) => {
    const ta = w.in;
    d.ss = CP(w, ta.selectionStart);
    d.se = CP(w, ta.selectionEnd);
    d.sd = ta.selectionDirection === "backward" ? "b" : "f";
    d.sv = w.ver;
    return d;
  };
  const txSet = (w, t) => {
    w.txt = t;
    w.astral = /[\uD800-\uDFFF]/.test(t);
    w.cm = null;
    w.in.value = t;
  };
  const rins = (r, pos, n) => {
    for (let i = 0; i < r.length; i += 2) {
      if (r[i] >= pos) {
        r[i] += n;
        r[i + 1] += n;
      } else if (r[i + 1] > pos) r[i + 1] += n;
    }
  };
  const rdel = (r, a, b) => {
    const n = b - a, out = [];
    for (let i = 0; i < r.length; i += 2) {
      const s = r[i] <= a ? r[i] : r[i] <= b ? a : r[i] - n;
      const e = r[i + 1] <= a ? r[i + 1] : r[i + 1] <= b ? a : r[i + 1] - n;
      if (e > s) {
        if (out.length && out[out.length - 1] >= s) out[out.length - 1] = Math.max(out[out.length - 1], e);
        else out.push(s, e);
      }
    }
    return out;
  };
  const txEdits = (w, list) => {
    for (const [p, n, s] of list) {
      const a = U(w, p), b = U(w, p + n);
      w.in.setRangeText(s, a, b, "preserve");
      w.txt = w.txt.slice(0, a) + s + w.txt.slice(b);
      if (!w.astral && /[\uD800-\uDFFF]/.test(s)) w.astral = true;
      w.cm = null;
      const len = w.astral ? [...s].length : s.length;
      for (const k in w.tg) {
        if (n) w.tg[k] = rdel(w.tg[k], p, p + n);
        if (len) rins(w.tg[k], p, len);
      }
    }
    txDirty(w);
  };
  const txSelApply = (w) => {
    const sel = w.sel, a = sel ? sel[0] : w.ins, b = sel ? sel[1] : w.ins;
    w.applying = (w.applying || 0) + 1;
    try { w.in.setSelectionRange(U(w, a), U(w, b), sel && w.ins === sel[0] && a !== b ? "backward" : "forward"); } catch {}
    setTimeout(() => w.applying--);
  };
  const txSelReport = (w) => {
    if (w.applying || !S.w[w.id]) return;
    const d = txd(w, { t: "tsel", x: 0, y: 0, m: 0 }), sel = w.sel;
    if (sel ? d.ss === sel[0] && d.se === sel[1] : d.ss === d.se && d.ss === w.ins) return;
    push(w, "ev", d, true);
  };
  const txDirty = (w) => {
    if (w.rq) return;
    w.rq = requestAnimationFrame(() => {
      w.rq = 0;
      if (S.w[w.id]) txRender(w);
    });
  };
  const esc = (s) => s.replace(/[&<>"]/g, (c) => (c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : "&quot;"));
  const tstyle = (c) => {
    if (!c) return "";
    let s = "";
    const on = (v) => v && v !== "0" && v !== "false";
    if (c.foreground) s += "color:" + color(c.foreground) + ";";
    if (c.background) s += "background:" + color(c.background) + ";";
    if (c.font) {
      const f = font(c.font)[0];
      if (/bold/.test(f)) s += "font-weight:bold;";
      if (/italic/.test(f)) s += "font-style:italic;";
    }
    if (on(c.underline)) s += "text-decoration:underline;";
    if (on(c.overstrike)) s += "text-decoration:line-through;";
    return s;
  };
  const txRender = (w) => {
    const t = w.txt, n = t.length, pts = new Map();
    const add = (p, name, d) => {
      p = Math.max(0, Math.min(n, p));
      let a = pts.get(p);
      if (!a) pts.set(p, (a = []));
      a.push([name, d]);
    };
    const rank = {};
    w.to.forEach((name, i) => (rank[name] = i));
    const sty = {};
    for (const name of w.to) {
      const r = w.tg[name];
      if (!r || !r.length) continue;
      sty[name] = name === "sel" ? "" : tstyle(w.tc[name]);
      if (!sty[name] && name !== "sel") continue;
      for (let i = 0; i < r.length; i += 2) {
        const a = U(w, r[i]), b = U(w, r[i + 1]);
        if (b > a) {
          add(a, name, 1);
          add(b, name, -1);
        }
      }
    }
    const ew = {};
    for (const id in w.wins) {
      const p = U(w, w.wins[id]);
      if (p < n) {
        ew[p] = id;
        add(p, "", 0);
      }
    }
    const keys = [...pts.keys()].sort((a, b) => a - b);
    const act = new Map(), lines = [];
    let line = "", open = "", pos = 0;
    const openTag = () => {
      if (!act.size) return "";
      const names = [...act.keys()].sort((a, b) => (rank[a] ?? 0) - (rank[b] ?? 0));
      let st = "", cls = "";
      for (const nm of names) {
        if (nm === "sel") cls = " class=tk-s";
        else st += sty[nm] || "";
      }
      return `<span${cls}${st ? ` style="${st}"` : ""}>`;
    };
    const emit = (seg) => {
      const parts = seg.split("\n");
      for (let i = 0; i < parts.length; i++) {
        if (i) {
          if (open) line += "</span>";
          lines.push(line);
          line = open;
        }
        line += esc(parts[i]);
      }
    };
    for (const k of keys) {
      if (k > pos) {
        emit(t.slice(pos, k));
        pos = k;
      }
      const ch = pts.get(k);
      if (ch.some(([nm]) => nm)) {
        for (const [nm, d] of ch) {
          if (!nm) continue;
          const c = (act.get(nm) || 0) + d;
          if (c > 0) act.set(nm, c);
          else act.delete(nm);
        }
        if (open) line += "</span>";
        open = openTag();
        line += open;
      }
      if (ew[k] !== undefined && k >= pos) {
        line += `<span class=tk-ew data-ew="${esc(ew[k])}">${esc(t[k])}</span>`;
        pos = k + 1;
      }
    }
    if (pos < n) emit(t.slice(pos));
    if (open) line += "</span>";
    lines.push(line);
    w.hl.innerHTML = lines.map((l) => "<div>" + l + "</div>").join("");
    for (const c of [...w.el.children]) if (c.classList.contains("tk-emb") && !(c.dataset.tk in w.wins)) c.remove();
    if (w.yvq != null) {
      const d = w.hl.children[Math.floor(w.yvq)];
      if (d) w.in.scrollTop = d.offsetTop + (w.yvq % 1) * d.offsetHeight - (parseFloat(getComputedStyle(w.in).paddingTop) || 0);
      w.yvq = null;
    }
    if (w.seeq != null) {
      txSee(w, w.seeq);
      w.seeq = null;
    }
    txSync(w);
    txView(w);
  };
  const txSync = (w) => {
    w.hl.scrollTop = w.in.scrollTop;
    w.hl.scrollLeft = w.in.scrollLeft;
    for (const id in w.wins) {
      const c = S.w[id], ph = w.hl.querySelector(`[data-ew="${CSS.escape(id)}"]`);
      if (!c?.el || !ph) continue;
      if (c.el.parentNode !== w.el) {
        c.el.classList.add("tk-emb");
        w.el.append(c.el);
      }
      c.el.style.left = ph.offsetLeft - w.hl.scrollLeft + "px";
      c.el.style.top = ph.offsetTop - w.hl.scrollTop + "px";
    }
  };
  const txSee = (w, off) => {
    const u = U(w, off), t = w.txt;
    let ln = 0;
    for (let i = t.indexOf("\n"); i >= 0 && i < u; i = t.indexOf("\n", i + 1)) ln++;
    const d = w.hl.children[ln], ta = w.in;
    if (!d) return;
    const top = d.offsetTop, hgt = d.offsetHeight, vh = ta.clientHeight;
    if (top < ta.scrollTop) ta.scrollTop = top - 2;
    else if (top + hgt > ta.scrollTop + vh) ta.scrollTop = top + hgt - vh + 2;
  };
  const txView = (w) => {
    clearTimeout(w.vt);
    w.vt = setTimeout(() => {
      const ta = w.in, kids = w.hl.children;
      if (!kids.length || !ta.isConnected || !S.w[w.id]) return;
      const st = ta.scrollTop, vh = ta.clientHeight, cs = getComputedStyle(ta);
      const py = parseFloat(cs.paddingTop) || 0, px = parseFloat(cs.paddingLeft) || 0, lh = parseFloat(cs.lineHeight) || 18;
      if (!w.cw) {
        const m = h("span", "", w.el);
        m.style.cssText = "position:absolute;visibility:hidden;white-space:pre;font:inherit";
        m.textContent = "0".repeat(20);
        w.cw = m.getBoundingClientRect().width / 20 || 8;
        m.remove();
      }
      let lo = 0, hi = kids.length - 1;
      while (lo < hi) {
        const mid = (lo + hi) >> 1, d = kids[mid];
        if (d.offsetTop + d.offsetHeight <= st) lo = mid + 1;
        else hi = mid;
      }
      const b = w.el.clientTop, lines = [];
      for (let i = lo; i < kids.length; i++) {
        const d = kids[i];
        if (d.offsetTop >= st + vh) break;
        lines.push([i + 1, d.offsetTop - st + b, d.offsetHeight]);
      }
      const f = kids[lo];
      const top = lo + Math.max(0, Math.min(1, (st - f.offsetTop) / (f.offsetHeight || 1)));
      const v = { t: "view", x: 0, y: 0, m: 0, top: Math.round(top * 100) / 100, rows: lines.length || Math.round(vh / lh), lh, cw: w.cw, px: px + b, py: py + b, lines };
      const key = JSON.stringify(v);
      if (key === w.vk) return;
      w.vk = key;
      push(w, "ev", v, true);
    }, 60);
  };
  const txKey = (w, d) => push(w, "ev", txd(w, d));
  const txBind = (w) => {
    const ta = w.in;
    ta.addEventListener("keydown", (e) => {
      e.tkDone = true;
      if (e.isComposing || e.keyCode === 229 || MODK.has(e.key)) return;
      const mod = e.ctrlKey || e.metaKey, lk = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      if ((mod && lk === "v") || (e.shiftKey && e.key === "Insert")) return;
      if (!(mod && lk === "c") && e.key !== "F12") e.preventDefault();
      txKey(w, keyd(e, "key"));
    });
    ta.addEventListener("keyup", (e) => {
      e.tkDone = true;
      if (MODK.has(e.key) || !want(w, "keyup")) return;
      txKey(w, keyd(e, "keyup"));
    });
    ta.addEventListener("paste", (e) => {
      e.preventDefault();
      txKey(w, { t: "paste", s: e.clipboardData?.getData("text/plain") || "", x: 0, y: 0, m: 0 });
    });
    ta.addEventListener("cut", (e) => {
      e.preventDefault();
      txKey(w, { t: "key", k: "x", c: "x", m: 4, x: 0, y: 0 });
    });
    ta.addEventListener("drop", (e) => e.preventDefault());
    ta.addEventListener("beforeinput", (e) => {
      if (!e.cancelable) return;
      e.preventDefault();
      const t = e.inputType, k = (k, c) => txKey(w, { t: "key", k, c, m: 0, x: 0, y: 0 });
      if (t === "insertText" || t === "insertReplacementText") txKey(w, { t: "text", s: e.data || "", x: 0, y: 0, m: 0 });
      else if (t === "insertLineBreak" || t === "insertParagraph") k("Return", "\r");
      else if (t === "deleteContentBackward") k("BackSpace", "\b");
      else if (t === "deleteContentForward") k("Delete", "\x7f");
    });
    ta.addEventListener("compositionend", (e) => {
      ta.value = w.txt;
      txSelApply(w);
      if (e.data) txKey(w, { t: "text", s: e.data, x: 0, y: 0, m: 0 });
    });
    ta.addEventListener("scroll", () => {
      txSync(w);
      txView(w);
    });
    const rep = () => setTimeout(() => txSelReport(w));
    ta.addEventListener("pointerup", rep);
    ta.addEventListener("select", rep);
    new ResizeObserver(() => txView(w)).observe(w.el);
    if (!S.selch) {
      S.selch = 1;
      document.addEventListener("selectionchange", () => {
        const a = document.activeElement, x = a && a.classList?.contains("tk-ta") && S.w[a.parentNode?.dataset.tk];
        if (x) txSelReport(x);
      });
    }
  };
  const make = (s, id, k, pa, p) => {
    const w = { id, s, k, pa, b: new Set(), p: {}, top: id };
    let el = null;
    if (WIN.has(k)) {
      el = h("div", "tk-win");
      el.tabIndex = -1;
      w.bar = h("div", "tk-bar", el);
      w.ttl = h("span", "", w.bar);
      const x = h("button", "tk-x", w.bar);
      x.textContent = "×";
      x.onclick = () => {
        if (w.closing && Date.now() - w.closing > 1500) return gone(s);
        w.closing ||= Date.now();
        push(w, "close");
      };
      w.mb = h("div", "tk-mb", el);
      w.mb.hidden = true;
      w.body = h("div", "tk-body", el);
      w.box = h("div", "tk-box tk-root", w.body);
      w.grip = h("div", "tk-grip", el);
      w.el = el;
      drag(w);
      resize(w);
      w.wo = new ResizeObserver(() => {
        if (S.w[id] !== w) return;
        if (!w.moved) fit(el);
        const bw = w.body.clientWidth;
        if (bw === w.bw) return;
        w.bw = bw;
        probe(w);
      });
      w.wo.observe(w.body);
      listen(w, el);
      el.addEventListener("pointerdown", () => raise(w), true);
      const n = S.n++ % 8;
      el.style.left = 40 + n * 28 + "px";
      el.style.top = 40 + n * 28 + "px";
      lift(el);
      S.layer.append(el);
      S.fresh.push(el);
    } else {
      w.top = S.w[pa]?.top;
      switch (k) {
        case "LabelFrame":
          el = h("fieldset", "tk-lf");
          w.lg = h("legend", "", el);
          w.box = h("div", "tk-box", el);
          break;
        case "Notebook":
          el = h("div", "tk-nb");
          w.tabs = h("div", "tk-tabs", el);
          w.box = h("div", "tk-box tk-nbb", el);
          break;
        case "Label":
          el = h("div", "tk-label");
          break;
        case "Button":
          el = h("button", "tk-btn");
          el.onclick = () => push(w, "cmd");
          break;
        case "Entry":
        case "Spinbox":
          el = w.in = h("input", "tk-in tk-el");
          el.spellcheck = false;
          el.autocomplete = "off";
          if (k === "Spinbox") el.type = "number";
          el.oninput = () => {
            dirty(w, el.value);
            if (k === "Spinbox") push(w, "cmd", undefined, true);
          };
          break;
        case "Text":
          el = h("div", "tk-tx tk-el");
          w.hl = h("div", "tk-hl", el);
          w.in = h("textarea", "tk-ta", el);
          w.in.spellcheck = false;
          w.in.autocomplete = "off";
          w.in.setAttribute("autocapitalize", "off");
          Object.assign(w, { txt: "", tg: {}, tc: {}, to: ["sel"], ver: 0, ins: 0, sel: null, wins: {}, astral: false });
          w.el = el;
          txBind(w);
          break;
        case "Checkbutton":
        case "Radiobutton":
          el = h("label", "tk-chk");
          w.in = h("input", "", el);
          w.in.type = k === "Checkbutton" ? "checkbox" : "radio";
          w.tx = h("span", "", el);
          w.in.onchange = () => {
            el.classList.toggle("tk-on", w.in.checked);
            dirty(w, w.in.checked);
            push(w, "cmd");
          };
          break;
        case "Scale":
          el = h("div", "tk-scale");
          w.lb = h("div", "", el);
          w.lb.hidden = true;
          w.in = h("input", "", el);
          w.in.type = "range";
          w.vl = h("div", "tk-sv", el);
          w.in.oninput = () => {
            const v = +w.in.value;
            w.vl.textContent = fmt(w, v);
            dirty(w, v);
            push(w, "cmd", v, true);
          };
          break;
        case "Listbox":
          el = h("div", "tk-list tk-el");
          el.tabIndex = 0;
          el.onclick = (e) => {
            const r = e.target.closest(".tk-row");
            if (r) pick(w, +r.dataset.i, e);
          };
          break;
        case "Canvas":
          el = h("div", "tk-cv tk-el");
          w.svg = sv("svg");
          w.g = w.svg.appendChild(sv("g"));
          el.append(w.svg);
          w.org = [0, 0];
          w.t = [0, 0];
          el.addEventListener("scroll", () => {
            const sr = w.p.sr || [0, 0, 0, 0];
            if (sr[2] - sr[0] > el.clientWidth) w.org[0] = sr[0] + el.scrollLeft;
            if (sr[3] - sr[1] > el.clientHeight) w.org[1] = sr[1] + el.scrollTop;
          });
          w.vo = new ResizeObserver(() => S.w[id] === w && cvView(w));
          w.vo.observe(el);
          w.it = {};
          break;
        case "Combobox":
          el = h("div", "tk-cb tk-el");
          break;
        case "Progressbar":
          el = h("div", "tk-pg tk-el");
          w.fill = h("div", "", el);
          break;
        case "Separator":
          el = h("div", "tk-sep");
          break;
        case "Scrollbar":
          el = h("div", "tk-sb");
          break;
        case "Menu":
          break;
        default:
          el = w.box = h("div", "tk-frame tk-box");
      }
      w.el = el;
    }
    if (el) el.dataset.tk = id;
    S.w[id] = w;
    apply(w, p);
    if (k === "Combobox" && !w.in) combo(w);
    if (WIN.has(k)) grip(w);
    size(w);
    if (WIN.has(k) && !Object.values(S.w).some((o) => o.s === s && WIN.has(o.k) && o !== w && o.el.contains(document.activeElement))) el.focus({ preventScroll: true });
  };
  const kill = (id) => {
    const w = S.w[id];
    if (!w) return;
    for (const c of Object.values(S.w)) if (c.pa === id) kill(c.id);
    w.ro?.disconnect();
    w.wo?.disconnect();
    w.vo?.disconnect();
    (w.pc || w.el)?.remove();
    delete S.w[id];
  };
  const gone = (s) => {
    for (const w of Object.values(S.w)) {
      if (w.s !== s) continue;
      w.ro?.disconnect();
      w.wo?.disconnect();
      w.vo?.disconnect();
      if (WIN.has(w.k)) w.el.remove();
      delete S.w[w.id];
    }
    S.layer.querySelectorAll(`.tk-modal[data-s="${s}"]`).forEach((e) => e.remove());
    clearTimeout(S.q[s]?.t);
    delete S.q[s];
    closeDrop();
    refocus();
  };

  const parcel = (w, o) => {
    const c = h("div", w.box ? "tk-pc tk-ct" : "tk-pc"), el = w.el;
    const [pl, pr] = pair(o.padx), [pt, pb] = pair(o.pady);
    c.style.padding = `${pt} ${pr} ${pb} ${pl}`;
    c.pv = `${pt} + ${pb}`;
    const a = o.anchor || "center", f = o.fill || "none";
    w.fx = f === "x" || f === "both";
    w.fy = f === "y" || f === "both";
    al(el.style, "justifySelf", w.fx ? "stretch" : hz(a));
    al(el.style, "alignSelf", w.fy ? "stretch" : vt(a));
    el.style.flexGrow = "";
    el.style.setProperty("--ix", (+o.ipadx || 0) + "px");
    el.style.setProperty("--iy", (+o.ipady || 0) + "px");
    c.append(el);
    w.pc = c;
    size(w);
    return c;
  };
  const vert = (o) => o.side !== "left" && o.side !== "right";
  const WRAP = !!window.CSS?.supports?.("flex-basis", "min-content");
  const pack = (cav, list) => {
    cav.style.display = "flex";
    if (!list.length) return;
    const v = vert(list[0][1]);
    let i = 0;
    while (i < list.length && vert(list[i][1]) === v) i++;
    const run = list.slice(0, i), rest = list.slice(i);
    cav.classList.add(v ? "tk-vr" : "tk-hr");
    const end = (o) => o.side === "bottom" || o.side === "right";
    const put = ([w, o]) => {
      const c = parcel(w, o);
      if (o.expand) c.classList.add("tk-gx");
      cav.append(c);
    };
    run.filter(([, o]) => !end(o)).forEach(put);
    const mid = h("div", "tk-cav", cav);
    if (!run.some(([, o]) => o.expand) || rest.some(([, o]) => o.expand)) mid.classList.add("tk-gx");
    pack(mid, rest);
    run.filter(([, o]) => end(o)).reverse().forEach(put);
  };
  const grid = (box, list, cols, rws) => {
    box.style.display = "grid";
    box.style.justifyContent = "start";
    box.style.alignContent = "start";
    let nc = 0, nr = 0;
    for (const [, o] of list) {
      nc = Math.max(nc, o.column + (o.columnspan || 1));
      nr = Math.max(nr, o.row + (o.rowspan || 1));
    }
    const tpl = (n, cfg) => Array.from({ length: n }, (_, i) => (cfg?.[i]?.[0] ? `minmax(auto,${cfg[i][0]}fr)` : "auto")).join(" ");
    box.style.gridTemplateColumns = tpl(nc, cols);
    box.style.gridTemplateRows = tpl(nr, rws);
    if (Object.values(cols || {}).some((c) => c[0])) box.style.justifyContent = "stretch";
    if (Object.values(rws || {}).some((c) => c[0])) box.style.alignContent = "stretch";
    const strut = (cfg, n, col) => {
      for (const i in cfg || {}) {
        if (!(cfg[i][1] > 0) || +i >= n) continue;
        const e = h("div", "", box);
        e.style.cssText = `visibility:hidden;pointer-events:none;grid-area:${col ? `1/${+i + 1}` : `${+i + 1}/1`};min-${col ? "width" : "height"}:${+cfg[i][1]}px`;
      }
    };
    strut(cols, nc, true);
    strut(rws, nr, false);
    for (const [w, o] of list) {
      const s = o.sticky || "", n = s.includes("n"), so = s.includes("s"), e = s.includes("e"), we = s.includes("w");
      const fill = e && we ? (n && so ? "both" : "x") : n && so ? "y" : "none";
      const anchor = (n && !so ? "n" : so && !n ? "s" : "") + (we && !e ? "w" : e && !we ? "e" : "") || "center";
      const c = parcel(w, { padx: o.padx, pady: o.pady, ipadx: o.ipadx, ipady: o.ipady, fill, anchor });
      c.style.gridArea = `${o.row + 1} / ${o.column + 1} / span ${o.rowspan || 1} / span ${o.columnspan || 1}`;
      box.append(c);
    }
  };
  const place = (box, list) => {
    for (const [w, o] of list) {
      const c = h("div", "tk-pl"), s = c.style, el = w.el;
      s.left = `calc(${(+o.relx || 0) * 100}% + ${+o.x || 0}px)`;
      s.top = `calc(${(+o.rely || 0) * 100}% + ${+o.y || 0}px)`;
      const fw = o.width != null || o.relwidth != null, fh = o.height != null || o.relheight != null;
      if (fw) s.width = `calc(${(+o.relwidth || 0) * 100}% + ${+o.width || 0}px)`;
      if (fh) s.height = `calc(${(+o.relheight || 0) * 100}% + ${+o.height || 0}px)`;
      const a = o.anchor || "nw";
      const tx = a === "center" || a === "n" || a === "s" ? -50 : a.includes("e") ? -100 : 0;
      const ty = a === "center" || a === "e" || a === "w" ? -50 : a.includes("s") ? -100 : 0;
      s.transform = `translate(${tx}%,${ty}%)`;
      w.fx = w.fy = false;
      el.style.justifySelf = "";
      el.style.flexGrow = fw ? 1 : "";
      el.style.alignSelf = fh ? "stretch" : "";
      c.append(el);
      w.pc = c;
      size(w);
      box.append(c);
    }
  };
  const panes = (w, L) => {
    const box = w.box, v = w.p.orient === "vertical", ps = (w.ps ||= {});
    const list = L.pw.map(([id, o]) => [S.w[id], o]).filter(([c, o]) => c?.el && !o.hide), last = list.length - 1;
    box.style.display = "flex";
    box.classList.add(v ? "tk-vr" : "tk-hr", "tk-pw");
    list.forEach(([c, o], i) => {
      const p = parcel(c, { fill: "both", padx: o.padx, pady: o.pady }), st = o.stretch || "last";
      const grow = o.weight != null ? o.weight > 0 : st === "always" || (st === "last" && i === last) || (st === "first" && !i) || (st === "middle" && i > 0 && i < last);
      const want = ps[c.id] ?? (v ? o.height : o.width);
      p.style.flex = c.id in ps ? `0 0 ${want}px` : `${grow ? 1 : 0} 1 ${want ? want + "px" : "auto"}`;
      box.append(p);
      if (i === last) return;
      const s = h("div", v ? "tk-sash tk-v" : "tk-sash", box);
      s.style[v ? "height" : "width"] = (w.p.sash ?? 3) + "px";
      s.onpointerdown = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const r = p.getBoundingClientRect(), at = v ? e.clientY : e.clientX, was = v ? r.height : r.width;
        s.setPointerCapture(e.pointerId);
        s.onpointermove = (e) => {
          ps[c.id] = Math.max(0, Math.round(was + (v ? e.clientY : e.clientX) - at));
          p.style.flex = `0 0 ${ps[c.id]}px`;
        };
        s.onpointerup = s.onpointercancel = () => (s.onpointermove = null);
      };
    });
  };
  const tabs = (w, L) => {
    w.tabs.replaceChildren();
    (L.n || []).forEach(([, text], i) => {
      const b = h("button", i === L.cur ? "on" : "", w.tabs);
      b.textContent = text;
      b.onclick = () => {
        if (L.cur === i) return;
        L.cur = i;
        layout(w, L);
        push(w, "sel", i);
      };
    });
    w.box.style.display = "grid";
    w.box.style.gridTemplate = "1fr / 1fr";
    (L.n || []).forEach(([id], i) => {
      const c = S.w[id];
      if (!c?.el) return;
      const p = parcel(c, { fill: "both" });
      p.style.gridArea = "1 / 1";
      if (i !== L.cur) p.classList.add("tk-hid");
      w.box.append(p);
    });
  };
  const layout = (w, L) => {
    if (!w?.box) return;
    const f = document.activeElement, box = w.box, s = box.style;
    w.L = L;
    box.replaceChildren();
    s.display = s.flexDirection = s.gridTemplateColumns = s.gridTemplateRows = s.justifyContent = s.alignContent = "";
    box.classList.remove("tk-vr", "tk-hr", "tk-wr", "tk-pw");
    const get = (l) => (l || []).map(([id, o]) => [S.w[id], o]).filter(([c]) => c?.el);
    if (w.k === "Notebook") tabs(w, L);
    else if (L.pw) panes(w, L);
    else if (L.p?.length) pack(box, get(L.p));
    else if (L.g?.length) grid(box, get(L.g), L.c, L.r);
    if (L.x?.length) place(box, get(L.x));
    size(w);
    need(w);
    if (f && f !== document.activeElement && f.isConnected) f.focus({ preventScroll: true });
  };

  const probe = (w) => {
    const el = w.el;
    if (!el?.isConnected) return;
    w.pd = 0;
    const y = w.body.scrollTop;
    el.classList.add("tk-probe");
    const list = [...el.querySelectorAll(".tk-root,.tk-cav,.tk-ct")];
    const hs = list.map((e) => e.getBoundingClientRect().height);
    el.classList.remove("tk-probe");
    list.forEach((e, i) => (e.style.minHeight = Math.ceil(hs[i] * 100) / 100 + "px"));
    if (y) w.body.scrollTop = y;
  };
  const wraps = (w) => {
    if (!WRAP || !w.el) return;
    for (const r of w.el.querySelectorAll(".tk-hr:not(.tk-pw)")) r.classList.toggle("tk-wr", !r.querySelector(".tk-ve"));
  };
  const tick = () => {
    for (const w of Object.values(S.w)) {
      if (!w.pd) continue;
      wraps(w);
      probe(w);
    }
  };
  const need = (w, soft) => {
    const t = w && (WIN.has(w.k) ? w : top(w));
    if (!t) return;
    t.pd = 1;
    if (soft) {
      S.soft ||= setTimeout(() => {
        S.soft = 0;
        tick();
      }, 200);
      return;
    }
    S.raf ||= requestAnimationFrame(() => {
      S.raf = 0;
      tick();
    });
  };
  const QUIET = new Set(["sel", "ins", "ver", "tags", "tcfg", "torder", "caret", "selbg", "selbg2", "value", "on", "b", "cursor", "fg", "bg", "state", "topmost", "alpha", "title", "run", "items", "wins", "geo", "zoom", "sr", "from", "to", "res", "group", "show", "justify", "anchor", "transient"]);
  const loud = (w, p) => {
    let r = 0;
    for (const k in p) if (!QUIET.has(k) && !(k === "text" && w.k === "Text")) r = Math.max(r, k === "text" ? 1 : 2);
    return r;
  };

  const pts = (p) => {
    const r = [];
    for (let i = 0; i + 1 < p.length; i += 2) r.push(p[i] + "," + p[i + 1]);
    return r.join(" ");
  };
  const arc = ([x1, y1, x2, y2], o) => {
    const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2, rx = Math.abs(x2 - x1) / 2, ry = Math.abs(y2 - y1) / 2;
    const s = +o.start || 0, x = Math.max(-359.99, Math.min(359.99, +(o.extent ?? 90)));
    const P = (a) => [cx + rx * Math.cos((a * Math.PI) / 180), cy - ry * Math.sin((a * Math.PI) / 180)];
    const [ax, ay] = P(s), [bx, by] = P(s + x);
    const a = `${ax},${ay}A${rx},${ry} 0 ${Math.abs(x) > 180 ? 1 : 0} ${x > 0 ? 0 : 1} ${bx},${by}`;
    return o.style === "arc" ? "M" + a : o.style === "chord" ? "M" + a + "Z" : `M${cx},${cy}L${a}Z`;
  };
  const TAG = { line: "polyline", rectangle: "rect", oval: "ellipse", text: "text", window: "foreignObject", image: "image" };
  const draw = (e) => {
    const o = e.o, p = e.xy || [], t = e.t;
    const A = (k, v) => (v == null || v === "" ? e.removeAttribute(k) : e.setAttribute(k, v));
    const col = (v, d) => (v === undefined || v === null ? d : v === "" ? "none" : color(v) || d);
    e.style.display = o.state === "hidden" ? "none" : "";
    if (t === "image") {
      const im = (S.img ||= {})[o.img], iw = o.iw || im?.w || 0, ih = o.ih || im?.h || 0, a = o.anchor || "center";
      e.dataset.img = o.img || "";
      A("href", im?.u);
      A("width", iw);
      A("height", ih);
      A("x", p[0] - (a === "center" || a === "n" || a === "s" ? iw / 2 : a.includes("e") ? iw : 0));
      A("y", p[1] - (a === "center" || a === "e" || a === "w" ? ih / 2 : a.includes("s") ? ih : 0));
      return;
    }
    if (t === "window") {
      A("x", p[0]);
      A("y", p[1]);
      A("width", 1);
      A("height", 1);
      e.style.overflow = "visible";
      if (!e.box) e.box = h("div", "tk-cvwin", e);
      const a = o.anchor || "center", c = S.w[o.win];
      const tx = a === "center" || a === "n" || a === "s" ? -50 : a.includes("e") ? -100 : 0;
      const ty = a === "center" || a === "e" || a === "w" ? -50 : a.includes("s") ? -100 : 0;
      e.box.style.transform = `translate(${tx}%,${ty}%)`;
      if (c?.el && c.el.parentNode !== e.box) e.box.replaceChildren(c.el);
      if (c?.el) {
        c.el.style.width = o.width ? o.width + "px" : "";
        c.el.style.height = o.height ? o.height + "px" : "";
      }
      return;
    }
    if (t === "text") {
      const a = o.anchor || "center", L = String(o.text ?? "").split("\n");
      const north = a !== "center" && a.includes("n"), south = a !== "center" && a.includes("s");
      A("x", p[0]);
      A("y", p[1]);
      A("fill", col(o.fill, "currentColor"));
      A("text-anchor", a === "center" || a === "n" || a === "s" ? "middle" : a.includes("w") ? "start" : "end");
      A("dominant-baseline", north ? "hanging" : south ? "text-after-edge" : "central");
      const [f, d] = o.font ? font(o.font) : ["13px var(--mono,monospace)", ""];
      e.style.font = f;
      e.style.textDecoration = d;
      const first = north ? 0 : south ? -(L.length - 1) * 1.2 : -(L.length - 1) * 0.6;
      e.replaceChildren(...L.map((s, i) => {
        const ts = sv("tspan");
        ts.setAttribute("x", p[0]);
        ts.setAttribute("dy", (i ? 1.2 : first) + "em");
        ts.textContent = s;
        return ts;
      }));
      return;
    }
    A("stroke", t === "line" ? col(o.fill, "currentColor") : col(o.outline, t === "polygon" ? "none" : "currentColor"));
    A("fill", t === "line" || (t === "arc" && o.style === "arc") ? "none" : col(o.fill, t === "polygon" ? "currentColor" : "none"));
    A("stroke-width", o.width ?? 1);
    A("stroke-dasharray", o.dash ? [].concat(o.dash).join(" ") : null);
    A("stroke-linecap", o.capstyle === "round" ? "round" : o.capstyle === "projecting" ? "square" : null);
    A("stroke-linejoin", "round");
    const [x1, y1, x2, y2] = p;
    if (t === "line") A("points", pts(p));
    else if (t === "rectangle") {
      A("x", Math.min(x1, x2));
      A("y", Math.min(y1, y2));
      A("width", Math.abs(x2 - x1));
      A("height", Math.abs(y2 - y1));
    } else if (t === "oval") {
      A("cx", (x1 + x2) / 2);
      A("cy", (y1 + y2) / 2);
      A("rx", Math.abs(x2 - x1) / 2);
      A("ry", Math.abs(y2 - y1) / 2);
    } else if (t === "polygon") A("d", "M" + pts(p) + "Z");
    else if (t === "arc") A("d", arc(p, o));
  };
  const item = (w, i, t, xy, o) => {
    let e = w.it[i];
    if (!e) {
      e = w.it[i] = sv(TAG[t] || "path");
      e.t = t;
      e.o = {};
      e.dataset.ti = i;
      w.g.append(e);
    }
    if (xy) e.xy = xy;
    if (o) Object.assign(e.o, o);
    draw(e);
  };

  const modal = (s, id, o) => {
    const ov = h("div", "tk-modal", S.layer);
    ov.dataset.s = s;
    const box = h("div", "tk-win", ov);
    h("div", "tk-bar", box).append(Object.assign(h("span"), { textContent: o.title || "" }));
    if (o.msg) h("div", "tk-msg", box).textContent = o.msg;
    let inp = null;
    if (o.inp != null) {
      inp = h("input", "tk-in tk-din", box);
      inp.value = o.inp;
      inp.spellcheck = false;
      if (o.show) inp.type = "password";
    }
    const bs = h("div", "tk-btns", box);
    const done = (k) => {
      ov.remove();
      push({ id, s }, "dlg", { k, v: inp ? inp.value : null });
    };
    const btns = o.btns.map(([k, label]) => {
      const b = h("button", "tk-btn", bs);
      b.textContent = label;
      b.onclick = () => done(k);
      return b;
    });
    ov.onkeydown = (e) => {
      e.stopPropagation();
      if (e.key === "Enter") done(o.btns[o.def || 0][0]);
      else if (e.key === "Escape") done(o.btns[o.btns.length - 1][0]);
      else return;
      e.preventDefault();
    };
    (inp || btns[o.def || 0])?.focus({ preventScroll: true });
    inp?.select();
  };

  const run = (s, o) => {
    const id = o[1], w = S.w[id];
    switch (o[0]) {
      case "w": if (w) kill(id); make(s, id, o[2], o[3], o[4] || {}); need(S.w[id]); break;
      case "c":
        if (w) {
          apply(w, o[2]);
          const l = loud(w, o[2]);
          if (l) need(w, l < 2);
        }
        break;
      case "L": if (w) layout(w, o[2]); break;
      case "d": need(w); kill(id); refocus(); break;
      case "i": if (w) item(w, o[2], o[3], o[4], o[5]); break;
      case "x":
        if (w) for (const i of o[2] || Object.keys(w.it)) {
          w.it[i]?.remove();
          delete w.it[i];
        }
        break;
      case "z": if (w?.it[o[2]]) o[3] ? w.g.append(w.it[o[2]]) : w.g.prepend(w.it[o[2]]); break;
      case "cs":
        if (w) {
          const el = w.el, i = o[2] === "y" ? 1 : 0, sr = w.p.sr || [0, 0, 0, 0], len = sr[i + 2] - sr[i];
          const view = i ? el.clientHeight : el.clientWidth, cur = (i ? el.scrollTop : el.scrollLeft) - w.t[i];
          w.org[i] = o[3] === "moveto" ? sr[i] + +o[4] * len : cur + +o[4] * (o[5] === "pages" ? view * 0.9 : 20);
          cvView(w);
        }
        break;
      case "f": if (w) S.foc = w; break;
      case "te": if (w) txEdits(w, o[2]); break;
      case "see": if (w) { w.seeq = o[2]; txDirty(w); } break;
      case "yv": if (w) { w.yvq = o[2]; txDirty(w); } break;
      case "sr": if (w?.in?.setSelectionRange) try { w.in.setSelectionRange(o[2], o[3]); } catch {} break;
      case "ls": if (w) w.el.children[o[2]]?.scrollIntoView({ block: "nearest" }); break;
      case "r": if (w) o[2] ? raise(w) : (w.el.style.zIndex = 0); break;
      case "m": modal(s, id, o[2]); break;
      case "img": {
        (S.img ||= {})[id] = { u: o[2], w: o[3], h: o[4] };
        S.layer.querySelectorAll(`img[data-img="${CSS.escape(id)}"]`).forEach((e) => {
          e.src = o[2];
          e.width = o[3];
          e.height = o[4];
        });
        for (const c of Object.values(S.w)) if (c.k === "Canvas") for (const e of Object.values(c.it)) if (e.t === "image" && e.o.img === id) draw(e);
        break;
      }
      case "P": drop(S.w[id], null, o[2], o[3]); break;
      case "q": gone(s); break;
    }
  };
  window.ktTk = (m) => {
    S.fresh = [];
    S.foc = null;
    if (m.a !== undefined) ack(m.s, m.a, m.l);
    for (const o of m.o) run(m.s, o);
    menus(m.s);
    const foc = S.foc;
    if (foc && S.w[foc.id]) {
      const top = S.w[foc.top];
      raise(top);
      (foc.in || foc.el)?.focus({ preventScroll: true });
    }
    const fresh = S.fresh;
    requestAnimationFrame(() => fresh.forEach(fit));
    return 1;
  };
  return window.ktTk(m);
}
