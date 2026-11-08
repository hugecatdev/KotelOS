// kt-xclipd: общий буфер обмена X и браузера. Пакет kt-xclipd (его тянет xorg), запускает startx.
//
// X -> браузер: у CLIPBOARD новый владелец (событие XFixes) - демон забирает у программы текст и шлёт
// странице командой xclip (TCP 192.168.86.1:7771, как kt copy: "xclip - длина\n" + текст), она кладёт его
// в буфер браузера.
// Браузер -> X: на Ctrl+V и Ctrl+Shift+V на экране страница сначала присылает свой буфер, если в X не он:
// порт 7703, "SET длина\n" + текст, ответ "OK\n". Демон становится владельцем CLIPBOARD и сам отдаёт текст
// программам X, а страница только потом пускает клавишу в машину.
// Программа, у которой был буфер, закрылась - буфер переходит к демону, текст остаётся. PRIMARY
// (выделение мышью и вставка средней кнопкой) не трогает: он живёт только между программами X.
// X закрылся - выход. Второй не нужен: порт занят - выход с 0.
#include <arpa/inet.h>
#include <netinet/in.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
#include <xcb/xcb.h>
#include <xcb/xfixes.h>

#define PORT 7703
#define PAGE_IP "192.168.86.1"
#define PAGE_PORT 7771
#define MAXTEXT (8 << 20)  // одним свойством X отдаёт до 16 МБ (BIG-REQUESTS) - INCR не нужен

static xcb_connection_t *X;
static xcb_window_t win;
static xcb_atom_t CLIPBOARD, UTF8, MIME_UTF8, TEXT, TARGETS, TIMESTAMP, INCR, PROP, STAMP;
static uint8_t xfixes;
static uint32_t maxreq;

static char *text;  // текст CLIPBOARD, каким его знает демон; NULL - там не текст или пусто
static size_t len;
static int own;     // владелец CLIPBOARD - демон
static xcb_timestamp_t own_time;

// что сделать по событиям XFixes (берётся последнее): забрать текст у нового владельца, оставить
// текст себе - владелец закрылся, забыть - буфер очистили
enum { NOTHING, FETCH, KEEP, FORGET };
static int todo;

static long now_ms(void)
{
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return t.tv_sec * 1000L + t.tv_nsec / 1000000;
}

static xcb_atom_t atom(const char *name)
{
  xcb_intern_atom_reply_t *r = xcb_intern_atom_reply(X, xcb_intern_atom(X, 0, strlen(name), name), NULL);
  xcb_atom_t a = r ? r->atom : XCB_ATOM_NONE;
  free(r);
  return a;
}

static void set_text(char *t, size_t n)
{
  free(text);
  text = t;
  len = n;
}

// STRING (latin-1) -> UTF-8
static char *from_latin1(const unsigned char *s, size_t n, size_t *out)
{
  char *d = malloc(n * 2 + 1), *p = d;
  for (size_t i = 0; d && i < n; i++) {
    if (s[i] < 0x80) {
      *p++ = s[i];
    } else {
      *p++ = 0xc0 | s[i] >> 6;
      *p++ = 0x80 | (s[i] & 0x3f);
    }
  }
  *out = d ? (size_t)(p - d) : 0;
  return d;
}

// UTF-8 -> STRING для старых программ: чего нет в latin-1 - «?»
static char *to_latin1(const unsigned char *s, size_t n, size_t *out)
{
  char *d = malloc(n + 1), *p = d;
  for (size_t i = 0; d && i < n;) {
    unsigned cp = s[i], k = cp < 0x80 ? 1 : cp >> 5 == 6 ? 2 : cp >> 4 == 14 ? 3 : cp >> 3 == 30 ? 4 : 0;
    if (!k) {
      cp = '?';
      k = 1;
    } else if (k > 1) {
      cp &= 0x7f >> k;
      for (unsigned j = 1; j < k; j++) {
        if (i + j >= n || (s[i + j] & 0xc0) != 0x80) {
          cp = '?';
          k = j;
          break;
        }
        cp = cp << 6 | (s[i + j] & 0x3f);
      }
    }
    *p++ = cp < 256 ? cp : '?';
    i += k;
  }
  *out = d ? (size_t)(p - d) : 0;
  return d;
}

static void serve(xcb_selection_request_event_t *q);

// событие, которого не ждали: запрос к буферу демона - ответ сразу, XFixes - на потом (todo)
static void other(xcb_generic_event_t *e)
{
  uint8_t t = e->response_type & 0x7f;
  if (t == xfixes + XCB_XFIXES_SELECTION_NOTIFY) {
    xcb_xfixes_selection_notify_event_t *s = (void *)e;
    if (s->owner != win)
      todo = s->owner ? FETCH : s->subtype == XCB_XFIXES_SELECTION_EVENT_SET_SELECTION_OWNER ? FORGET : KEEP;
  } else if (t == XCB_SELECTION_REQUEST) {
    serve((void *)e);
  } else if (t == XCB_SELECTION_CLEAR) {
    own = 0;
  }
}

// событие X, для которого want() истинно, за ms миллисекунд (NULL - не дождались); остальные - other()
static xcb_generic_event_t *wait_for(int (*want)(xcb_generic_event_t *), int ms)
{
  long end = now_ms() + ms;
  for (;;) {
    xcb_generic_event_t *e;
    while ((e = xcb_poll_for_event(X))) {
      if (want(e))
        return e;
      other(e);
      free(e);
    }
    if (xcb_connection_has_error(X))
      exit(0);
    long left = end - now_ms();
    if (left <= 0)
      return NULL;
    xcb_flush(X);
    struct pollfd p = { xcb_get_file_descriptor(X), POLLIN, 0 };
    poll(&p, 1, left);
  }
}

static int is_notify(xcb_generic_event_t *e)
{
  return (e->response_type & 0x7f) == XCB_SELECTION_NOTIFY && ((xcb_selection_notify_event_t *)e)->requestor == win;
}

static int is_value(xcb_generic_event_t *e)
{
  xcb_property_notify_event_t *p = (void *)e;
  return (e->response_type & 0x7f) == XCB_PROPERTY_NOTIFY && p->window == win && p->atom == PROP &&
         p->state == XCB_PROPERTY_NEW_VALUE;
}

static int is_stamp(xcb_generic_event_t *e)
{
  xcb_property_notify_event_t *p = (void *)e;
  return (e->response_type & 0x7f) == XCB_PROPERTY_NOTIFY && p->window == win && p->atom == STAMP;
}

static xcb_get_property_reply_t *prop(void)
{
  return xcb_get_property_reply(X, xcb_get_property(X, 1, win, PROP, XCB_GET_PROPERTY_TYPE_ANY, 0, MAXTEXT / 4), NULL);
}

// текст из свойства PROP своего окна (читается с удалением), INCR - по частям; 0 - не вышло
static int take_prop(int latin1)
{
  xcb_get_property_reply_t *r = prop();
  char *buf = NULL;
  size_t n = 0;
  int incr, big = 0;
  if (!r)
    return 0;
  incr = r->type == INCR;
  if (!incr) {
    n = xcb_get_property_value_length(r);
    big = r->bytes_after > 0;
    if ((buf = malloc(n + 1)))
      memcpy(buf, xcb_get_property_value(r), n);
  }
  free(r);
  // INCR: программа кладёт текст частями, следующую - когда прочитана прежняя; пустая часть - конец
  while (incr) {
    xcb_generic_event_t *e = wait_for(is_value, 3000);
    if (!e || !(r = prop())) {
      free(e);
      free(buf);
      return 0;
    }
    free(e);
    size_t l = xcb_get_property_value_length(r);
    if (!l) {
      incr = 0;
    } else if (big || n + l > MAXTEXT) {
      big = 1;  // дочитать до конца, иначе программа так и будет ждать, но не хранить
    } else {
      char *nb = realloc(buf, n + l + 1);
      if (nb) {
        memcpy(nb + n, xcb_get_property_value(r), l);
        buf = nb;
        n += l;
      } else {
        big = 1;
      }
    }
    free(r);
  }
  if (big || (!buf && n)) {
    free(buf);
    return 0;
  }
  if (latin1 && buf) {
    size_t m;
    char *u = from_latin1((unsigned char *)buf, n, &m);
    free(buf);
    buf = u;
    n = m;
  }
  set_text(buf, n);
  return 1;
}

// текст CLIPBOARD у владельца: UTF8_STRING, у старых программ - STRING
static int fetch(void)
{
  xcb_atom_t want[] = { UTF8, XCB_ATOM_STRING };
  for (int i = 0; i < 2; i++) {
    xcb_delete_property(X, win, PROP);
    xcb_convert_selection(X, win, CLIPBOARD, want[i], PROP, XCB_CURRENT_TIME);
    xcb_selection_notify_event_t *n = (void *)wait_for(is_notify, 3000);
    if (!n)
      return 0;
    int got = n->property != XCB_ATOM_NONE;
    free(n);
    if (got)
      return take_prop(want[i] == XCB_ATOM_STRING);
  }
  return 0;
}

// стать владельцем CLIPBOARD: со временем сервера (его даёт PropertyNotify на своё свойство), как велит ICCCM
static void take(void)
{
  xcb_change_property(X, XCB_PROP_MODE_REPLACE, win, STAMP, XCB_ATOM_INTEGER, 32, 0, "");
  xcb_property_notify_event_t *p = (void *)wait_for(is_stamp, 3000);
  own_time = p ? p->time : XCB_CURRENT_TIME;
  free(p);
  xcb_set_selection_owner(X, win, CLIPBOARD, own_time);
  xcb_get_selection_owner_reply_t *r = xcb_get_selection_owner_reply(X, xcb_get_selection_owner(X, CLIPBOARD), NULL);
  own = r && r->owner == win;
  free(r);
}

// программа X просит буфер демона
static void serve(xcb_selection_request_event_t *q)
{
  union {
    xcb_selection_notify_event_t n;
    char raw[32];
  } ev = { .n = { .response_type = XCB_SELECTION_NOTIFY, .time = q->time, .requestor = q->requestor,
                  .selection = q->selection, .target = q->target, .property = XCB_ATOM_NONE } };
  xcb_atom_t t = q->target, p = q->property ? q->property : q->target;  // старые программы свойство не называют
  if (own && q->selection == CLIPBOARD && text) {
    if (t == TARGETS) {
      xcb_atom_t list[] = { TARGETS, TIMESTAMP, UTF8, MIME_UTF8, TEXT, XCB_ATOM_STRING };
      xcb_change_property(X, XCB_PROP_MODE_REPLACE, q->requestor, p, XCB_ATOM_ATOM, 32, 6, list);
      ev.n.property = p;
    } else if (t == TIMESTAMP) {
      xcb_change_property(X, XCB_PROP_MODE_REPLACE, q->requestor, p, XCB_ATOM_INTEGER, 32, 1, &own_time);
      ev.n.property = p;
    } else if ((t == UTF8 || t == MIME_UTF8 || t == TEXT) && len <= maxreq) {
      xcb_change_property(X, XCB_PROP_MODE_REPLACE, q->requestor, p, t == MIME_UTF8 ? t : UTF8, 8, len, text);
      ev.n.property = p;
    } else if (t == XCB_ATOM_STRING) {
      size_t n;
      char *l = to_latin1((unsigned char *)text, len, &n);
      if (l && n <= maxreq) {
        xcb_change_property(X, XCB_PROP_MODE_REPLACE, q->requestor, p, XCB_ATOM_STRING, 8, n, l);
        ev.n.property = p;
      }
      free(l);
    }
  }
  xcb_send_event(X, 0, q->requestor, XCB_EVENT_MASK_NO_EVENT, ev.raw);
  xcb_flush(X);
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

static int read_all(int s, char *p, size_t n)
{
  while (n) {
    ssize_t r = read(s, p, n);
    if (r <= 0)
      return -1;
    p += r;
    n -= r;
  }
  return 0;
}

// текст CLIPBOARD - странице, в буфер браузера
static void to_page(void)
{
  struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(PAGE_PORT) };
  struct timeval tv = { 5, 0 };
  char head[40];
  int h = snprintf(head, sizeof head, "xclip - %zu\n", len), s = socket(AF_INET, SOCK_STREAM, 0);
  if (s < 0)
    return;
  inet_pton(AF_INET, PAGE_IP, &a.sin_addr);
  setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof tv);
  if (!connect(s, (void *)&a, sizeof a) && !write_all(s, head, h))
    write_all(s, text, len);
  close(s);
}

// буфер браузера от страницы: "SET длина\n" + текст - демон становится владельцем CLIPBOARD
static void from_page(int ls)
{
  struct timeval tv = { 5, 0 };
  char head[32], *buf;
  size_t h = 0, n;
  int c = accept(ls, NULL, NULL);
  if (c < 0)
    return;
  setsockopt(c, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof tv);
  while (h < sizeof head - 1 && read(c, head + h, 1) == 1 && head[h] != '\n')
    h++;
  head[h] = 0;
  if (sscanf(head, "SET %zu", &n) == 1 && n <= MAXTEXT && (buf = malloc(n + 1))) {
    if (read_all(c, buf, n)) {
      free(buf);
    } else {
      set_text(buf, n);
      take();
      write_all(c, own ? "OK\n" : "NO\n", 3);
    }
  }
  close(c);
}

int main(void)
{
  struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(PORT), .sin_addr.s_addr = htonl(INADDR_ANY) };
  int ls, on = 1, sn;
  signal(SIGPIPE, SIG_IGN);
  X = xcb_connect(NULL, &sn);
  if (xcb_connection_has_error(X))
    return 1;
  xcb_screen_iterator_t it = xcb_setup_roots_iterator(xcb_get_setup(X));
  for (; sn > 0 && it.rem > 1; sn--)
    xcb_screen_next(&it);
  const xcb_query_extension_reply_t *ext = xcb_get_extension_data(X, &xcb_xfixes_id);
  if (!ext || !ext->present)
    return 1;
  xfixes = ext->first_event;
  free(xcb_xfixes_query_version_reply(X, xcb_xfixes_query_version(X, 1, 0), NULL));

  uint32_t mask = XCB_EVENT_MASK_PROPERTY_CHANGE;
  win = xcb_generate_id(X);
  xcb_create_window(X, 0, win, it.data->root, 0, 0, 1, 1, 0, XCB_WINDOW_CLASS_INPUT_ONLY, XCB_COPY_FROM_PARENT,
                    XCB_CW_EVENT_MASK, &mask);
  CLIPBOARD = atom("CLIPBOARD");
  UTF8 = atom("UTF8_STRING");
  MIME_UTF8 = atom("text/plain;charset=utf-8");
  TEXT = atom("TEXT");
  TARGETS = atom("TARGETS");
  TIMESTAMP = atom("TIMESTAMP");
  INCR = atom("INCR");
  PROP = atom("KT_XCLIPD");
  STAMP = atom("KT_XCLIPD_TIME");
  xcb_xfixes_select_selection_input(X, win, CLIPBOARD, XCB_XFIXES_SELECTION_EVENT_MASK_SET_SELECTION_OWNER |
                                    XCB_XFIXES_SELECTION_EVENT_MASK_SELECTION_WINDOW_DESTROY |
                                    XCB_XFIXES_SELECTION_EVENT_MASK_SELECTION_CLIENT_CLOSE);
  maxreq = xcb_get_maximum_request_length(X) * 4 - 64;
  free(xcb_get_input_focus_reply(X, xcb_get_input_focus(X), NULL));  // запросы дошли до сервера
  // порт - последним: слушает - значит, буфер X уже под присмотром
  if ((ls = socket(AF_INET, SOCK_STREAM, 0)) < 0)
    return 1;
  setsockopt(ls, SOL_SOCKET, SO_REUSEADDR, &on, sizeof on);
  if (bind(ls, (void *)&a, sizeof a) || listen(ls, 4))
    return 0;  // порт занят: демон уже есть

  for (;;) {
    xcb_generic_event_t *e;
    while ((e = xcb_poll_for_event(X))) {
      other(e);
      free(e);
    }
    if (xcb_connection_has_error(X))
      return 0;
    int what = todo;
    todo = NOTHING;
    if (what == FETCH) {
      if (!fetch())
        set_text(NULL, 0);  // не текст (картинка) или программа не ответила
      else if (len)
        to_page();
      continue;
    }
    if (what == KEEP && text) {
      take();
      continue;
    }
    if (what == FORGET)
      set_text(NULL, 0);
    xcb_flush(X);
    struct pollfd p[2] = { { xcb_get_file_descriptor(X), POLLIN, 0 }, { ls, POLLIN, 0 } };
    if (poll(p, 2, -1) > 0 && p[1].revents & POLLIN)
      from_page(ls);
  }
}
