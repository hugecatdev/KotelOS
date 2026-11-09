/*
 * Флаги под JIT v86: проверка для любых правок генератора, задевающих флаги (например
 * patches/v86-experiments/jit-flags-in-locals.patch). Горячие циклы: каждая операция над
 * псевдослучайными операндами, потом флаги читаются тремя способами - pushf, все 16 условий
 * через setcc и через переход; переносы цепочкой (adc/sbb, rcl/rcr), inc/dec с сохранением CF,
 * lahf/sahf, popf, cmov, bt, 64-битная арифметика, строковые операции с DF, и страничный отказ
 * между установкой флагов и чтением (обработчик SIGSEGV снимает защиту, запись повторяется).
 * Печатает контрольные суммы: тот же статический бинарник даёт их на хосте.
 *   i686-linux-musl-gcc -O2 -static -o jitflags tests/jitflags.c;  ./jitflags > host.txt
 *   в машине: jitflags > vm.txt  -> файлы совпадают, последняя строка JITFLAGS-DONE
 */
#define _GNU_SOURCE
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>

#define N 300000
/* флаги, которые операции определяют всегда: CF PF ZF SF OF (AF у логических не определён) */
#define ARITH 0x8C5
#define ALL 0x8D5

static uint32_t seed = 12345;
static inline uint32_t rnd(void)
{
    seed = seed * 1103515245 + 12345;
    uint32_t r = seed >> 8;
    /* чаще крайние значения: нули, знаки, равные операнды */
    switch (seed >> 29) {
    case 0: return r & 0xFF;
    case 1: return r | 0x80000000;
    case 2: return 0;
    case 3: return 0xFFFFFFFF;
    default: return r ^ (seed << 11);
    }
}

/* операция с двумя операндами, флаги через pushf; cf - входной перенос (для adc/sbb/rcl) */
#define OP2(name, insn, reg, mask) \
    static __attribute__((noinline)) uint32_t name(uint32_t a, uint32_t b, uint32_t cf) \
    { \
        uint32_t f; \
        __asm__("bt $0, %[cf]\n" insn " %" reg "[b], %" reg "[a]\npushf\npop %[f]" \
                : [a] "+q"(a), [f] "=&r"(f) : [b] "q"(b), [cf] "r"(cf) : "cc"); \
        return (f & (mask)) + a * 31; \
    }
#define OP2S(n, insn, mask) OP2(n##8, insn "b", "b", mask) OP2(n##16, insn "w", "w", mask) OP2(n##32, insn "l", "k", mask)
OP2S(add, "add", ALL) OP2S(sub, "sub", ALL) OP2S(cmp, "cmp", ALL) OP2S(adc, "adc", ALL) OP2S(sbb, "sbb", ALL)
OP2S(and, "and", ARITH) OP2S(or, "or", ARITH) OP2S(xor, "xor", ARITH) OP2S(test, "test", ARITH)

/* операция с одним операндом */
#define OP1(name, insn, reg, mask) \
    static __attribute__((noinline)) uint32_t name(uint32_t a, uint32_t b, uint32_t cf) \
    { \
        uint32_t f; \
        (void)b; \
        __asm__("bt $0, %[cf]\n" insn " %" reg "[a]\npushf\npop %[f]" : [a] "+q"(a), [f] "=&r"(f) : [cf] "r"(cf) : "cc"); \
        return (f & (mask)) + a * 31; \
    }
#define OP1S(n, insn, mask) OP1(n##8, insn "b", "b", mask) OP1(n##16, insn "w", "w", mask) OP1(n##32, insn "l", "k", mask)
OP1S(inc, "inc", ALL) OP1S(dec, "dec", ALL) OP1S(neg, "neg", ALL)

/* сдвиги на cl: при нулевом счётчике флаги остаются прежними (от bt), OF определён только для 1 */
#define SH(name, insn, reg) \
    static __attribute__((noinline)) uint32_t name(uint32_t a, uint32_t b, uint32_t cf) \
    { \
        uint32_t f, c = b & 31; \
        __asm__("bt $0, %[cf]\n" insn " %%cl, %" reg "[a]\npushf\npop %[f]" : [a] "+q"(a), [f] "=&r"(f) : "c"(c), [cf] "r"(cf) : "cc"); \
        return (c == 0 ? 0 : f & (c == 1 ? 0x8C5 : 0xC5)) + a * 31; \
    }
#define SHS(n, insn) SH(n##8, insn "b", "b") SH(n##16, insn "w", "w") SH(n##32, insn "l", "k")
SHS(shl, "shl") SHS(shr, "shr") SHS(sar, "sar")
/* вращения меняют только CF (и OF при счётчике 1) */
#define ROT(name, insn, reg) \
    static __attribute__((noinline)) uint32_t name(uint32_t a, uint32_t b, uint32_t cf) \
    { \
        uint32_t f, c = b & 31; \
        __asm__("bt $0, %[cf]\n" insn " %%cl, %" reg "[a]\npushf\npop %[f]" : [a] "+q"(a), [f] "=&r"(f) : "c"(c), [cf] "r"(cf) : "cc"); \
        return (c == 0 ? 0 : f & 1) + a * 31; \
    }
ROT(rol32, "roll", "k") ROT(ror32, "rorl", "k") ROT(rcl32, "rcll", "k") ROT(rcr32, "rcrl", "k")

/* все 16 условий после операции: setcc */
#define CC16(X) X(o) X(no) X(b) X(ae) X(e) X(ne) X(be) X(a) X(s) X(ns) X(p) X(np) X(l) X(ge) X(le) X(g)
#define COND1(cc) \
    static __attribute__((noinline)) uint32_t c_##cc(uint32_t a, uint32_t b, int op) \
    { \
        uint8_t r; \
        switch (op) { \
        case 0: __asm__("cmpl %[b], %[a]\nset" #cc " %[r]" : [r] "=q"(r) : [a] "r"(a), [b] "r"(b) : "cc"); break; \
        case 1: __asm__("testl %[b], %[a]\nset" #cc " %[r]" : [r] "=q"(r) : [a] "r"(a), [b] "r"(b) : "cc"); break; \
        case 2: __asm__("addl %[b], %[a]\nset" #cc " %[r]" : [r] "=q"(r), [a] "+r"(a) : [b] "r"(b) : "cc"); break; \
        case 3: __asm__("subw %w[b], %w[a]\nset" #cc " %[r]" : [r] "=q"(r), [a] "+r"(a) : [b] "r"(b) : "cc"); break; \
        case 4: __asm__("cmpb %b[b], %b[a]\nset" #cc " %[r]" : [r] "=q"(r) : [a] "q"(a), [b] "q"(b) : "cc"); break; \
        case 5: __asm__("andw %w[b], %w[a]\nset" #cc " %[r]" : [r] "=q"(r), [a] "+r"(a) : [b] "r"(b) : "cc"); break; \
        case 6: __asm__("incl %[a]\nset" #cc " %[r]" : [r] "=q"(r), [a] "+r"(a) : : "cc"); break; \
        case 7: __asm__("decb %b[a]\nset" #cc " %[r]" : [r] "=q"(r), [a] "+q"(a) : : "cc"); break; \
        case 8: __asm__("negl %[a]\nset" #cc " %[r]" : [r] "=q"(r), [a] "+r"(a) : : "cc"); break; \
        default: __asm__("xorl %[b], %[a]\nset" #cc " %[r]" : [r] "=q"(r), [a] "+r"(a) : [b] "r"(b) : "cc"); break; \
        } \
        return r + a * 3; \
    } \
    /* то же условие переходом и cmov, флаги стоят до обращения к памяти */ \
    static __attribute__((noinline)) uint32_t j_##cc(uint32_t a, uint32_t b, volatile uint32_t *m) \
    { \
        uint32_t r = 1, t = 7; \
        __asm__("cmpl %[b], %[a]\nmovl (%[m]), %%ecx\naddl $1, %%ecx\nmovl %%ecx, (%[m])\nj" #cc " 1f\nmovl $2, %[r]\n1:\n" \
                "subl %[a], %[b]\nleal 5(%[r]), %%ecx\ncmov" #cc " %%ecx, %[t]" \
                : [r] "+r"(r), [t] "+r"(t), [b] "+r"(b) : [a] "r"(a), [m] "r"(m) : "cc", "ecx", "memory"); \
        return r * 16 + t; \
    }
CC16(COND1)

static volatile uint32_t *page;
static volatile int faults;
static void on_segv(int sig, siginfo_t *si, void *ctx)
{
    (void)sig, (void)ctx;
    faults++;
    mprotect((void *)((uintptr_t)si->si_addr & ~4095), 4096, PROT_READ | PROT_WRITE);
}

typedef uint32_t (*fn3)(uint32_t, uint32_t, uint32_t);
static uint32_t run3(fn3 f)
{
    uint32_t s = 0;
    for (int i = 0; i < N; i++) {
        uint32_t a = rnd(), b = rnd();
        s = s * 33 + f(a, b, i & 1);
    }
    return s;
}

int main(void)
{
#define R(n) printf(#n " %08x\n", run3(n));
#define R3(n) R(n##8) R(n##16) R(n##32)
    R3(add) R3(sub) R3(cmp) R3(adc) R3(sbb) R3(and) R3(or) R3(xor) R3(test)
    R3(inc) R3(dec) R3(neg) R3(shl) R3(shr) R3(sar) R(rol32) R(ror32) R(rcl32) R(rcr32)

    uint32_t s = 0;
#define RC(cc) for (int i = 0; i < N / 4; i++) { uint32_t a = rnd(), b = i & 3 ? rnd() : a; s = s * 33 + c_##cc(a, b, i % 10); }
    CC16(RC)
    printf("setcc %08x\n", s);

    /* условия после обращения к памяти; страница время от времени закрыта: отказ между cmp и jcc */
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_sigaction = on_segv;
    sa.sa_flags = SA_SIGINFO;
    sigaction(SIGSEGV, &sa, 0);
    page = mmap(0, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    s = 0;
#define RJ(cc) for (int i = 0; i < N / 4; i++) { uint32_t a = rnd(), b = i & 3 ? rnd() : a; \
        if (i % 9973 == 0) mprotect((void *)page, 4096, PROT_NONE); \
        s = s * 33 + j_##cc(a, b, page); }
    CC16(RJ)
    printf("jcc_cmov_fault %08x mem %u faults %s\n", s, *page, faults > 100 ? "yes" : "no");

    /* переносы цепочкой и 64 бита */
    uint64_t x = 0x0123456789abcdefull, y = 0xfedcba9876543210ull, z = 0;
    for (int i = 0; i < N; i++) {
        uint64_t a = ((uint64_t)rnd() << 32) | rnd();
        x += a;
        y -= x ^ (a >> 7);
        z += (x < y) + (x * (a | 1)) + (y >> (i & 63)) + ((int64_t)x >> (i % 61)) + (y << (i % 37));
        if ((int64_t)(x ^ y) < (int64_t)z)
            z ^= x - y;
    }
    printf("u64 %016llx %016llx %016llx\n", (unsigned long long)x, (unsigned long long)y, (unsigned long long)z);

    /* lahf/sahf, pushf/popf, bt, mul/imul, cld/std со строковыми операциями */
    s = 0;
    static uint8_t buf[256], buf2[256];
    for (int i = 0; i < N; i++) {
        uint32_t a = rnd(), b = rnd(), r = 0, f;
        __asm__("cmpl %[b], %[a]\nlahf\nmovzbl %%ah, %[r]\nxorb $0x41, %%ah\nsahf\npushf\npop %[f]"
                : [r] "=&r"(r), [f] "=&r"(f) : [a] "r"(a), [b] "r"(b) : "cc", "eax");
        s = s * 33 + (r & 0xD5) + (f & 0xD5) * 256;
        __asm__("addl %[b], %[a]\npushf\norl $0x1, (%%esp)\nandl $0xffffffbf, (%%esp)\npopf\nsetc %b[r]\nsetz %%ch\naddb %%ch, %b[r]"
                : [r] "+q"(r), [a] "+r"(a) : [b] "r"(b) : "cc", "ecx");
        s = s * 33 + r;
        __asm__("btl %[b], %[a]\nsetc %b[r]\nbtsl %[b], %[a]\nadcl $0, %[r]\nbtcl $3, %[a]\nadcl %[a], %[r]"
                : [r] "+q"(r), [a] "+r"(a) : [b] "r"(b & 31) : "cc");
        s = s * 33 + r;
        uint32_t lo = a, hi;
        __asm__("mull %[b]\nseto %b[r]\nsetc %%cl\naddb %%cl, %b[r]" : "+a"(lo), "=d"(hi), [r] "+q"(r) : [b] "r"(b) : "cc", "ecx");
        s = s * 33 + lo + hi + r;
        __asm__("imull %[b], %[a]\nseto %b[r]" : [a] "+r"(a), [r] "+q"(r) : [b] "r"(b) : "cc");
        s = s * 33 + a + r;
        if ((i & 255) == 0) {
            buf[i >> 8 & 255] = i;
            void *si = buf + 199, *di = buf2 + 199;
            uint32_t n = 100;
            __asm__("std\nrep movsb\ncld\npushf\npop %[f]" : "+S"(si), "+D"(di), "+c"(n), [f] "=&r"(f) : : "cc", "memory");
            s = s * 33 + buf2[150] + (f & 0x400);
            si = buf, di = buf2, n = 200;
            __asm__("repe cmpsb\nsetne %b[r]\nadcl $0, %[r]" : "+S"(si), "+D"(di), "+c"(n), [r] "+q"(r) : : "cc", "memory");
            s = s * 33 + r + n;
        }
    }
    printf("misc %08x\n", s);
    printf("JITFLAGS-DONE\n");
    return 0;
}
