/*
 * Переходы между функциями гостя внутри одной страницы кода под JIT v86 (patches/v86-experiments/jit-functions.patch: модуль
 * страницы - набор функций wasm, по одной на функцию гостя, между ними - диспетчер модуля).
 * Все функции лежат подряд в одной секции (помещаются в страницу-две), горячие: прямые вызовы,
 * рекурсия, вызовы по указателю, хвостовые переходы, возврат через несколько уровней, долгий
 * цикл вызовов (диспетчер отдаёт управление по счётчику инструкций, eip обязан быть верным),
 * сигнал посреди такого цикла. Печатает контрольные суммы: тот же статический бинарник даёт их
 * на хосте, сравнить вывод.
 *   i686-linux-musl-gcc -O2 -static -fno-inline -o jitfn tests/jitfn.c;  ./jitfn > host.txt
 *   в машине: jitfn > vm.txt  -> файлы совпадают, последняя строка JITFN-DONE
 */
#define _GNU_SOURCE
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/time.h>

#define F __attribute__((noinline, section(".text.jitfn")))

static volatile uint32_t ticks;
static uint32_t (*volatile table[4])(uint32_t, uint32_t);

F static uint32_t mix(uint32_t a, uint32_t b) { return (a ^ (b << 7)) * 2654435761u + (a >> 3); }
F static uint32_t add3(uint32_t a, uint32_t b) { return a + b * 3; }
F static uint32_t rot(uint32_t a, uint32_t b) { return (a << (b & 31)) | (a >> (-b & 31)); }
F static uint32_t sel(uint32_t a, uint32_t b) { return a & 1 ? mix(a, b) : add3(b, a); }

F static uint32_t fib(uint32_t n) { return n < 2 ? n : fib(n - 1) + fib(n - 2); }

/* взаимная рекурсия */
F static uint32_t odd(uint32_t n);
F static uint32_t even(uint32_t n) { return n == 0 ? 1 : odd(n - 1); }
F static uint32_t odd(uint32_t n) { return n == 0 ? 0 : even(n - 1); }

/* хвостовой переход: gcc -O2 делает из вызова в конце jmp */
F static uint32_t tail2(uint32_t a, uint32_t b) { return mix(b, a); }
F static uint32_t tail1(uint32_t a, uint32_t b) { return tail2(a + 1, b ^ a); }

/* цикл с вызовами и ветвлениями внутри функции */
F static uint32_t loop_calls(uint32_t n, uint32_t s)
{
    for (uint32_t i = 0; i < n; i++) {
        s = mix(s, i);
        if (s & 4)
            s = add3(s, i);
        else if (s & 8)
            s = rot(s, i);
        s = sel(s, i);
    }
    return s;
}

F static uint32_t by_pointer(uint32_t n, uint32_t s)
{
    for (uint32_t i = 0; i < n; i++)
        s = table[s & 3](s, i);
    return s;
}

/* глубина: возврат через несколько уровней одной страницы */
F static uint32_t deep(uint32_t d, uint32_t s) { return d == 0 ? mix(s, 1) : add3(deep(d - 1, s + d), d); }

static void on_alarm(int sig) { (void)sig; ticks++; }

int main(void)
{
    table[0] = mix, table[1] = add3, table[2] = rot, table[3] = sel;

    printf("loop_calls %08x\n", loop_calls(3000000, 1));
    printf("by_pointer %08x\n", by_pointer(3000000, 7));
    printf("fib %u\n", fib(30));
    uint32_t s = 0;
    for (uint32_t i = 0; i < 20000; i++)
        s += even(i % 300) + 2 * odd(i % 211);
    printf("even_odd %u\n", s);
    s = 5;
    for (uint32_t i = 0; i < 2000000; i++)
        s = tail1(s, i);
    printf("tail %08x\n", s);
    s = 9;
    for (uint32_t i = 0; i < 30000; i++)
        s = deep(i % 60, s);
    printf("deep %08x\n", s);

    /* сигналы посреди долгого цикла вызовов: обработчик на другой странице, возврат - в середину */
    struct itimerval it = {{0, 2000}, {0, 2000}};
    signal(SIGALRM, on_alarm);
    setitimer(ITIMER_REAL, &it, 0);
    s = loop_calls(20000000, 3);
    it.it_interval.tv_usec = it.it_value.tv_usec = 0;
    setitimer(ITIMER_REAL, &it, 0);
    printf("signals %08x %s\n", s, ticks > 10 ? "ticks" : "no ticks");
    printf("JITFN-DONE\n");
    return 0;
}
