#!/bin/sh
# Xorg без OpenGL (без GLX, glamor, DRI): сервер и драйвер экрана modesetting (KMS)
# собираются тулчейном musl против заголовков и библиотек Alpine x86. Версия - та же, что в Alpine,
# поэтому подходят её библиотеки и драйверы (ввод - xf86-input-evdev). Ядро без консолей (VT) -
# patches/xorg-server-novt.patch. Результат -> packages/xorg (Xorg, модули, libpciaccess, раскладки и
# шрифты; в git не идут)
#   GLAMOR=1 MESA_INST=каталог - с glamor, DRI3 и GLX: 2D сервера и OpenGL программ рисует GPU
#   (virtio-gpu); заголовки и библиотеки Mesa - из её сборки с DRI (scripts/build-mesa.sh API=dri,
#   каталог сборки/inst), libepoxy - из Alpine. OUT=каталог, XORG_BUILD=каталог сборки - чтобы
#   такой вариант не перезаписал пакет
set -e
cd "$(dirname "$0")/.."

VER=21.1.19
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SRC=$CACHE/xorg-server-$VER
B=${XORG_BUILD:-$CACHE/xorg-build}
SR=${XORG_BUILD:+$XORG_BUILD-sysroot}
SR=${SR:-$CACHE/xsysroot}
OUT=${OUT:-$PWD/packages/xorg}
GL_OPTS="-Dglx=false -Dglamor=false -Ddri1=false -Ddri2=false -Ddri3=false"
GL_PKGS=
if [ -n "$GLAMOR" ]; then
  [ -f "$MESA_INST/usr/lib/pkgconfig/gbm.pc" ] || { echo "GLAMOR=1: нужен MESA_INST - inst сборки mesa с API=dri"; exit 1; }
  GL_OPTS="-Dglx=true -Dglamor=true -Ddri1=false -Ddri2=true -Ddri3=true"
  GL_PKGS="libepoxy-dev libxshmfence-dev"
fi

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
python3 - "$SR" $GL_PKGS <<'EOF'
import sys
import alpine
pkgs, provides = alpine.index(tag="xorg-", max_age=7 * 86400)
want = ("xorgproto xtrans pixman-dev libxfont2-dev libxcvt-dev libdrm-dev libpciaccess-dev libmd-dev "
        "libxau-dev libxkbfile-dev xkbcomp-dev").split() + sys.argv[2:]
for n in alpine.resolve(want, pkgs, provides, {"python3", "linux-headers"}) + ["xkeyboard-config", "font-misc-misc"]:
    f = f"{n}-{pkgs[n]['ver']}.apk"
    alpine.extract(alpine.fetch(f"{alpine.MIRROR}/{pkgs[n]['repo']}/x86/{f}", f"{alpine.CACHE}/apk/{f}"), sys.argv[1], [], [])
EOF
# Mesa - своя (без mesa-dev Alpine с LLVM): заголовки, .pc и библиотеки для ссылок
if [ -n "$GLAMOR" ]; then
  cp -a $MESA_INST/usr/include/. $SR/usr/include/
  cp -a $MESA_INST/usr/lib/. $SR/usr/lib/
  [ -d $MESA_INST/usr/share/pkgconfig ] && cp -a $MESA_INST/usr/share/pkgconfig/. $SR/usr/share/pkgconfig/
fi

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
  $GL_OPTS -Dxvmc=false -Ddga=false -Dagp=false \
  -Dudev=false -Dudev_kms=false -Dhal=false -Dsystemd_logind=false -Dsuid_wrapper=false \
  -Dxdmcp=false -Dxdm-auth-1=false -Dsecure-rpc=false -Dlisten_tcp=false -Dxselinux=false \
  -Dpciaccess=true -Dint10=false -Dvgahw=false -Dlinux_acpi=false -Dlinux_apm=false \
  -Dxf86-input-inputtest=false -Dsha1=libmd -Ddefault_font_path=built-ins \
  -Dmodule_dir=/usr/lib/xorg/modules -Dxkb_dir=/usr/share/X11/xkb -Dxkb_output_dir=/var/lib/xkb \
  -Dxkb_bin_dir=/usr/bin -Ddocs=false -Ddevel-docs=false > $B/setup.log 2>&1 || { tail -40 $B/setup.log; exit 1; }
ninja -C $B > $B/build.log 2>&1 || { grep -B2 -A12 'error' $B/build.log | head -60; exit 1; }
DESTDIR=$B/inst meson install -C $B --no-rebuild > $B/install.log 2>&1

rm -rf $OUT/usr/bin/Xorg $OUT/usr/lib $OUT/usr/share/X11/xkb $OUT/usr/share/fonts
mkdir -p $OUT/usr/bin $OUT/usr/lib/xorg
cp $B/inst/usr/bin/Xorg $OUT/usr/bin/Xorg
cp -r $B/inst/usr/lib/xorg/modules $OUT/usr/lib/xorg/modules
rm -f $OUT/usr/lib/xorg/modules/*.la $OUT/usr/lib/xorg/modules/*/*.la
# libpciaccess - своей копией: пакет Alpine тянет базу имён PCI (hwdata-pci, 1.5 МБ); libdrm - пакет
# libdrm (урезанный в get-packages.sh, его берёт и mesa-xlib)
cp -P $SR/usr/lib/libpciaccess.so.0 $SR/usr/lib/libpciaccess.so.0.* $OUT/usr/lib/
# раскладки: из xkeyboard-config (3.3 МБ) только us и ru с переключением CapsLock - 0.8 МБ;
# symbols - всё, что берёт xkbcomp для pc105, us,ru и grp:caps_toggle по правилам evdev
# (клавиатура) и base (виртуальная клавиатура сервера). Проверять с пустым путём поиска
# (xkbcomp -I -I<каталог>): иначе недостающее молча берётся из xkeyboard-config хоста
# (так потерялся kpdl из ru, и раскладка us,ru не загружалась)
X=$SR/usr/share/X11/xkb
K=$OUT/usr/share/X11/xkb
mkdir -p $K/rules $K/geometry $K/symbols
cp -r $X/types $X/compat $X/keycodes $K/
cp $X/rules/evdev $X/rules/base $K/rules/
cp $X/geometry/pc $K/geometry/
for f in altwin capslock ctrl group inet keypad kpdl level3 level5 pc ru shift srvr_ctrl us; do cp $X/symbols/$f $K/symbols/; done
# шрифты: встроенный в сервер fixed - только латиница; из font-misc-misc (4.2 МБ) - fixed (6x13) и
# 9x15 в Юникоде, с кириллицей, обычные и жирные - 0.2 МБ, и 6x13 в ISO8859-1 и ISO8859-5.
# fonts.alias, как везде: fixed - ISO8859-1. Набор шрифтов (fontset: заголовки и меню twm)
# в UTF-8 берёт только кодировку того, на что указывает fixed, и с fixed на Юникоде рисовал
# латиницу квадратами; xterm в UTF-8 сам находит Юникод-версию того же шрифта.
# fonts.dir - по свойству FONT из самих файлов
F=$OUT/usr/share/fonts/misc
mkdir -p $F
for f in 6x13 6x13B 9x15 9x15B 6x13-ISO8859-1 6x13B-ISO8859-1 6x13-ISO8859-5 6x13B-ISO8859-5; do
  cp $SR/usr/share/fonts/misc/$f.pcf.gz $F/
done
python3 - $F <<'EOF'
import gzip
import os
import struct
import sys

d = sys.argv[1]


def xlfd(path):
    b = gzip.open(path).read()
    n = struct.unpack_from("<i", b, 4)[0]
    for i in range(n):
        typ, fmt, size, off = struct.unpack_from("<4i", b, 8 + 16 * i)
        if typ != 1:  # PCF_PROPERTIES
            continue
        e = ">" if struct.unpack_from("<i", b, off)[0] & 4 else "<"
        nprops = struct.unpack_from(e + "i", b, off + 4)[0]
        props = [struct.unpack_from(e + "ibi", b, off + 8 + 9 * j) for j in range(nprops)]
        strings = off + 8 + 9 * nprops + (4 - nprops % 4) % 4 + 4
        name = lambda o: b[strings + o:b.index(b"\0", strings + o)].decode()
        return next(name(v) for k, isstr, v in props if isstr and name(k) == "FONT")


names = {f: xlfd(os.path.join(d, f)) for f in sorted(os.listdir(d)) if f.endswith(".pcf.gz")}
with open(os.path.join(d, "fonts.dir"), "w") as out:
    out.write("%d\n" % len(names) + "".join("%s %s\n" % kv for kv in names.items()))
fixed = names["6x13-ISO8859-1.pcf.gz"]
with open(os.path.join(d, "fonts.alias"), "w") as out:
    out.write("fixed %s\nvariable %s\n6x13 %s\n9x15 %s\n" % (fixed, fixed, fixed, names["9x15.pcf.gz"]))
print(open(os.path.join(d, "fonts.dir")).read())
EOF
echo "Xorg -> $OUT ($(du -sh $OUT/usr | cut -f1))"
find $OUT/usr -type f | sed "s|$OUT/||" | sort
