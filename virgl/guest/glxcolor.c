/*
 * Проверка показа кадра GLX: окно ШxВ заливается цветом, который меняется каждый кадр
 * (красный, зелёный, синий по кругу); после N кадров остаётся на последнем и ждёт.
 * По снимку экрана видно, что лежит у краёв: текущий цвет, прошлый кадр или мусор.
 *   glxcolor [ширина высота кадров x y]
 */
#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv)
{
   int w = argc > 1 ? atoi(argv[1]) : 290, h = argc > 2 ? atoi(argv[2]) : 290;
   int frames = argc > 3 ? atoi(argv[3]) : 30;
   int x = argc > 4 ? atoi(argv[4]) : 505, y = argc > 5 ? atoi(argv[5]) : 20;
   Display *dpy = XOpenDisplay(NULL);
   if (!dpy) {
      fprintf(stderr, "нет дисплея\n");
      return 1;
   }
   int attr[] = { GLX_RGBA, GLX_DOUBLEBUFFER, GLX_RED_SIZE, 8, GLX_GREEN_SIZE, 8, GLX_BLUE_SIZE, 8, None };
   XVisualInfo *vi = glXChooseVisual(dpy, DefaultScreen(dpy), attr);
   Window root = RootWindow(dpy, vi->screen);
   XSetWindowAttributes swa = { .colormap = XCreateColormap(dpy, root, vi->visual, AllocNone),
                                .border_pixel = 0, .event_mask = StructureNotifyMask };
   Window win = XCreateWindow(dpy, root, x, y, w, h, 0, vi->depth, InputOutput, vi->visual,
                              CWColormap | CWBorderPixel | CWEventMask, &swa);
   XSizeHints hints = { .flags = USPosition | USSize, .x = x, .y = y, .width = w, .height = h };
   XSetNormalHints(dpy, win, &hints);
   XStoreName(dpy, win, "glxcolor");
   XMapWindow(dpy, win);
   for (XEvent e;;) {
      XNextEvent(dpy, &e);
      if (e.type == MapNotify)
         break;
   }
   GLXContext ctx = glXCreateContext(dpy, vi, NULL, True);
   glXMakeCurrent(dpy, win, ctx);
   static const float c[3][3] = { { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 } };
   for (int i = 0; i < frames; i++) {
      glViewport(0, 0, w, h);
      glClearColor(c[i % 3][0], c[i % 3][1], c[i % 3][2], 1);
      glClear(GL_COLOR_BUFFER_BIT);
      glXSwapBuffers(dpy, win);
   }
   glFinish();
   printf("последний кадр %d: %s\n", frames - 1, (const char *[]){ "красный", "зелёный", "синий" }[(frames - 1) % 3]);
   fflush(stdout);
   pause();
   return 0;
}
