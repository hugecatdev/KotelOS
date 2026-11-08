#!/bin/sh
# Программы FOX для GreenOS: PathFinder (файлы), Adie (редактор с подсветкой), Calculator, ShutterBug
# (снимок экрана), ControlPanel (цвета и шрифт всех программ FOX; тема - /etc/foxrc/Desktop). fox из
# Alpine собран с OpenGL и тянет mesa-xlib (libGL 17 МБ) - здесь FOX 1.6 без OpenGL, тулчейном musl на
# sysroot от build.sh (сначала он); libstdc++ - пакет Alpine. reswrap (картинки -> C) исполняется при
# сборке - он для хоста. Родные значки программ (GIF из исходников) -> PNG для меню JWM.
# Результат -> bundles/greenos/root (в git не идёт), как у build.sh.
set -e
cd "$(dirname "$0")/../.."

FOX=1.6.59
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SR=$CACHE/greenos-sysroot
B=$CACHE/greenos-build
OUT=$PWD/bundles/greenos/root

[ -d $SR/usr/include/X11/Xft ] || { echo "нет $SR - сначала bundles/greenos/build.sh"; exit 1; }
f=fox-$FOX.tar.gz
# только http; сумма - та же, что у sha512 в APKBUILD fox Alpine
[ -f $CACHE/$f ] || curl -fsSL http://fox-toolkit.org/ftp/$f -o $CACHE/$f.tmp
[ -f $CACHE/$f ] || mv $CACHE/$f.tmp $CACHE/$f
[ "$(sha256sum $CACHE/$f | cut -d' ' -f1)" = 48f33d2dd5371c2d48f6518297f0ef5bbf3fcd37719e99f815dc6fc6e0f928ae ] ||
  { echo "$f: не та контрольная сумма" >&2; exit 1; }
F=$B/fox-$FOX
rm -rf $F
mkdir -p $B $OUT/usr/bin $OUT/usr/lib $OUT/usr/share/greenos/icons/fox
tar -xzf $CACHE/$f -C $B
g++ -O2 -o $B/reswrap $F/utils/reswrap.cpp

export PATH=$TC/bin:$PATH
export PKG_CONFIG_LIBDIR=$SR/usr/lib/pkgconfig:$SR/usr/share/pkgconfig PKG_CONFIG_SYSROOT_DIR=$SR
(cd $F && ./configure -q --host=i686-linux-musl --prefix=/usr --enable-shared --disable-static \
  CC="i686-linux-musl-gcc -march=pentium4 -mtune=generic" CXX="i686-linux-musl-g++ -march=pentium4 -mtune=generic" \
  CFLAGS=-Os CXXFLAGS="-Os -DNDEBUG" CPPFLAGS="-I$SR/usr/include -I$SR/usr/include/freetype2" \
  LDFLAGS="-L$SR/usr/lib -Wl,-rpath-link,$SR/usr/lib:$SR/lib -Wl,--as-needed" \
  --x-includes=$SR/usr/include --x-libraries=$SR/usr/lib \
  --with-opengl=no --with-xft=yes --enable-png --enable-jpeg --enable-zlib --disable-tiff --disable-bz2lib \
  --with-xshm=yes --with-shape=yes --with-xrender=yes --with-xrandr=yes \
  --with-xcursor=no --with-xfixes=no --with-xinput=no --with-xim=no)
# configure FOX вписывает заголовки freetype хоста
find $F -name Makefile -exec sed -i "s|-I/usr/include/freetype2|-I$SR/usr/include/freetype2|g" {} +
for d in src adie pathfinder calculator shutterbug; do
  make -C $F/$d -s -j"$(nproc)" RESWRAP=$B/reswrap
done
make -C $F/tests -s RESWRAP=$B/reswrap ControlPanel

cp -P $F/src/.libs/libFOX-1.6.so* $OUT/usr/lib/
for p in adie/adie pathfinder/PathFinder calculator/calculator shutterbug/shutterbug tests/ControlPanel; do
  if [ -f $F/${p%/*}/.libs/${p#*/} ]; then cp $F/${p%/*}/.libs/${p#*/} $OUT/usr/bin/; else cp $F/$p $OUT/usr/bin/; fi
done
i686-linux-musl-strip $OUT/usr/bin/adie $OUT/usr/bin/PathFinder $OUT/usr/bin/calculator $OUT/usr/bin/shutterbug \
  $OUT/usr/bin/ControlPanel $OUT/usr/lib/libFOX-1.6.so.*.*

python3 - "$F" "$OUT/usr/share/greenos/icons/fox" <<'EOF'
import sys
from PIL import Image
src, out = sys.argv[1:]
for name, gif in (("adie", "adie/big_gif.gif"), ("calculator", "calculator/bigcalc.gif"),
                  ("pathfinder", "pathfinder/foxbig.gif"), ("shutterbug", "shutterbug/shutterbug.gif")):
    Image.open(f"{src}/{gif}").convert("RGBA").save(f"{out}/{name}.png")
EOF

cd $OUT
for f in usr/bin/adie usr/bin/PathFinder usr/bin/calculator usr/bin/shutterbug usr/bin/ControlPanel usr/lib/libFOX-1.6.so.*.*; do
  echo "$f $(du -h $f | cut -f1): $(i686-linux-musl-readelf -d $f | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' ')"
done
