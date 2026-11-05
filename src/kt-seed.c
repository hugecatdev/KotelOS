#include <fcntl.h>
#include <linux/random.h>
#include <sys/ioctl.h>
#include <unistd.h>

int main(void)
{
	struct { int count, size; unsigned char buf[64]; } e;
	int n = read(0, e.buf, sizeof e.buf);
	int fd = open("/dev/urandom", O_WRONLY);

	if (n <= 0 || fd < 0)
		return 1;
	e.count = n * 8;
	e.size = n;
	if (ioctl(fd, RNDADDENTROPY, &e))
		return 1;
	return ioctl(fd, RNDRESEEDCRNG) ? 1 : 0;
}
