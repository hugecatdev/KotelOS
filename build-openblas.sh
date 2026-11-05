#!/bin/sh
set -e
cd "$(dirname "$0")"

VER=0.3.28
CACHE=.cache
TC=$CACHE/i686-linux-musl-cross
SRC=$CACHE/OpenBLAS-$VER
OUT=packages/openblas

[ -x $TC/bin/i686-linux-musl-gfortran ] || { echo "нет тулчейна, сначала ./build-busybox.sh"; exit 1; }
[ -f $CACHE/OpenBLAS-$VER.tar.gz ] || curl -fsSL https://github.com/OpenMathLib/OpenBLAS/releases/download/v$VER/OpenBLAS-$VER.tar.gz -o $CACHE/OpenBLAS-$VER.tar.gz
rm -rf $SRC
tar -xzf $CACHE/OpenBLAS-$VER.tar.gz -C $CACHE

export PATH="$PWD/$TC/bin:$PATH"
: > $CACHE/openblas-build.log
for goal in libs netlib shared; do
  make -C $SRC -j"$(nproc)" CC=i686-linux-musl-gcc FC=i686-linux-musl-gfortran HOSTCC=gcc \
    AR=i686-linux-musl-ar RANLIB=i686-linux-musl-ranlib \
    TARGET=PRESCOTT BINARY=32 DYNAMIC_ARCH=0 USE_THREAD=0 USE_OPENMP=0 NO_AVX=1 NO_AVX2=1 NO_AVX512=1 \
    MAJOR_VERSION=3 COMMON_OPT="-O2 -march=pentium4 -mtune=generic -mfpmath=sse" \
    FCOMMON_OPT="-O2 -march=pentium4 -mtune=generic -mfpmath=sse -frecursive" $goal >> $CACHE/openblas-build.log 2>&1 \
    || { tail -30 $CACHE/openblas-build.log; exit 1; }
done

lib=$(ls $SRC/libopenblas*-r$VER.so | head -n 1)
i686-linux-musl-strip --strip-unneeded "$lib"
if objdump -d "$lib" | grep -q -E "\s(palignr|pshufb|phadd[wd]|pmaddubsw|pmulhrsw|pabs[bwd]|psign[bwd])\s"; then
  echo "в $lib есть SSSE3, v86 его не умеет"
  exit 1
fi
rm -f $OUT/usr/lib/libopenblas*
install -D -m 755 "$lib" $OUT/usr/lib/libopenblas.so.3
echo "musl libgfortran" > $OUT/.deps
echo "openblas $VER (PRESCOTT, без SSSE3) -> $OUT ($(du -h $OUT/usr/lib/libopenblas.so.3 | cut -f1), $(readelf -dW $OUT/usr/lib/libopenblas.so.3 | sed -n 's/.*SONAME.*\[\(.*\)\]/\1/p'))"
