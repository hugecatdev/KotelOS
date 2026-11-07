/*
 * Мост vtest в госте: Mesa (GALLIUM_DRIVER=virpipe) подключается к unix-сокету, мост
 * открывает на каждого клиента TCP-соединение к странице и гоняет байты в обе стороны.
 * Клиенты по очереди: сервер на странице держит одного (в протоколе 0 номера ресурсов
 * выбирает клиент).
 *   vtest-bridge [-s /tmp/.virgl_test] [-a 192.168.86.1] [-p 7790]
 */
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

static int relay(int a, int b)
{
   static char buf[1 << 16];
   struct pollfd p[2] = { { a, POLLIN, 0 }, { b, POLLIN, 0 } };
   for (;;) {
      if (poll(p, 2, -1) < 0) {
         if (errno == EINTR)
            continue;
         return -1;
      }
      for (int i = 0; i < 2; i++) {
         if (!(p[i].revents & (POLLIN | POLLHUP | POLLERR)))
            continue;
         ssize_t n = read(p[i].fd, buf, sizeof(buf));
         if (n <= 0)
            return 0;
         for (ssize_t off = 0; off < n;) {
            ssize_t w = write(p[1 - i].fd, buf + off, n - off);
            if (w < 0) {
               if (errno == EINTR)
                  continue;
               return -1;
            }
            off += w;
         }
      }
   }
}

int main(int argc, char **argv)
{
   const char *sock = "/tmp/.virgl_test", *addr = "192.168.86.1";
   int port = 7790, opt;
   while ((opt = getopt(argc, argv, "s:a:p:")) != -1) {
      if (opt == 's') sock = optarg;
      else if (opt == 'a') addr = optarg;
      else if (opt == 'p') port = atoi(optarg);
      else {
         fprintf(stderr, "vtest-bridge [-s сокет] [-a адрес] [-p порт]\n");
         return 2;
      }
   }
   signal(SIGPIPE, SIG_IGN);

   int ls = socket(AF_UNIX, SOCK_STREAM, 0);
   struct sockaddr_un un = { .sun_family = AF_UNIX };
   strncpy(un.sun_path, sock, sizeof(un.sun_path) - 1);
   unlink(sock);
   if (bind(ls, (struct sockaddr *)&un, sizeof(un)) < 0 || listen(ls, 4) < 0) {
      perror(sock);
      return 1;
   }

   struct sockaddr_in in = { .sin_family = AF_INET, .sin_port = htons(port) };
   inet_pton(AF_INET, addr, &in.sin_addr);
   for (;;) {
      int c = accept(ls, NULL, NULL);
      if (c < 0)
         continue;
      int t = socket(AF_INET, SOCK_STREAM, 0);
      int one = 1;
      setsockopt(t, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
      if (connect(t, (struct sockaddr *)&in, sizeof(in)) < 0) {
         fprintf(stderr, "vtest-bridge: %s:%d: %s\n", addr, port, strerror(errno));
      } else {
         relay(c, t);
      }
      close(t);
      close(c);
   }
}
