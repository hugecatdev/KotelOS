#!/bin/sh
set -e
cd "$(dirname "$0")/.."

VER=6.6.32
CACHE=.cache
TC=$CACHE/i686-linux-musl-cross
SRC=$CACHE/linux-$VER
OUT=${1:-images/bzImage}

mkdir -p $CACHE
[ -x $TC/bin/i686-linux-musl-gcc ] || curl -fsSL https://musl.cc/i686-linux-musl-cross.tgz | tar -xz -C $CACHE
if [ ! -d $SRC ]; then
  [ -f $CACHE/linux-$VER.tar.xz ] || curl -fsSL https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-$VER.tar.xz -o $CACHE/linux-$VER.tar.xz
  tar -xJf $CACHE/linux-$VER.tar.xz -C $CACHE
fi

export PATH="$PWD/$TC/bin:$PATH"
K="make -C $SRC ARCH=x86 CROSS_COMPILE=i686-linux-musl- KBUILD_BUILD_USER=kotel KBUILD_BUILD_HOST=kotel"

cp config/linux.config $SRC/.config
$K olddefconfig > /dev/null
for v in $(sed -n 's/^CONFIG_\(NET_VENDOR_[A-Z0-9_]*\)=y/\1/p' $SRC/.config); do
  $SRC/scripts/config --file $SRC/.config --disable "$v"
done
# EXTRA_FRAGMENT=файл - ещё опции поверх config/kernel.fragment (проба цены, частное ядро)
for f in config/kernel.fragment $EXTRA_FRAGMENT; do
  sed -n 's/^\(# \)\{0,1\}CONFIG_\([A-Z0-9_]*\)[= ].*/\2/p' $f | while read -r k; do
    sed -i "/^\(# \)\{0,1\}CONFIG_$k[= ]/d" $SRC/.config
  done
  cat $f >> $SRC/.config
done
$K olddefconfig > /dev/null
$K -j"$(nproc)" bzImage > $CACHE/kernel-build.log 2>&1 || { tail -30 $CACHE/kernel-build.log; exit 1; }

mkdir -p "$(dirname "$OUT")"
cp $SRC/arch/x86/boot/bzImage $OUT
cp $SRC/.config $CACHE/kernel.config
echo "bzImage -> $OUT ($(du -h $OUT | cut -f1))"
