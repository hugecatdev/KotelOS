#!/bin/sh
# Этап 0 без v86: треугольник нативного клиента Mesa (virpipe) через virglrenderer в wasm
# в headless Chromium. Нужны собранный build/virgl (scripts/build-virgl.sh), cc, EGL/GLES хоста.
#   virgl/harness/run-tri.sh [--debug]
set -e
cd "$(dirname "$0")/../.."
T=$(mktemp -d)
trap 'kill $BRIDGE 2>/dev/null; wait $BRIDGE 2>/dev/null; rm -rf $T' EXIT

cc -O2 -o $T/tri virgl/harness/tri.c -lEGL -lGLESv2
python3 virgl/harness/bridge.py --sock $T/vt.sock --port ${PORT:-8790} --chrome "$@" > $T/bridge.log 2>&1 &
BRIDGE=$!
i=0
until grep -q "WebGL:" $T/bridge.log; do
  i=$((i + 1))
  [ $i -lt 120 ] || { cat $T/bridge.log; echo "страница не поднялась"; exit 1; }
  sleep 0.5
done

# Mesa: EGL от Mesa, а не от другого поставщика glvnd; программный драйвер - virpipe
ok=0
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json \
VTEST_SOCKET_NAME=$T/vt.sock LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=virpipe \
  timeout ${TIMEOUT:-30} $T/tri $T/tri.ppm || ok=$?
sleep 0.5
echo "--- страница"
cat $T/bridge.log
[ -f $T/tri.ppm ] && cp $T/tri.ppm build/virgl/tri.ppm
exit $ok
