#!/bin/sh
set -e
cd "$(dirname "$0")/.."

VER=1.36.1
BRVER=2024.02.5
CACHE=.cache
TC=$CACHE/i686-linux-musl-cross
SRC=$CACHE/busybox-$VER
BR=$CACHE/buildroot-$BRVER

mkdir -p $CACHE
[ -x $TC/bin/i686-linux-musl-gcc ] || curl -fsSL https://musl.cc/i686-linux-musl-cross.tgz | tar -xz -C $CACHE

# патчи и конфиг busybox берутся из Buildroot
if [ ! -d $BR/package/busybox ]; then
  [ -f $CACHE/buildroot-$BRVER.tar.gz ] || curl -fsSL https://buildroot.org/downloads/buildroot-$BRVER.tar.gz -o $CACHE/buildroot-$BRVER.tar.gz
  tar -xzf $CACHE/buildroot-$BRVER.tar.gz -C $CACHE buildroot-$BRVER/package/busybox
fi

rm -rf $SRC
[ -f $CACHE/busybox-$VER.tar.bz2 ] || curl -fsSL https://busybox.net/downloads/busybox-$VER.tar.bz2 -o $CACHE/busybox-$VER.tar.bz2
tar -xjf $CACHE/busybox-$VER.tar.bz2 -C $CACHE
for p in $BR/package/busybox/*.patch; do patch -s -d $SRC -p1 < "$p"; done

cp $BR/package/busybox/busybox.config $SRC/.config
{
  echo CONFIG_STATIC=y
  echo CONFIG_INIT=y
  echo CONFIG_USE_BB_CRYPT_SHA=y
  echo CONFIG_FEATURE_LESS_DASHCMD=y
  echo CONFIG_FEATURE_LESS_RAW=y
  echo CONFIG_FEATURE_LESS_TRUNCATE=y
  echo CONFIG_FEATURE_LESS_FLAGS=y
  echo CONFIG_FEATURE_LESS_ENV=y
  echo "# CONFIG_NOMMU is not set"
  echo "# CONFIG_SHA1_HWACCEL is not set"
  echo "# CONFIG_SHA256_HWACCEL is not set"
  cat config/busybox.fragment
} > $CACHE/fragment
sed -n 's/^\(# \)\{0,1\}\(CONFIG_[A-Z0-9_]*\)[= ].*/\2/p' $CACHE/fragment | while read -r k; do
  sed -i "/^\(# \)\{0,1\}$k[= ]/d" $SRC/.config
done
cat $CACHE/fragment >> $SRC/.config

export PATH="$PWD/$TC/bin:$PATH"
yes "" | make -C $SRC CROSS_COMPILE=i686-linux-musl- oldconfig > /dev/null
make -C $SRC CROSS_COMPILE=i686-linux-musl- -j"$(nproc)" busybox > $CACHE/busybox-build.log 2>&1 \
  || { tail -30 $CACHE/busybox-build.log; exit 1; }
i686-linux-musl-strip $SRC/busybox

mkdir -p overlay/bin
install -m 4755 $SRC/busybox overlay/bin/busybox
mkdir -p overlay/usr/bin
for a in timeout pgrep pkill; do ln -sf ../../bin/busybox overlay/usr/bin/$a; done
echo "busybox $VER (static, unicode) -> overlay/bin/busybox ($(du -h overlay/bin/busybox | cut -f1))"

i686-linux-musl-gcc -static -no-pie -Os -s -ffunction-sections -fdata-sections -Wl,--gc-sections \
  -Wl,-z,norelro -Wl,--build-id=none -o overlay/usr/sbin/kt-seed src/kt-seed.c
echo "kt-seed -> overlay/usr/sbin/kt-seed ($(du -h overlay/usr/sbin/kt-seed | cut -f1))"
i686-linux-musl-gcc -static -no-pie -Os -s -ffunction-sections -fdata-sections -Wl,--gc-sections \
  -Wl,-z,norelro -Wl,--build-id=none -o overlay/usr/sbin/kt-net src/kt-net.c
ln -sf kt-net overlay/usr/sbin/kt-netd
echo "kt-net -> overlay/usr/sbin/kt-net ($(du -h overlay/usr/sbin/kt-net | cut -f1))"
mkdir -p packages/pyzygote/usr/local/bin
i686-linux-musl-gcc -static -no-pie -Os -s -ffunction-sections -fdata-sections -Wl,--gc-sections \
  -Wl,-z,norelro -Wl,--build-id=none -o packages/pyzygote/usr/local/bin/python3 src/pyzygote.c
echo "pyzygote -> packages/pyzygote/usr/local/bin/python3 ($(du -h packages/pyzygote/usr/local/bin/python3 | cut -f1))"
