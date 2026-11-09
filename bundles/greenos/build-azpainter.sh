#!/bin/sh
# AzPainter 3 для GreenOS - рисовалка (слои, кисти, фильтры) на своём тулките поверх Xlib, без GTK и Qt.
# Официальный репозиторий автора - gitlab.com/azelpg/azpainter (на GitHub только чужие копии), тег и
# сумма архива - ниже. Тулчейн musl на sysroot от build.sh (сначала он) + заголовки Xcursor, Xi, tiff,
# webp. configure.c собирается и запускается на хосте: он только пишет build.ninja (флаги - из
# pkg-config sysroot), NASM в этой версии выключен - для i686 годится чистый C.
# Результат -> bundles/greenos/root (/usr/bin/azpainter, /usr/share/azpainter3, значок)
set -e
cd "$(dirname "$0")/../.."

V=3.0.12.3
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SR=$CACHE/greenos-sysroot
B=$CACHE/greenos-build
OUT=$PWD/bundles/greenos/root

[ -d $SR/usr/include/X11/Xft ] || { echo "нет $SR - сначала bundles/greenos/build.sh"; exit 1; }
f=azpainter-$V.tar.gz
[ -f $CACHE/$f ] || curl -fsSL https://gitlab.com/azelpg/azpainter/-/archive/$V/$f -o $CACHE/$f.tmp
[ -f $CACHE/$f ] || mv $CACHE/$f.tmp $CACHE/$f
[ "$(sha256sum $CACHE/$f | cut -d' ' -f1)" = 09ba8f56ee04be57b88e8b05a96b3e8c0b630ca35f14c4cc6bffabbe424f1d85 ] ||
  { echo "$f: не та контрольная сумма" >&2; exit 1; }
S=$B/azpainter-$V
rm -rf $S $B/azpainter-root
mkdir -p $B
tar -xzf $CACHE/$f -C $B

python3 - "$SR" <<'EOF'
import sys
import alpine
pkgs, provides = alpine.index(tag="xorg-", max_age=7 * 86400)
for n in alpine.resolve("libxcursor-dev libxi-dev tiff-dev libwebp-dev".split(), pkgs, provides, {"python3", "linux-headers"}):
    f = f"{n}-{pkgs[n]['ver']}.apk"
    alpine.extract(alpine.fetch(f"{alpine.MIRROR}/{pkgs[n]['repo']}/x86/{f}", f"{alpine.CACHE}/apk/{f}"), sys.argv[1], [], [])
EOF

export PKG_CONFIG_LIBDIR=$SR/usr/lib/pkgconfig:$SR/usr/share/pkgconfig PKG_CONFIG_SYSROOT_DIR=$SR
(cd $S && ./configure --prefix=/usr \
  CC="$TC/bin/i686-linux-musl-gcc -march=pentium4 -mtune=generic" \
  CFLAGS="-Os -DNDEBUG -I$SR/usr/include -I$SR/usr/include/freetype2" \
  LDFLAGS="-s -L$SR/usr/lib -Wl,-rpath-link,$SR/usr/lib:$SR/lib -Wl,--as-needed")
ninja -C $S/build
(cd $S/build && DESTDIR=$B/azpainter-root sh install.sh install > /dev/null)
D=$B/azpainter-root/usr
mkdir -p $OUT/usr/bin $OUT/usr/share/pixmaps
cp $D/bin/azpainter $OUT/usr/bin/
rm -rf $OUT/usr/share/azpainter3
cp -r $D/share/azpainter3 $OUT/usr/share/
cp $D/share/icons/hicolor/48x48/apps/azpainter.png $OUT/usr/share/pixmaps/
echo "azpainter $(du -h $OUT/usr/bin/azpainter | cut -f1), данные $(du -sh $OUT/usr/share/azpainter3 | cut -f1): $($TC/bin/i686-linux-musl-readelf -d $OUT/usr/bin/azpainter | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' ')"
