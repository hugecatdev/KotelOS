#!/bin/sh
# VirGL в браузере: virglrenderer (vrend) и libepoxy, собранные Emscripten в wasm. vrend идёт по
# своей ветке для хоста GLES, Emscripten переводит GLES 3.0 в WebGL2. Контексты GL даёт страница
# (колбэки virgl_renderer_callbacks), EGL/GLX/GBM и libdrm не нужны. Результат -> vendor/virgl (лежит в
# git, как vendor/v86: бандлам Emscripten не нужен; сборка воспроизводима - тот же sha256), OUT=каталог -
# собрать в другое место
set -e
cd "$(dirname "$0")/.."

CACHE=$PWD/.cache
EMSDK=$CACHE/emsdk
EMVER=6.0.13
VIRGL=1.3.0
VIRGL_SUM=065bc56e89e6f631f96101cd62eba0748e48eb888b434edc86e89d05395e76f3
EPOXY=1.5.10
EPOXY_SUM=a7ced37f4102b745ac86d6a70a9da399cc139ff168ba6b8002b4d8d43c900c15
B=$CACHE/virgl-build
P=$B/prefix
OUT=${OUT:-$PWD/vendor/virgl}

# через .tmp и с проверкой суммы: оборванная загрузка не остаётся в кэше «готовым» архивом
fetch() {
  if [ "$(sha256sum "$2" 2>/dev/null | cut -d' ' -f1)" != "$3" ]; then
    curl -fsSL "$1" -o "$2.tmp"
    mv "$2.tmp" "$2"
    [ "$(sha256sum "$2" | cut -d' ' -f1)" = "$3" ] || { echo "$2: не та контрольная сумма" >&2; exit 1; }
  fi
}
mkdir -p $CACHE/virgl-src
fetch https://gitlab.freedesktop.org/virgl/virglrenderer/-/archive/$VIRGL/virglrenderer-$VIRGL.tar.gz \
  $CACHE/virgl-src/virglrenderer-$VIRGL.tar.gz $VIRGL_SUM
fetch https://github.com/anholt/libepoxy/archive/refs/tags/$EPOXY.tar.gz \
  $CACHE/virgl-src/libepoxy-$EPOXY.tar.gz $EPOXY_SUM

if ! "$EMSDK/upstream/emscripten/emcc" --version 2>/dev/null | grep -q " $EMVER "; then
  [ -d "$EMSDK" ] || git clone --depth 1 https://github.com/emscripten-core/emsdk.git "$EMSDK"
  "$EMSDK/emsdk" install $EMVER
  "$EMSDK/emsdk" activate $EMVER
fi
EMSDK_QUIET=1 . "$EMSDK/emsdk_env.sh"

# модуль страницы: сервер vtest (virgl/vtest_web.c), устройство virtio-gpu (virgl/vgpu_web.c) + vrend +
# epoxy -> $OUT/virgl.{js,wasm}
link() {
  S=$B/virglrenderer-$VIRGL
  mkdir -p $OUT
  for f in vtest_web vgpu_web; do
    emcc -O2 $VTW_CFLAGS -Wall -Wextra -Wno-unused-parameter -I$S/src -I$S/vtest -I$B/vrend/src -I$P/include \
      -c virgl/$f.c -o $B/$f.o
  done
  emcc -O2 $VTW_LDFLAGS -o $OUT/virgl.js $B/vtest_web.o $B/vgpu_web.o $B/vrend/vtest/libvtest.a $B/vrend/src/libvirglrenderer.a \
    $P/lib/libepoxy.a \
    -sMODULARIZE=1 -sEXPORT_NAME=createVirgl -sENVIRONMENT=web,worker -sALLOW_MEMORY_GROWTH=1 \
    -sSTACK_SIZE=2MB -sMIN_WEBGL_VERSION=2 -sMAX_WEBGL_VERSION=2 -sGL_ENABLE_GET_PROC_ADDRESS=1 \
    -sFORCE_FILESYSTEM=1 -sEXPORTED_FUNCTIONS=_malloc,_free \
    -sINCOMING_MODULE_JS_API=wasmBinary,preRun,print,printErr,onAbort \
    --pre-js virgl/vgl.js --pre-js virgl/vtest_web.js --pre-js virgl/vgpu_web.js
  ls -l $OUT/virgl.js $OUT/virgl.wasm
}

# again: пересобрать уже распакованное дерево (правки на месте при подготовке патчей)
if [ "$1" = again ]; then
  ninja -C $B/epoxy install > $B/epoxy.log 2>&1 || { tail -20 $B/epoxy.log; exit 1; }
  ninja -C $B/vrend -k 0 > $B/vrend.log 2>&1 || { grep -E "error:|FAILED" $B/vrend.log | head -60; exit 1; }
  link
  exit 0
fi

rm -rf $B
mkdir -p $B
tar -xzf $CACHE/virgl-src/libepoxy-$EPOXY.tar.gz -C $B
tar -xzf $CACHE/virgl-src/virglrenderer-$VIRGL.tar.gz -C $B
for p in patches/virgl/0*-epoxy-*.patch; do patch -d $B/libepoxy-$EPOXY -p1 -s < "$p"; done
for p in patches/virgl/1*-virgl-*.patch; do [ -f "$p" ] && patch -d $B/virglrenderer-$VIRGL -p1 -s < "$p"; done

cat > $B/em.cross <<EOF
[binaries]
c = 'emcc'
cpp = 'em++'
ar = 'emar'
ranlib = 'emranlib'
pkg-config = 'pkg-config'

[built-in options]
c_args = ['-O2']
default_library = 'static'

[properties]
pkg_config_libdir = ['$P/lib/pkgconfig']
needs_exe_wrapper = true

[host_machine]
system = 'emscripten'
cpu_family = 'wasm32'
cpu = 'wasm32'
endian = 'little'
EOF

meson setup $B/epoxy $B/libepoxy-$EPOXY --cross-file $B/em.cross --prefix=$P --libdir=lib \
  --buildtype=release -Dglx=no -Degl=no -Dx11=false -Dtests=false -Ddocs=false > $B/epoxy.log
ninja -C $B/epoxy install >> $B/epoxy.log

meson setup $B/vrend $B/virglrenderer-$VIRGL --cross-file $B/em.cross --prefix=$P --libdir=lib \
  --buildtype=release -Dplatforms=[] -Dcheck-gl-errors=false -Dvenus=false -Dvideo=false \
  -Dtests=false -Dfuzzer=false > $B/vrend.log
ninja -C $B/vrend >> $B/vrend.log 2>&1 || { tail -40 $B/vrend.log; exit 1; }

link
echo "virglrenderer $VIRGL, libepoxy $EPOXY, emcc $EMVER -> $OUT"
