#!/bin/sh
# xosview для GreenOS - системный монитор полосами (загрузка, CPU, память, сеть) на чистом Xlib;
# github.com/hills/xosview по коммиту, сумма - ниже. Тулчейн musl на sysroot от build.sh (сначала он).
# Цвета и набор полос - X-ресурсы xosview в conf/Xdefaults. Результат -> bundles/greenos/root/usr/bin
set -e
cd "$(dirname "$0")/../.."

C=22506a79f0c706ed7b3a0d9546b8b799c127be42
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SR=$CACHE/greenos-sysroot
B=$CACHE/greenos-build
OUT=$PWD/bundles/greenos/root

[ -f $SR/usr/include/X11/xpm.h ] || { echo "нет $SR - сначала bundles/greenos/build.sh"; exit 1; }
f=xosview-$(echo $C | cut -c1-7).tar.gz
[ -f $CACHE/$f ] || curl -fsSL https://codeload.github.com/hills/xosview/tar.gz/$C -o $CACHE/$f.tmp
[ -f $CACHE/$f ] || mv $CACHE/$f.tmp $CACHE/$f
[ "$(sha256sum $CACHE/$f | cut -d' ' -f1)" = 82048eab8441057dcf520e321a207eeed195ae97d3a210af0fcda9327ed1259f ] ||
  { echo "$f: не та контрольная сумма" >&2; exit 1; }
S=$B/xosview-$C
rm -rf $S
mkdir -p $B $OUT/usr/bin $OUT/usr/share/pixmaps
tar -xzf $CACHE/$f -C $B

# CPPFLAGS и LDFLAGS - окружением: Makefile их дополняет (+=), а из командной строки они бы заменили его -I
CPPFLAGS="-I$SR/usr/include" LDFLAGS="-s -L$SR/usr/lib -Wl,-rpath-link,$SR/usr/lib:$SR/lib -Wl,--as-needed" \
  make -C $S -s -j"$(nproc)" PLATFORM=linux ARCH=i686 \
  CXX="$TC/bin/i686-linux-musl-g++ -march=pentium4 -mtune=generic" OPTFLAGS="-Os -w"
cp $S/xosview $OUT/usr/bin/
cp $S/xosview.png $OUT/usr/share/pixmaps/
echo "xosview $(du -h $OUT/usr/bin/xosview | cut -f1): $($TC/bin/i686-linux-musl-readelf -d $OUT/usr/bin/xosview | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' ')"
