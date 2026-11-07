/*
 * Отладка падений в госте без gdb: LD_PRELOAD=/usr/lib/segv-trace.so программа
 * Программе не даётся перехватить SIGSEGV (её sigaction для него молча игнорируется), а при
 * падении в stderr идут EIP, адрес обращения, вызовы по цепочке кадров (EBP) и строки
 * /proc/self/maps с этими адресами - по ним addr2line в несжатой сборке.
 *   i686-linux-musl-gcc -O1 -fPIC -shared -o segv-trace.so segv-trace.c
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ucontext.h>
#include <unistd.h>

static void show_map(unsigned long addr)
{
   char line[512];
   FILE *f = fopen("/proc/self/maps", "r");
   if (!f)
      return;
   while (fgets(line, sizeof(line), f)) {
      unsigned long lo, hi;
      if (sscanf(line, "%lx-%lx", &lo, &hi) == 2 && addr >= lo && addr < hi) {
         fprintf(stderr, "  %08lx in %s", addr, line);
         break;
      }
   }
   fclose(f);
}

static void handler(int sig, siginfo_t *si, void *ctx)
{
   ucontext_t *uc = ctx;
   unsigned long eip = uc->uc_mcontext.gregs[REG_EIP];
   unsigned long ebp = uc->uc_mcontext.gregs[REG_EBP];
   fprintf(stderr, "segv-trace: сигнал %d, адрес %p, eip %08lx\n", sig, si->si_addr, eip);
   show_map(eip);
   /* цепочка кадров: [ebp] - прошлый ebp, [ebp+4] - адрес возврата (если код с указателем кадра) */
   for (int i = 0; i < 12 && ebp && !(ebp & 3); i++) {
      unsigned long *frame = (unsigned long *)ebp;
      unsigned long ret = frame[1];
      if (!ret)
         break;
      show_map(ret);
      if (frame[0] <= ebp)
         break;
      ebp = frame[0];
   }
   signal(sig, SIG_DFL);
   raise(sig);
}

__attribute__((constructor)) static void init(void)
{
   struct sigaction sa;
   memset(&sa, 0, sizeof(sa));
   sa.sa_sigaction = handler;
   sa.sa_flags = SA_SIGINFO;
   int (*real)(int, const struct sigaction *, struct sigaction *) = dlsym(RTLD_NEXT, "sigaction");
   real(SIGSEGV, &sa, NULL);
   real(SIGBUS, &sa, NULL);
}

int sigaction(int sig, const struct sigaction *act, struct sigaction *old)
{
   static int (*real)(int, const struct sigaction *, struct sigaction *);
   if (!real)
      real = dlsym(RTLD_NEXT, "sigaction");
   if ((sig == SIGSEGV || sig == SIGBUS) && act)
      return 0;
   return real(sig, act, old);
}
