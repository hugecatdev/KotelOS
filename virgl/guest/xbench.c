/*
 * 2D сервера X так, как рисуют программы на Qt Widgets (Designer): готовая картинка окна
 * (XPutImage и XShmPutImage, как QXcbBackingStore), прокрутка (XCopyArea), заливка, текст.
 * Каждая проба - серия операций с XSync в конце, итог - мс на операцию (меньше - лучше).
 *   xbench [секунд на пробу]
 */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/XShm.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <time.h>

#define W 400
#define H 300

static double now(void)
{
   struct timespec t;
   clock_gettime(CLOCK_MONOTONIC, &t);
   return t.tv_sec + t.tv_nsec / 1e9;
}

typedef void (*op_fn)(int i);
static Display *d;
static Window win;
static GC gc;
static XImage *img, *shm_img;
static XShmSegmentInfo shm;
static XFontStruct *font;

static void op_put(int i) { XPutImage(d, win, gc, img, 0, 0, i & 7, i & 7, W, H); }
static void op_shm(int i) { XShmPutImage(d, win, gc, shm_img, 0, 0, i & 7, i & 7, W, H, False); }
static void op_copy(int i) { (void)i; XCopyArea(d, win, win, gc, 0, 10, W, H - 10, 0, 0); }
static void op_fill(int i) { XSetForeground(d, gc, i & 1 ? 0xffffff : 0x3070c0); XFillRectangle(d, win, gc, 0, 0, W, H); }
static void op_text(int i)
{
   static const char line[] = "QLabel *label = new QLabel(tr(\"Hello, World\"), this); // 0123456789";
   XSetForeground(d, gc, i & 1 ? 0 : 0x202020);
   for (int y = 0; y < 20; y++)
      XDrawString(d, win, gc, 4, 14 + y * 14, line, sizeof(line) - 1);
}

static void bench(const char *name, op_fn fn, double secs)
{
   XSync(d, False);
   double t0 = now();
   int n = 0;
   while (now() - t0 < secs) {
      for (int k = 0; k < 4; k++)
         fn(n++);
      XSync(d, False);
   }
   double t = now() - t0;
   printf("%-8s %7.2f мс/оп  (%d за %.1f с)\n", name, t * 1000 / n, n, t);
   fflush(stdout);
}

int main(int argc, char **argv)
{
   double secs = argc > 1 ? atof(argv[1]) : 5;
   d = XOpenDisplay(NULL);
   if (!d) {
      fprintf(stderr, "нет дисплея\n");
      return 2;
   }
   int scr = DefaultScreen(d);
   win = XCreateSimpleWindow(d, RootWindow(d, scr), 300, 40, W, H, 0, 0, 0xffffff);
   XSelectInput(d, win, ExposureMask);
   XMapWindow(d, win);
   for (XEvent e;;) {
      XNextEvent(d, &e);
      if (e.type == Expose)
         break;
   }
   gc = XCreateGC(d, win, 0, NULL);
   font = XLoadQueryFont(d, "fixed");
   if (font)
      XSetFont(d, gc, font->fid);
   Visual *vis = DefaultVisual(d, scr);
   int depth = DefaultDepth(d, scr);

   char *data = malloc(W * H * 4);
   for (int i = 0; i < W * H; i++)
      ((unsigned *)data)[i] = (i * 2654435761u) ^ (i / W * 0x010101);
   img = XCreateImage(d, vis, depth, ZPixmap, 0, data, W, H, 32, 0);

   /* MIT-SHM - если в ядре есть System V IPC (иначе и Qt рисует обычным XPutImage) */
   if (XShmQueryExtension(d)) {
      shm_img = XShmCreateImage(d, vis, depth, ZPixmap, NULL, &shm, W, H);
      shm.shmid = shmget(IPC_PRIVATE, shm_img->bytes_per_line * H, IPC_CREAT | 0600);
      if (shm.shmid < 0) {
         puts("shmput   нет (shmget: в ядре нет System V IPC)");
         XDestroyImage(shm_img);
         shm_img = NULL;
      } else {
         shm.shmaddr = shm_img->data = shmat(shm.shmid, NULL, 0);
         shm.readOnly = False;
         memcpy(shm_img->data, data, W * H * 4);
         XShmAttach(d, &shm);
         shmctl(shm.shmid, IPC_RMID, NULL);
      }
   }

   bench("putimage", op_put, secs);
   if (shm_img)
      bench("shmput", op_shm, secs);
   bench("copyarea", op_copy, secs);
   bench("fill", op_fill, secs);
   if (font)
      bench("text", op_text, secs);
   puts("XBENCH-DONE");
   return 0;
}
