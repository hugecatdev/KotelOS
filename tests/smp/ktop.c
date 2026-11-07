// ktop OUT [min_s] [max_s]
// Сэмплер для замера «потолка SMP» в однопроцессорном госте.
// Раз в 50 мс: /proc/stat (занято, простой, procs_running) и свои тики - занятые
// тики шага кладутся в корзину по числу ДРУГИХ готовых задач в конце шага
// (на N ядрах такой кусок шёл бы в min(k, N) раз быстрее). Раз в 500 мс -
// время каждого потока (/proc/*/task/*/stat). Выход: после min_s, когда 2 с
// занято (без себя) меньше 10%, или по SIGTERM, или через max_s. Итог - в OUT,
// потом строка KTOP-DONE в /dev/console (страница видит её без нагрузки на гостя).
#include <dirent.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define MAXT 8192
#define NK 9
struct th { int tid, tgid; unsigned long long start; long base, last; char comm[20]; };
static struct th t[MAXT];
static int nt, self;
static volatile int stop;

static void onsig(int s) { (void)s; stop = 1; }

static double now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

static int rd(const char *p, char *buf, int n) {
    int fd = open(p, O_RDONLY), k;
    if (fd < 0) return -1;
    k = read(fd, buf, n - 1);
    close(fd);
    if (k < 0) return -1;
    buf[k] = 0;
    return k;
}

// cpu  user nice system idle iowait irq softirq steal; procs_running N
static void cpustat(long long *busy, long long *idle, int *running) {
    static char b[4096];
    long long v[8] = {0};
    if (rd("/proc/stat", b, sizeof b) < 0) return;
    sscanf(b, "cpu %lld %lld %lld %lld %lld %lld %lld %lld", v, v + 1, v + 2, v + 3, v + 4, v + 5, v + 6, v + 7);
    *busy = v[0] + v[1] + v[2] + v[5] + v[6] + v[7];
    *idle = v[3] + v[4];
    char *r = strstr(b, "procs_running ");
    *running = r ? atoi(r + 14) : 1;
}

static int fields(char *b, char **f, int max, char *comm) {
    char *r = strrchr(b, ')'), *c = strchr(b, '(');
    int n = 0;
    if (!r || !c) return 0;
    int l = r - c - 1;
    if (l > 19) l = 19;
    memcpy(comm, c + 1, l);
    comm[l] = 0;
    for (int j = 0; j < l; j++) if (comm[j] == ' ') comm[j] = '_';
    for (char *s = strtok(r + 2, " "); s && n < max; s = strtok(0, " ")) f[n++] = s;
    return n;
}

static long owncpu(void) {
    char b[1024], *f[24], comm[20];
    if (rd("/proc/self/stat", b, sizeof b) < 0) return 0;
    if (fields(b, f, 24, comm) < 13) return 0;
    return atol(f[11]) + atol(f[12]);
}

static void one(int tgid, int tid, int first) {
    char p[64], b[1024], *f[24], comm[20];
    int i;
    snprintf(p, sizeof p, "/proc/%d/task/%d/stat", tgid, tid);
    if (rd(p, b, sizeof b) < 0) return;
    if (fields(b, f, 24, comm) < 20) return;
    long ticks = atol(f[11]) + atol(f[12]);
    unsigned long long st = strtoull(f[19], 0, 10);
    for (i = 0; i < nt; i++)
        if (t[i].tid == tid && t[i].start == st) break;
    if (i == nt) {
        if (nt == MAXT) return;
        nt++;
        t[i].tid = tid; t[i].tgid = tgid; t[i].start = st;
        t[i].base = first ? ticks : 0;
    }
    t[i].last = ticks;
    strcpy(t[i].comm, comm);  // exec меняет имя - берём последнее
}

static void scan(int first) {
    DIR *d = opendir("/proc"), *e;
    struct dirent *x, *y;
    char p[64];
    if (!d) return;
    while ((x = readdir(d))) {
        int pid = atoi(x->d_name);
        if (pid <= 0 || pid == self) continue;
        snprintf(p, sizeof p, "/proc/%d/task", pid);
        if (!(e = opendir(p))) continue;
        while ((y = readdir(e))) {
            int tid = atoi(y->d_name);
            if (tid > 0) one(pid, tid, first);
        }
        closedir(e);
    }
    closedir(d);
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "ktop OUT [min_s] [max_s]\n"); return 2; }
    double minimum = argc > 2 ? atof(argv[2]) : 3, maximum = argc > 3 ? atof(argv[3]) : 600;
    enum { IV = 50, SCAN = 10, WIN = 40, W = 64 };  // шаг 50 мс, потоки раз в 500 мс, окно тишины 2 с
    self = getpid();
    signal(SIGTERM, onsig);
    signal(SIGINT, onsig);
    long long busy0 = 0, idle0 = 0, busy, idle, pb, pi, lasti, hist[NK] = {0}, wb[W], wi[W];
    long own0, own, po;
    int run, k = 0;
    double t0 = now(), tlast = t0, tn;
    cpustat(&busy0, &idle0, &run);
    own0 = po = owncpu();
    scan(1);
    pb = busy0; pi = lasti = idle0;
    for (;;) {
        usleep(IV * 1000);
        cpustat(&busy, &idle, &run);
        own = owncpu();
        tn = now();
        long long db = (busy - pb) - (own - po), di = idle - pi;
        if (db < 0) db = 0;
        int others = run - 1;  // сами мы сейчас работаем
        if (others < 0) others = 0;
        if (others >= NK) others = NK - 1;
        hist[others] += db;
        if (db >= 2 && db * 3 > db + di) { tlast = tn; lasti = idle; }
        pb = busy; pi = idle; po = own;
        wb[k % W] = busy - (own - own0); wi[k % W] = idle; k++;
        if (k % SCAN == 0) scan(0);
        if (stop || tn - t0 > maximum) break;
        if (tn - t0 > minimum && k > WIN) {
            long long b2 = wb[(k - 1) % W] - wb[(k - 1 - WIN) % W], i2 = wi[(k - 1) % W] - wi[(k - 1 - WIN) % W];
            if (b2 + i2 > 0 && b2 * 10 < b2 + i2) break;
        }
    }
    scan(0);
    own = owncpu();
    char tmp[256];
    snprintf(tmp, sizeof tmp, "%s.tmp", argv[1]);
    FILE *o = fopen(tmp, "w");
    if (!o) return 1;
    // S: занято всего (без себя), простой до последней работы, с до последней работы, с всего, свои тики, шагов
    fprintf(o, "S %lld %lld %.2f %.2f %ld %d\n", (busy - busy0) - (own - own0), lasti - idle0, tlast - t0, now() - t0, own - own0, k);
    for (int i = 0; i < NK; i++) fprintf(o, "H %d %lld\n", i, hist[i]);
    for (int i = 0; i < nt; i++) {
        long d = t[i].last - t[i].base;
        if (d > 0) fprintf(o, "T %d %d %s %ld\n", t[i].tid, t[i].tgid, t[i].comm, d);
    }
    fclose(o);
    rename(tmp, argv[1]);
    int c = open("/dev/console", O_WRONLY | O_NOCTTY);
    if (c >= 0) { if (write(c, "\r\nKTOP-DONE\r\n", 13) < 0) c = c; close(c); }
    return 0;
}
