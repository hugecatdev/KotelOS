/* Doom на экране KotelOS: платформа для движка doomgeneric (его собирает scripts/build-doom.sh).
 * Кадр 320x200 растягивается до 4:3 целым множителем по ширине; экран - KMS: свой буфер прямо в
 * видеопамяти и режим 640x480, если он есть (у /dev/fb0 DRM кадр копирует из тени по таймеру,
 * раз в 50 мс), без KMS - /dev/fb0. Клавиши - из evdev (клавиатура PS/2: в неё страница шлёт и
 * клавиши, и кнопки ряда). */
#include <dirent.h>
#include <drm/drm.h>
#include <drm/drm_mode.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/input.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#include "doomgeneric.h"

/* коды клавиш движка (doomkeys.h: его KEY_* те же по имени, что в linux/input.h) */
enum {
	D_RIGHT = 0xae, D_LEFT = 0xac, D_UP = 0xad, D_DOWN = 0xaf, D_USE = 0xa2, D_FIRE = 0xa3,
	D_ESC = 27, D_ENTER = 13, D_TAB = 9, D_BKSP = 0x7f, D_PAUSE = 0xff,
	D_SHIFT = 0x80 + 0x36, D_ALT = 0x80 + 0x38,
	D_HOME = 0x80 + 0x47, D_END = 0x80 + 0x4f, D_PGUP = 0x80 + 0x49, D_PGDN = 0x80 + 0x51,
	D_INS = 0x80 + 0x52, D_DEL = 0x80 + 0x53,
};

static uint8_t *fb;
static int fd_fb = -1, stride, ox, oy, ow, oh;
static size_t fb_size;
static int *xmap;
static int inputs[8], ninputs;
static unsigned char queue[256][2];
static unsigned qr, qw;
static struct timespec t0;

static int doom_key(int code)
{
	static const char *rows[] = { "1234567890-=", "qwertyuiop[]", "asdfghjkl;'`", "\\zxcvbnm,./" };
	static const int first[] = { KEY_1, KEY_Q, KEY_A, KEY_BACKSLASH };
	switch (code) {
	case KEY_RIGHT: return D_RIGHT;
	case KEY_LEFT: return D_LEFT;
	case KEY_UP: return D_UP;
	case KEY_DOWN: return D_DOWN;
	case KEY_LEFTCTRL: case KEY_RIGHTCTRL: return D_FIRE;
	case KEY_SPACE: return D_USE;
	case KEY_LEFTALT: case KEY_RIGHTALT: return D_ALT;
	case KEY_LEFTSHIFT: case KEY_RIGHTSHIFT: return D_SHIFT;
	case KEY_ESC: return D_ESC;
	case KEY_ENTER: case KEY_KPENTER: return D_ENTER;
	case KEY_TAB: return D_TAB;
	case KEY_BACKSPACE: return D_BKSP;
	case KEY_PAUSE: return D_PAUSE;
	case KEY_HOME: return D_HOME;
	case KEY_END: return D_END;
	case KEY_PAGEUP: return D_PGUP;
	case KEY_PAGEDOWN: return D_PGDN;
	case KEY_INSERT: return D_INS;
	case KEY_DELETE: return D_DEL;
	case KEY_F11: return 0x80 + 0x57;
	case KEY_F12: return 0x80 + 0x58;
	}
	if (code >= KEY_F1 && code <= KEY_F10)
		return 0x80 + 0x3b + code - KEY_F1;
	for (int i = 0; i < 4; i++)
		if (code >= first[i] && code < first[i] + (int)strlen(rows[i]))
			return rows[i][code - first[i]];
	return 0;
}

static void poll_keys(void)
{
	struct input_event ev[16];
	for (int i = 0; i < ninputs; i++) {
		ssize_t n;
		while ((n = read(inputs[i], ev, sizeof ev)) > 0) {
			for (int j = 0; j < n / (ssize_t)sizeof ev[0]; j++) {
				int k;
				if (ev[j].type != EV_KEY || ev[j].value == 2 || !(k = doom_key(ev[j].code)))
					continue;
				if (qw - qr < 256) {
					queue[qw % 256][0] = ev[j].value;
					queue[qw % 256][1] = k;
					qw++;
				}
			}
		}
	}
}

static void open_inputs(void)
{
	DIR *d = opendir("/dev/input");
	struct dirent *e;
	while (d && (e = readdir(d)) && ninputs < 8) {
		char path[300];
		unsigned long keys[KEY_MAX / (8 * sizeof(long)) + 1] = { 0 };
		if (strncmp(e->d_name, "event", 5))
			continue;
		snprintf(path, sizeof path, "/dev/input/%s", e->d_name);
		int fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
		if (fd < 0)
			continue;
		/* только клавиатуры: у них есть буквы */
		if (ioctl(fd, EVIOCGBIT(EV_KEY, sizeof keys), keys) < 0 ||
		    !(keys[KEY_A / (8 * sizeof(long))] & 1UL << KEY_A % (8 * sizeof(long)))) {
			close(fd);
			continue;
		}
		inputs[ninputs++] = fd;
	}
	if (d)
		closedir(d);
}

static void clear_screen(void)
{
	if (fb)
		memset(fb, 0, fb_size);
}

/* KMS: режим 640x480 (или первый, что даёт разъём) и dumb-буфер, показанный сразу. Ресурсы
 * отпускает выход: тогда DRM возвращает экран своему /dev/fb0 */
static int kms_try(const char *path, unsigned *w, unsigned *h)
{
	int fd = open(path, O_RDWR | O_CLOEXEC);
	if (fd < 0)
		return -1;
	uint32_t conn[8], crtc[8];
	struct drm_mode_card_res res = { 0 };
	if (ioctl(fd, DRM_IOCTL_MODE_GETRESOURCES, &res) || !res.count_connectors || !res.count_crtcs ||
	    res.count_connectors > 8 || res.count_crtcs > 8)
		goto fail;
	res = (struct drm_mode_card_res){ .connector_id_ptr = (uintptr_t)conn, .count_connectors = res.count_connectors,
		.crtc_id_ptr = (uintptr_t)crtc, .count_crtcs = res.count_crtcs };
	if (ioctl(fd, DRM_IOCTL_MODE_GETRESOURCES, &res))
		goto fail;
	struct drm_mode_get_connector c = { .connector_id = conn[0] };
	if (ioctl(fd, DRM_IOCTL_MODE_GETCONNECTOR, &c) || !c.count_modes)
		goto fail;
	struct drm_mode_modeinfo *modes = calloc(c.count_modes, sizeof *modes), mode;
	c = (struct drm_mode_get_connector){ .connector_id = conn[0], .modes_ptr = (uintptr_t)modes, .count_modes = c.count_modes };
	if (!modes || ioctl(fd, DRM_IOCTL_MODE_GETCONNECTOR, &c))
		goto fail;
	mode = modes[0];
	for (unsigned i = 0; i < c.count_modes; i++)
		if (modes[i].hdisplay == 640 && modes[i].vdisplay == 480)
			mode = modes[i];
	free(modes);
	struct drm_mode_create_dumb cd = { .width = mode.hdisplay, .height = mode.vdisplay, .bpp = 32 };
	if (ioctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &cd))
		goto fail;
	struct drm_mode_fb_cmd fbc = { .width = cd.width, .height = cd.height, .pitch = cd.pitch, .bpp = 32, .depth = 24, .handle = cd.handle };
	struct drm_mode_map_dumb md = { .handle = cd.handle };
	if (ioctl(fd, DRM_IOCTL_MODE_ADDFB, &fbc) || ioctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &md))
		goto fail;
	fb = mmap(NULL, cd.size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, md.offset);
	if (fb == MAP_FAILED)
		goto fail;
	memset(fb, 0, cd.size);
	struct drm_mode_crtc sc = { .crtc_id = crtc[0], .fb_id = fbc.fb_id, .set_connectors_ptr = (uintptr_t)conn,
		.count_connectors = 1, .mode = mode, .mode_valid = 1 };
	if (ioctl(fd, DRM_IOCTL_MODE_SETCRTC, &sc)) {
		munmap(fb, cd.size);
		goto fail;
	}
	stride = cd.pitch;
	fb_size = cd.size;
	*w = cd.width;
	*h = cd.height;
	return fd;
fail:
	fb = NULL;
	close(fd);
	return -1;
}

/* первая карта с разъёмом: у virtio-gpu без своего экрана (только 3D) KMS нет, а номер у неё
 * может быть меньше, чем у VGA */
static int kms_init(unsigned *w, unsigned *h)
{
	char path[32];
	for (int i = 0; i < 8; i++) {
		snprintf(path, sizeof path, "/dev/dri/card%d", i);
		int fd = kms_try(path, w, h);
		if (fd >= 0)
			return fd;
	}
	return -1;
}

static void fbdev_init(unsigned *w, unsigned *h)
{
	struct fb_var_screeninfo v;
	struct fb_fix_screeninfo f;
	fd_fb = open("/dev/fb0", O_RDWR | O_CLOEXEC);
	if (fd_fb < 0 || ioctl(fd_fb, FBIOGET_VSCREENINFO, &v) || ioctl(fd_fb, FBIOGET_FSCREENINFO, &f)) {
		perror("doom: /dev/fb0");
		exit(1);
	}
	if (v.bits_per_pixel != 32) {
		fprintf(stderr, "doom: /dev/fb0 %u бит, нужно 32\n", v.bits_per_pixel);
		exit(1);
	}
	/* без консоли на экране DRM включает его только по set_par */
	v.activate = FB_ACTIVATE_NOW | FB_ACTIVATE_FORCE;
	ioctl(fd_fb, FBIOPUT_VSCREENINFO, &v);
	stride = f.line_length;
	fb_size = (size_t)stride * v.yres;
	fb = mmap(NULL, fb_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd_fb, 0);
	if (fb == MAP_FAILED) {
		perror("doom: mmap /dev/fb0");
		exit(1);
	}
	*w = v.xres;
	*h = v.yres;
}

void DG_Init(void)
{
	unsigned w, h;
	if (kms_init(&w, &h) < 0)
		fbdev_init(&w, &h);
	/* 320x200 в пропорции 4:3 (пиксели Doom вытянуты по высоте), целый множитель по ширине */
	int s = w / DOOMGENERIC_RESX;
	if (h / (DOOMGENERIC_RESY * 6 / 5) < (unsigned)s)
		s = h / (DOOMGENERIC_RESY * 6 / 5);
	if (s < 1)
		s = 1;
	ow = DOOMGENERIC_RESX * s;
	oh = DOOMGENERIC_RESY * 6 / 5 * s;
	if (ow > (int)w) ow = w;
	if (oh > (int)h) oh = h;
	ox = (w - ow) / 2;
	oy = (h - oh) / 2;
	xmap = malloc(ow * sizeof *xmap);
	for (int x = 0; x < ow; x++)
		xmap[x] = x * DOOMGENERIC_RESX / ow;
	clear_screen();
	atexit(clear_screen);
	open_inputs();
	clock_gettime(CLOCK_MONOTONIC, &t0);
}

void DG_DrawFrame(void)
{
	int prev = -1;
	uint32_t *last = NULL;
	for (int y = 0; y < oh; y++) {
		uint32_t *dst = (uint32_t *)(fb + (size_t)(oy + y) * stride) + ox;
		int sy = y * DOOMGENERIC_RESY / oh;
		if (sy == prev) {
			memcpy(dst, last, ow * 4);
		} else {
			const uint32_t *src = DG_ScreenBuffer + sy * DOOMGENERIC_RESX;
			for (int x = 0; x < ow; x++)
				dst[x] = src[xmap[x]];
		}
		prev = sy;
		last = dst;
	}
	poll_keys();
}

void DG_SleepMs(uint32_t ms)
{
	usleep(ms * 1000);
}

uint32_t DG_GetTicksMs(void)
{
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return (t.tv_sec - t0.tv_sec) * 1000 + (t.tv_nsec - t0.tv_nsec) / 1000000;
}

int DG_GetKey(int *pressed, unsigned char *key)
{
	poll_keys();
	if (qr == qw)
		return 0;
	*pressed = queue[qr % 256][0];
	*key = queue[qr % 256][1];
	qr++;
	return 1;
}

void DG_SetWindowTitle(const char *title)
{
	(void)title;
}

int main(int argc, char **argv)
{
	doomgeneric_Create(argc, argv);
	for (;;)
		doomgeneric_Tick();
}
