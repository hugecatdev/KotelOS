#!/bin/sh
# Программы FOX для GreenOS: Xfe (файлы), Adie (редактор с подсветкой), Calculator, ShutterBug (снимок
# экрана), ControlPanel (цвета и шрифт программ FOX; тема - /etc/foxrc/Desktop). fox из Alpine собран с
# OpenGL и тянет mesa-xlib (libGL 17 МБ) - здесь FOX 1.6 без OpenGL, тулчейном musl на sysroot от
# build.sh (сначала он); libstdc++ - пакет Alpine. reswrap (картинки -> C) исполняется при сборке - он
# для хоста. Родные значки программ (GIF из исходников) -> PNG для меню JWM.
# Xfe - xfe, архиватор xfa и просмотр картинок xfi (текст открывает adie: xferc-greenos), значки - его тема
# kde-theme, русский интерфейс - его перевод (gettext в musl; LC_MESSAGES ставит xinitrc).
# Результат -> bundles/greenos/root (в git не идёт), как у build.sh.
set -e
cd "$(dirname "$0")/../.."

FOX=1.6.59
XFE=2.0.1
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SR=$CACHE/greenos-sysroot
B=$CACHE/greenos-build
OUT=$PWD/bundles/greenos/root

[ -d $SR/usr/include/X11/Xft ] || { echo "нет $SR - сначала bundles/greenos/build.sh"; exit 1; }
get() {
  [ -f $CACHE/$1 ] || curl -fsSL "$2/$1" -o $CACHE/$1.tmp
  [ -f $CACHE/$1 ] || mv $CACHE/$1.tmp $CACHE/$1
  [ "$(sha256sum $CACHE/$1 | cut -d' ' -f1)" = "$3" ] || { echo "$1: не та контрольная сумма" >&2; exit 1; }
}
# суммы - те же, что у sha512 в APKBUILD fox и xfe Alpine; FOX - только по http
get fox-$FOX.tar.gz http://fox-toolkit.org/ftp 48f33d2dd5371c2d48f6518297f0ef5bbf3fcd37719e99f815dc6fc6e0f928ae
get xfe-$XFE.tar.xz https://downloads.sourceforge.net/xfe be5bb4cac853ef6ad6401d1aa8295e22c749499e2410bf0c52c6044f556a25b3
F=$B/fox-$FOX
X=$B/xfe-$XFE
rm -rf $F $X $OUT/usr/bin/PathFinder $OUT/usr/share/greenos/icons/fox
mkdir -p $B/bin $OUT/usr/bin $OUT/usr/lib $OUT/usr/share/greenos/icons/fox
tar -xzf $CACHE/fox-$FOX.tar.gz -C $B
tar -xJf $CACHE/xfe-$XFE.tar.xz -C $B
patch -d $X -p1 -s < bundles/greenos/xfe-nosn.patch  # без startup notification Xfe 2.0.1 не собирается
g++ -O2 -o $B/reswrap $F/utils/reswrap.cpp

export PATH=$B/bin:$TC/bin:$PATH
export PKG_CONFIG_LIBDIR=$SR/usr/lib/pkgconfig:$SR/usr/share/pkgconfig PKG_CONFIG_SYSROOT_DIR=$SR
CC="i686-linux-musl-gcc -march=pentium4 -mtune=generic"
CXX="i686-linux-musl-g++ -march=pentium4 -mtune=generic"
CPPFLAGS="-I$SR/usr/include -I$SR/usr/include/freetype2"
LDFLAGS="-L$SR/usr/lib -Wl,-rpath-link,$SR/usr/lib:$SR/lib -Wl,--as-needed"

(cd $F && ./configure -q --host=i686-linux-musl --prefix=/usr --enable-shared --disable-static \
  CC="$CC" CXX="$CXX" CFLAGS=-Os CXXFLAGS="-Os -DNDEBUG" CPPFLAGS="$CPPFLAGS" LDFLAGS="$LDFLAGS" \
  --x-includes=$SR/usr/include --x-libraries=$SR/usr/lib \
  --with-opengl=no --with-xft=yes --enable-png --enable-jpeg --enable-zlib --disable-tiff --disable-bz2lib \
  --with-xshm=yes --with-shape=yes --with-xrender=yes --with-xrandr=yes \
  --with-xcursor=no --with-xfixes=no --with-xinput=no --with-xim=no)
# configure FOX вписывает заголовки freetype хоста
find $F -name Makefile -exec sed -i "s|-I/usr/include/freetype2|-I$SR/usr/include/freetype2|g" {} +
for d in src adie calculator shutterbug; do
  make -C $F/$d -s -j"$(nproc)" RESWRAP=$B/reswrap
done
make -C $F/tests -s RESWRAP=$B/reswrap ControlPanel
cp -P $F/src/.libs/libFOX-1.6.so* $OUT/usr/lib/
for p in adie/adie calculator/calculator shutterbug/shutterbug tests/ControlPanel; do
  if [ -f $F/${p%/*}/.libs/${p#*/} ]; then cp $F/${p%/*}/.libs/${p#*/} $OUT/usr/bin/; else cp $F/$p $OUT/usr/bin/; fi
done
python3 - "$F" "$OUT/usr/share/greenos/icons/fox" <<'EOF'
import sys
from PIL import Image
src, out = sys.argv[1:]
for name, gif in (("adie", "adie/big_gif.gif"), ("calculator", "calculator/bigcalc.gif"), ("shutterbug", "shutterbug/shutterbug.gif")):
    Image.open(f"{src}/{gif}").convert("RGBA").save(f"{out}/{name}.png")
EOF

# Xfe: FOX - в sysroot, fox-config - с путями sysroot; gettext - из musl (проверка configure ищет GNU
# gettext и без подсказки выключает перевод); malloc(0) при кросс-сборке не проверить - без подсказки
# configure подменяет malloc на rpl_malloc, и заголовки C++ не собираются
mkdir -p $SR/usr/include/fox-1.6
cp $F/include/*.h $SR/usr/include/fox-1.6/
cp -P $F/src/.libs/libFOX-1.6.so* $SR/usr/lib/
printf '#!/bin/sh\ncase $1 in --cflags) echo "-I%s/usr/include/fox-1.6" ;; --libs) echo "-lFOX-1.6 -lXft" ;; esac\n' "$SR" > $B/bin/fox-config
# configure Xfe спрашивает pkexec хоста и тогда требует polkit - в машине его нет
printf '#!/bin/sh\nexit 1\n' > $B/bin/pkexec
chmod +x $B/bin/fox-config $B/bin/pkexec
(cd $X && ./configure -q --host=i686-linux-musl --prefix=/usr --sysconfdir=/etc --disable-sn \
  gt_cv_func_gnugettext1_libc=yes gt_cv_func_gnugettext2_libc=yes \
  ac_cv_func_malloc_0_nonnull=yes ac_cv_func_realloc_0_nonnull=yes \
  CC="$CC" CXX="$CXX" CFLAGS=-Os CXXFLAGS="-Os -DNDEBUG" CPPFLAGS="$CPPFLAGS" LDFLAGS="$LDFLAGS")
make -C $X/src -s -j"$(nproc)" xfe xfa xfi
cp $X/src/xfe $X/src/xfa $X/src/xfi $OUT/usr/bin/
rm -rf $OUT/usr/share/xfe
mkdir -p $OUT/usr/share/xfe/icons $OUT/usr/share/pixmaps $OUT/usr/share/locale/ru/LC_MESSAGES
cp -r $X/icons/kde-theme $OUT/usr/share/xfe/icons/
find $OUT/usr/share/xfe/icons -name 'Makefile*' -delete
# kde-theme - не вся: недостающее Xfe при установке ссылками берёт из default-theme (iconlinks.sh) -
# здесь только эти значки, копиями
for i in $X/icons/default-theme/*.png; do
  [ -f $OUT/usr/share/xfe/icons/kde-theme/${i##*/} ] || cp $i $OUT/usr/share/xfe/icons/kde-theme/
done
cp $X/icons/apps/xfe.png $X/icons/apps/xfa.png $X/icons/apps/xfi.png $OUT/usr/share/pixmaps/
cp $X/po/ru.gmo $OUT/usr/share/locale/ru/LC_MESSAGES/xfe.mo
python3 bundles/greenos/xferc.py $X/xferc bundles/greenos/xferc-greenos $OUT/usr/share/xfe/xferc

i686-linux-musl-strip $OUT/usr/bin/xfe $OUT/usr/bin/xfa $OUT/usr/bin/xfi $OUT/usr/bin/adie $OUT/usr/bin/calculator $OUT/usr/bin/shutterbug \
  $OUT/usr/bin/ControlPanel $OUT/usr/lib/libFOX-1.6.so.*.*
cd $OUT
for f in usr/bin/xfe usr/bin/xfa usr/bin/xfi usr/bin/adie usr/bin/calculator usr/bin/shutterbug usr/bin/ControlPanel usr/lib/libFOX-1.6.so.*.*; do
  echo "$f $(du -h $f | cut -f1): $(i686-linux-musl-readelf -d $f | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' ')"
done
echo "usr/share/xfe $(du -sh usr/share/xfe | cut -f1)"
