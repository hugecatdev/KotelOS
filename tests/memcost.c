/*
 * Цена обращения к памяти под JIT v86 (проверка TLB на каждое): циклы по N повторов -
 * на регистрах, push/pop, чтение и запись [esp+4] - нс на повтор и разница с регистрами.
 *   memcost [N]
 */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static double now(void)
{
   struct timespec t;
   clock_gettime(CLOCK_MONOTONIC, &t);
   return t.tv_sec + t.tv_nsec / 1e9;
}

__attribute__((noinline)) static void regs(unsigned n)
{
   __asm__ volatile("1: mov %%eax, %%edx\n mov %%edx, %%eax\n mov %%eax, %%edx\n mov %%edx, %%eax\n"
                    " dec %0\n jnz 1b" : "+c"(n) : : "eax", "edx");
}

__attribute__((noinline)) static void pushpop(unsigned n)
{
   __asm__ volatile("1: push %%eax\n pop %%edx\n push %%edx\n pop %%eax\n"
                    " dec %0\n jnz 1b" : "+c"(n) : : "eax", "edx");
}

__attribute__((noinline)) static void stackrw(unsigned n)
{
   __asm__ volatile("sub $8, %%esp\n"
                    "1: mov %%eax, 4(%%esp)\n mov 4(%%esp), %%edx\n mov %%edx, 4(%%esp)\n mov 4(%%esp), %%eax\n"
                    " dec %0\n jnz 1b\n add $8, %%esp" : "+c"(n) : : "eax", "edx");
}

static double run(void (*f)(unsigned), unsigned n)
{
   f(n / 100); /* разогрев: JIT */
   f(n / 100);
   double t = now();
   f(n);
   return (now() - t) * 1e9 / n;
}

int main(int argc, char **argv)
{
   unsigned n = argc > 1 ? atoi(argv[1]) : 100000000;
   double r = run(regs, n), p = run(pushpop, n), s = run(stackrw, n);
   printf("регистры %.2f нс, push/pop %.2f нс (+%.2f на 4 обращения), [esp+4] %.2f нс (+%.2f на 4)\n",
          r, p, p - r, s, s - r);
   return 0;
}
