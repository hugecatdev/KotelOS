#!/bin/sh
# idesk 0.7.5 для GreenOS - значки на рабочем столе (картинка imlib2 - она уже есть у feh, подпись Xft,
# тень); пакета в Alpine нет. Тулчейн musl на sysroot от build.sh (сначала он) + заголовки imlib2.
# idesk-gcc.patch - правки под современный C++, idesk-motion.patch - перетаскивание без отставания (из
# очереди - только последнее движение мыши). Результат -> bundles/greenos/root/usr/bin/idesk
set -e
cd "$(dirname "$0")/../.."

V=0.7.5
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SR=$CACHE/greenos-sysroot
B=$CACHE/greenos-build
OUT=$PWD/bundles/greenos/root

[ -d $SR/usr/include/X11/Xft ] || { echo "нет $SR - сначала bundles/greenos/build.sh"; exit 1; }
f=idesk-$V.tar.bz2
[ -f $CACHE/$f ] || curl -fsSL https://downloads.sourceforge.net/idesk/$f -o $CACHE/$f.tmp
[ -f $CACHE/$f ] || mv $CACHE/$f.tmp $CACHE/$f
[ "$(sha256sum $CACHE/$f | cut -d' ' -f1)" = d4b7ea5dcf6d49d83e2df9512d4c6388f11632a702b14f42a1bc6bffb617b3d3 ] ||
  { echo "$f: не та контрольная сумма" >&2; exit 1; }
S=$B/idesk-$V
rm -rf $S
mkdir -p $B/bin $OUT/usr/bin
tar -xjf $CACHE/$f -C $B
for p in bundles/greenos/idesk-*.patch; do patch -d $S -p1 -s < "$p"; done

python3 - "$SR" <<'EOF'
import sys
import alpine
pkgs, provides = alpine.index(tag="xorg-", max_age=7 * 86400)
for n in alpine.resolve(["imlib2-dev"], pkgs, provides, {"python3", "linux-headers"}):
    f = f"{n}-{pkgs[n]['ver']}.apk"
    alpine.extract(alpine.fetch(f"{alpine.MIRROR}/{pkgs[n]['repo']}/x86/{f}", f"{alpine.CACHE}/apk/{f}"), sys.argv[1], [], [])
EOF
# imlib2 давно без imlib2-config, а configure idesk ищет его
printf '#!/bin/sh\ncase $1 in --version) echo 1.12.0 ;; --cflags) echo "-I%s/usr/include" ;; --libs) echo "-lImlib2" ;; --prefix) echo /usr ;; esac\n' "$SR" > $B/bin/imlib2-config
chmod +x $B/bin/imlib2-config

export PATH=$B/bin:$TC/bin:$PATH
export PKG_CONFIG_LIBDIR=$SR/usr/lib/pkgconfig:$SR/usr/share/pkgconfig PKG_CONFIG_SYSROOT_DIR=$SR
(cd $S && ./configure -q --host=i686-linux-musl --prefix=/usr \
  CC="i686-linux-musl-gcc -march=pentium4 -mtune=generic" CXX="i686-linux-musl-g++ -march=pentium4 -mtune=generic" \
  CXXFLAGS="-Os -DNDEBUG -std=gnu++98" CPPFLAGS="-I$SR/usr/include -I$SR/usr/include/freetype2" \
  LDFLAGS="-s -L$SR/usr/lib -Wl,-rpath-link,$SR/usr/lib:$SR/lib -Wl,--as-needed" \
  --x-includes=$SR/usr/include --x-libraries=$SR/usr/lib)
make -C $S -s
cp $S/src/idesk $OUT/usr/bin/idesk
echo "idesk $(du -h $OUT/usr/bin/idesk | cut -f1): $(i686-linux-musl-readelf -d $OUT/usr/bin/idesk | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' ')"
