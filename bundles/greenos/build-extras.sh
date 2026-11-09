#!/bin/sh
# Мелочи для GreenOS с GitHub (по коммитам, суммы - ниже), тулчейн musl на sysroot от build.sh:
# - xroach (interkosmos/xroach) - тараканы, что прячутся под окнами;
# - oneko (IreneKnapp/oneko) - кошка бегает за курсором.
# Результат -> bundles/greenos/root/usr/bin
set -e
cd "$(dirname "$0")/../.."

CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SR=$CACHE/greenos-sysroot
B=$CACHE/greenos-build
OUT=$PWD/bundles/greenos/root

[ -d $SR/usr/include/X11/Xft ] || { echo "нет $SR - сначала bundles/greenos/build.sh"; exit 1; }
get() {  # get имя репозиторий коммит сумма
  f=$1-$(echo $3 | cut -c1-7).tar.gz
  [ -f $CACHE/$f ] || curl -fsSL https://codeload.github.com/$2/tar.gz/$3 -o $CACHE/$f.tmp
  [ -f $CACHE/$f ] || mv $CACHE/$f.tmp $CACHE/$f
  [ "$(sha256sum $CACHE/$f | cut -d' ' -f1)" = "$4" ] || { echo "$f: не та контрольная сумма" >&2; exit 1; }
  rm -rf $B/$1-$3
  tar -xzf $CACHE/$f -C $B
}
mkdir -p $B $OUT/usr/bin
get xroach interkosmos/xroach 3ef9309005936050a45e43f93e821eece2ac6eb7 47cb1efe7aeddbf97929aa6c243e21169dfcaf8910ae2eb27cd5e66e61ffefce
get oneko IreneKnapp/oneko fe5a09264a765d4613c9dcc2703b03e06f77875b 4643fe1340eb6afeef93307bab27a6b4eab562a45b24bb9b37236186e1c57647

CC="$TC/bin/i686-linux-musl-gcc -march=pentium4 -mtune=generic -Os -w"
INC="-I$SR/usr/include -I$SR/usr/include/freetype2"
LINK="-s -L$SR/usr/lib -Wl,-rpath-link,$SR/usr/lib:$SR/lib -Wl,--as-needed"

R=$B/xroach-3ef9309005936050a45e43f93e821eece2ac6eb7
$CC $INC -I$R -o $OUT/usr/bin/xroach $R/xroach.c $LINK -lX11 -lm
K=$B/oneko-fe5a09264a765d4613c9dcc2703b03e06f77875b
$CC $INC -I$K -DSHAPE -o $OUT/usr/bin/oneko $K/oneko.c $LINK -lXext -lX11 -lm

# значки для меню - их же картинки (XBM): таракан и кошка с маской
mkdir -p $OUT/usr/share/greenos/icons/extras
python3 - $R/roach000.xbm $K/bitmaps/neko/awake.xbm $K/bitmasks/neko/awake_mask.xbm $OUT/usr/share/greenos/icons/extras <<'EOF'
import sys
from PIL import Image
roach, neko, mask, out = sys.argv[1:]
def paint(xbm, color, base=None):
    bits = Image.open(xbm).convert("L")
    im = base or Image.new("RGBA", bits.size, (0, 0, 0, 0))
    im.paste(Image.new("RGBA", bits.size, color), (0, 0), bits)
    return im
paint(roach, (110, 70, 30, 255)).save(f"{out}/xroach.png")
paint(neko, (20, 20, 20, 255), paint(mask, (255, 255, 255, 255))).save(f"{out}/oneko.png")
EOF

for f in xroach oneko; do
  echo "$f $(du -h $OUT/usr/bin/$f | cut -f1): $($TC/bin/i686-linux-musl-readelf -d $OUT/usr/bin/$f | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' ')"
done
