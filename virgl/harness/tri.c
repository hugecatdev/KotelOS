/*
 * Проверка VirGL на хосте: EGL без окна, GLES 2 (Mesa даёт высшую версию, какую может),
 * красный треугольник на синем в FBO 64x64, пиксели читаются назад (TRANSFER_GET) и
 * сверяются. Картинка - в PPM, если задан путь. --pbuffer: рисовать в буфер поверхности EGL
 * (формат как у окна, с глубиной), а не в FBO с текстурой RGBA.
 *   cc -O2 -o tri tri.c -lEGL -lGLESv2
 *   VTEST_SOCKET_NAME=/tmp/vt.sock LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=virpipe ./tri [--pbuffer] [out.ppm]
 */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define W 64
#define H 64

static GLuint shader(GLenum type, const char *src)
{
   GLuint s = glCreateShader(type);
   glShaderSource(s, 1, &src, NULL);
   glCompileShader(s);
   GLint ok;
   glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
   if (!ok) {
      char log[1024];
      glGetShaderInfoLog(s, sizeof(log), NULL, log);
      fprintf(stderr, "шейдер: %s\n", log);
      exit(1);
   }
   return s;
}

int main(int argc, char **argv)
{
   int pbuffer = argc > 1 && !strcmp(argv[1], "--pbuffer");
   if (pbuffer) {
      argc--;
      argv++;
   }
   PFNEGLGETPLATFORMDISPLAYEXTPROC get_display =
      (PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");
   EGLDisplay dpy = get_display(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
   if (!eglInitialize(dpy, NULL, NULL)) {
      fprintf(stderr, "eglInitialize: %#x\n", eglGetError());
      return 1;
   }
   eglBindAPI(EGL_OPENGL_ES_API);
   const EGLint cfg_attr[] = { EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
                               EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8,
                               EGL_DEPTH_SIZE, pbuffer ? 24 : 0, EGL_NONE };
   EGLConfig cfg;
   EGLint n;
   if (!eglChooseConfig(dpy, cfg_attr, &cfg, 1, &n) || !n) {
      fprintf(stderr, "нет конфигурации EGL\n");
      return 1;
   }
   const EGLint ctx_attr[] = { EGL_CONTEXT_MAJOR_VERSION, 2, EGL_NONE };
   EGLContext ctx = eglCreateContext(dpy, cfg, EGL_NO_CONTEXT, ctx_attr);
   EGLSurface surf = EGL_NO_SURFACE;
   if (pbuffer) {
      const EGLint pb_attr[] = { EGL_WIDTH, W, EGL_HEIGHT, H, EGL_NONE };
      surf = eglCreatePbufferSurface(dpy, cfg, pb_attr);
   }
   if (!ctx || !eglMakeCurrent(dpy, surf, surf, ctx)) {
      fprintf(stderr, "контекст: %#x\n", eglGetError());
      return 1;
   }
   printf("GL_RENDERER: %s\nGL_VERSION: %s\nGLSL: %s\n", glGetString(GL_RENDERER),
          glGetString(GL_VERSION), glGetString(GL_SHADING_LANGUAGE_VERSION));

   GLuint tex, fb;
   if (pbuffer)
      goto draw;
   glGenTextures(1, &tex);
   glBindTexture(GL_TEXTURE_2D, tex);
   glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, W, H, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
   glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
   glGenFramebuffers(1, &fb);
   glBindFramebuffer(GL_FRAMEBUFFER, fb);
   glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, tex, 0);
   if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
      fprintf(stderr, "FBO не готов\n");
      return 1;
   }

draw:;
   GLuint prog = glCreateProgram();
   glAttachShader(prog, shader(GL_VERTEX_SHADER,
      "attribute vec2 p;\nvoid main() { gl_Position = vec4(p, 0.0, 1.0); }\n"));
   glAttachShader(prog, shader(GL_FRAGMENT_SHADER,
      "precision mediump float;\nvoid main() { gl_FragColor = vec4(1.0, 0.0, 0.0, 1.0); }\n"));
   glBindAttribLocation(prog, 0, "p");
   glLinkProgram(prog);
   glUseProgram(prog);

   static const float tri[] = { -0.8f, -0.8f, 0.8f, -0.8f, 0.0f, 0.8f };
   GLuint vbo;
   glGenBuffers(1, &vbo);
   glBindBuffer(GL_ARRAY_BUFFER, vbo);
   glBufferData(GL_ARRAY_BUFFER, sizeof(tri), tri, GL_STATIC_DRAW);
   glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, 0);
   glEnableVertexAttribArray(0);

   glViewport(0, 0, W, H);
   glClearColor(0.0f, 0.0f, 1.0f, 1.0f);
   glEnable(GL_DEPTH_TEST);
   glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
   glDrawArrays(GL_TRIANGLES, 0, 3);

   static unsigned char px[W * H * 4];
   glReadPixels(0, 0, W, H, GL_RGBA, GL_UNSIGNED_BYTE, px);
   GLenum err = glGetError();

   const unsigned char *c = px + (H / 2 * W + W / 2) * 4, *k = px;
   printf("центр %d,%d,%d угол %d,%d,%d ошибка GL %#x\n", c[0], c[1], c[2], k[0], k[1], k[2], err);
   int ok = c[0] > 200 && c[2] < 50 && k[0] < 50 && k[2] > 200 && !err;

   if (argc > 1) {
      FILE *f = fopen(argv[1], "wb");
      fprintf(f, "P6\n%d %d\n255\n", W, H);
      for (int y = H - 1; y >= 0; y--)
         for (int x = 0; x < W; x++)
            fwrite(px + (y * W + x) * 4, 1, 3, f);
      fclose(f);
   }
   puts(ok ? "TRI-OK" : "TRI-FAIL");
   eglTerminate(dpy);
   return ok ? 0 : 1;
}
