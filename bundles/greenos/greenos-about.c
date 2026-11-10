/* «О системе GreenOS»: окно на Xlib + Xft (+ XRender и libpng для логотипа) - то, что и так есть
 * у JWM. Имя, версия, подпись и автор - /usr/share/greenos/release (по строке), остальное - из ядра и /proc.
 * Закрыть - кнопкой, Enter, Escape или крестиком окна. Собирает bundles/greenos/build.sh. */
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xft/Xft.h>
#include <X11/extensions/Xrender.h>
#include <X11/keysym.h>
#include <locale.h>
#include <png.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>

#define W 500
#define H 353
#define LOGO "/usr/share/greenos/logo.png"
#define RELEASE "/usr/share/greenos/release"

static Display *dpy;
static int scr;
static Window win;
static XftDraw *xd;
static XftFont *f_big, *f_mid, *f_txt, *f_bold, *f_small;
static XftColor c_text, c_dim, c_white, c_green;
static GC gc;
static Picture logo;
static int logo_w, logo_h;
static int hover, pressed;
static char line[8][160], name[64] = "GreenOS", version[96] = "1.0", footer[512] = "";
static int nlines;
static const char *labels[] = { "Ядро", "Процессор", "Память", "Время работы", "Оболочка", "Сборка", "Автор" };
static const int bx = W - 150, by = H - 54, bw = 128, bh = 36;

static unsigned long px(const char *hex) {
  XColor c;
  XParseColor(dpy, DefaultColormap(dpy, scr), hex, &c);
  XAllocColor(dpy, DefaultColormap(dpy, scr), &c);
  return c.pixel;
}

static void rrect(int x, int y, int w, int h, int r, unsigned long color) {
  XSetForeground(dpy, gc, color);
  XFillRectangle(dpy, win, gc, x + r, y, w - 2 * r, h);
  XFillRectangle(dpy, win, gc, x, y + r, w, h - 2 * r);
  XFillArc(dpy, win, gc, x, y, 2 * r, 2 * r, 90 * 64, 90 * 64);
  XFillArc(dpy, win, gc, x + w - 2 * r - 1, y, 2 * r, 2 * r, 0, 90 * 64);
  XFillArc(dpy, win, gc, x, y + h - 2 * r - 1, 2 * r, 2 * r, 180 * 64, 90 * 64);
  XFillArc(dpy, win, gc, x + w - 2 * r - 1, y + h - 2 * r - 1, 2 * r, 2 * r, 270 * 64, 90 * 64);
}

static int text_w(XftFont *f, const char *s) {
  XGlyphInfo g;
  XftTextExtentsUtf8(dpy, f, (const FcChar8 *)s, strlen(s), &g);
  return g.xOff;
}

static void text(XftFont *f, XftColor *c, int x, int y, const char *s) {
  XftDrawStringUtf8(xd, c, f, x, y, (const FcChar8 *)s, strlen(s));
}

static void load_logo(void) {
  png_image img;
  memset(&img, 0, sizeof img);
  img.version = PNG_IMAGE_VERSION;
  png_image_begin_read_from_file(&img, LOGO);
  img.format = PNG_FORMAT_BGRA;
  unsigned char *buf = malloc(PNG_IMAGE_SIZE(img));
  png_image_finish_read(&img, NULL, buf, 0, NULL);
  for (unsigned i = 0; i < img.width * img.height; i++) {  /* XRender ждёт цвет, умноженный на альфу */
    unsigned char *p = buf + i * 4;
    for (int k = 0; k < 3; k++)
      p[k] = p[k] * p[3] / 255;
  }
  logo_w = img.width;
  logo_h = img.height;
  Pixmap pm = XCreatePixmap(dpy, win, logo_w, logo_h, 32);
  XImage *xi = XCreateImage(dpy, NULL, 32, ZPixmap, 0, (char *)buf, logo_w, logo_h, 32, 0);
  GC g = XCreateGC(dpy, pm, 0, NULL);
  XPutImage(dpy, pm, g, xi, 0, 0, 0, 0, logo_w, logo_h);
  XFreeGC(dpy, g);
  XDestroyImage(xi);
  logo = XRenderCreatePicture(dpy, pm, XRenderFindStandardFormat(dpy, PictStandardARGB32), 0, NULL);
  XFreePixmap(dpy, pm);
}

static void read_info(void) {
  FILE *f;
  char buf[512];
  struct utsname u;
  /* release: имя, версия, подпись, автор - по строке */
  char *dst[] = { name, version, footer, line[6] };
  size_t len[] = { sizeof name, sizeof version, sizeof footer, sizeof line[6] };
  f = fopen(RELEASE, "r");
  for (int i = 0; i < 4; i++) {
    fgets(buf, sizeof buf, f);
    buf[strcspn(buf, "\n")] = 0;
    snprintf(dst[i], len[i], "%s", buf);
  }
  fclose(f);
  uname(&u);
  snprintf(line[0], sizeof line[0], "%s %s (%s)", u.sysname, u.release, u.machine);
  f = fopen("/proc/cpuinfo", "r");
  while (fgets(buf, sizeof buf, f))
    if (!strncmp(buf, "model name", 10)) {
      char *v = strchr(buf, ':') + 1;
      v += strspn(v, " \t");
      v[strcspn(v, "\n")] = 0;
      snprintf(line[1], sizeof line[1], "%s", v);
      break;
    }
  fclose(f);
  long total = 0, avail = 0;
  f = fopen("/proc/meminfo", "r");
  while (fgets(buf, sizeof buf, f)) {
    sscanf(buf, "MemTotal: %ld", &total);
    sscanf(buf, "MemAvailable: %ld", &avail);
  }
  fclose(f);
  snprintf(line[2], sizeof line[2], "%ld МБ, свободно %ld МБ", total / 1024, avail / 1024);
  double up;
  f = fopen("/proc/uptime", "r");
  fscanf(f, "%lf", &up);
  fclose(f);
  snprintf(line[3], sizeof line[3], "%d ч %02d мин", (int)up / 3600, (int)up / 60 % 60);
  snprintf(line[4], sizeof line[4], "JWM 2.4.6, X.Org");
  f = fopen("/usr/lib/os-release", "r");
  while (fgets(buf, sizeof buf, f))
    if (!strncmp(buf, "VERSION_ID=", 11)) {
      buf[strcspn(buf, "\n")] = 0;
      snprintf(line[5], sizeof line[5], "%s", buf + 11);
    }
  fclose(f);
  nlines = 7;
}

static void draw(void) {
  XSetForeground(dpy, gc, px("#fbfcfa"));
  XFillRectangle(dpy, win, gc, 0, 0, W, H);
  XSetForeground(dpy, gc, px("#eef3ea"));
  XFillRectangle(dpy, win, gc, 0, 0, 150, H);
  XRenderComposite(dpy, PictOpOver, logo, None, XftDrawPicture(xd), 0, 0, 0, 0, (150 - logo_w) / 2, 34, logo_w, logo_h);
  text(f_big, &c_text, 172, 58, name);
  text(f_mid, &c_green, 172, 84, version);
  XSetForeground(dpy, gc, px("#dbe5d3"));
  XFillRectangle(dpy, win, gc, 172, 100, W - 196, 1);
  int lw = 0;
  for (int i = 0; i < nlines; i++)
    if (text_w(f_bold, labels[i]) > lw)
      lw = text_w(f_bold, labels[i]);
  for (int i = 0; i < nlines; i++) {
    text(f_bold, &c_dim, 172, 126 + i * 23, labels[i]);
    text(f_txt, &c_text, 172 + lw + 14, 126 + i * 23, line[i]);
  }
  if (*footer) {
    /* подпись - под логотипом, в несколько строк по словам */
    char tmp[sizeof footer], out[sizeof footer] = "";
    int y = 34 + logo_h + 34;
    snprintf(tmp, sizeof tmp, "%s", footer);
    for (char *w = strtok(tmp, " "); w; w = strtok(NULL, " ")) {
      char next[sizeof footer];
      snprintf(next, sizeof next, "%s%s%s", out, *out ? " " : "", w);
      if (*out && text_w(f_small, next) > 128) {
        text(f_small, &c_dim, (150 - text_w(f_small, out)) / 2, y, out);
        y += 16;
        snprintf(out, sizeof out, "%s", w);
      } else
        snprintf(out, sizeof out, "%s", next);
    }
    if (*out)
      text(f_small, &c_dim, (150 - text_w(f_small, out)) / 2, y, out);
  }
  rrect(bx, by, bw, bh, 2, px("#2b8a1d"));
  rrect(bx + 1, by + 1, bw - 2, bh - 2, 1, px(pressed ? "#2e9a1f" : hover ? "#5fd04a" : "#3dbb2b"));
  const char *b = "Закрыть";
  text(f_txt, &c_white, bx + (bw - text_w(f_txt, b)) / 2, by + bh / 2 + f_txt->ascent / 2 - 1, b);
  XFlush(dpy);
}

static int inside(int x, int y) {
  return x >= bx && x < bx + bw && y >= by && y < by + bh;
}

int main(void) {
  setlocale(LC_ALL, "");
  dpy = XOpenDisplay(NULL);
  scr = DefaultScreen(dpy);
  read_info();
  win = XCreateSimpleWindow(dpy, RootWindow(dpy, scr), 0, 0, W, H, 0, 0, px("#fbfcfa"));
  const char *title = "О системе GreenOS";
  XClassHint ch = { "greenos-about", "GreenAbout" };
  XSizeHints sh = { .flags = PMinSize | PMaxSize, .min_width = W, .max_width = W, .min_height = H, .max_height = H };
  Xutf8SetWMProperties(dpy, win, title, title, NULL, 0, &sh, NULL, &ch);
  XChangeProperty(dpy, win, XInternAtom(dpy, "_NET_WM_NAME", False), XInternAtom(dpy, "UTF8_STRING", False), 8,
                  PropModeReplace, (const unsigned char *)title, strlen(title));
  Atom del = XInternAtom(dpy, "WM_DELETE_WINDOW", False);
  XSetWMProtocols(dpy, win, &del, 1);
  XSelectInput(dpy, win, ExposureMask | KeyPressMask | ButtonPressMask | ButtonReleaseMask | PointerMotionMask | LeaveWindowMask);
  gc = XCreateGC(dpy, win, 0, NULL);
  xd = XftDrawCreate(dpy, win, DefaultVisual(dpy, scr), DefaultColormap(dpy, scr));
  f_big = XftFontOpenName(dpy, scr, "Cantarell:size=22:weight=bold");
  f_mid = XftFontOpenName(dpy, scr, "Cantarell:size=12");
  f_txt = XftFontOpenName(dpy, scr, "Cantarell:size=10");
  f_bold = XftFontOpenName(dpy, scr, "Cantarell:size=10:weight=bold");
  f_small = XftFontOpenName(dpy, scr, "Cantarell:size=8");
  Visual *v = DefaultVisual(dpy, scr);
  Colormap cm = DefaultColormap(dpy, scr);
  XftColorAllocName(dpy, v, cm, "#24301f", &c_text);
  XftColorAllocName(dpy, v, cm, "#6b7866", &c_dim);
  XftColorAllocName(dpy, v, cm, "#ffffff", &c_white);
  XftColorAllocName(dpy, v, cm, "#2e9a1f", &c_green);
  load_logo();
  XMapWindow(dpy, win);
  for (;;) {
    XEvent e;
    XNextEvent(dpy, &e);
    switch (e.type) {
    case Expose:
      if (e.xexpose.count == 0)
        draw();
      break;
    case MotionNotify:
      if (inside(e.xmotion.x, e.xmotion.y) != hover) {
        hover = !hover;
        draw();
      }
      break;
    case LeaveNotify:
      if (hover) {
        hover = 0;
        draw();
      }
      break;
    case ButtonPress:
      if (e.xbutton.button == 1 && inside(e.xbutton.x, e.xbutton.y)) {
        pressed = 1;
        draw();
      }
      break;
    case ButtonRelease:
      if (pressed && inside(e.xbutton.x, e.xbutton.y))
        return 0;
      pressed = 0;
      draw();
      break;
    case KeyPress: {
      KeySym k = XLookupKeysym(&e.xkey, 0);
      if (k == XK_Escape || k == XK_Return || k == XK_KP_Enter)
        return 0;
      break;
    }
    case ClientMessage:
      if ((Atom)e.xclient.data.l[0] == del)
        return 0;
      break;
    }
  }
}
