/*
 * Сервер vtest для страницы: команды Mesa (драйвер virpipe) приходят порциями из JS,
 * ответы уходят в устройство /dev/vtest (его пишет страница, см. vtest_web.js).
 * Повторяет vtest_client_dispatch_commands() из vtest_server.c, но ничего не ждёт:
 * в WebGL2 забор становится готовым только после возврата в цикл событий, поэтому
 * RESOURCE_BUSY_WAIT с флагом WAIT при занятом GPU остаётся в очереди до следующего
 * vtw_run(). Клиент один: в протоколе 0 номера ресурсов выбирает клиент.
 */
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <emscripten.h>

#include "virglrenderer.h"
#include "vtest.h"
#include "vtest_protocol.h"

/* GL-контексты - виртуальные, поверх одного WebGL2 (vgl.js) */
EM_JS(int, vgl_create, (void), { return Module.vgl.create(); });
EM_JS(void, vgl_destroy, (int id), { Module.vgl.destroy(id); });
EM_JS(int, vgl_make_current, (int id), { return Module.vgl.makeCurrent(id); });

static virgl_renderer_gl_context create_gl_context(void *cookie, int scanout,
                                                   struct virgl_renderer_gl_ctx_param *param)
{
   (void)cookie; (void)scanout; (void)param;
   return (virgl_renderer_gl_context)(intptr_t)vgl_create();
}

static void destroy_gl_context(void *cookie, virgl_renderer_gl_context ctx)
{
   (void)cookie;
   vgl_destroy((int)(intptr_t)ctx);
}

static int make_current(void *cookie, int scanout, virgl_renderer_gl_context ctx)
{
   (void)cookie; (void)scanout;
   return vgl_make_current((int)(intptr_t)ctx);
}

/* сообщения vrend (ошибки компиляции шейдеров и т.п.) - в stderr, то есть в консоль страницы */
static void log_message(enum virgl_log_level_flags level, const char *message, void *data)
{
   (void)level; (void)data;
   fputs(message, stderr);
}

static const struct virgl_renderer_callbacks context_cbs = {
   .create_gl_context = create_gl_context,
   .destroy_gl_context = destroy_gl_context,
   .make_current = make_current,
};

static const struct {
   int (*dispatch)(uint32_t);
   bool init_context;
} commands[] = {
   [VCMD_GET_CAPS]              = { vtest_send_caps,             false },
   [VCMD_RESOURCE_CREATE]       = { vtest_create_resource,       true  },
   [VCMD_RESOURCE_UNREF]        = { vtest_resource_unref,        true  },
   [VCMD_TRANSFER_GET]          = { vtest_transfer_get,          true  },
   [VCMD_TRANSFER_PUT]          = { vtest_transfer_put,          true  },
   [VCMD_SUBMIT_CMD]            = { vtest_submit_cmd,            true  },
   [VCMD_RESOURCE_BUSY_WAIT]    = { vtest_resource_busy_wait,    false },
   [VCMD_GET_CAPS2]             = { vtest_send_caps2,            false },
   [VCMD_PING_PROTOCOL_VERSION] = { vtest_ping_protocol_version, false },
   [VCMD_PROTOCOL_VERSION]      = { vtest_protocol_version,      false },
};

/* контекст vtest запоминает указатель на ввод: он постоянный, меняется только буфер */
static struct vtest_buffer cmd_buf;
static struct vtest_input cmd_input = { .data.buffer = &cmd_buf, .read = vtest_buf_read };

static bool renderer_ready;
static struct vtest_context *client;
static int out_fd = -1;
static uint8_t *in_buf;
static size_t in_len, in_cap;

EMSCRIPTEN_KEEPALIVE int vtw_init(void)
{
   if (renderer_ready)
      return 0;
   virgl_set_log_callback(log_message, NULL, NULL);
   vtest_set_context_callbacks(&context_cbs);
   if (vtest_init_renderer(false, VIRGL_RENDERER_USE_GLES, NULL) < 0)
      return -1;
   renderer_ready = true;
   return 0;
}

/* новый клиент: прежний (если был) закрывается */
static int reopen(const char *out_path)
{
   if (client) {
      vtest_destroy_context(client);
      client = NULL;
   }
   if (out_fd >= 0)
      close(out_fd);
   in_len = 0;
   out_fd = open(out_path, O_WRONLY);
   return out_fd < 0 ? -errno : 0;
}

EMSCRIPTEN_KEEPALIVE int vtw_connect(void)
{
   return reopen("/dev/vtest");
}

EMSCRIPTEN_KEEPALIVE void vtw_disconnect(void)
{
   reopen("/dev/null");
   close(out_fd);
   out_fd = -1;
}

/* место под n байт ввода; потом vtw_push(n) */
EMSCRIPTEN_KEEPALIVE uint8_t *vtw_reserve(size_t n)
{
   if (in_len + n > in_cap) {
      size_t cap = in_cap ? in_cap : 65536;
      while (cap < in_len + n)
         cap *= 2;
      uint8_t *p = realloc(in_buf, cap);
      if (!p)
         return NULL;
      in_buf = p;
      in_cap = cap;
   }
   return in_buf + in_len;
}

EMSCRIPTEN_KEEPALIVE void vtw_push(size_t n)
{
   in_len += n;
}

/* сколько байт занимает команда целиком, 0 - заголовок ещё не дошёл */
static size_t command_size(const uint8_t *p, size_t avail)
{
   uint32_t hdr[VTEST_HDR_SIZE];
   if (avail < sizeof(hdr))
      return 0;
   memcpy(hdr, p, sizeof(hdr));
   size_t size = sizeof(hdr);
   if (hdr[VTEST_CMD_ID] == VCMD_CREATE_RENDERER) {
      size += hdr[VTEST_CMD_LEN]; /* длина имени в байтах, а не в словах */
   } else if (hdr[VTEST_CMD_ID] == VCMD_TRANSFER_PUT) {
      /* в длине Mesa учитывает данные с округлением до слов, а шлёт их без выравнивания:
       * сервер читает по data_size, так и считаем */
      uint32_t data_size;
      if (avail < sizeof(hdr) + VCMD_TRANSFER_HDR_SIZE * 4)
         return 0;
      memcpy(&data_size, p + sizeof(hdr) + VCMD_TRANSFER_DATA_SIZE * 4, 4);
      size += VCMD_TRANSFER_HDR_SIZE * 4 + (size_t)data_size;
   } else {
      size += (size_t)hdr[VTEST_CMD_LEN] * 4;
   }
   return size;
}

static bool must_wait(const uint8_t *p)
{
   uint32_t hdr[VTEST_HDR_SIZE + VCMD_BUSY_WAIT_SIZE];
   memcpy(hdr, p, sizeof(hdr));
   if (hdr[VTEST_CMD_ID] != VCMD_RESOURCE_BUSY_WAIT)
      return false;
   if (!(hdr[VTEST_HDR_SIZE + VCMD_BUSY_WAIT_FLAGS] & VCMD_BUSY_WAIT_FLAG_WAIT))
      return false;
   return vtest_resource_busy();
}

/*
 * Разбирает всё, что пришло целиком. 0 - очередь пуста или ждёт данных,
 * 1 - стоит ожидание GPU (вызвать снова после возврата в цикл событий),
 * <0 - ошибка, клиента закрыть.
 */
EMSCRIPTEN_KEEPALIVE int vtw_run(void)
{
   size_t pos = 0;
   int ret = 0;

   while (ret == 0) {
      size_t size = command_size(in_buf + pos, in_len - pos);
      if (!size || in_len - pos < size) {
#ifdef VTW_DEBUG
         if (in_len > pos)
            fprintf(stderr, "vtw: ждём данных: есть %zu, нужно %zu (%08x %08x)\n", in_len - pos, size,
                    in_len - pos >= 8 ? ((uint32_t *)(in_buf + pos))[0] : 0,
                    in_len - pos >= 8 ? ((uint32_t *)(in_buf + pos))[1] : 0);
#endif
         break;
      }

      cmd_buf.buffer = (const char *)in_buf + pos;
      cmd_buf.size = (int)size;
      uint32_t hdr[VTEST_HDR_SIZE];
      cmd_input.read(&cmd_input, hdr, sizeof(hdr));
#ifdef VTW_DEBUG
      fprintf(stderr, "vtw: команда %u, %zu байт\n", hdr[VTEST_CMD_ID], size);
#endif

      if (!client) {
         /* первая команда обязана быть VCMD_CREATE_RENDERER */
         if (hdr[VTEST_CMD_ID] != VCMD_CREATE_RENDERER ||
             vtest_create_context(&cmd_input, out_fd, hdr[VTEST_CMD_LEN], &client) < 0) {
            ret = -EINVAL;
            break;
         }
         vtest_poll_resource_busy_wait();
         pos += size;
         continue;
      }

      vtest_poll_resource_busy_wait();
      uint32_t id = hdr[VTEST_CMD_ID];
      if (id == 0 || id >= sizeof(commands) / sizeof(commands[0]) || !commands[id].dispatch) {
         fprintf(stderr, "vtest: неожиданная команда %u\n", id);
         ret = -EINVAL;
         break;
      }
      if (must_wait(in_buf + pos)) {
         ret = 1;
         break;
      }
      if (commands[id].init_context && vtest_lazy_init_context(client)) {
         ret = -EINVAL;
         break;
      }
      vtest_set_current_context(client);
      if (commands[id].dispatch(hdr[VTEST_CMD_LEN]) < 0) {
         fprintf(stderr, "vtest: команда %u не выполнена\n", id);
         ret = -EINVAL;
         break;
      }
      pos += size;
   }

   memmove(in_buf, in_buf + pos, in_len - pos);
   in_len -= pos;
   return ret;
}

/* заборы vrend: опрашивать после возврата в цикл событий */
EMSCRIPTEN_KEEPALIVE void vtw_poll(void)
{
   if (renderer_ready)
      virgl_renderer_poll();
}
