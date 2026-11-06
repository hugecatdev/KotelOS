#!/bin/sh
set -e
cd "$(dirname "$0")/.."

VER=0.3.28
CACHE=.cache
TC=$CACHE/i686-linux-musl-cross
SRC=$CACHE/OpenBLAS-$VER
DEV=$PWD/$CACHE/openblas-dev  # заголовки, libopenblas.so и openblas.pc для scripts/build-numpy.sh
OUT=build/packages/openblas

[ -x $TC/bin/i686-linux-musl-gcc ] || { echo "нет тулчейна, сначала scripts/build-busybox.sh"; exit 1; }
[ -f $CACHE/OpenBLAS-$VER.tar.gz ] || curl -fsSL https://github.com/OpenMathLib/OpenBLAS/releases/download/v$VER/OpenBLAS-$VER.tar.gz -o $CACHE/OpenBLAS-$VER.tar.gz
rm -rf $SRC $DEV
tar -xzf $CACHE/OpenBLAS-$VER.tar.gz -C $CACHE

# NORTHWOOD: ядра на SSE2. У PRESCOTT комплексные (zgemm, ztrsm) на addsubpd/addsubps из SSE3,
# которых v86 не умеет: SIGILL в комплексной линейной алгебре numpy и scipy.
# LAPACK - C-перевод из OpenBLAS (C_LAPACK) вместо фортрановского: без libgfortran и libquadmath;
# соглашения о вызовах остаются как у gfortran, scipy (он сам на gfortran) работает с ним как раньше.
# LAPACKE (C-обёртки) не нужны ни numpy, ни scipy.
set -- CC=i686-linux-musl-gcc HOSTCC=gcc AR=i686-linux-musl-ar RANLIB=i686-linux-musl-ranlib \
  TARGET=NORTHWOOD BINARY=32 DYNAMIC_ARCH=0 USE_THREAD=0 USE_OPENMP=0 NO_AVX=1 NO_AVX2=1 NO_AVX512=1 \
  NOFORTRAN=1 C_LAPACK=1 NO_LAPACKE=1 MAJOR_VERSION=3 COMMON_OPT="-O2 -march=pentium4 -mtune=generic -mfpmath=sse"
export PATH="$PWD/$TC/bin:$PATH"
: > $CACHE/openblas-build.log
for goal in libs netlib shared; do
  make -C $SRC -j"$(nproc)" "$@" $goal >> $CACHE/openblas-build.log 2>&1 || { tail -30 $CACHE/openblas-build.log; exit 1; }
done
make -C $SRC "$@" PREFIX="$DEV" install >> $CACHE/openblas-build.log 2>&1 || { tail -30 $CACHE/openblas-build.log; exit 1; }

lib=$(ls $SRC/libopenblas*-r$VER.so | head -n 1)
i686-linux-musl-strip --strip-unneeded "$lib"
scripts/check-isa.sh "$lib" || { echo "$lib не пойдёт в v86"; exit 1; }
if readelf -dW "$lib" | grep -q 'NEEDED.*gfortran'; then
  echo "$lib всё ещё требует libgfortran"
  exit 1
fi
rm -f $OUT/usr/lib/libopenblas*
install -D -m 755 "$lib" $OUT/usr/lib/libopenblas.so.3
echo "musl" > $OUT/.deps
echo "openblas $VER (NORTHWOOD, LAPACK на C) -> $OUT ($(du -h $OUT/usr/lib/libopenblas.so.3 | cut -f1), $(readelf -dW $OUT/usr/lib/libopenblas.so.3 | sed -n 's/.*SONAME.*\[\(.*\)\]/\1/p'))"
