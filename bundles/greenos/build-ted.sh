#!/bin/sh
# Ted 2.23 для GreenOS - текстовый процессор RTF, как WordPad: шрифты Xft, таблицы, колонтитулы, сноски,
# печать в PostScript/PDF. Окна - Motif (пакет Alpine), а не GTK: GTK тянул бы десятки мегабайт.
# Исходник - официальное зеркало автора (ftp.nluug.nl/pub/editors/ted, сумма ниже), GPL. Тулчейн musl на
# sysroot от build.sh (сначала он) + заголовки motif, pcre, libpaper и картинок. Данные Ted (метрики
# шрифтов, справка, настройки) - его TedDatadir.tar без английского словаря проверки орфографии (4.4 МБ).
# Результат -> bundles/greenos/root
set -e
cd "$(dirname "$0")/../.."

V=2.23
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SR=$CACHE/greenos-sysroot
B=$CACHE/greenos-build
OUT=$PWD/bundles/greenos/root

[ -d $SR/usr/include/X11/Xft ] || { echo "нет $SR - сначала bundles/greenos/build.sh"; exit 1; }
f=ted-$V.src.tar.gz
[ -f $CACHE/$f ] || curl -fsSL https://ftp.nluug.nl/pub/editors/ted/$f -o $CACHE/$f.tmp
[ -f $CACHE/$f ] || mv $CACHE/$f.tmp $CACHE/$f
[ "$(sha256sum $CACHE/$f | cut -d' ' -f1)" = 3fa992c2bc96af3ca788ef941cb5314f4a1d843202efd0201b8b4ee9adbf316c ] ||
  { echo "$f: не та контрольная сумма" >&2; exit 1; }
S=$B/Ted-$V
rm -rf $S
mkdir -p $B $OUT/usr/bin $OUT/usr/share/Ted
tar -xzf $CACHE/$f -C $B

python3 - "$SR" <<'EOF'
import sys
import alpine
pkgs, provides = alpine.index(tag="xorg-", max_age=7 * 86400)
want = ["motif-dev", "pcre-dev", "libpaper-dev", "tiff-dev", "libxpm-dev", "libjpeg-turbo-dev", "libpng-dev", "zlib-dev"]
for n in alpine.resolve(want, pkgs, provides, {"python3", "linux-headers"}):
    f = f"{n}-{pkgs[n]['ver']}.apk"
    alpine.extract(alpine.fetch(f"{alpine.MIRROR}/{pkgs[n]['repo']}/x86/{f}", f"{alpine.CACHE}/apk/{f}"), sys.argv[1], [], [])
EOF

# configure у Ted ищет библиотеки через pkg-config, а не нашёл - в /usr/include и /usr/lib64 хоста.
# Под именами, которые он спрашивает: libtiff (у Alpine - libtiff-4) и libpaper (без .pc); Motif - его
# переменными ac_xm_*
mkdir -p $B/pc
printf 'Name: libtiff\nDescription: libtiff-4\nVersion: 4\nRequires: libtiff-4\n' > $B/pc/libtiff.pc
printf 'Name: libpaper\nDescription: libpaper\nVersion: 1\nCflags: -I/usr/include\nLibs: -L/usr/lib -lpaper\n' > $B/pc/libpaper.pc
export ac_xm_includes=$SR/usr/include ac_xm_libraries=$SR/usr/lib
export PATH=$TC/bin:$PATH
export CC="i686-linux-musl-gcc -march=pentium4 -mtune=generic" CFLAGS="-Os -w"
export CPPFLAGS="-I$SR/usr/include -I$SR/usr/include/freetype2"
export LDFLAGS="-s -L$SR/usr/lib -Wl,-rpath-link,$SR/usr/lib:$SR/lib -Wl,--as-needed"
export PKG_CONFIG_LIBDIR=$B/pc:$SR/usr/lib/pkgconfig:$SR/usr/share/pkgconfig PKG_CONFIG_SYSROOT_DIR=$SR
make -C $S -s compile.shared \
  CONFIGURE_OPTIONS="--with-MOTIF --prefix=/usr --host=i686-linux-musl --x-includes=$SR/usr/include --x-libraries=$SR/usr/lib"
cp $S/Ted/Ted $OUT/usr/bin/Ted
tar -xf $S/tedPackage/TedDatadir.tar -C $OUT/usr/share/Ted --exclude 'dfa/*'
echo "Ted $(du -h $OUT/usr/bin/Ted | cut -f1): $($TC/bin/i686-linux-musl-readelf -d $OUT/usr/bin/Ted | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' ')"
