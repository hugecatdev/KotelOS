/* Громкость GreenOS, как в MATE: щелчок по значку на панели - над ним всплывает ползунок. Тянуть,
 * щёлкнуть по шкале или крутить колесо - громкость; кнопка с динамиком внизу - звук выкл/вкл; щелчок мимо,
 * Escape или Enter - закрыть. Клавиши: стрелки - шаг, M - выкл/вкл.
 * Уровень - Master карты (alsa-lib); у SB16 нет выключателя звука, поэтому «выкл» - Master 0, а прежний
 * уровень - в /tmp/.greenos-mute, как у /usr/lib/greenos/volume (колесо над значком), - они понимают друг друга.
 * Окно без рамки (override-redirect) и с захватом мыши и клавиатуры - как меню. Картинка окна рисуется в
 * своём буфере со сглаженными краями (X сам не сглаживает) и кладётся целиком, проценты - Xft поверх; на
 * кнопке - значки MATE «звук есть» и «звук выключен». Собирает build.sh. */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xft/Xft.h>
#include <X11/keysym.h>
#include <alsa/asoundlib.h>
#include <locale.h>
#include <math.h>
#include <png.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define W 60
#define H 224
#define TRAY 36          /* высота панели JWM (Tray в /etc/system.jwmrc) - окно встаёт над ней */
#define T0 44            /* шкала по высоте: верх - громче */
#define T1 (H - 62)
#define KNOB 9
#define MUTE "/tmp/.greenos-mute"
#define ICONS "/usr/share/greenos/icons/"

static Display *dpy;
static int scr;
static Window win;
static Pixmap buf;
static GC gc;
static XImage *img;
static unsigned int *pix;  /* картинка окна, 0xRRGGBB - экран X 24-битный (startx) */
typedef struct { int w, h; unsigned char *rgba; } Icon;
static Icon ic_on, ic_off;
static XftDraw *xd;
static XftFont *f_pct;
static XftColor c_text, c_dim;
static snd_mixer_t *mx;
static snd_mixer_elem_t *el;
static long vmin, vmax, level;
static int muted, dragging, pressed;
static const int mbx = W / 2 - 20, mby = H - 48, mbw = 40, mbh = 36;

static unsigned long px(const char *hex) {
  XColor c;
  XParseColor(dpy, DefaultColormap(dpy, scr), hex, &c);
  XAllocColor(dpy, DefaultColormap(dpy, scr), &c);
  return c.pixel;
}

static unsigned int rgb(const char *hex) {
  return (unsigned int)strtoul(hex + 1, NULL, 16);
}

/* точка цвета c с непрозрачностью a поверх того, что в буфере */
static void blend(int x, int y, unsigned int c, double a) {
  if (x < 0 || y < 0 || x >= W || y >= H || a <= 0)
    return;
  if (a > 1)
    a = 1;
  unsigned int d = pix[y * W + x], o = 0;
  for (int b = 0; b < 24; b += 8)
    o |= (unsigned int)(((c >> b) & 255) * a + ((d >> b) & 255) * (1 - a) + 0.5) << b;
  pix[y * W + x] = o;
}

/* скруглённый прямоугольник (и круг: w = h = 2r) со сглаженным краем: покрытие точки - по расстоянию
 * от её центра до фигуры. Пустой (w или h <= 0) не рисуется, радиус - не больше половины стороны */
static void rrect(double x, double y, double w, double h, double r, unsigned int c) {
  if (w <= 0 || h <= 0)
    return;
  r = fmin(r, fmin(w, h) / 2);
  for (int j = (int)floor(y); j < (int)ceil(y + h); j++)
    for (int i = (int)floor(x); i < (int)ceil(x + w); i++) {
      double qx = fabs(i + 0.5 - (x + w / 2)) - (w / 2 - r), qy = fabs(j + 0.5 - (y + h / 2)) - (h / 2 - r);
      double d = hypot(fmax(qx, 0), fmax(qy, 0)) + fmin(fmax(qx, qy), 0) - r;
      blend(i, j, c, 0.5 - d);
    }
}

/* значок темы (48x48) -> вдвое меньше, усреднением с учётом прозрачности - без ореолов по краю */
static void load_icon(Icon *ic, const char *path) {
  png_image im;
  memset(&im, 0, sizeof im);
  im.version = PNG_IMAGE_VERSION;
  if (!png_image_begin_read_from_file(&im, path))
    return;
  im.format = PNG_FORMAT_RGBA;
  unsigned char *src = malloc(PNG_IMAGE_SIZE(im));
  if (!src || !png_image_finish_read(&im, NULL, src, 0, NULL)) {
    free(src);
    return;
  }
  ic->w = im.width / 2;
  ic->h = im.height / 2;
  ic->rgba = malloc(ic->w * ic->h * 4);
  for (int y = 0; y < ic->h; y++)
    for (int x = 0; x < ic->w; x++) {
      unsigned int a = 0, c[3] = { 0, 0, 0 };
      for (int k = 0; k < 4; k++) {
        unsigned char *p = src + ((2 * y + k / 2) * im.width + 2 * x + k % 2) * 4;
        a += p[3];
        for (int b = 0; b < 3; b++)
          c[b] += p[b] * p[3];
      }
      unsigned char *q = ic->rgba + (y * ic->w + x) * 4;
      for (int b = 0; b < 3; b++)
        q[b] = a ? c[b] / a : 0;
      q[3] = a / 4;
    }
  free(src);
}

static void icon(Icon *ic, int x, int y) {
  for (int j = 0; ic->rgba && j < ic->h; j++)
    for (int i = 0; i < ic->w; i++) {
      unsigned char *q = ic->rgba + (j * ic->w + i) * 4;
      blend(x + i, y + j, (unsigned int)q[0] << 16 | q[1] << 8 | q[2], q[3] / 255.0);
    }
}

static long read_saved(void) {
  long v = vmax;
  FILE *f = fopen(MUTE, "r");
  if (f) {
    if (fscanf(f, "%ld", &v) != 1)
      v = vmax;
    fclose(f);
  }
  return v < vmin ? vmin : v > vmax ? vmax : v;
}

static void mixer_set(long v) {
  snd_mixer_selem_set_playback_volume_all(el, v);
}

static void set_level(long v) {
  v = v < vmin ? vmin : v > vmax ? vmax : v;
  if (muted) {
    remove(MUTE);
    muted = 0;
  } else if (v == level)
    return;
  level = v;
  mixer_set(v);
}

static void toggle_mute(void) {
  if (muted) {
    remove(MUTE);
    muted = 0;
    mixer_set(level);
    return;
  }
  FILE *f = fopen(MUTE, "w");
  if (!f)
    return;
  fprintf(f, "%ld\n", level);
  fclose(f);
  muted = 1;
  mixer_set(vmin);
}

static int knob_y(void) {
  return T1 - (int)((level - vmin) * (T1 - T0) / (vmax > vmin ? vmax - vmin : 1));
}

static long level_at(int y) {
  long span = vmax - vmin;
  return vmin + ((long)(T1 - y) * span + (T1 - T0) / 2) / (T1 - T0);
}

static void draw(void) {
  char s[16];
  for (int i = 0; i < W * H; i++)
    pix[i] = 0xffffff;
  int ky = knob_y(), cx = W / 2;
  rrect(cx - 3, T0, 6, T1 - T0, 3, rgb("#dde6d6"));
  rrect(cx - 3, ky, 6, T1 - ky, 3, rgb(muted ? "#b9c4b3" : "#3dbb2b"));
  rrect(cx - KNOB, ky - KNOB, 2 * KNOB, 2 * KNOB, KNOB, rgb(muted ? "#9aa894" : dragging ? "#2a8d1c" : "#2e9f1f"));
  rrect(cx - KNOB + 3, ky - KNOB + 3, 2 * KNOB - 6, 2 * KNOB - 6, KNOB - 3, 0xffffff);
  rrect(mbx, mby, mbw, mbh, 6, rgb(pressed ? "#cfeec4" : muted ? "#f6e6e4" : "#eef3ea"));
  Icon *ic = muted ? &ic_off : &ic_on;
  icon(ic, mbx + (mbw - ic->w) / 2, mby + (mbh - ic->h) / 2);
  XPutImage(dpy, buf, gc, img, 0, 0, 0, 0, W, H);

  if (muted)
    snprintf(s, sizeof s, "Выкл");
  else
    snprintf(s, sizeof s, "%ld%%", (level - vmin) * 100 / (vmax > vmin ? vmax - vmin : 1));
  XGlyphInfo g;
  XftTextExtentsUtf8(dpy, f_pct, (const FcChar8 *)s, strlen(s), &g);
  XftDrawStringUtf8(xd, muted ? &c_dim : &c_text, f_pct, (W - g.xOff) / 2, 26, (const FcChar8 *)s, strlen(s));
  XCopyArea(dpy, buf, win, gc, 0, 0, W, H, 0, 0);
  XFlush(dpy);
}

static int on_scale(int x, int y) {
  return x >= 0 && x < W && y >= T0 - KNOB - 6 && y <= T1 + KNOB + 6;
}

static int on_mute(int x, int y) {
  return x >= mbx && x < mbx + mbw && y >= mby && y < mby + mbh;
}

/* JWM ещё держит мышь, пока отпускают кнопку на панели: захват - с повтором, как у меню */
static void grab(void) {
  struct timespec ms = { 0, 1000000 };
  for (int i = 0; i < 500; i++) {
    if (XGrabPointer(dpy, win, False, ButtonPressMask | ButtonReleaseMask | PointerMotionMask, GrabModeAsync,
                     GrabModeAsync, None, None, CurrentTime) == GrabSuccess)
      break;
    nanosleep(&ms, NULL);
  }
  for (int i = 0; i < 500; i++) {
    if (XGrabKeyboard(dpy, win, True, GrabModeAsync, GrabModeAsync, CurrentTime) == GrabSuccess)
      break;
    nanosleep(&ms, NULL);
  }
}

int main(void) {
  setlocale(LC_ALL, "");
  snd_mixer_selem_id_t *sid;
  snd_mixer_selem_id_alloca(&sid);
  snd_mixer_selem_id_set_name(sid, "Master");
  if (snd_mixer_open(&mx, 0) < 0 || snd_mixer_attach(mx, "default") < 0 || snd_mixer_selem_register(mx, NULL, NULL) < 0 ||
      snd_mixer_load(mx) < 0 || !(el = snd_mixer_find_selem(mx, sid))) {
    fprintf(stderr, "mixer: нет звуковой карты (Master)\n");
    return 1;
  }
  snd_mixer_selem_get_playback_volume_range(el, &vmin, &vmax);
  snd_mixer_selem_get_playback_volume(el, SND_MIXER_SCHN_FRONT_LEFT, &level);
  if ((muted = !access(MUTE, F_OK)))
    level = read_saved();

  if (!(dpy = XOpenDisplay(NULL))) {
    fprintf(stderr, "mixer: нет X (DISPLAY)\n");
    return 1;
  }
  scr = DefaultScreen(dpy);
  Window root = RootWindow(dpy, scr), rr, cw;
  int rx = 0, ry = 0, wx, wy;
  unsigned mask;
  XQueryPointer(dpy, root, &rr, &cw, &rx, &ry, &wx, &wy, &mask);
  int sw = DisplayWidth(dpy, scr), shh = DisplayHeight(dpy, scr);
  int x = rx - W / 2;
  x = x < 4 ? 4 : x > sw - W - 6 ? sw - W - 6 : x;
  XSetWindowAttributes a = { .override_redirect = True, .background_pixel = px("#ffffff"), .border_pixel = px("#b0d0a0") };
  win = XCreateWindow(dpy, root, x, shh - TRAY - H - 6, W, H, 1, CopyFromParent, InputOutput, CopyFromParent,
                      CWOverrideRedirect | CWBackPixel | CWBorderPixel, &a);
  XClassHint ch = { "greenos-mixer", "GreenMixer" };
  XSetClassHint(dpy, win, &ch);
  XSelectInput(dpy, win, ExposureMask | KeyPressMask | ButtonPressMask | ButtonReleaseMask | PointerMotionMask);
  gc = XCreateGC(dpy, win, 0, NULL);
  buf = XCreatePixmap(dpy, win, W, H, DefaultDepth(dpy, scr));
  pix = calloc(W * H, sizeof *pix);
  img = XCreateImage(dpy, DefaultVisual(dpy, scr), DefaultDepth(dpy, scr), ZPixmap, 0, (char *)pix, W, H, 32, W * 4);
  load_icon(&ic_on, ICONS "volume.png");
  load_icon(&ic_off, ICONS "volume-muted.png");
  Visual *v = DefaultVisual(dpy, scr);
  Colormap cm = DefaultColormap(dpy, scr);
  xd = XftDrawCreate(dpy, buf, v, cm);
  f_pct = XftFontOpenName(dpy, scr, "Cantarell:size=10:weight=bold");
  XftColorAllocName(dpy, v, cm, "#24301f", &c_text);
  XftColorAllocName(dpy, v, cm, "#8a9784", &c_dim);
  XMapRaised(dpy, win);
  grab();

  for (;;) {
    XEvent e;
    XNextEvent(dpy, &e);
    switch (e.type) {
    case Expose:
      if (e.xexpose.count == 0)
        draw();
      break;
    case ButtonPress: {
      int bx = e.xbutton.x, by = e.xbutton.y;
      if (bx < 0 || by < 0 || bx >= W || by >= H)
        return 0;
      if (e.xbutton.button == 4 || e.xbutton.button == 5)
        set_level(level + (e.xbutton.button == 4 ? 1 : -1));
      else if (e.xbutton.button == 1 && on_scale(bx, by)) {
        dragging = 1;
        set_level(level_at(by));
      } else if (e.xbutton.button == 1 && on_mute(bx, by))
        pressed = 1;
      draw();
      break;
    }
    case MotionNotify:
      if (dragging) {
        while (XCheckTypedWindowEvent(dpy, win, MotionNotify, &e))
          ;
        set_level(level_at(e.xmotion.y));
        draw();
      }
      break;
    case ButtonRelease:
      if (pressed && on_mute(e.xbutton.x, e.xbutton.y))
        toggle_mute();
      dragging = pressed = 0;
      draw();
      break;
    case KeyPress: {
      KeySym k = XLookupKeysym(&e.xkey, 0);
      if (k == XK_Escape || k == XK_Return || k == XK_KP_Enter)
        return 0;
      if (k == XK_Up || k == XK_Right || k == XK_Down || k == XK_Left)
        set_level(level + (k == XK_Up || k == XK_Right ? 1 : -1));
      else if (k == XK_m || k == XK_M)
        toggle_mute();
      draw();
      break;
    }
    }
  }
}
