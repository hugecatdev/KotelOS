/*
 * Текстуры старых форматов, которые хост GL хранит каналом R и показывает перестановкой
 * (TEXTURE_SWIZZLE, в WebGL2 её нет): GL_ALPHA, GL_LUMINANCE, GL_LUMINANCE_ALPHA, GL_INTENSITY.
 * Каждая - четверть окна с GL_REPLACE поверх цвета (255, 0, 0); цвет читается glReadPixels и
 * сверяется с тем, что требует GL. Сравнивать с LIBGL_ALWAYS_SOFTWARE=1 (softpipe).
 *   swztest  -> строки "формат R G B A ожидалось ... OK|FAIL", в конце SWZTEST-OK|SWZTEST-FAIL
 */
#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>
#include <stdio.h>
#include <stdlib.h>

#define W 64

static int check(const char *name, int x, int y, const int want[4])
{
   unsigned char p[4];
   glReadPixels(x, y, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, p);
   int ok = 1;
   for (int i = 0; i < 4; i++)
      if (abs(p[i] - want[i]) > 2)
         ok = 0;
   printf("%-16s %3d %3d %3d %3d  ожидалось %3d %3d %3d %3d  %s\n", name, p[0], p[1], p[2], p[3],
          want[0], want[1], want[2], want[3], ok ? "OK" : "FAIL");
   return ok;
}

static void quad(GLenum format, const unsigned char *texel, float x0, float y0)
{
   GLuint t;
   glGenTextures(1, &t);
   glBindTexture(GL_TEXTURE_2D, t);
   glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
   unsigned char data[4 * 4 * 2];
   int n = format == GL_LUMINANCE_ALPHA ? 2 : 1;
   for (int i = 0; i < 16; i++)
      for (int c = 0; c < n; c++)
         data[i * n + c] = texel[c];
   /* GL_INTENSITY - только внутренний формат, данные - как у GL_LUMINANCE */
   glTexImage2D(GL_TEXTURE_2D, 0, format, 4, 4, 0, format == GL_INTENSITY ? GL_LUMINANCE : format, GL_UNSIGNED_BYTE, data);
   glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
   glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
   glBegin(GL_QUADS);
   glTexCoord2f(0, 0); glVertex2f(x0, y0);
   glTexCoord2f(1, 0); glVertex2f(x0 + 1, y0);
   glTexCoord2f(1, 1); glVertex2f(x0 + 1, y0 + 1);
   glTexCoord2f(0, 1); glVertex2f(x0, y0 + 1);
   glEnd();
}

int main(void)
{
   Display *d = XOpenDisplay(NULL);
   if (!d) {
      fprintf(stderr, "нет дисплея\n");
      return 2;
   }
   int attr[] = { GLX_RGBA, GLX_RED_SIZE, 8, GLX_GREEN_SIZE, 8, GLX_BLUE_SIZE, 8, GLX_ALPHA_SIZE, 8,
                  GLX_DOUBLEBUFFER, None };
   XVisualInfo *vi = glXChooseVisual(d, DefaultScreen(d), attr);
   if (!vi) {
      int attr2[] = { GLX_RGBA, GLX_RED_SIZE, 8, GLX_GREEN_SIZE, 8, GLX_BLUE_SIZE, 8, GLX_DOUBLEBUFFER, None };
      vi = glXChooseVisual(d, DefaultScreen(d), attr2);
   }
   /* визуал GLX может отличаться от корневого: тогда нужны своя палитра и цвет рамки */
   XSetWindowAttributes swa = { .colormap = XCreateColormap(d, RootWindow(d, vi->screen), vi->visual, AllocNone),
                                .border_pixel = 0 };
   Window w = XCreateWindow(d, RootWindow(d, vi->screen), 400, 40, W, W, 0, vi->depth, InputOutput, vi->visual,
                            CWColormap | CWBorderPixel, &swa);
   XMapWindow(d, w);
   GLXContext ctx = glXCreateContext(d, vi, NULL, True);
   glXMakeCurrent(d, w, ctx);
   int alpha_bits = 0;
   glGetIntegerv(GL_ALPHA_BITS, &alpha_bits);
   printf("renderer: %s, бит альфы %d\n", glGetString(GL_RENDERER), alpha_bits);

   glViewport(0, 0, W, W);
   glMatrixMode(GL_PROJECTION);
   glLoadIdentity();
   glOrtho(0, 2, 0, 2, -1, 1);
   glClearColor(0, 0, 1, 1);
   glClear(GL_COLOR_BUFFER_BIT);
   glEnable(GL_TEXTURE_2D);
   glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);
   glColor4ub(255, 0, 0, 255);

   static const unsigned char a[] = { 200 }, l[] = { 128 }, la[] = { 60, 180 }, i[] = { 90 };
   quad(GL_ALPHA, a, 0, 0);
   quad(GL_LUMINANCE, l, 1, 0);
   quad(GL_LUMINANCE_ALPHA, la, 0, 1);
   quad(GL_INTENSITY, i, 1, 1);
   glFinish();

   /* GL_REPLACE: ALPHA - (Cf, As), LUMINANCE - (L, L, L, Af), LUMINANCE_ALPHA - (L, L, L, A),
    * INTENSITY - (I, I, I, I); без альфы в буфере читается 255 */
   int A = alpha_bits ? -1 : 255;
   int wa[] = { 255, 0, 0, A < 0 ? 200 : A }, wl[] = { 128, 128, 128, 255 },
       wla[] = { 60, 60, 60, A < 0 ? 180 : A }, wi[] = { 90, 90, 90, A < 0 ? 90 : A };
   int ok = 1;
   ok &= check("ALPHA", W / 4, W / 4, wa);
   ok &= check("LUMINANCE", 3 * W / 4, W / 4, wl);
   ok &= check("LUMINANCE_ALPHA", W / 4, 3 * W / 4, wla);
   ok &= check("INTENSITY", 3 * W / 4, 3 * W / 4, wi);
   glXSwapBuffers(d, w);
   puts(ok ? "SWZTEST-OK" : "SWZTEST-FAIL");
   return !ok;
}
