/*
 * На что уходит процессор у программы на Qt Widgets (Designer): она сама (раскладка, рисование
 * растром Qt) или X-сервер (вывод картинки). Ждёт окно программы, печатает время до него, затем
 * СЕКУНД меняет его размер каждые 0.5 с (перекладка и перерисовка всего окна) и печатает тики
 * процессора каждого PID за запуск и за перерисовку, а также всей машины (user/system/idle).
 *   xresize ИМЯ СЕКУНД PID...   (ИМЯ - часть WM_CLASS без учёта регистра)
 */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <time.h>
#include <unistd.h>

#define MAXP 8

static double now(void)
{
   struct timespec t;
   clock_gettime(CLOCK_MONOTONIC, &t);
   return t.tv_sec + t.tv_nsec / 1e9;
}

/* utime + stime процесса (поля 14 и 15 /proc/PID/stat; имя в скобках может содержать пробелы) */
static long ticks(int pid)
{
   char path[64], buf[1024];
   snprintf(path, sizeof(path), "/proc/%d/stat", pid);
   FILE *f = fopen(path, "r");
   if (!f)
      return -1;
   size_t n = fread(buf, 1, sizeof(buf) - 1, f);
   fclose(f);
   buf[n] = 0;
   char *p = strrchr(buf, ')');
   long u = 0, s = 0;
   /* после ")": состояние (3) ... utime (14) stime (15) */
   if (!p || sscanf(p + 2, "%*c %*d %*d %*d %*d %*d %*u %*u %*u %*u %*u %ld %ld", &u, &s) != 2)
      return -1;
   return u + s;
}

static void cpu(long v[3])
{
   long user, nice, sys, idle, iow, irq, sirq;
   FILE *f = fopen("/proc/stat", "r");
   if (!f || fscanf(f, "cpu %ld %ld %ld %ld %ld %ld %ld", &user, &nice, &sys, &idle, &iow, &irq, &sirq) != 7)
      user = nice = sys = idle = iow = irq = sirq = 0;
   if (f)
      fclose(f);
   v[0] = user + nice;
   v[1] = sys + irq + sirq;
   v[2] = idle + iow;
}

static int match(Display *d, Window w, const char *name)
{
   XClassHint h;
   if (!XGetClassHint(d, w, &h))
      return 0;
   int ok = (h.res_name && strcasestr(h.res_name, name)) || (h.res_class && strcasestr(h.res_class, name));
   XFree(h.res_name);
   XFree(h.res_class);
   return ok;
}

/* самое большое показанное окно с таким WM_CLASS (главное, а не диалог); оконный менеджер кладёт
 * окна программ в свои рамки - ищем вглубь */
static void search(Display *d, Window w, const char *name, int depth, Window *best, unsigned *area)
{
   Window root, parent, *kids;
   unsigned n;
   if (depth > 3 || !XQueryTree(d, w, &root, &parent, &kids, &n))
      return;
   for (unsigned i = 0; i < n; i++) {
      XWindowAttributes a;
      if (!XGetWindowAttributes(d, kids[i], &a) || a.map_state != IsViewable)
         continue;
      if (match(d, kids[i], name)) {
         if ((unsigned)(a.width * a.height) > *area) {
            *area = a.width * a.height;
            *best = kids[i];
         }
      } else
         search(d, kids[i], name, depth + 1, best, area);
   }
   if (kids)
      XFree(kids);
}

static Window find(Display *d, const char *name)
{
   Window best = 0;
   unsigned area = 0;
   search(d, DefaultRootWindow(d), name, 0, &best, &area);
   return best;
}

static void report(const char *what, int np, int *pid, long *t0, long *t1, long *c0, long *c1)
{
   printf("%s:", what);
   for (int i = 0; i < np; i++)
      printf(" pid%d %ld", pid[i], t1[i] - t0[i]);
   printf(" | машина user %ld system %ld idle %ld (тиков)\n", c1[0] - c0[0], c1[1] - c0[1], c1[2] - c0[2]);
   fflush(stdout);
}

int main(int argc, char **argv)
{
   if (argc < 3) {
      fprintf(stderr, "xresize ИМЯ СЕКУНД PID...\n");
      return 2;
   }
   double t_start = now(), secs = atof(argv[2]);
   int np = 0, pid[MAXP];
   long a[MAXP], b[MAXP], c[MAXP], ca[3], cb[3], cc[3];
   for (int i = 3; i < argc && np < MAXP; i++)
      pid[np++] = atoi(argv[i]);
   for (int i = 0; i < np; i++)
      a[i] = ticks(pid[i]);
   cpu(ca);

   Display *d = XOpenDisplay(NULL);
   if (!d) {
      fprintf(stderr, "нет дисплея\n");
      return 2;
   }
   Window w = 0;
   while (!(w = find(d, argv[1]))) {
      if (now() - t_start > 600) {
         puts("XRESIZE-FAIL нет окна");
         return 1;
      }
      usleep(100000);
   }
   printf("окно через %.1f с\n", now() - t_start);
   /* дорисоваться после показа */
   sleep(3);
   for (int i = 0; i < np; i++)
      b[i] = ticks(pid[i]);
   cpu(cb);
   report("запуск", np, pid, a, b, ca, cb);

   int n = 0;
   for (double t0 = now(); now() - t0 < secs; n++) {
      if (n & 1)
         XMoveResizeWindow(d, w, 0, 0, 900, 640);
      else
         XMoveResizeWindow(d, w, 0, 0, 700, 500);
      XSync(d, False);
      usleep(500000);
   }
   for (int i = 0; i < np; i++)
      c[i] = ticks(pid[i]);
   cpu(cc);
   printf("перерисовка (%d смен размера за %.0f с):", n, secs);
   report("", np, pid, b, c, cb, cc);
   puts("XRESIZE-DONE");
   return 0;
}
