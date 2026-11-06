#!/bin/sh
# Doom: движок doomgeneric (GPLv2, закреплённый коммит) + своя платформа src/kt-doom.c
# (/dev/fb0 и evdev) -> packages/doom/usr/lib/doom/doom; первый эпизод (shareware v1.9) ->
# build/packages/doom-shareware
set -e
cd "$(dirname "$0")/.."

DG=e257a09527062bfb986b6e5e0780839b6cbd5b71
WAD_SHA1=5b2e249b9c5133ec987b3ea77596381dc0d6bc1d
CACHE=.cache
TC=$CACHE/i686-linux-musl-cross
SRC=$CACHE/doomgeneric-$DG/doomgeneric

mkdir -p $CACHE
[ -x $TC/bin/i686-linux-musl-gcc ] || curl -fsSL https://musl.cc/i686-linux-musl-cross.tgz | tar -xz -C $CACHE
if [ ! -d $SRC ]; then
  curl -fsSL https://github.com/ozkl/doomgeneric/archive/$DG.tar.gz -o $CACHE/doomgeneric-$DG.tar.gz
  tar -xzf $CACHE/doomgeneric-$DG.tar.gz -C $CACHE
fi

OUT=packages/doom/usr/lib/doom/doom
mkdir -p "$(dirname $OUT)"
# движок без чужих платформ (doomgeneric_*.c) и звука SDL/Allegro, кадр 320x200 - растягивает kt-doom.c
$TC/bin/i686-linux-musl-gcc -Os -static -s -ffunction-sections -fdata-sections -Wl,--gc-sections \
  -Wl,-z,norelro -Wl,--build-id=none -w -DNORMALUNIX -DLINUX -D_DEFAULT_SOURCE \
  -DDOOMGENERIC_RESX=320 -DDOOMGENERIC_RESY=200 -I$SRC \
  -o $OUT $(ls $SRC/*.c | grep -v '/doomgeneric_\|/i_sdl\|/i_allegro') src/kt-doom.c -lm
echo "doom -> $OUT ($(du -h $OUT | cut -f1))"

WAD=$CACHE/doom1.wad
check() { [ -f $WAD ] && [ "$(sha1sum $WAD | cut -d' ' -f1)" = $WAD_SHA1 ]; }
for u in https://raw.githubusercontent.com/Akbar30Bill/DOOM_wads/master/doom1.wad \
         https://distro.ibiblio.org/slitaz/sources/packages/d/doom1.wad; do
  check && break
  curl -fsSL -m 120 "$u" -o $WAD.tmp && mv $WAD.tmp $WAD || rm -f $WAD.tmp
done
check || { echo "doom1.wad не скачался или не тот (sha1 $WAD_SHA1)" >&2; exit 1; }
P=build/packages/doom-shareware
rm -rf $P
mkdir -p $P/usr/share/games/doom
cp $WAD $P/usr/share/games/doom/doom1.wad
: > $P/.deps
echo "doom1.wad -> $P"
