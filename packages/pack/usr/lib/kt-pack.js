const open = () => new Promise((ok, err) => {
  const r = indexedDB.open('kt-pack', 1);
  r.onupgradeneeded = () => r.result.createObjectStore('packs');
  r.onsuccess = () => ok(r.result);
  r.onerror = () => err(r.error);
});
const req = async (mode, fn) => {
  const d = await open();
  return new Promise((ok, err) => {
    const t = d.transaction('packs', mode);
    const q = fn(t.objectStore('packs'));
    t.oncomplete = () => { d.close(); ok(q.result); };
    t.onerror = () => { d.close(); err(t.error); };
  });
};
const get = async (n) => {
  const v = await req('readonly', (s) => s.get(n));
  if (!v) throw new Error('нет ' + n);
  return v;
};
const put = (n, v) => req('readwrite', (s) => s.put(v, n));
const del = (n) => req('readwrite', (s) => s.delete(n));
const list = async () => {
  const out = [];
  for (const k of await req('readonly', (s) => s.getAllKeys())) out.push({ name: k, ...(await get(k)) });
  return out.sort((a, b) => a.created - b.created);
};
