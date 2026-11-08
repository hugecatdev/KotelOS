/*
 * Страничные отказы под JIT v86 при переходах между страницами кода (patches/v86/11: модули
 * переходят друг в друга напрямую). Функции на разных страницах (aligned 4096), горячие - их
 * компилирует JIT; запись идёт в буфер, страницы которого время от времени только для чтения.
 * Обработчик SIGSEGV сверяет адрес отказа и EIP (должен быть внутри функции записи), снимает
 * защиту - запись повторяется. Потом то же после fork (копирование при записи в потомке).
 *   jitpf  -> строки итогов и JITPF-OK | JITPF-FAIL
 */
#define _GNU_SOURCE
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <ucontext.h>
#include <unistd.h>

#define PAGES 16
#define N 3000000

static volatile uint32_t *buf;
static volatile uintptr_t want_addr;
static volatile int faults, bad;
extern char store_begin[], store_end[];

/* на своей странице: запись с переходом по границе страниц буфера (смещение i % ...) */
__attribute__((aligned(4096), noinline)) void store(uint32_t i, uint32_t v)
{
   __asm__ volatile(".globl store_begin\nstore_begin:");
   uint32_t k = (i * 1031) % (PAGES * 1024);
   want_addr = (uintptr_t)&buf[k];
   buf[k] = buf[k] + v;
   __asm__ volatile(".globl store_end\nstore_end:");
}

__attribute__((aligned(4096), noinline)) uint32_t mix(uint32_t x)
{
   return x * 2654435761u ^ (x >> 7);
}

__attribute__((aligned(4096), noinline)) uint64_t run(uint32_t n, int protect)
{
   uint64_t sum = 0;
   for (uint32_t i = 0; i < n; i++) {
      uint32_t v = mix(i) & 0xFF;
      if (protect && (i & 0xFFFF) == 0)
         mprotect((void *)buf, PAGES * 4096, PROT_READ);
      store(i, v);
      sum += v;
   }
   return sum;
}

static void on_segv(int sig, siginfo_t *si, void *uc_)
{
   ucontext_t *uc = uc_;
   uintptr_t eip = uc->uc_mcontext.gregs[REG_EIP];
   (void)sig;
   faults++;
   if ((uintptr_t)si->si_addr != want_addr || eip < (uintptr_t)store || eip >= (uintptr_t)store + 4096) {
      if (bad++ < 5)
         fprintf(stderr, "не тот отказ: адрес %p (ждали %p), eip %p (store %p..%p)\n", si->si_addr,
                 (void *)want_addr, (void *)eip, (void *)store, (void *)store_end);
   }
   mprotect((void *)buf, PAGES * 4096, PROT_READ | PROT_WRITE);
}

static uint64_t total(void)
{
   uint64_t s = 0;
   for (int k = 0; k < PAGES * 1024; k++)
      s += buf[k];
   return s;
}

int main(void)
{
   buf = mmap(NULL, PAGES * 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
   struct sigaction sa = { .sa_sigaction = on_segv, .sa_flags = SA_SIGINFO };
   sigaction(SIGSEGV, &sa, NULL);

   /* разогрев: JIT компилирует run, mix, store */
   uint64_t sum = run(N, 0);
   sum += run(N, 1);
   uint64_t t = total();
   printf("записи %llu, в буфере %llu, отказов %d, неверных %d\n", (unsigned long long)sum,
          (unsigned long long)t, faults, bad);
   int ok = sum == t && faults > 0 && !bad;

   /* копирование при записи: потомок пишет в общий буфер, родитель видит свой */
   pid_t p = fork();
   if (p == 0) {
      uint64_t s = run(N, 0);
      _exit(total() == t + s && !bad ? 0 : 1);
   }
   int st = 0;
   waitpid(p, &st, 0);
   int cow = WIFEXITED(st) && WEXITSTATUS(st) == 0 && total() == t;
   printf("fork: потомок %s, у родителя буфер %s\n", WIFEXITED(st) && !WEXITSTATUS(st) ? "OK" : "FAIL",
          total() == t ? "прежний" : "ИЗМЕНЁН");
   ok &= cow;
   puts(ok ? "JITPF-OK" : "JITPF-FAIL");
   return !ok;
}
