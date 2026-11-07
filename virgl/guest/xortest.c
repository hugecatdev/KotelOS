/*
 * Логические операции X (GC function) на экране: на узор из полос рисуются прямоугольники с
 * GXxor (дважды - узор должен вернуться, один раз - инверсия), GXinvert, GXor, GXand, GXequiv;
 * результат читается XGetImage и сверяется с ожидаемым. Так рисуют контуры twm и выделение.
 *   xortest  -> строки "имя OK|FAIL (неверных пикселей N)"
 */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#define W 64
#define H 64

static unsigned long pattern(int x, int y)
{
   /* полосы: чёрный, белый, красный, зелёный; каналы - 0 или 255 */
   static const unsigned long c[4] = { 0x000000, 0xffffff, 0xff0000, 0x00ff00 };
   return c[((x / 8) + (y / 16)) & 3];
}

static void fill(Display *d, Window w, GC gc)
{
   XSetFunction(d, gc, GXcopy);
   for (int y = 0; y < H; y++)
      for (int x = 0; x < W; x++) {
         XSetForeground(d, gc, pattern(x, y));
         XDrawPoint(d, w, gc, x, y);
      }
}

static int check(Display *d, Window w, const char *name, unsigned long (*expect)(unsigned long))
{
   XSync(d, False);
   XImage *img = XGetImage(d, w, 0, 0, W, H, AllPlanes, ZPixmap);
   int bad = 0;
   for (int y = 0; y < H; y++)
      for (int x = 0; x < W; x++)
         if ((XGetPixel(img, x, y) & 0xffffff) != (expect(pattern(x, y)) & 0xffffff))
            bad++;
   XDestroyImage(img);
   printf("%-14s %s (неверных пикселей %d)\n", name, bad ? "FAIL" : "OK", bad);
   return bad;
}

static unsigned long same(unsigned long p) { return p; }
static unsigned long inv(unsigned long p) { return ~p; }
static unsigned long or_red(unsigned long p) { return p | 0xff0000; }
static unsigned long and_red(unsigned long p) { return p & 0xff0000; }
static unsigned long equiv_red(unsigned long p) { return ~(p ^ 0xff0000); }

static void op(Display *d, Window w, GC gc, int func, unsigned long fg)
{
   XSetFunction(d, gc, func);
   XSetForeground(d, gc, fg);
   XFillRectangle(d, w, gc, 0, 0, W, H);
}

int main(void)
{
   Display *d = XOpenDisplay(NULL);
   if (!d) {
      fprintf(stderr, "нет дисплея\n");
      return 2;
   }
   Window w = XCreateSimpleWindow(d, DefaultRootWindow(d), 300, 60, W, H, 0, 0, 0);
   XSelectInput(d, w, ExposureMask);
   XMapWindow(d, w);
   for (XEvent e;;) {
      XNextEvent(d, &e);
      if (e.type == Expose)
         break;
   }
   GC gc = XCreateGC(d, w, 0, NULL);
   int bad = 0;

   fill(d, w, gc);
   bad += check(d, w, "узор", same);
   op(d, w, gc, GXxor, 0xffffff);
   bad += check(d, w, "xor", inv);
   op(d, w, gc, GXxor, 0xffffff);
   bad += check(d, w, "xor дважды", same);
   op(d, w, gc, GXinvert, 0);
   bad += check(d, w, "invert", inv);
   fill(d, w, gc);
   op(d, w, gc, GXor, 0xff0000);
   bad += check(d, w, "or", or_red);
   fill(d, w, gc);
   op(d, w, gc, GXand, 0xff0000);
   bad += check(d, w, "and", and_red);
   fill(d, w, gc);
   op(d, w, gc, GXequiv, 0xff0000);
   bad += check(d, w, "equiv", equiv_red);
   puts(bad ? "XORTEST-FAIL" : "XORTEST-OK");
   return bad != 0;
}
