/*
 * OpenGL 3.0 в госте: версия, шейдеры GLSL 1.30 (in/out, целые, побитовые операции,
 * texelFetch из массива текстур, glBindFragDataLocation), вызовы GL 3.0 (glEnablei/glColorMaski,
 * glBeginConditionalRender, glClearBufferfv), кадр сверяется по пикселям.
 *   gl3test  -> строки проверок и GL3TEST-OK | GL3TEST-FAIL
 */
#define GL_GLEXT_PROTOTYPES
#include <GL/gl.h>
#include <GL/glext.h>
#include <GL/glx.h>
#include <X11/Xlib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define W 64

static const char *vs =
   "#version 130\n"
   "in vec2 pos;\n"
   "flat out ivec2 cell;\n"
   "void main() {\n"
   "   cell = ivec2(gl_VertexID & 1, gl_VertexID >> 1);\n"
   "   gl_Position = vec4(pos, 0.0, 1.0);\n"
   "}\n";

static const char *fs =
   "#version 130\n"
   "uniform sampler2DArray tex;\n"
   "uniform int bits;\n"
   "flat in ivec2 cell;\n"
   "out vec4 color;\n"
   "void main() {\n"
   "   vec4 t = texelFetch(tex, ivec3(0, 0, 1), 0);\n"   /* слой 1 - (0, 0.5, 1, 1) */
   "   int r = (bits >> 4) & 0xF;\n"                      /* 0x5A -> 5 */
   "   color = vec4(float(r) / 15.0, t.g, t.b, 1.0);\n"
   "}\n";

static GLuint shader(GLenum type, const char *src)
{
   GLuint s = glCreateShader(type);
   glShaderSource(s, 1, &src, NULL);
   glCompileShader(s);
   GLint ok = 0;
   glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
   if (!ok) {
      char log[1024];
      glGetShaderInfoLog(s, sizeof(log), NULL, log);
      printf("шейдер не собрался: %s\n", log);
   }
   return s;
}

int main(void)
{
   Display *d = XOpenDisplay(NULL);
   if (!d) {
      fprintf(stderr, "нет дисплея\n");
      return 2;
   }
   int attr[] = { GLX_RGBA, GLX_RED_SIZE, 8, GLX_GREEN_SIZE, 8, GLX_BLUE_SIZE, 8, GLX_DOUBLEBUFFER, None };
   XVisualInfo *vi = glXChooseVisual(d, DefaultScreen(d), attr);
   XSetWindowAttributes swa = { .colormap = XCreateColormap(d, RootWindow(d, vi->screen), vi->visual, AllocNone),
                                .border_pixel = 0 };
   Window w = XCreateWindow(d, RootWindow(d, vi->screen), 480, 40, W, W, 0, vi->depth, InputOutput, vi->visual,
                            CWColormap | CWBorderPixel, &swa);
   XMapWindow(d, w);
   GLXContext ctx = glXCreateContext(d, vi, NULL, True);
   glXMakeCurrent(d, w, ctx);

   const char *ver = (const char *)glGetString(GL_VERSION);
   const char *sl = (const char *)glGetString(GL_SHADING_LANGUAGE_VERSION);
   printf("renderer %s, OpenGL %s, GLSL %s\n", glGetString(GL_RENDERER), ver, sl);
   int ok = atof(ver) >= 3.0 && atof(sl) >= 1.3;

   /* массив текстур 1x1x2: слой 0 - красный, слой 1 - (0, 128, 255) */
   GLuint tex;
   glGenTextures(1, &tex);
   glBindTexture(GL_TEXTURE_2D_ARRAY, tex);
   unsigned char texels[] = { 255, 0, 0, 255, 0, 128, 255, 255 };
   glTexImage3D(GL_TEXTURE_2D_ARRAY, 0, GL_RGBA8, 1, 1, 2, 0, GL_RGBA, GL_UNSIGNED_BYTE, texels);
   glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
   glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MAG_FILTER, GL_NEAREST);

   GLuint prog = glCreateProgram();
   glAttachShader(prog, shader(GL_VERTEX_SHADER, vs));
   glAttachShader(prog, shader(GL_FRAGMENT_SHADER, fs));
   glBindAttribLocation(prog, 0, "pos");
   glBindFragDataLocation(prog, 0, "color");
   glLinkProgram(prog);
   GLint linked = 0;
   glGetProgramiv(prog, GL_LINK_STATUS, &linked);
   ok &= linked;
   glUseProgram(prog);
   glUniform1i(glGetUniformLocation(prog, "tex"), 0);
   glUniform1i(glGetUniformLocation(prog, "bits"), 0x5A);

   static const float tri[] = { -1, -1, 3, -1, -1, 3 };
   GLuint vbo, vao;
   glGenVertexArrays(1, &vao);
   glBindVertexArray(vao);
   glGenBuffers(1, &vbo);
   glBindBuffer(GL_ARRAY_BUFFER, vbo);
   glBufferData(GL_ARRAY_BUFFER, sizeof(tri), tri, GL_STATIC_DRAW);
   glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, 0);
   glEnableVertexAttribArray(0);

   glViewport(0, 0, W, W);
   GLfloat clear[] = { 0, 0, 0, 1 };
   glClearBufferfv(GL_COLOR, 0, clear);
   glEnablei(GL_BLEND, 0);
   glDisablei(GL_BLEND, 0);
   glColorMaski(0, GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);

   /* условное рисование по запросу, в котором что-то нарисовано */
   GLuint q;
   glGenQueries(1, &q);
   glBeginQuery(GL_SAMPLES_PASSED, q);
   glDrawArrays(GL_TRIANGLES, 0, 3);
   glEndQuery(GL_SAMPLES_PASSED);
   glBeginConditionalRender(q, GL_QUERY_WAIT);
   glDrawArrays(GL_TRIANGLES, 0, 3);
   glEndConditionalRender();
   glFinish();

   /* результат запроса: на GLES vrend считает ANY_SAMPLES_PASSED и умножает на площадь - не 0 */
   GLuint samples = 0;
   glGetQueryObjectuiv(q, GL_QUERY_RESULT, &samples);
   printf("запрос GL_SAMPLES_PASSED: %u %s\n", samples, samples ? "OK" : "FAIL");
   ok &= samples != 0;

   unsigned char p[4];
   glReadPixels(W / 2, W / 2, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, p);
   int want[] = { 85, 128, 255 }; /* 5/15 = 85 */
   int pix = abs(p[0] - want[0]) <= 2 && abs(p[1] - want[1]) <= 2 && abs(p[2] - want[2]) <= 2;
   printf("пиксель %d %d %d (ожидалось %d %d %d) %s\n", p[0], p[1], p[2], want[0], want[1], want[2], pix ? "OK" : "FAIL");
   GLenum err = glGetError();
   printf("glGetError 0x%x %s\n", err, err ? "FAIL" : "OK");
   ok &= pix && !err;
   glXSwapBuffers(d, w);
   puts(ok ? "GL3TEST-OK" : "GL3TEST-FAIL");
   return !ok;
}
