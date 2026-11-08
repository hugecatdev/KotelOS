const open = () => new Promise((ok, err) => {
  const r = indexedDB.open('kt-sync', 1);
  r.onupgradeneeded = () => r.result.createObjectStore('dirs');
  r.onsuccess = () => ok(r.result);
  r.onerror = () => err(r.error);
});
const req = async (mode, fn) => {
  const d = await open();
  return new Promise((ok, err) => {
    const t = d.transaction('dirs', mode);
    const q = fn(t.objectStore('dirs'));
    t.oncomplete = () => { d.close(); ok(q.result); };
    t.onerror = () => { d.close(); err(t.error); };
  });
};
const get = (k) => req('readonly', (s) => s.get(k));
const put = (k, v) => req('readwrite', (s) => s.put(v, k));
const del = (k) => req('readwrite', (s) => s.delete(k));
const mb = (n) => (n / 1048576).toFixed(1) + ' МБ';
const safe = (n) => n.normalize('NFC').replace(/[^\p{L}\p{N}._\-+=@,()]+/gu, '_').replace(/^\.+/, '_') || 'dir';
const SKIP = new Set(['.git', 'node_modules', '__pycache__', '.venv', 'venv', '.DS_Store']);

const tar = async (root) => {
  const enc = new TextEncoder(), parts = [];
  let size = 0, files = 0;
  const header = (path, len, mtime, type) => {
    const h = new Uint8Array(512);
    let name = enc.encode(path), prefix = new Uint8Array(0);
    if (name.length > 100) {
      let i = name.length - 1;
      while (i >= 0 && !(name[i] === 47 && i <= 155 && name.length - i - 1 <= 100)) i--;
      if (i < 0) return null;
      prefix = name.subarray(0, i);
      name = name.subarray(i + 1);
    }
    const set = (off, str) => h.set(enc.encode(str), off);
    const oct = (off, w, n) => set(off, n.toString(8).padStart(w - 1, '0') + '\0');
    h.set(name, 0);
    oct(100, 8, type === '5' ? 0o755 : 0o644);
    oct(108, 8, 0);
    oct(116, 8, 0);
    oct(124, 12, len);
    oct(136, 12, Math.floor(mtime / 1000));
    h.fill(32, 148, 156);
    set(156, type);
    set(257, 'ustar\x0000');
    h.set(prefix, 345);
    let sum = 0;
    for (const b of h) sum += b;
    set(148, sum.toString(8).padStart(6, '0') + '\0 ');
    return h;
  };
  const walk = async (dir, path) => {
    for await (const [name, h] of dir.entries()) {
      if (SKIP.has(name)) continue;
      const p = path ? path + '/' + name : name;
      if (h.kind === 'directory') {
        const hd = header(p + '/', 0, Date.now(), '5');
        if (hd) parts.push(hd);
        await walk(h, p);
      } else {
        const f = await h.getFile();
        const hd = header(p, f.size, f.lastModified, '0');
        if (!hd) continue;
        parts.push(hd, f, new Uint8Array((512 - (f.size % 512)) % 512));
        size += f.size;
        files++;
      }
    }
  };
  await walk(root, '');
  parts.push(new Uint8Array(1024));
  return { blob: new Blob(parts), size, files };
};

const pick = async (to, dest) => {
  if (!window.showDirectoryPicker) throw new Error('нужен браузер на Chromium');
  let h;
  try {
    h = await kt.gesture('Папка с диска скопируется в машину, правки из машины пойдут обратно', 'Выбрать', () => showDirectoryPicker({ mode: 'readwrite' }));
  } catch (e) {
    throw new Error(e.name === 'AbortError' ? 'браузер не показал выбор папки или его закрыли' : e.message);
  }
  const t = await tar(h);
  if (t.size > 20 * 1048576) await kt.gesture(`В папке ${mb(t.size)}, копировать в машину долго`, 'Копировать');
  to = to || '/mnt/' + safe(h.name);
  await put(to, h);
  await kt.write(dest, t.blob);
  return [to, h.name, t.files, t.size].join('\t');
};

const allow = async (root, h) => {
  if (await h.queryPermission({ mode: 'readwrite' }) === 'granted') return;
  const w = (window.ktSyncAsk ||= {});
  w[root] ||= kt.gesture(`Писать изменения из ${root} в папку ${h.name}?`, 'Разрешить', () => h.requestPermission({ mode: 'readwrite' }))
    .catch(() => {}).finally(() => delete w[root]);
  await w[root];
  if (await h.queryPermission({ mode: 'readwrite' }) !== 'granted') throw new Error('нет разрешения писать в ' + h.name);
};

const write = async (root, changed, removed) => {
  const h = await get(root);
  if (!h) throw new Error(root + ' не синхронизируется');
  await allow(root, h);
  const at = async (rel, create) => {
    const path = rel.split('/');
    const name = path.pop();
    let d = h;
    for (const p of path) d = await d.getDirectoryHandle(p, { create });
    return [d, name];
  };
  for (const rel of changed.split('\n').filter(Boolean)) {
    let data;
    try { data = await kt.read(root + '/' + rel); } catch { continue; }
    const [d, name] = await at(rel, true);
    const w = await (await d.getFileHandle(name, { create: true })).createWritable();
    await w.write(data);
    await w.close();
  }
  for (const rel of removed.split('\n').filter(Boolean)) {
    try {
      const [d, name] = await at(rel, false);
      await d.removeEntry(name);
    } catch (e) {
      if (e.name !== 'NotFoundError') throw e;
    }
  }
};
