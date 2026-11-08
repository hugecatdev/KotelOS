/*
 * virglrenderer для устройства virtio-gpu в v86 (virtio_gpu.js): вызовы из JS по командам
 * гостя. Память гостя - в другом модуле wasm (v86), поэтому подложку ресурсов здесь не
 * держим: при передачах устройство собирает нужный кусок страниц гостя во временный буфер
 * этого модуля и передаёт его явным iov (и наоборот при чтении).
 * Кадр на экран: текстура ресурса рисуется на холст WebGL (свой виртуальный контекст).
 */
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/uio.h>

#include <emscripten.h>
#include <epoxy/gl.h>

#include "virglrenderer.h"
#include "virgl_hw.h"

/* виртуальные контексты (vgl.js); vgl_create/destroy/make_current - из vtest_web.c */
int vgl_create(void);
void vgl_destroy(int id);
int vgl_make_current(int id);
EM_JS(int, vgl_current, (void), { return Module.vgl.current(); });
EM_JS(void, js_fence, (uint32_t fence), { if (Module.onFence) Module.onFence(fence); });

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

static void write_fence(void *cookie, uint32_t fence)
{
   (void)cookie;
   js_fence(fence);
}

static void log_message(enum virgl_log_level_flags level, const char *message, void *data)
{
   (void)level; (void)data;
   /* stderr Emscripten выводит по переводу строки, а сообщения vrend бывают без него */
   size_t n = strlen(message);
   fprintf(stderr, "%s%s", message, n && message[n - 1] == '\n' ? "" : "\n");
}

static struct virgl_renderer_callbacks cbs = {
   .version = 1,
   .write_fence = write_fence,
   .create_gl_context = create_gl_context,
   .destroy_gl_context = destroy_gl_context,
   .make_current = make_current,
};

static bool ready;
static int present_ctx;
static GLuint present_prog, present_vao, present_sampler;
static GLint present_alpha, present_flip;

EMSCRIPTEN_KEEPALIVE int vgw_init(void)
{
   if (ready)
      return 0;
   virgl_set_log_callback(log_message, NULL, NULL);
   /* cookie не нужен, но должен быть не NULL */
   int r = virgl_renderer_init(&cbs, VIRGL_RENDERER_USE_GLES, &cbs);
   if (r)
      return r;
   ready = true;
   return 0;
}

/* ---- ресурсы ---- */

EMSCRIPTEN_KEEPALIVE int vgw_resource_create(uint32_t handle, uint32_t target, uint32_t format,
                                             uint32_t bind, uint32_t width, uint32_t height,
                                             uint32_t depth, uint32_t array_size, uint32_t last_level,
                                             uint32_t nr_samples, uint32_t flags)
{
   struct virgl_renderer_resource_create_args a = {
      .handle = handle, .target = target, .format = format, .bind = bind,
      .width = width, .height = height, .depth = depth, .array_size = array_size,
      .last_level = last_level, .nr_samples = nr_samples, .flags = flags,
   };
   return virgl_renderer_resource_create(&a, NULL, 0);
}

EMSCRIPTEN_KEEPALIVE void vgw_resource_unref(uint32_t handle)
{
   virgl_renderer_resource_unref(handle);
}

/* box: x y z w h d - по порядку в памяти (6 x uint32) */
static void to_box(const uint32_t *b, struct virgl_box *box)
{
   box->x = b[0]; box->y = b[1]; box->z = b[2];
   box->w = b[3]; box->h = b[4]; box->d = b[5];
}

EMSCRIPTEN_KEEPALIVE int vgw_transfer_write(uint32_t handle, uint32_t ctx, uint32_t level,
                                            uint32_t stride, uint32_t layer_stride,
                                            const uint32_t *b, void *data, uint32_t len)
{
   struct virgl_box box;
   struct iovec iov = { data, len };
   to_box(b, &box);
   return virgl_renderer_transfer_write_iov(handle, ctx, level, stride, layer_stride, &box, 0, &iov, 1);
}

EMSCRIPTEN_KEEPALIVE int vgw_transfer_read(uint32_t handle, uint32_t ctx, uint32_t level,
                                           uint32_t stride, uint32_t layer_stride,
                                           const uint32_t *b, void *data, uint32_t len)
{
   struct virgl_box box;
   struct iovec iov = { data, len };
   to_box(b, &box);
   return virgl_renderer_transfer_read_iov(handle, ctx, level, stride, layer_stride, &box, 0, &iov, 1);
}

/* сведения о ресурсе: handle format width height depth flags tex_id stride (8 x uint32) */
EMSCRIPTEN_KEEPALIVE int vgw_resource_info(uint32_t handle, uint32_t *out)
{
   struct virgl_renderer_resource_info info;
   int r = virgl_renderer_resource_get_info(handle, &info);
   if (r)
      return r;
   out[0] = info.handle; out[1] = info.virgl_format; out[2] = info.width; out[3] = info.height;
   out[4] = info.depth; out[5] = info.flags; out[6] = info.tex_id; out[7] = info.stride;
   return 0;
}

/* ---- 3D ---- */

EMSCRIPTEN_KEEPALIVE int vgw_ctx_create(uint32_t ctx, uint32_t capset, const char *name, uint32_t nlen)
{
   if (capset)
      return virgl_renderer_context_create_with_flags(ctx, capset, nlen, name);
   return virgl_renderer_context_create(ctx, nlen, name);
}

EMSCRIPTEN_KEEPALIVE void vgw_ctx_destroy(uint32_t ctx)
{
   virgl_renderer_context_destroy(ctx);
}

EMSCRIPTEN_KEEPALIVE void vgw_ctx_attach(uint32_t ctx, uint32_t handle)
{
   virgl_renderer_ctx_attach_resource(ctx, handle);
}

EMSCRIPTEN_KEEPALIVE void vgw_ctx_detach(uint32_t ctx, uint32_t handle)
{
   virgl_renderer_ctx_detach_resource(ctx, handle);
}

EMSCRIPTEN_KEEPALIVE int vgw_submit(void *cmd, uint32_t ctx, uint32_t ndw)
{
   return virgl_renderer_submit_cmd(cmd, ctx, ndw);
}

/* наибольшая версия и размер набора возможностей: out[0] версия, out[1] размер */
EMSCRIPTEN_KEEPALIVE void vgw_capset_info(uint32_t set, uint32_t *out)
{
   virgl_renderer_get_cap_set(set, &out[0], &out[1]);
}

EMSCRIPTEN_KEEPALIVE void vgw_capset_fill(uint32_t set, uint32_t version, void *caps)
{
   virgl_renderer_fill_caps(set, version, caps);
   /* хост не видит память гостя напрямую: без передач в потоке команд (TRANSFER, vrend читал бы
    * подложку сам), без промежуточных буферов (COPY_TRANSFER) и без постоянно отображённых
    * буферов - данные носит устройство командами TRANSFER_TO/FROM_HOST_3D */
   if (set == 2) {
      union virgl_caps *c = caps;
      c->v2.capability_bits &= ~(VIRGL_CAP_TRANSFER | VIRGL_CAP_COPY_TRANSFER | VIRGL_CAP_ARB_BUFFER_STORAGE);
      /* и чтение назад через промежуточный буфер (хост пишет в подложку), и ресурсы-блобы */
      c->v2.capability_bits_v2 &= ~(VIRGL_CAP_V2_COPY_TRANSFER_BOTH_DIRECTIONS | VIRGL_CAP_V2_UNTYPED_RESOURCE);
   }
}

/* ресурсы, в которые хост пишет сам (VIRGL_BIND_CUSTOM: результаты запросов), держат
 * подложку здесь; устройство сверяет её с памятью гостя до и после команд */
EMSCRIPTEN_KEEPALIVE void *vgw_shadow_attach(uint32_t handle, uint32_t size)
{
   /* virglrenderer хранит указатель на iovec, а не копию: он живёт вместе с подложкой (на стеке
    * запись результата запроса шла в мусор - «Query state does not fit IOV size») */
   struct iovec *iov = malloc(sizeof(*iov));
   void *p = calloc(1, size);
   if (!iov || !p) {
      free(iov);
      free(p);
      return NULL;
   }
   iov->iov_base = p;
   iov->iov_len = size;
   if (virgl_renderer_resource_attach_iov(handle, iov, 1)) {
      free(iov);
      free(p);
      return NULL;
   }
   return p;
}

EMSCRIPTEN_KEEPALIVE void vgw_shadow_detach(uint32_t handle, void *p)
{
   struct iovec *iov = NULL;
   int num_iovs = 0;
   virgl_renderer_resource_detach_iov(handle, &iov, &num_iovs);
   free(iov);
   free(p);
}

EMSCRIPTEN_KEEPALIVE int vgw_fence(uint32_t fence, uint32_t ctx)
{
   return virgl_renderer_create_fence(fence, ctx);
}

EMSCRIPTEN_KEEPALIVE void vgw_poll(void)
{
   if (ready)
      virgl_renderer_poll();
}

/* ---- кадр на холст ---- */

static GLuint compile(GLenum type, const char *src)
{
   GLuint s = glCreateShader(type);
   glShaderSource(s, 1, &src, NULL);
   glCompileShader(s);
   GLint ok;
   glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
   if (!ok) {
      char log[512];
      glGetShaderInfoLog(s, sizeof(log), NULL, log);
      fprintf(stderr, "vgpu: шейдер вывода: %s\n", log);
   }
   return s;
}

static void present_setup(void)
{
   present_ctx = vgl_create();
   vgl_make_current(present_ctx);
   /* полноэкранный треугольник. flip: строка 0 текстуры - верх экрана. Так у буферов GBM (glamor,
    * kmscube: в памяти сверху вниз, как читает дисплей); ресурсы 2D (Y_0_TOP: dumb, fbdev, курсор)
    * vrend при загрузке сам кладёт снизу вверх */
   static const char *vs =
      "#version 300 es\n"
      "uniform bool flip;\n"
      "out vec2 tc;\n"
      "void main() {\n"
      "   vec2 p = vec2(float((gl_VertexID & 1) << 2) - 1.0, float((gl_VertexID & 2) << 1) - 1.0);\n"
      "   tc = vec2((p.x + 1.0) * 0.5, flip ? (1.0 - p.y) * 0.5 : (p.y + 1.0) * 0.5);\n"
      "   gl_Position = vec4(p, 0.0, 1.0);\n"
      "}\n";
   static const char *fs =
      "#version 300 es\n"
      "precision mediump float;\n"
      "uniform sampler2D img;\n"
      "uniform bool alpha;\n"
      "in vec2 tc;\n"
      "out vec4 color;\n"
      "void main() { vec4 t = texture(img, tc); color = vec4(t.rgb, alpha ? t.a : 1.0); }\n";
   present_prog = glCreateProgram();
   glAttachShader(present_prog, compile(GL_VERTEX_SHADER, vs));
   glAttachShader(present_prog, compile(GL_FRAGMENT_SHADER, fs));
   glLinkProgram(present_prog);
   present_alpha = glGetUniformLocation(present_prog, "alpha");
   present_flip = glGetUniformLocation(present_prog, "flip");
   glGenVertexArrays(1, &present_vao);
   glGenSamplers(1, &present_sampler);
   glSamplerParameteri(present_sampler, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
   glSamplerParameteri(present_sampler, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
   glSamplerParameteri(present_sampler, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
   glSamplerParameteri(present_sampler, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
}

/* нарисовать ресурс на весь холст ширины w и высоты h, поверх - курсор (ресурс cursor, левый верхний
 * угол в cx, cy; 0 - без курсора); 0 - готово */
EMSCRIPTEN_KEEPALIVE int vgw_present(uint32_t handle, int w, int h, uint32_t cursor, int cx, int cy)
{
   struct virgl_renderer_resource_info info;
   if (virgl_renderer_resource_get_info(handle, &info) || !info.tex_id)
      return -ENOENT;
   int prev = vgl_current();
   if (!present_ctx)
      present_setup();
   vgl_make_current(present_ctx);
   glBindFramebuffer(GL_FRAMEBUFFER, 0);
   glViewport(0, 0, w, h);
   glUseProgram(present_prog);
   glUniform1i(present_alpha, 0);
   glUniform1i(present_flip, !(info.flags & VIRGL_RESOURCE_Y_0_TOP));
   glBindVertexArray(present_vao);
   glActiveTexture(GL_TEXTURE0);
   glBindTexture(GL_TEXTURE_2D, info.tex_id);
   glBindSampler(0, present_sampler);
   glDrawArrays(GL_TRIANGLES, 0, 3);

   struct virgl_renderer_resource_info ci;
   if (cursor && !virgl_renderer_resource_get_info(cursor, &ci) && ci.tex_id) {
      /* альфа курсоров X предумножена */
      glEnable(GL_BLEND);
      glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
      glViewport(cx, h - cy - (int)ci.height, ci.width, ci.height);
      glUniform1i(present_alpha, 1);
      glUniform1i(present_flip, !(ci.flags & VIRGL_RESOURCE_Y_0_TOP));
      glBindTexture(GL_TEXTURE_2D, ci.tex_id);
      glDrawArrays(GL_TRIANGLES, 0, 3);
      glDisable(GL_BLEND);
   }
   glBindTexture(GL_TEXTURE_2D, 0);
   vgl_make_current(prev);
   return 0;
}
