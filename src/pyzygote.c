#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#ifndef PY
#define PY "/usr/bin/python3"
#endif
#ifndef SRV
#define SRV "/usr/sbin/pyzygote"
#endif
#ifndef RUN
#define RUN "/run/pyzygote"
#endif

extern char **environ;
static volatile pid_t child;
static volatile sig_atomic_t pending, gotint;
static const int sigs[] = { SIGINT, SIGTERM, SIGHUP, SIGQUIT, SIGUSR1, SIGUSR2, SIGWINCH, SIGALRM, SIGTSTP, SIGCONT };

static void real(char **argv)
{
	argv[0] = PY;
	execv(PY, argv);
	_exit(127);
}

static void spawn(void)
{
	struct stat st;
	char **env;
	int n = 0, fd;
	pid_t p;

	if (!stat(RUN "/try", &st) && time(0) - st.st_mtime < 10)
		return;
	mkdir(RUN, 0755);
	fd = open(RUN "/try", O_WRONLY | O_CREAT | O_CLOEXEC, 0644);
	if (fd < 0)
		return;
	futimens(fd, 0);
	close(fd);
	p = fork();
	if (p) {
		if (p > 0)
			waitpid(p, 0, 0);
		return;
	}
	setsid();
	if (fork())
		_exit(0);
	for (fd = sysconf(_SC_OPEN_MAX); fd > 2; fd--)
		close(fd);
	fd = open("/dev/null", O_RDWR);
	dup2(fd, 0);
	dup2(fd, 1);
	dup2(fd, 2);
	if (fd > 2)
		close(fd);
	while (environ[n])
		n++;
	env = malloc((n + 1) * sizeof *env);
	if (!env)
		_exit(1);
	for (n = 0; *environ; environ++)
		if (strncmp(*environ, "PYTHON", 6))
			env[n++] = *environ;
	env[n] = 0;
	execve(PY, (char *[]){ PY, SRV, 0 }, env);
	_exit(127);
}

static void note(int argc, const char *why)
{
	if (argc > 1 || !isatty(0) || !isatty(2))
		return;
	if (*why)
		dprintf(2, "pyzygote: без ускорения (%s)\n", why);
	else
		dprintf(2, "pyzygote: без ускорения\n");
}

static const char *idle(void)
{
	int fd = open(RUN "/lock", O_RDONLY | O_CLOEXEC);
	const char *r = "сервер не запущен";

	if (fd >= 0) {
		if (flock(fd, LOCK_EX | LOCK_NB) < 0)
			r = "сервер запускается";
		close(fd);
	}
	return r;
}

static void send_sig(int s)
{
	if (kill(-child, s) < 0)
		kill(child, s);
}

static void fwd(int s)
{
	if (s == SIGINT)
		gotint = 1;
	if (!child) {
		pending |= 1u << s;
		return;
	}
	if (s == SIGTSTP) {
		send_sig(SIGSTOP);
		kill(getpid(), SIGSTOP);
		send_sig(SIGCONT);
		return;
	}
	send_sig(s);
}

static size_t put(char *b, const char *s)
{
	size_t n = strlen(s) + 1;

	if (b)
		memcpy(b, s, n);
	return n;
}

static size_t pack(char *b, const char *cwd, const char *mask, const char *argc, char **argv)
{
	size_t n = 0;
	char **e;

	n += put(b ? b + n : 0, cwd);
	n += put(b ? b + n : 0, mask);
	n += put(b ? b + n : 0, argc);
	for (e = argv; *e; e++)
		n += put(b ? b + n : 0, *e);
	for (e = environ; *e; e++)
		n += put(b ? b + n : 0, *e);
	return n;
}

int main(int argc, char **argv)
{
	struct sockaddr_un a = { .sun_family = AF_UNIX, .sun_path = RUN "/sock" };
	char cwd[4096], mask[16], num[16], line[160], *buf, c;
	union { char b[CMSG_SPACE(3 * sizeof(int))]; struct cmsghdr h; } ctl;
	struct msghdr msg = { 0 };
	struct cmsghdr *cm;
	struct iovec iov;
	struct sigaction sa = { .sa_handler = fwd, .sa_flags = SA_RESTART };
	size_t len, off;
	ssize_t r;
	int fd, i, n = 0, code;
	mode_t m;

	if (argc < 2 && !isatty(0))
		real(argv);
	for (i = 0; i < 3; i++)
		if (fcntl(i, F_GETFD) < 0)
			real(argv);
	fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
	if (fd < 0)
		real(argv);
	if (connect(fd, (struct sockaddr *)&a, sizeof a)) {
		close(fd);
		note(argc, idle());
		spawn();
		real(argv);
	}
	if (!getcwd(cwd, sizeof cwd))
		real(argv);
	m = umask(0);
	umask(m);
	snprintf(mask, sizeof mask, "%o", (unsigned)m);
	snprintf(num, sizeof num, "%d", argc);
	len = pack(0, cwd, mask, num, argv);
	buf = malloc(len + 4);
	if (!buf)
		real(argv);
	for (i = 0; i < 4; i++)
		buf[i] = len >> (8 * i);
	pack(buf + 4, cwd, mask, num, argv);
	iov.iov_base = buf;
	iov.iov_len = len + 4;
	msg.msg_iov = &iov;
	msg.msg_iovlen = 1;
	msg.msg_control = ctl.b;
	msg.msg_controllen = sizeof ctl.b;
	cm = CMSG_FIRSTHDR(&msg);
	cm->cmsg_level = SOL_SOCKET;
	cm->cmsg_type = SCM_RIGHTS;
	cm->cmsg_len = CMSG_LEN(3 * sizeof(int));
	memcpy(CMSG_DATA(cm), (int[]){ 0, 1, 2 }, 3 * sizeof(int));
	r = sendmsg(fd, &msg, MSG_NOSIGNAL);
	if (r <= 0)
		real(argv);
	for (off = r; off < len + 4; off += r) {
		r = send(fd, buf + off, len + 4 - off, MSG_NOSIGNAL);
		if (r <= 0)
			real(argv);
	}
	free(buf);
	sigfillset(&sa.sa_mask);
	for (i = 0; i < (int)(sizeof sigs / sizeof *sigs); i++)
		sigaction(sigs[i], &sa, 0);
	for (;;) {
		r = read(fd, &c, 1);
		if (r <= 0)
			break;
		if (c != '\n') {
			if (n < (int)sizeof line - 1)
				line[n++] = c;
			continue;
		}
		line[n] = 0;
		n = 0;
		if (line[0] == 'E') {
			close(fd);
			note(argc, line + 1);
			real(argv);
		}
		if (line[0] == 'P') {
			child = atoi(line + 1);
			for (i = 1; i < 32; i++)
				if (pending & (1u << i))
					fwd(i);
			continue;
		}
		if (line[0] != 'X')
			continue;
		code = atoi(line + 1);
		if (code < 0) {
			signal(-code, SIG_DFL);
			sigprocmask(SIG_SETMASK, &(sigset_t){ 0 }, 0);
			kill(getpid(), -code);
			return 128 - code;
		}
		if (code == 130 && gotint) {
			signal(SIGINT, SIG_DFL);
			kill(getpid(), SIGINT);
		}
		return code;
	}
	if (!child)
		real(argv);
	return 1;
}
