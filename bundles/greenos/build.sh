#!/bin/sh
# JWM и greenos-about для GreenOS: тулчейн musl против заголовков и библиотек Alpine x86, как dwm
# (scripts/build-dwm.sh). Это данные бандла (bundles/greenos/greenos.txt, --file), не пакеты
# репозитория; результат - дерево bundles/greenos/root (в git не идёт). Программы FOX - build-fox.sh.
# JWM 2.4 сглаживает шрифты только через Pango (а с ним glib, harfbuzz, cairo - мегабайты), без него -
# растровые шрифты X без кириллицы; jwm-xft.patch возвращает прямой Xft, как было в JWM 2.3.
# jwm-utf8-names.patch - русские заголовки окон: без NLS JWM не звал setlocale и не раскодировал
# WM_NAME в COMPOUND_TEXT (так его ставят xterm и все программы Xt). Ещё у
# JWM из Alpine cairo и librsvg (значки SVG) - здесь без них: Xft, Xrender, PNG и XPM (значки), Shape
# (окна непрямоугольной формы - xeyes), Xinerama; без Xmu (он - только ради скруглённых углов окон) и NLS.
set -e
cd "$(dirname "$0")/../.."

JWM=2.4.6
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SR=$CACHE/greenos-sysroot
B=$CACHE/greenos-build
OUT=$PWD/bundles/greenos/root

[ -x $TC/bin/i686-linux-musl-gcc ] || { echo "нет тулчейна, сначала scripts/build-busybox.sh"; exit 1; }
f=jwm-$JWM.tar.xz
[ -f $CACHE/$f ] || curl -fsSL https://github.com/joewing/jwm/releases/download/v$JWM/$f -o $CACHE/$f.tmp
[ -f $CACHE/$f ] || mv $CACHE/$f.tmp $CACHE/$f
[ "$(sha256sum $CACHE/$f | cut -d' ' -f1)" = b5871ec28317594b3fa22b83ed5524cc911d498c455eaab3ae68def195dd802d ] ||
  { echo "$f: не та контрольная сумма" >&2; exit 1; }
rm -rf $B/jwm-$JWM
mkdir -p $B $OUT/usr/bin
tar -xJf $CACHE/$f -C $B
patch -d $B/jwm-$JWM -p1 -s < bundles/greenos/jwm-xft.patch
patch -d $B/jwm-$JWM -p1 -s < bundles/greenos/jwm-utf8-names.patch

# заголовки и .pc из Alpine (и для build-fox.sh); индекс - свой и свежий, как у scripts/build-xorg.sh
rm -rf $SR
python3 - "$SR" <<'EOF'
import sys
import alpine
pkgs, provides = alpine.index(tag="xorg-", max_age=7 * 86400)
want = """libx11-dev libxext-dev libxft-dev libxrender-dev libxpm-dev libxmu-dev libxinerama-dev libxrandr-dev
libpng-dev libjpeg-turbo-dev zlib-dev fontconfig-dev freetype-dev""".split()
for n in alpine.resolve(want, pkgs, provides, {"python3", "linux-headers"}):
    f = f"{n}-{pkgs[n]['ver']}.apk"
    alpine.extract(alpine.fetch(f"{alpine.MIRROR}/{pkgs[n]['repo']}/x86/{f}", f"{alpine.CACHE}/apk/{f}"), sys.argv[1], [], [])
EOF

export PKG_CONFIG_LIBDIR=$SR/usr/lib/pkgconfig:$SR/usr/share/pkgconfig PKG_CONFIG_SYSROOT_DIR=$SR
CC="$TC/bin/i686-linux-musl-gcc -march=pentium4 -mtune=generic"
CPPFLAGS="-I$SR/usr/include -I$SR/usr/include/freetype2 -I$SR/usr/include/libpng16"
LDFLAGS="-s -L$SR/usr/lib -Wl,-rpath-link,$SR/usr/lib:$SR/lib -Wl,--as-needed"

S=$B/jwm-$JWM
(cd $S && ./configure -q --host=i686-linux-musl --prefix=/usr --sysconfdir=/etc \
  CC="$CC" CFLAGS=-Os CPPFLAGS="$CPPFLAGS" LDFLAGS="$LDFLAGS" \
  --disable-nls --disable-cairo --disable-rsvg --disable-pango --disable-jpeg --disable-xbm --disable-xmu \
  --enable-xft --enable-xrender --enable-png --enable-xpm --enable-shape --enable-xinerama)
make -C $S/src -s
cp $S/src/jwm $OUT/usr/bin/jwm

$CC -Os -Wall -Wno-format-truncation $CPPFLAGS -o $OUT/usr/bin/greenos-about bundles/greenos/greenos-about.c \
  $LDFLAGS -lXft -lXrender -lX11 -lpng16

# конфиги - без комментариев и отступов (в машине всё в памяти); исходники с пояснениями - conf/
mkdir -p $OUT/etc $OUT/root
python3 bundles/greenos/minify.py xml bundles/greenos/conf/system.jwmrc $OUT/etc/system.jwmrc
python3 bundles/greenos/minify.py xres bundles/greenos/conf/Xdefaults $OUT/root/.Xdefaults

for f in $OUT/usr/bin/jwm $OUT/usr/bin/greenos-about; do
  echo "${f#$PWD/} $(du -h $f | cut -f1): $($TC/bin/i686-linux-musl-readelf -d $f | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' ')"
done
