#!/bin/sh
# OpenGL без LLVM: mesa с GLX через Xlib (рисует картинкой через обычный X, расширение GLX серверу не
# нужно) и программным softpipe - libGL.so.1 для Qt5 и простых OpenGL-программ. mesa из Alpine
# тянет LLVM (llvmpipe) - вместе ~480 МБ. Версия - та же, что в Alpine. Собирается тулчейном musl
# против заголовков Alpine x86 -> packages/mesa-xlib (в git не идёт)
#   GALLIUM=softpipe,virgl - ещё драйвер virgl: GALLIUM_DRIVER=virpipe рисует через VirGL по
#   протоколу vtest (сокет VTEST_SOCKET_NAME); libGL тогда требует libdrm.so.2
#   OUT=каталог, MESA_BUILD=каталог сборки - чтобы такой вариант не перезаписал пакет
set -e
cd "$(dirname "$0")/.."

VER=25.1.9
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SRC=$CACHE/mesa-$VER
SR=$CACHE/msysroot
B=${MESA_BUILD:-$CACHE/mesa-build}
OUT=${OUT:-$PWD/packages/mesa-xlib}
GALLIUM=${GALLIUM:-softpipe}
EXTRA=
case ,$GALLIUM, in *,virgl,*) EXTRA=libdrm-dev ;; esac

[ -x $TC/bin/i686-linux-musl-gcc ] || { echo "нет тулчейна, сначала scripts/build-busybox.sh"; exit 1; }
python3 -c "import mako, yaml" 2>/dev/null || { echo "нужны python3 mako и yaml (генераторы mesa)"; exit 1; }
# через .tmp и с проверкой суммы: оборванная загрузка не остаётся в кэше «готовым» архивом,
# а битый архив качается заново (sha512 сверен с APKBUILD mesa в Alpine 3.22)
TAR=$CACHE/mesa-$VER.tar.xz
SUM=412df33a1bb3c785ed698555a3972118a37c458e7accf6ae53f4bb87b3db454a
if [ "$(sha256sum $TAR 2>/dev/null | cut -d' ' -f1)" != $SUM ]; then
  curl -fsSL https://archive.mesa3d.org/mesa-$VER.tar.xz -o $TAR.tmp
  mv $TAR.tmp $TAR
  [ "$(sha256sum $TAR | cut -d' ' -f1)" = $SUM ] || { echo "mesa-$VER.tar.xz: не та контрольная сумма" >&2; exit 1; }
fi
rm -rf $SRC
tar -xJf $TAR -C $CACHE
# virgl (virpipe) под xlib GLX: показ кадра без контекста
patch -d $SRC -p1 -s < patches/mesa-virgl-xlib-swap.patch

rm -rf $SR
python3 - "$SR" $EXTRA <<'EOF'
import sys
import alpine
pkgs, provides = alpine.index(tag="xorg-", max_age=7 * 86400)
want = "xorgproto libx11-dev libxext-dev libxcb-dev libxshmfence-dev libxfixes-dev libxrandr-dev libxxf86vm-dev zlib-dev".split()
want += sys.argv[2:]
for n in alpine.resolve(want, pkgs, provides, {"python3", "linux-headers"}):
    f = f"{n}-{pkgs[n]['ver']}.apk"
    alpine.extract(alpine.fetch(f"{alpine.MIRROR}/{pkgs[n]['repo']}/x86/{f}", f"{alpine.CACHE}/apk/{f}"), sys.argv[1], [], [])
EOF

rm -rf $B
mkdir -p $B
cat > $B.cross <<EOF
[binaries]
c = '$TC/bin/i686-linux-musl-gcc'
cpp = '$TC/bin/i686-linux-musl-g++'
ar = '$TC/bin/i686-linux-musl-ar'
strip = '$TC/bin/i686-linux-musl-strip'
pkg-config = 'pkg-config'

[built-in options]
c_args = ['-I$SR/usr/include', '-march=pentium4', '-mtune=generic']
cpp_args = ['-I$SR/usr/include', '-march=pentium4', '-mtune=generic']
c_link_args = ['-L$SR/usr/lib', '-Wl,-rpath-link,$SR/usr/lib:$SR/lib', '-Wl,--build-id=sha1']
cpp_link_args = ['-L$SR/usr/lib', '-Wl,-rpath-link,$SR/usr/lib:$SR/lib', '-Wl,--build-id=sha1']

[properties]
pkg_config_libdir = ['$SR/usr/lib/pkgconfig', '$SR/usr/share/pkgconfig']
sys_root = '$SR'

[host_machine]
system = 'linux'
cpu_family = 'x86'
cpu = 'i686'
endian = 'little'
EOF

meson setup $B $SRC --cross-file $B.cross --prefix=/usr --buildtype=release -Dstrip=true -Db_ndebug=true \
  -Dplatforms=x11 -Dgallium-drivers=$GALLIUM -Dvulkan-drivers= -Dglx=xlib -Degl=disabled -Dgbm=disabled \
  -Dgles1=disabled -Dgles2=disabled -Dglvnd=disabled -Dllvm=disabled -Dshared-llvm=disabled -Ddraw-use-llvm=false \
  -Dxlib-lease=disabled -Dvalgrind=disabled -Dlibunwind=disabled -Dlmsensors=disabled -Dzstd=disabled -Dxmlconfig=disabled \
  -Dshader-cache=disabled -Dvideo-codecs= -Dgallium-va=disabled -Dgallium-vdpau=disabled \
  -Dgallium-d3d12-video=disabled -Dmicrosoft-clc=disabled -Dbuild-tests=false -Dosmesa=false \
  > $B/setup.log 2>&1 || { tail -40 $B/setup.log; exit 1; }
ninja -C $B > $B/build.log 2>&1 || { grep -B2 -A12 'error' $B/build.log | head -60; exit 1; }
DESTDIR=$B/inst meson install -C $B --no-rebuild > $B/install.log 2>&1

rm -rf $OUT/usr
mkdir -p $OUT/usr/lib
cp -P $B/inst/usr/lib/lib*.so.* $OUT/usr/lib/
echo "mesa-xlib -> $OUT ($(du -sh $OUT/usr | cut -f1))"
find $OUT/usr | sed "s|$OUT/||" | sort
