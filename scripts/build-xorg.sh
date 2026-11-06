#!/bin/sh
# Xorg без OpenGL (без GLX, glamor, DRI): сервер и драйвер экрана modesetting (KMS, /dev/dri/card0)
# собираются тулчейном musl против заголовков и библиотек Alpine x86. Версия - та же, что в Alpine,
# поэтому подходят её библиотеки и драйверы (ввод - xf86-input-evdev). Ядро без консолей (VT) -
# patches/xorg-server-novt.patch. Результат -> packages/xorg (Xorg, модули, libpciaccess и раскладки;
# в git не идут)
set -e
cd "$(dirname "$0")/.."

VER=21.1.19
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SRC=$CACHE/xorg-server-$VER
SR=$CACHE/xsysroot
B=$CACHE/xorg-build
OUT=$PWD/packages/xorg

[ -x $TC/bin/i686-linux-musl-gcc ] || { echo "нет тулчейна, сначала scripts/build-busybox.sh"; exit 1; }
[ -f $CACHE/xorg-server-$VER.tar.xz ] || curl -fsSL https://www.x.org/releases/individual/xserver/xorg-server-$VER.tar.xz -o $CACHE/xorg-server-$VER.tar.xz
rm -rf $SRC
tar -xJf $CACHE/xorg-server-$VER.tar.xz -C $CACHE
patch -d $SRC -p1 -s < patches/xorg-server-novt.patch
# в архив 21.1.19 не попал test/bugs/meson.build (Alpine доносит его патчем); тест там только
# для Xvfb+Xephyr+glamor, которых нет, - хватает пустого
mkdir -p $SRC/test/bugs
: > $SRC/test/bugs/meson.build

# заголовки и .pc зависимостей сервера (python3 нужен только для генерации xcb-proto); индекс -
# свой и свежий: старые версии с зеркала пропадают, а общий индекс трогать незачем
rm -rf $SR
python3 - "$SR" <<'EOF'
import sys
import alpine
pkgs, provides = alpine.index(tag="xorg-", max_age=7 * 86400)
want = ("xorgproto xtrans pixman-dev libxfont2-dev libxcvt-dev libdrm-dev libpciaccess-dev libmd-dev "
        "libxau-dev libxkbfile-dev xkbcomp-dev").split()
for n in alpine.resolve(want, pkgs, provides, {"python3", "linux-headers"}) + ["xkeyboard-config"]:
    f = f"{n}-{pkgs[n]['ver']}.apk"
    alpine.extract(alpine.fetch(f"{alpine.MIRROR}/{pkgs[n]['repo']}/x86/{f}", f"{alpine.CACHE}/apk/{f}"), sys.argv[1], [], [])
EOF

rm -rf $B
mkdir -p $B
cat > $B.cross <<EOF
[binaries]
c = '$TC/bin/i686-linux-musl-gcc'
ar = '$TC/bin/i686-linux-musl-ar'
strip = '$TC/bin/i686-linux-musl-strip'
pkg-config = 'pkg-config'

[built-in options]
c_args = ['-I$SR/usr/include', '-march=pentium4', '-mtune=generic', '-Wno-error=array-bounds']
c_link_args = ['-L$SR/usr/lib', '-Wl,-rpath-link,$SR/usr/lib:$SR/lib', '-Wl,-z,lazy']

[properties]
pkg_config_libdir = ['$SR/usr/lib/pkgconfig', '$SR/usr/share/pkgconfig']
sys_root = '$SR'

[host_machine]
system = 'linux'
cpu_family = 'x86'
cpu = 'i686'
endian = 'little'
EOF

meson setup $B $SRC --cross-file $B.cross --prefix=/usr --buildtype=release -Dstrip=true \
  -Dxorg=true -Dxvfb=false -Dxnest=false -Dxephyr=false -Dxwin=false -Dxquartz=false \
  -Dglx=false -Dglamor=false -Ddri1=false -Ddri2=false -Ddri3=false -Dxvmc=false -Ddga=false -Dagp=false \
  -Dudev=false -Dudev_kms=false -Dhal=false -Dsystemd_logind=false -Dsuid_wrapper=false \
  -Dxdmcp=false -Dxdm-auth-1=false -Dsecure-rpc=false -Dlisten_tcp=false -Dxselinux=false \
  -Dpciaccess=true -Dint10=false -Dvgahw=false -Dlinux_acpi=false -Dlinux_apm=false \
  -Dxf86-input-inputtest=false -Dsha1=libmd -Ddefault_font_path=built-ins \
  -Dmodule_dir=/usr/lib/xorg/modules -Dxkb_dir=/usr/share/X11/xkb -Dxkb_output_dir=/var/lib/xkb \
  -Dxkb_bin_dir=/usr/bin -Ddocs=false -Ddevel-docs=false > $B/setup.log 2>&1 || { tail -40 $B/setup.log; exit 1; }
ninja -C $B > $B/build.log 2>&1 || { grep -B2 -A12 'error' $B/build.log | head -60; exit 1; }
DESTDIR=$B/inst meson install -C $B --no-rebuild > $B/install.log 2>&1

rm -rf $OUT/usr/bin/Xorg $OUT/usr/lib $OUT/usr/share/X11/xkb
mkdir -p $OUT/usr/bin $OUT/usr/lib/xorg
cp $B/inst/usr/bin/Xorg $OUT/usr/bin/Xorg
cp -r $B/inst/usr/lib/xorg/modules $OUT/usr/lib/xorg/modules
rm -f $OUT/usr/lib/xorg/modules/*.la $OUT/usr/lib/xorg/modules/*/*.la
# libpciaccess и libdrm - своими копиями: пакет Alpine libpciaccess тянет базу имён PCI
# (hwdata-pci, 1.5 МБ), а libdrm - ещё библиотеки чужих видеокарт и тот же libpciaccess
cp -P $SR/usr/lib/libpciaccess.so.0 $SR/usr/lib/libpciaccess.so.0.* $SR/usr/lib/libdrm.so.2 $SR/usr/lib/libdrm.so.2.* $OUT/usr/lib/
# раскладки: из xkeyboard-config (3.3 МБ) только us и ru с переключением Alt+Shift - 0.8 МБ;
# symbols - всё, что берёт xkbcomp для pc105, us,ru и grp:alt_shift_toggle по правилам evdev
# (клавиатура) и base (виртуальная клавиатура сервера)
X=$SR/usr/share/X11/xkb
K=$OUT/usr/share/X11/xkb
mkdir -p $K/rules $K/geometry $K/symbols
cp -r $X/types $X/compat $X/keycodes $K/
cp $X/rules/evdev $X/rules/base $K/rules/
cp $X/geometry/pc $K/geometry/
for f in altwin capslock ctrl group inet keypad level3 level5 pc ru shift srvr_ctrl us; do cp $X/symbols/$f $K/symbols/; done
echo "Xorg -> $OUT ($(du -sh $OUT/usr | cut -f1))"
find $OUT/usr -type f | sed "s|$OUT/||" | sort
