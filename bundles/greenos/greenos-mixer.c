/* Громкость GreenOS, как в MATE: щелчок по значку на панели - над ним всплывает ползунок. Тянуть,
 * щёлкнуть по шкале или крутить колесо - громкость; кнопка с динамиком внизу - звук выкл/вкл; щелчок мимо,
 * Escape или Enter - закрыть. Клавиши: стрелки - шаг, M - выкл/вкл.
 * Уровень - Master карты (alsa-lib); у SB16 нет выключателя звука, поэтому «выкл» - Master 0, а прежний
 * уровень - в /tmp/.greenos-mute, как у /usr/lib/greenos/volume (колесо над значком), - они понимают друг друга.
 * Окно без рамки (override-redirect) и с захватом мыши и клавиатуры - как меню. Собирает build.sh. */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xft/Xft.h>
#include <X11/keysym.h>
#include <alsa/asoundlib.h>
#include <locale.h>
#include <stdio.h>
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

static Display *dpy;
static int scr;
static Window win;
static Pixmap buf;
static GC gc;
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

static void rrect(int x, int y, int w, int h, int r, unsigned long color) {
  XSetForeground(dpy, gc, color);
  XFillRectangle(dpy, buf, gc, x + r, y, w - 2 * r, h);
  XFillRectangle(dpy, buf, gc, x, y + r, w, h - 2 * r);
  XFillArc(dpy, buf, gc, x, y, 2 * r, 2 * r, 90 * 64, 90 * 64);
  XFillArc(dpy, buf, gc, x + w - 2 * r - 1, y, 2 * r, 2 * r, 0, 90 * 64);
  XFillArc(dpy, buf, gc, x, y + h - 2 * r - 1, 2 * r, 2 * r, 180 * 64, 90 * 64);
  XFillArc(dpy, buf, gc, x + w - 2 * r - 1, y + h - 2 * r - 1, 2 * r, 2 * r, 270 * 64, 90 * 64);
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
  XSetForeground(dpy, gc, px("#ffffff"));
  XFillRectangle(dpy, buf, gc, 0, 0, W, H);
  if (muted)
    snprintf(s, sizeof s, "Выкл");
  else
    snprintf(s, sizeof s, "%ld%%", (level - vmin) * 100 / (vmax > vmin ? vmax - vmin : 1));
  XGlyphInfo g;
  XftTextExtentsUtf8(dpy, f_pct, (const FcChar8 *)s, strlen(s), &g);
  XftDrawStringUtf8(xd, muted ? &c_dim : &c_text, f_pct, (W - g.xOff) / 2, 26, (const FcChar8 *)s, strlen(s));

  int ky = knob_y(), cx = W / 2;
  rrect(cx - 3, T0, 6, T1 - T0, 3, px("#dde6d6"));
  rrect(cx - 3, ky, 6, T1 - ky, 3, px(muted ? "#b9c4b3" : "#3dbb2b"));
  XSetForeground(dpy, gc, px(muted ? "#9aa894" : dragging ? "#2a8d1c" : "#2e9f1f"));
  XFillArc(dpy, buf, gc, cx - KNOB, ky - KNOB, 2 * KNOB, 2 * KNOB, 0, 360 * 64);
  XSetForeground(dpy, gc, px("#ffffff"));
  XFillArc(dpy, buf, gc, cx - KNOB + 3, ky - KNOB + 3, 2 * KNOB - 6, 2 * KNOB - 6, 0, 360 * 64);

  /* кнопка: динамик, с волнами - звук есть, с крестиком - выключен */
  rrect(mbx, mby, mbw, mbh, 4, px(pressed ? "#cfeec4" : muted ? "#f3e3e1" : "#eef3ea"));
  int sx = cx - 9, sy = mby + mbh / 2;
  XSetForeground(dpy, gc, px("#24301f"));
  XFillRectangle(dpy, buf, gc, sx, sy - 4, 5, 8);
  XPoint cone[] = { { sx + 4, sy - 4 }, { sx + 10, sy - 10 }, { sx + 10, sy + 10 }, { sx + 4, sy + 4 } };
  XFillPolygon(dpy, buf, gc, cone, 4, Convex, CoordModeOrigin);
  XSetLineAttributes(dpy, gc, 2, LineSolid, CapRound, JoinRound);
  if (muted) {
    XSetForeground(dpy, gc, px("#d0453a"));
    XDrawLine(dpy, buf, gc, sx + 14, sy - 5, sx + 22, sy + 5);
    XDrawLine(dpy, buf, gc, sx + 14, sy + 5, sx + 22, sy - 5);
  } else {
    XDrawArc(dpy, buf, gc, sx + 6, sy - 6, 12, 12, -50 * 64, 100 * 64);
    XDrawArc(dpy, buf, gc, sx + 4, sy - 11, 22, 22, -50 * 64, 100 * 64);
  }
  XSetLineAttributes(dpy, gc, 1, LineSolid, CapButt, JoinMiter);
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
