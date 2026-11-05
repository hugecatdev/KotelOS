#include <arpa/inet.h>
#include <netinet/in.h>
#include <poll.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

static char buf[65536];

static int pass(int from, int to)
{
	ssize_t n = read(from, buf, sizeof buf), o = 0;

	while (o < n) {
		ssize_t w = write(to, buf + o, n - o);
		if (w <= 0)
			return -1;
		o += w;
	}
	return n;
}

static void quit(int sig)
{
	(void)sig;
	_exit(3);
}

static int client(const char *host, int port)
{
	struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(port) };
	struct pollfd p[2] = { { 0, POLLIN, 0 }, { -1, POLLIN, 0 } };
	int s = socket(AF_INET, SOCK_STREAM, 0);

	signal(SIGUSR1, quit);
	if (s < 0 || inet_pton(AF_INET, host, &a.sin_addr) != 1 || connect(s, (void *)&a, sizeof a))
		return 2;
	p[1].fd = s;
	for (;;) {
		if (poll(p, 2, -1) < 0)
			continue;
		if (p[0].revents && pass(0, s) <= 0) {
			shutdown(s, SHUT_WR);
			p[0].fd = -1;
		}
		if (p[1].revents) {
			int n = pass(s, 1);
			if (n <= 0)
				return n < 0;
		}
	}
}

static int server(int port, char **cmd)
{
	struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(port) };
	int s = socket(AF_INET, SOCK_STREAM, 0), on = 1;
	pid_t child = 0;

	signal(SIGCHLD, SIG_IGN);
	signal(SIGUSR1, SIG_IGN);
	setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof on);
	if (s < 0 || bind(s, (void *)&a, sizeof a) || listen(s, 4)) {
		sleep(2);
		return 1;
	}
	for (;;) {
		int c = accept(s, 0, 0);
		if (c < 0)
			continue;
		if (child > 0)
			kill(child, SIGTERM);
		child = fork();
		if (!child) {
			signal(SIGCHLD, SIG_DFL);
			signal(SIGUSR1, SIG_DFL);
			close(s);
			setsid();
			dup2(c, 0);
			dup2(c, 1);
			if (c > 1)
				close(c);
			execv(cmd[0], cmd);
			_exit(127);
		}
		close(c);
	}
}

int main(int argc, char **argv)
{
	const char *me = strrchr(argv[0], '/');

	me = me ? me + 1 : argv[0];
	if (!strcmp(me, "kt-netd") && argc > 2)
		return server(atoi(argv[1]), argv + 2);
	if (argc == 3)
		return client(argv[1], atoi(argv[2]));
	return 2;
}
