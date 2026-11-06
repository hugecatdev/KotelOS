// kt-ttyd: виртуальные консоли для страницы. Держит pty с шеллами; страница подключается по TCP (порт 7702)
// и рисует их своим xterm.js - разбор и отрисовка экрана идут в браузере, а не в эмуляторе, как у tmux.
// Без страницы шеллы живут дальше, последние 64 КБ вывода каждой консоли ждут её: после перезагрузки
// страницы или восстановления машины экраны рисуются заново. Соединение одно: новое заменяет старое.
// Запускает страница, когда консоль понадобилась: kt-ttyd уходит в фон, когда порт уже слушается,
// и сразу возвращает 0; уже запущенный (порт занят) - тоже 0, второго не будет.
//
// страница -> гость: HELLO | NEW id cols rows len + команда (len 0 - шелл входа) | IN id len + байты |
//                    SIZE id cols rows | KILL id
// гость -> страница: TTY id cols rows (на HELLO - по каждой живой) + OUT с хвостом | OUT id len + байты |
//                    EXIT id код | READY (после ответа на HELLO)
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <pty.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>

#define PORT 7702
#define MAX 32
#define TAIL 65536
#define LINE 4096

struct tty {
  int id, fd, cols, rows;
  pid_t pid;
  char *tail;  // кольцо последнего вывода
  size_t tpos, tlen;
};

static struct tty T[MAX];
static int cli = -1;
static char in[LINE + 65536];
static size_t inlen;

static void send_all(const void *p, size_t n) {
  const char *s = p;
  while (cli >= 0 && n) {
    ssize_t w = write(cli, s, n);
    if (w < 0 && errno == EINTR) continue;
    if (w <= 0) {
      close(cli);
      cli = -1;
      return;
    }
    s += w;
    n -= w;
  }
}

static void sendf(const char *fmt, int a, int b, int c) {
  char buf[96];
  int n = snprintf(buf, sizeof buf, fmt, a, b, c);
  send_all(buf, n);
}

static void out(struct tty *t, const char *p, size_t n) {
  char head[32];
  int h = snprintf(head, sizeof head, "OUT %d %zu\n", t->id, n);
  send_all(head, h);
  send_all(p, n);
}

static void keep(struct tty *t, const char *p, size_t n) {
  for (size_t i = 0; i < n; i++) {
    t->tail[t->tpos] = p[i];
    t->tpos = (t->tpos + 1) % TAIL;
  }
  t->tlen = t->tlen + n > TAIL ? TAIL : t->tlen + n;
}

static void replay(struct tty *t) {
  size_t start = (t->tpos + TAIL - t->tlen) % TAIL;
  if (start + t->tlen <= TAIL) {
    out(t, t->tail + start, t->tlen);
  } else {
    out(t, t->tail + start, TAIL - start);
    out(t, t->tail, t->tlen - (TAIL - start));
  }
}

static struct tty *find(int id) {
  for (int i = 0; i < MAX; i++)
    if (T[i].fd >= 0 && T[i].id == id) return &T[i];
  return NULL;
}

static void resize(struct tty *t, int cols, int rows) {
  if (cols <= 0 || rows <= 0) return;
  struct winsize ws = {.ws_row = rows, .ws_col = cols};
  t->cols = cols;
  t->rows = rows;
  ioctl(t->fd, TIOCSWINSZ, &ws);
}

static void spawn(int id, int cols, int rows, const char *cmd) {
  if (find(id)) return;
  struct tty *t = NULL;
  for (int i = 0; i < MAX && !t; i++)
    if (T[i].fd < 0) t = &T[i];
  if (!t) {
    sendf("EXIT %d %d\n", id, 255, 0);
    return;
  }
  struct winsize ws = {.ws_row = rows > 0 ? rows : 24, .ws_col = cols > 0 ? cols : 80};
  int fd;
  pid_t pid = forkpty(&fd, NULL, NULL, &ws);
  if (pid < 0) {
    sendf("EXIT %d %d\n", id, 255, 0);
    return;
  }
  if (pid == 0) {
    char n[16];
    snprintf(n, sizeof n, "%d", id);
    setenv("TERM", "xterm-256color", 1);
    setenv("KT_TTY", n, 1);
    // сигналы шеллу - как с нуля: запустивший kt-ttyd (фоном из kt.exec) мог оставить SIGINT в SIG_IGN,
    // а игнор наследуется через exec - тогда Ctrl+C в консоли не работал бы
    sigset_t all;
    sigemptyset(&all);
    sigprocmask(SIG_SETMASK, &all, NULL);
    for (int s = 1; s < NSIG; s++) signal(s, SIG_DFL);
    const char *home = getenv("HOME");  // как вход в систему: шелл - в домашней папке
    if (home && chdir(home) != 0) chdir("/");
    if (cmd && *cmd)
      execl("/bin/sh", "sh", "-c", cmd, (char *)NULL);
    else
      execl("/bin/sh", "-sh", (char *)NULL);  // «-» - шелл входа: /etc/profile, kt, приглашение
    _exit(127);
  }
  fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK);
  fcntl(fd, F_SETFD, FD_CLOEXEC);
  if (!t->tail) t->tail = malloc(TAIL);
  t->id = id;
  t->fd = fd;
  t->pid = pid;
  t->cols = ws.ws_col;
  t->rows = ws.ws_row;
  t->tpos = t->tlen = 0;
}

static void gone(struct tty *t) {
  int st = 0;
  close(t->fd);
  t->fd = -1;
  kill(t->pid, SIGHUP);
  waitpid(t->pid, &st, 0);
  sendf("EXIT %d %d\n", t->id, WIFEXITED(st) ? WEXITSTATUS(st) : 128 + WTERMSIG(st), 0);
}

// одна команда из начала буфера; 0 - не хватает байтов
static size_t command(void) {
  char *nl = memchr(in, '\n', inlen);
  if (!nl) return inlen >= LINE ? inlen : 0;  // мусор без перевода строки - выбросить
  size_t hl = nl - in + 1;
  char line[LINE];
  memcpy(line, in, hl - 1);
  line[hl - 1] = 0;
  int id = 0, a = 0, b = 0;
  size_t len = 0;
  if (!strncmp(line, "IN ", 3) && sscanf(line + 3, "%d %zu", &id, &len) == 2) {
    if (inlen < hl + len) return 0;
    struct tty *t = find(id);
    for (size_t off = 0; t && off < len;) {
      ssize_t w = write(t->fd, in + hl + off, len - off);
      if (w > 0) off += w;
      else if (w < 0 && errno != EAGAIN && errno != EINTR) break;
      else poll(&(struct pollfd){.fd = t->fd, .events = POLLOUT}, 1, 100);
    }
    return hl + len;
  }
  if (!strncmp(line, "NEW ", 4) && sscanf(line + 4, "%d %d %d %zu", &id, &a, &b, &len) == 4) {
    if (inlen < hl + len) return 0;
    char cmd[LINE] = "";
    if (len && len < sizeof cmd) {
      memcpy(cmd, in + hl, len);
      cmd[len] = 0;
    }
    spawn(id, a, b, cmd);
    return hl + len;
  }
  if (!strncmp(line, "SIZE ", 5) && sscanf(line + 5, "%d %d %d", &id, &a, &b) == 3) {
    struct tty *t = find(id);
    if (t) resize(t, a, b);
  } else if (!strncmp(line, "KILL ", 5) && sscanf(line + 5, "%d", &id) == 1) {
    struct tty *t = find(id);
    if (t) kill(-t->pid, SIGHUP), kill(t->pid, SIGHUP);
  } else if (!strcmp(line, "HELLO")) {
    for (int i = 0; i < MAX; i++)
      if (T[i].fd >= 0) sendf("TTY %d %d %d\n", T[i].id, T[i].cols, T[i].rows);
    for (int i = 0; i < MAX; i++)
      if (T[i].fd >= 0 && T[i].tlen) replay(&T[i]);
    send_all("READY\n", 6);
  }
  return hl;
}

int main(void) {
  signal(SIGPIPE, SIG_IGN);
  for (int i = 0; i < MAX; i++) T[i].fd = -1;
  int ls = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0), on = 1;
  setsockopt(ls, SOL_SOCKET, SO_REUSEADDR, &on, sizeof on);
  struct sockaddr_in sa = {.sin_family = AF_INET, .sin_port = htons(PORT), .sin_addr.s_addr = htonl(INADDR_ANY)};
  if (bind(ls, (void *)&sa, sizeof sa) || listen(ls, 2)) return errno == EADDRINUSE ? 0 : 1;  // уже запущен
  pid_t d = fork();  // в фон, когда порт уже слушается: страница подключается сразу после возврата
  if (d < 0) return 1;
  if (d > 0) return 0;
  setsid();
  int nul = open("/dev/null", O_RDWR);
  if (nul >= 0) {
    dup2(nul, 0);
    dup2(nul, 1);
    dup2(nul, 2);
    if (nul > 2) close(nul);
  }
  chdir("/");
  struct pollfd p[MAX + 2];
  int map[MAX + 2];
  for (;;) {
    int n = 0;
    p[n] = (struct pollfd){.fd = ls, .events = POLLIN};
    map[n++] = -1;
    if (cli >= 0) {
      p[n] = (struct pollfd){.fd = cli, .events = POLLIN};
      map[n++] = -2;
    }
    for (int i = 0; i < MAX; i++)
      if (T[i].fd >= 0) {
        p[n] = (struct pollfd){.fd = T[i].fd, .events = POLLIN};
        map[n++] = i;
      }
    if (poll(p, n, -1) < 0) {
      if (errno == EINTR) continue;
      return 1;
    }
    for (int k = 0; k < n; k++) {
      if (!p[k].revents) continue;
      if (map[k] == -1) {
        int c = accept4(ls, NULL, NULL, SOCK_CLOEXEC);
        if (c < 0) continue;
        if (cli >= 0) close(cli);  // новая страница заменяет прежнюю
        cli = c;
        inlen = 0;
        setsockopt(cli, IPPROTO_TCP, TCP_NODELAY, &on, sizeof on);
      } else if (map[k] == -2) {
        ssize_t r = read(cli, in + inlen, sizeof in - inlen);
        if (r <= 0) {
          if (r < 0 && errno == EINTR) continue;
          close(cli);
          cli = -1;
          continue;
        }
        inlen += r;
        size_t used;
        while (inlen && (used = command())) {
          memmove(in, in + used, inlen - used);
          inlen -= used;
        }
      } else {
        struct tty *t = &T[map[k]];
        if (t->fd < 0) continue;
        char buf[16384];
        ssize_t r = read(t->fd, buf, sizeof buf);
        if (r > 0) {
          keep(t, buf, r);
          out(t, buf, r);
        } else if (r == 0 || (errno != EAGAIN && errno != EINTR)) {
          gone(t);  // EIO: шелл вышел, ведомой стороны pty больше нет
        }
      }
    }
  }
}
