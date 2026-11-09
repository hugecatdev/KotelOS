// kt-xwm: оконный менеджер X для страницы (бандл с --embed). Окна X без рамок, а рамки, заголовки,
// перенос, размер и фокус - у страницы: каждое окно она показывает отдельно (свой холст с куском экрана X)
// поверх сайта или терминала, корня X не видно. Место окна на экране X - его место на странице.
//
// Демон - механизм: ставит новое окно (где оно просило, диалог - над владельцем, остальные посередине;
// заголовок страницы - на экране), раскладывает окна по командам страницы и сообщает обо всём, что видно на
// экране X, в том числе о меню и подсказках (override-redirect). Протокол - строки по TCP: демон слушает
// порт 7704 и, когда готов, зовёт страницу командой xwm (192.168.86.1:7771, "xwm - 0\n"); она подключается
// и держит соединение. Новое соединение (страницу перезагрузили, машину восстановили) сменяет старое.
//
// Демон -> странице:
//   win ID X Y W H ВИД ВЛАДЕЛЕЦ ЗАГОЛОВОК   окно на экране (новое или поменялось): ВИД n - с рамкой
//                                          страницы, u - без рамки, p - меню (у него указатель: щелчок
//                                          мимо должен дойти до X), t - подсказка; ВЛАДЕЛЕЦ - окно диалога
//                                          или 0
//   geo ID X Y W H                         место и размер
//   title ID ЗАГОЛОВОК
//   gone ID                                окна больше нет на экране
//   stack ID...                            порядок окон снизу вверх
//   focus ID                               фокус клавиатуры (0 - ни у кого)
// Страница -> демону:
//   hello BAR      всё заново; BAR - высота заголовка страницы в точках X: окно с рамкой - не выше
//   move ID X Y
//   size ID W H    с подсказками размера окна (наименьший, наибольший, шаг)
//   raise ID       наверх (с диалогами) и фокус
//   close ID       WM_DELETE_WINDOW, если окно его понимает, иначе закрыть клиента
// X закрылся - выход. Другой оконный менеджер уже есть - выход с 1.
#include <arpa/inet.h>
#include <netinet/in.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#include <xcb/xcb.h>

#define PORT 7704
#define PAGE_IP "192.168.86.1"
#define PAGE_PORT 7771
#define MAXW 512

typedef struct {
  xcb_window_t id, owner;
  int x, y, w, h;
  char kind;    // n, u, p, t - см. win выше
  int managed;  // окно ведёт демон (не override-redirect)
  char title[256];
} Win;

static xcb_connection_t *X;
static xcb_window_t root, focused;
static int sw, sh, bar;
static Win wins[MAXW];
static int nwins, restack;
static int peer = -1;  // соединение страницы
static char out[1 << 16];
static size_t outn;

static xcb_atom_t WM_PROTOCOLS, WM_DELETE_WINDOW, WM_STATE, UTF8, NET_WM_NAME, NET_WM_TYPE, NET_ACTIVE, NET_SUPPORTED,
  NET_CHECK, MOTIF_HINTS, T_DOCK, T_DESKTOP, T_SPLASH, T_NOTIFICATION, T_TOOLTIP, T_DND, T_MENU, T_POPUP, T_DROPDOWN,
  T_COMBO;

static xcb_atom_t atom(const char *name)
{
  xcb_intern_atom_reply_t *r = xcb_intern_atom_reply(X, xcb_intern_atom(X, 0, strlen(name), name), NULL);
  xcb_atom_t a = r ? r->atom : XCB_ATOM_NONE;
  free(r);
  return a;
}

static int write_all(int s, const char *p, size_t n)
{
  while (n) {
    ssize_t w = write(s, p, n);
    if (w <= 0)
      return -1;
    p += w;
    n -= w;
  }
  return 0;
}

static void drop_peer(void)
{
  if (peer >= 0)
    close(peer);
  peer = -1;
  outn = 0;
}

static void flush_out(void)
{
  if (peer >= 0 && outn && write_all(peer, out, outn))
    drop_peer();
  outn = 0;
}

// строка странице (копится до конца прохода по событиям)
static void say(const char *fmt, ...)
{
  if (peer < 0)
    return;
  for (int i = 0; i < 2; i++) {
    va_list a;
    va_start(a, fmt);
    int n = vsnprintf(out + outn, sizeof out - outn, fmt, a);
    va_end(a);
    if (n >= 0 && outn + n < sizeof out) {
      outn += n;
      return;
    }
    flush_out();
  }
}

static Win *find(xcb_window_t id)
{
  for (int i = 0; i < nwins; i++)
    if (wins[i].id == id)
      return &wins[i];
  return NULL;
}

static Win *add(xcb_window_t id)
{
  if (nwins == MAXW)
    return NULL;
  Win *w = &wins[nwins++];
  memset(w, 0, sizeof *w);
  w->id = id;
  return w;
}

static void forget(Win *w)
{
  *w = wins[--nwins];
}

static xcb_get_property_reply_t *getprop(xcb_window_t w, xcb_atom_t p, xcb_atom_t type, uint32_t longs)
{
  xcb_get_property_reply_t *r = xcb_get_property_reply(X, xcb_get_property(X, 0, w, p, type, 0, longs), NULL);
  if (r && (r->type == XCB_ATOM_NONE || !xcb_get_property_value_length(r))) {
    free(r);
    return NULL;
  }
  return r;
}

// заголовок: _NET_WM_NAME (UTF-8), иначе WM_NAME (latin-1); переводы строк - пробелами
static void read_title(Win *w)
{
  xcb_get_property_reply_t *r = getprop(w->id, NET_WM_NAME, UTF8, 64);
  int utf8 = 1;
  if (!r) {
    r = getprop(w->id, XCB_ATOM_WM_NAME, XCB_GET_PROPERTY_TYPE_ANY, 64);
    utf8 = r && r->type == UTF8;
  }
  char *t = w->title;
  size_t n = 0;
  if (r) {
    const unsigned char *s = xcb_get_property_value(r);
    int l = xcb_get_property_value_length(r);
    for (int i = 0; i < l && n < sizeof w->title - 3; i++) {
      unsigned c = s[i] == '\n' || s[i] == '\r' || s[i] == '\t' ? ' ' : s[i];
      if (utf8 || c < 0x80) {
        t[n++] = c;
      } else {
        t[n++] = 0xc0 | c >> 6;
        t[n++] = 0x80 | (c & 0x3f);
      }
    }
    free(r);
  }
  t[n] = 0;
}

static xcb_atom_t wtype(xcb_window_t id)
{
  xcb_get_property_reply_t *r = getprop(id, NET_WM_TYPE, XCB_ATOM_ATOM, 1);
  xcb_atom_t t = r ? *(xcb_atom_t *)xcb_get_property_value(r) : XCB_ATOM_NONE;
  free(r);
  return t;
}

static xcb_window_t transient_for(xcb_window_t id)
{
  xcb_get_property_reply_t *r = getprop(id, XCB_ATOM_WM_TRANSIENT_FOR, XCB_ATOM_WINDOW, 1);
  xcb_window_t t = r ? *(xcb_window_t *)xcb_get_property_value(r) : 0;
  free(r);
  return t;
}

// _MOTIF_WM_HINTS: флаги, функции, украшения... - окно просит без рамки (Qt FramelessWindowHint и т.п.)
static int no_decor(xcb_window_t id)
{
  xcb_get_property_reply_t *r = getprop(id, MOTIF_HINTS, MOTIF_HINTS, 5);
  int no = 0;
  if (r && xcb_get_property_value_length(r) >= 12) {
    uint32_t *v = xcb_get_property_value(r);
    no = (v[0] & 2) && !v[2];
  }
  free(r);
  return no;
}

enum { US_POS = 1, P_POS = 4, P_MIN = 16, P_MAX = 32, P_INC = 64, P_BASE = 256 };
typedef struct {
  uint32_t flags;
  int32_t x, y, w, h, minw, minh, maxw, maxh, incw, inch, mina[2], maxa[2], basew, baseh, gravity;
} Hints;

static Hints hints(xcb_window_t id)
{
  Hints h = { 0 };
  xcb_get_property_reply_t *r = getprop(id, XCB_ATOM_WM_NORMAL_HINTS, XCB_ATOM_WM_SIZE_HINTS, 18);
  if (r) {
    int n = xcb_get_property_value_length(r);
    memcpy(&h, xcb_get_property_value(r), n < (int)sizeof h ? n : (int)sizeof h);
    free(r);
  }
  return h;
}

static char kind_managed(xcb_window_t id)
{
  xcb_atom_t t = wtype(id);
  if (t == T_DOCK || t == T_DESKTOP || t == T_SPLASH || t == T_NOTIFICATION || t == T_TOOLTIP || t == T_MENU ||
      t == T_POPUP || t == T_DROPDOWN || t == T_COMBO || t == T_DND || no_decor(id))
    return 'u';
  return 'n';
}

// override-redirect: подсказки и перетаскивание указателя не держат, остальное (меню, списки) - держит
static char kind_override(xcb_window_t id)
{
  xcb_atom_t t = wtype(id);
  return t == T_TOOLTIP || t == T_NOTIFICATION || t == T_DND ? 't' : 'p';
}

static void announce(Win *w)
{
  say("win %u %d %d %d %d %c %u %s\n", w->id, w->x, w->y, w->w, w->h, w->kind, w->owner, w->title);
}

static void set_state(xcb_window_t id, uint32_t state)
{
  uint32_t v[2] = { state, XCB_NONE };
  xcb_change_property(X, XCB_PROP_MODE_REPLACE, id, WM_STATE, WM_STATE, 32, 2, v);
}

static void set_focus(xcb_window_t id)
{
  focused = id;
  xcb_set_input_focus(X, XCB_INPUT_FOCUS_POINTER_ROOT, id ? id : XCB_INPUT_FOCUS_POINTER_ROOT, XCB_CURRENT_TIME);
  xcb_change_property(X, XCB_PROP_MODE_REPLACE, root, NET_ACTIVE, XCB_ATOM_WINDOW, 32, 1, &id);
  say("focus %u\n", id);
}

// наверх, его диалоги - над ним, фокус ему
static void activate(xcb_window_t id)
{
  Win *w = find(id);
  if (!w || !w->managed)
    return;
  uint32_t above = XCB_STACK_MODE_ABOVE;
  xcb_configure_window(X, id, XCB_CONFIG_WINDOW_STACK_MODE, &above);
  for (int i = 0; i < nwins; i++)
    if (wins[i].managed && wins[i].owner == id)
      xcb_configure_window(X, wins[i].id, XCB_CONFIG_WINDOW_STACK_MODE, &above);
  set_focus(id);
  restack = 1;
}

// фокус - верхнему окну с рамкой или без (не меню), если у ушедшего был фокус
static void refocus(void)
{
  xcb_query_tree_reply_t *r = xcb_query_tree_reply(X, xcb_query_tree(X, root), NULL);
  xcb_window_t next = 0;
  if (r) {
    xcb_window_t *c = xcb_query_tree_children(r);
    for (int i = xcb_query_tree_children_length(r) - 1; i >= 0 && !next; i--) {
      Win *w = find(c[i]);
      if (w && w->managed)
        next = w->id;
    }
    free(r);
  }
  set_focus(next);
}

static void send_stack(void)
{
  xcb_query_tree_reply_t *r = xcb_query_tree_reply(X, xcb_query_tree(X, root), NULL);
  if (!r)
    return;
  xcb_window_t *c = xcb_query_tree_children(r);
  int n = xcb_query_tree_children_length(r);
  char line[MAXW * 12 + 16];
  size_t l = snprintf(line, sizeof line, "stack");
  for (int i = 0; i < n; i++)
    if (find(c[i]) && l < sizeof line - 16)
      l += snprintf(line + l, sizeof line - l, " %u", c[i]);
  free(r);
  say("%s\n", line);
}

static void clamp(Win *w, int *x, int *y)
{
  int top = w->kind == 'n' ? bar : 0;
  if (*x + w->w > sw)
    *x = sw - w->w;
  if (*x < 0)
    *x = 0;
  if (*y + w->h > sh)
    *y = sh - w->h;
  if (*y < top)
    *y = top;
}

// новое окно: свойства, место, рамка X - ноль, WM_STATE, карта; странице - по MapNotify
static void manage(xcb_window_t id)
{
  xcb_get_geometry_reply_t *g = xcb_get_geometry_reply(X, xcb_get_geometry(X, id), NULL);
  if (!g)
    return;
  Win *w = find(id);
  if (!w && !(w = add(id))) {
    free(g);
    return;
  }
  w->managed = 1;
  w->w = g->width;
  w->h = g->height;
  int x = g->x, y = g->y;
  free(g);
  w->owner = transient_for(id);
  w->kind = kind_managed(id);
  read_title(w);
  Hints h = hints(id);
  Win *o = w->owner ? find(w->owner) : NULL;
  if (o) {
    x = o->x + (o->w - w->w) / 2;
    y = o->y + (o->h - w->h) / 2;
  } else if (!(h.flags & (US_POS | P_POS)) && !x && !y) {
    x = (sw - w->w) / 2;
    y = (sh - w->h) / 2;
  }
  clamp(w, &x, &y);
  w->x = x;
  w->y = y;
  uint32_t v[3] = { (uint32_t)x, (uint32_t)y, 0 };
  xcb_configure_window(X, id, XCB_CONFIG_WINDOW_X | XCB_CONFIG_WINDOW_Y | XCB_CONFIG_WINDOW_BORDER_WIDTH, v);
  uint32_t ev = XCB_EVENT_MASK_PROPERTY_CHANGE;
  xcb_change_window_attributes(X, id, XCB_CW_EVENT_MASK, &ev);
  set_state(id, 1);
  xcb_map_window(X, id);
}

// окно, которое уже на экране, но демон о нём не знал (меню; или всё - при старте демона)
static void track(xcb_window_t id, int override)
{
  xcb_get_geometry_reply_t *g = xcb_get_geometry_reply(X, xcb_get_geometry(X, id), NULL);
  if (!g)
    return;
  Win *w = find(id);
  if (!w)
    w = add(id);
  if (w) {
    w->x = g->x;
    w->y = g->y;
    w->w = g->width;
    w->h = g->height;
    w->managed = !override;
    w->owner = transient_for(id);
    w->kind = override ? kind_override(id) : kind_managed(id);
    read_title(w);
    if (!override) {
      uint32_t ev = XCB_EVENT_MASK_PROPERTY_CHANGE;
      xcb_change_window_attributes(X, id, XCB_CW_EVENT_MASK, &ev);
    }
    announce(w);
    restack = 1;
  }
  free(g);
}

static void unmanage(Win *w, int destroyed)
{
  xcb_window_t id = w->id;
  int was = w->managed;
  if (was && !destroyed)
    set_state(id, 0);
  say("gone %u\n", id);
  forget(w);
  restack = 1;
  if (was && id == focused)
    refocus();
}

// перерисовать весь экран, как xrefresh -none: окно во весь экран без фона на миг поверх всех - когда его
// нет, всё под ним получает Expose, а экран не мигает. После нового размера экрана (xrandr) X перерисовывает
// не всё: окна xcalc оставались чёрными
static xcb_window_t cover;
static void refresh(void)
{
  uint32_t v[2] = { XCB_BACK_PIXMAP_NONE, 1 };  // без фона, override-redirect
  cover = xcb_generate_id(X);
  xcb_create_window(X, XCB_COPY_FROM_PARENT, cover, root, 0, 0, sw, sh, 0, XCB_WINDOW_CLASS_INPUT_OUTPUT,
                    XCB_COPY_FROM_PARENT, XCB_CW_BACK_PIXMAP | XCB_CW_OVERRIDE_REDIRECT, v);
  xcb_map_window(X, cover);
  xcb_destroy_window(X, cover);
}

static void configure_request(xcb_configure_request_event_t *e)
{
  Win *w = find(e->window);
  uint32_t v[7];
  uint16_t m = 0;
  int i = 0;
  if (e->value_mask & XCB_CONFIG_WINDOW_X) {
    m |= XCB_CONFIG_WINDOW_X;
    v[i++] = (uint32_t)e->x;
  }
  if (e->value_mask & XCB_CONFIG_WINDOW_Y) {
    m |= XCB_CONFIG_WINDOW_Y;
    v[i++] = (uint32_t)(w && w->managed && w->kind == 'n' && e->y < bar ? bar : e->y);
  }
  if (e->value_mask & XCB_CONFIG_WINDOW_WIDTH) {
    m |= XCB_CONFIG_WINDOW_WIDTH;
    v[i++] = e->width;
  }
  if (e->value_mask & XCB_CONFIG_WINDOW_HEIGHT) {
    m |= XCB_CONFIG_WINDOW_HEIGHT;
    v[i++] = e->height;
  }
  if (e->value_mask & XCB_CONFIG_WINDOW_BORDER_WIDTH) {
    m |= XCB_CONFIG_WINDOW_BORDER_WIDTH;
    v[i++] = w && w->managed ? 0 : e->border_width;
  }
  if (e->value_mask & XCB_CONFIG_WINDOW_SIBLING) {
    m |= XCB_CONFIG_WINDOW_SIBLING;
    v[i++] = e->sibling;
  }
  if (e->value_mask & XCB_CONFIG_WINDOW_STACK_MODE) {
    m |= XCB_CONFIG_WINDOW_STACK_MODE;
    v[i++] = e->stack_mode;
  }
  xcb_configure_window(X, e->window, m, v);
}

static void close_win(xcb_window_t id)
{
  Win *w = find(id);
  if (!w || !w->managed)
    return;
  xcb_get_property_reply_t *r = getprop(id, WM_PROTOCOLS, XCB_ATOM_ATOM, 32);
  int polite = 0;
  if (r) {
    xcb_atom_t *a = xcb_get_property_value(r);
    for (int i = 0; i < xcb_get_property_value_length(r) / 4; i++)
      polite |= a[i] == WM_DELETE_WINDOW;
    free(r);
  }
  if (polite) {
    union {
      xcb_client_message_event_t m;
      char raw[32];
    } ev = { .m = { .response_type = XCB_CLIENT_MESSAGE, .format = 32, .window = id, .type = WM_PROTOCOLS } };
    ev.m.data.data32[0] = WM_DELETE_WINDOW;
    ev.m.data.data32[1] = XCB_CURRENT_TIME;
    xcb_send_event(X, 0, id, XCB_EVENT_MASK_NO_EVENT, ev.raw);
  } else {
    xcb_kill_client(X, id);
  }
}

static void resize(xcb_window_t id, int w, int h)
{
  Win *o = find(id);
  if (!o || !o->managed)
    return;
  Hints s = hints(id);
  int bw = s.flags & P_BASE ? s.basew : s.flags & P_MIN ? s.minw : 0;
  int bh = s.flags & P_BASE ? s.baseh : s.flags & P_MIN ? s.minh : 0;
  if (s.flags & P_INC && s.incw > 0 && w > bw)
    w = bw + (w - bw) / s.incw * s.incw;
  if (s.flags & P_INC && s.inch > 0 && h > bh)
    h = bh + (h - bh) / s.inch * s.inch;
  if (s.flags & P_MIN) {
    if (w < s.minw)
      w = s.minw;
    if (h < s.minh)
      h = s.minh;
  }
  if (s.flags & P_MAX) {
    if (s.maxw > 0 && w > s.maxw)
      w = s.maxw;
    if (s.maxh > 0 && h > s.maxh)
      h = s.maxh;
  }
  uint32_t v[2] = { w < 1 ? 1 : w, h < 1 ? 1 : h };
  xcb_configure_window(X, id, XCB_CONFIG_WINDOW_WIDTH | XCB_CONFIG_WINDOW_HEIGHT, v);
}

static void hello(void)
{
  say("root %d %d\n", sw, sh);
  for (int i = 0; i < nwins; i++)
    announce(&wins[i]);
  send_stack();
  say("focus %u\n", focused);
}

static void command(char *l)
{
  unsigned id;
  int a, b;
  if (sscanf(l, "hello %d", &a) == 1) {
    bar = a;
    hello();
  } else if (sscanf(l, "move %u %d %d", &id, &a, &b) == 3) {
    Win *w = find(id);
    if (w && w->managed) {
      uint32_t v[2] = { (uint32_t)a, (uint32_t)b };
      xcb_configure_window(X, id, XCB_CONFIG_WINDOW_X | XCB_CONFIG_WINDOW_Y, v);
    }
  } else if (sscanf(l, "size %u %d %d", &id, &a, &b) == 3) {
    resize(id, a, b);
  } else if (sscanf(l, "raise %u", &id) == 1) {
    activate(id);
  } else if (sscanf(l, "close %u", &id) == 1) {
    close_win(id);
  }
}

static void event(xcb_generic_event_t *e)
{
  switch (e->response_type & 0x7f) {
  case XCB_MAP_REQUEST:
    manage(((xcb_map_request_event_t *)e)->window);
    break;
  case XCB_CONFIGURE_REQUEST:
    configure_request((void *)e);
    break;
  case XCB_MAP_NOTIFY: {
    xcb_map_notify_event_t *m = (void *)e;
    if (m->event != root || m->window == cover)
      break;
    Win *w = find(m->window);
    if (w && w->managed) {
      announce(w);
      activate(w->id);
    } else if (!w && m->override_redirect) {
      track(m->window, 1);
    }
    restack = 1;
    break;
  }
  case XCB_UNMAP_NOTIFY: {
    xcb_unmap_notify_event_t *u = (void *)e;
    Win *w = u->event == root ? find(u->window) : NULL;
    if (w)
      unmanage(w, 0);
    break;
  }
  case XCB_DESTROY_NOTIFY: {
    Win *w = find(((xcb_destroy_notify_event_t *)e)->window);
    if (w)
      unmanage(w, 1);
    break;
  }
  case XCB_CONFIGURE_NOTIFY: {
    xcb_configure_notify_event_t *c = (void *)e;
    if (c->window == root) {
      // новый размер экрана (страница поменяла размер, машину открыли в другом окне): окна, что ушли за
      // край, - обратно на экран
      sw = c->width;
      sh = c->height;
      say("root %d %d\n", sw, sh);
      for (int i = 0; i < nwins; i++) {
        Win *w = &wins[i];
        int x = w->x, y = w->y;
        if (!w->managed)
          continue;
        clamp(w, &x, &y);
        if (x != w->x || y != w->y) {
          uint32_t v[2] = { (uint32_t)x, (uint32_t)y };
          xcb_configure_window(X, w->id, XCB_CONFIG_WINDOW_X | XCB_CONFIG_WINDOW_Y, v);
        }
      }
      refresh();
      break;
    }
    Win *w = c->event == root ? find(c->window) : NULL;
    if (w) {
      if (w->x != c->x || w->y != c->y || w->w != c->width || w->h != c->height) {
        w->x = c->x;
        w->y = c->y;
        w->w = c->width;
        w->h = c->height;
        say("geo %u %d %d %d %d\n", w->id, w->x, w->y, w->w, w->h);
      }
      restack = 1;
    }
    break;
  }
  case XCB_PROPERTY_NOTIFY: {
    xcb_property_notify_event_t *p = (void *)e;
    Win *w = find(p->window);
    if (w && (p->atom == XCB_ATOM_WM_NAME || p->atom == NET_WM_NAME)) {
      read_title(w);
      say("title %u %s\n", w->id, w->title);
    }
    break;
  }
  case XCB_CLIENT_MESSAGE: {
    xcb_client_message_event_t *m = (void *)e;
    if (m->type == NET_ACTIVE)
      activate(m->window);
    break;
  }
  }
}

// странице: демон готов, пусть подключается
static void call_page(void)
{
  struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(PAGE_PORT) };
  struct timeval tv = { 5, 0 };
  int s = socket(AF_INET, SOCK_STREAM, 0);
  if (s < 0)
    return;
  inet_pton(AF_INET, PAGE_IP, &a.sin_addr);
  setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof tv);
  if (!connect(s, (void *)&a, sizeof a))
    write_all(s, "xwm - 0\n", 8);
  close(s);
}

int main(void)
{
  struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(PORT), .sin_addr.s_addr = htonl(INADDR_ANY) };
  int ls, on = 1, sn;
  static char in[8192];
  size_t inn = 0;
  signal(SIGPIPE, SIG_IGN);
  X = xcb_connect(NULL, &sn);
  if (xcb_connection_has_error(X))
    return 1;
  xcb_screen_iterator_t it = xcb_setup_roots_iterator(xcb_get_setup(X));
  for (; sn > 0 && it.rem > 1; sn--)
    xcb_screen_next(&it);
  root = it.data->root;
  sw = it.data->width_in_pixels;
  sh = it.data->height_in_pixels;
  uint32_t mask = XCB_EVENT_MASK_SUBSTRUCTURE_REDIRECT | XCB_EVENT_MASK_SUBSTRUCTURE_NOTIFY |
                  XCB_EVENT_MASK_STRUCTURE_NOTIFY | XCB_EVENT_MASK_PROPERTY_CHANGE;
  xcb_generic_error_t *err = xcb_request_check(X, xcb_change_window_attributes_checked(X, root, XCB_CW_EVENT_MASK, &mask));
  if (err) {
    fprintf(stderr, "kt-xwm: в X уже есть оконный менеджер\n");
    return 1;
  }
  WM_PROTOCOLS = atom("WM_PROTOCOLS");
  WM_DELETE_WINDOW = atom("WM_DELETE_WINDOW");
  WM_STATE = atom("WM_STATE");
  UTF8 = atom("UTF8_STRING");
  NET_WM_NAME = atom("_NET_WM_NAME");
  NET_WM_TYPE = atom("_NET_WM_WINDOW_TYPE");
  NET_ACTIVE = atom("_NET_ACTIVE_WINDOW");
  NET_SUPPORTED = atom("_NET_SUPPORTED");
  NET_CHECK = atom("_NET_SUPPORTING_WM_CHECK");
  MOTIF_HINTS = atom("_MOTIF_WM_HINTS");
  T_DOCK = atom("_NET_WM_WINDOW_TYPE_DOCK");
  T_DESKTOP = atom("_NET_WM_WINDOW_TYPE_DESKTOP");
  T_SPLASH = atom("_NET_WM_WINDOW_TYPE_SPLASH");
  T_NOTIFICATION = atom("_NET_WM_WINDOW_TYPE_NOTIFICATION");
  T_TOOLTIP = atom("_NET_WM_WINDOW_TYPE_TOOLTIP");
  T_DND = atom("_NET_WM_WINDOW_TYPE_DND");
  T_MENU = atom("_NET_WM_WINDOW_TYPE_MENU");
  T_POPUP = atom("_NET_WM_WINDOW_TYPE_POPUP_MENU");
  T_DROPDOWN = atom("_NET_WM_WINDOW_TYPE_DROPDOWN_MENU");
  T_COMBO = atom("_NET_WM_WINDOW_TYPE_COMBO");

  // EWMH: окно-отметка «оконный менеджер есть» с именем; что понимаем
  xcb_window_t check = xcb_generate_id(X);
  xcb_create_window(X, 0, check, root, -1, -1, 1, 1, 0, XCB_WINDOW_CLASS_INPUT_ONLY, XCB_COPY_FROM_PARENT, 0, NULL);
  xcb_change_property(X, XCB_PROP_MODE_REPLACE, root, NET_CHECK, XCB_ATOM_WINDOW, 32, 1, &check);
  xcb_change_property(X, XCB_PROP_MODE_REPLACE, check, NET_CHECK, XCB_ATOM_WINDOW, 32, 1, &check);
  xcb_change_property(X, XCB_PROP_MODE_REPLACE, check, NET_WM_NAME, UTF8, 8, 6, "kt-xwm");
  xcb_atom_t supported[] = { NET_ACTIVE, NET_WM_NAME, NET_WM_TYPE, NET_CHECK };
  xcb_change_property(X, XCB_PROP_MODE_REPLACE, root, NET_SUPPORTED, XCB_ATOM_ATOM, 32, 4, supported);

  // окна, открытые до демона
  xcb_query_tree_reply_t *t = xcb_query_tree_reply(X, xcb_query_tree(X, root), NULL);
  if (t) {
    xcb_window_t *c = xcb_query_tree_children(t);
    for (int i = 0; i < xcb_query_tree_children_length(t); i++) {
      xcb_get_window_attributes_reply_t *at = xcb_get_window_attributes_reply(X, xcb_get_window_attributes(X, c[i]), NULL);
      if (at && at->map_state == XCB_MAP_STATE_VIEWABLE && c[i] != check)
        track(c[i], at->override_redirect);
      free(at);
    }
    free(t);
  }
  restack = 0;
  xcb_flush(X);

  if ((ls = socket(AF_INET, SOCK_STREAM, 0)) < 0)
    return 1;
  setsockopt(ls, SOL_SOCKET, SO_REUSEADDR, &on, sizeof on);
  if (bind(ls, (void *)&a, sizeof a) || listen(ls, 4)) {
    fprintf(stderr, "kt-xwm: порт %d занят\n", PORT);
    return 1;
  }
  call_page();

  for (;;) {
    xcb_generic_event_t *e;
    while ((e = xcb_poll_for_event(X))) {
      event(e);
      free(e);
    }
    if (xcb_connection_has_error(X))
      return 0;
    // ответ на query_tree читается из того же сокета: события, пришедшие раньше него, XCB кладёт в свою
    // очередь, и poll по сокету их уже не увидит - сначала разобрать их
    if (restack) {
      restack = 0;
      send_stack();
      continue;
    }
    flush_out();
    xcb_flush(X);
    struct pollfd p[3] = { { xcb_get_file_descriptor(X), POLLIN, 0 }, { ls, POLLIN, 0 }, { peer, POLLIN, 0 } };
    if (poll(p, peer >= 0 ? 3 : 2, -1) <= 0)
      continue;
    int old = peer;
    if (p[1].revents & POLLIN) {
      int c = accept(ls, NULL, NULL);
      if (c >= 0) {
        struct timeval tv = { 5, 0 };
        setsockopt(c, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof tv);
        drop_peer();
        peer = c;
        inn = 0;
      }
    }
    if (peer >= 0 && peer == old && p[2].revents & (POLLIN | POLLHUP | POLLERR)) {
      ssize_t n = read(peer, in + inn, sizeof in - 1 - inn);
      if (n <= 0) {
        drop_peer();
        continue;
      }
      inn += n;
      char *s = in, *nl;
      while ((nl = memchr(s, '\n', in + inn - s))) {
        *nl = 0;
        command(s);
        s = nl + 1;
      }
      inn -= s - in;
      memmove(in, s, inn);
      if (inn == sizeof in - 1)
        inn = 0;  // строка без конца - мусор
    }
  }
}
