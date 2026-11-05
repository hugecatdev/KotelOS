async (text) => {
  if (navigator.vibrate) navigator.vibrate([80, 60, 80]);
  if (document.hidden) {
    const title = document.title;
    let on = false;
    const t = setInterval(() => { document.title = (on = !on) ? '* ' + text : title; }, 1000);
    document.addEventListener('visibilitychange', () => { clearInterval(t); document.title = title; }, { once: true });
  }
  if (location.protocol === 'file:') throw new Error('в file:// браузер не даёт уведомления, нужен http(s)');
  if (!isSecureContext) throw new Error('нужен https или localhost');
  if (!window.Notification) throw new Error('не поддерживается');
  if (Notification.permission === 'default') {
    await kt.gesture('Показывать уведомления от kt notify?', 'Разрешить', () => Notification.requestPermission()).catch(() => {});
  }
  if (Notification.permission === 'denied') throw new Error('запрещены в настройках сайта');
  if (Notification.permission !== 'granted') throw new Error('браузер не дал разрешение, см. значок у адреса');
  try { new Notification('kotelos', { body: text }); } catch { throw new Error('не поддерживается'); }
}
