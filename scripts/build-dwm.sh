#!/bin/sh
# dwm, st и feh: свои сборки тулчейном musl против заголовков и библиотек Alpine x86, версии - те же,
# что в Alpine. dwm и st настраиваются только пересборкой (config.h). dwm - сборка пользователя:
# patches/dwm-dmitry.patch (его патчи: отступы, scratchpad, скрытие окон, systray...) и его
# настройки под машину - config/dwm-config.h (Alt вместо Super, шрифт fixed из пакета xorg);
# st - patches/st-config.patch (тот же шрифт); patches/dwm-grabkeys.patch - на смену раскладки dwm
# перехватывает заново только изменившиеся клавиши: в медленной машине первое сочетание после startx
# проваливалось в щель между снятием всех захватов и установкой новых. dwm-studio - тот же dwm для
# бандла qt (Designer и pyqt-studio) с patches/dwm-studio.patch: теги - этапы работы с формой, а на
# экране выше, чем шире (телефон стоя), плитка ставит главное окно сверху, остальные под ним.
# feh - без libcurl (с OpenSSL ~7 МБ в машине, а https из v86 всё равно не ходит) и libmagic (база
# типов файлов 10 МБ): картинки он узнаёт и так, через imlib2.
# Результат -> packages/dwm, packages/dwm-studio, packages/st, packages/feh (бинарники в git не идут)
set -e
cd "$(dirname "$0")/.."

DWM=6.5
ST=0.9.2
FEH=3.10.3
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SR=$CACHE/dwm-sysroot
B=$CACHE/dwm-build

[ -x $TC/bin/i686-linux-musl-gcc ] || { echo "нет тулчейна, сначала scripts/build-busybox.sh"; exit 1; }
get() {
  [ -f $CACHE/$1 ] || curl -fsSL "$2/$1" -o $CACHE/$1.tmp
  [ -f $CACHE/$1 ] || mv $CACHE/$1.tmp $CACHE/$1
  [ "$(sha256sum $CACHE/$1 | cut -d' ' -f1)" = "$3" ] || { echo "$1: не та контрольная сумма" >&2; exit 1; }
}
get dwm-$DWM.tar.gz https://dl.suckless.org/dwm 21d79ebfa9f2fb93141836c2666cb81f4784c69d64e7f1b2352f9b970ba09729
get st-$ST.tar.gz https://dl.suckless.org/st 6b215d4f472b21d6232f30f221117a777e24bcfee68955ddefb7426467f9494b
get feh-$FEH.tar.bz2 https://feh.finalrewind.org 5426e2799770217af1e01c2e8c182d9ca8687d84613321d8ab4a66fe4041e9c8
rm -rf $B
mkdir -p $B
tar -xzf $CACHE/st-$ST.tar.gz -C $B
tar -xjf $CACHE/feh-$FEH.tar.bz2 -C $B

# заголовки и .pc из Alpine (libxt-dev - только ради типов в заголовке feh, с libXt он не линкуется);
# индекс - свой и свежий, как у scripts/build-xorg.sh
rm -rf $SR
python3 - "$SR" <<'EOF'
import sys
import alpine
pkgs, provides = alpine.index(tag="xorg-", max_age=7 * 86400)
want = "libx11-dev libxft-dev libxinerama-dev fontconfig-dev freetype-dev imlib2-dev libpng-dev libxt-dev".split()
for n in alpine.resolve(want, pkgs, provides, {"python3", "linux-headers"}):
    f = f"{n}-{pkgs[n]['ver']}.apk"
    alpine.extract(alpine.fetch(f"{alpine.MIRROR}/{pkgs[n]['repo']}/x86/{f}", f"{alpine.CACHE}/apk/{f}"), sys.argv[1], [], [])
EOF

CC="$TC/bin/i686-linux-musl-gcc -march=pentium4 -mtune=generic"
LINK="-s -L$SR/usr/lib -Wl,-rpath-link,$SR/usr/lib:$SR/lib -Wl,--as-needed"
export PKG_CONFIG_LIBDIR=$SR/usr/lib/pkgconfig:$SR/usr/share/pkgconfig PKG_CONFIG_SYSROOT_DIR=$SR

make_dwm() {  # make_dwm папка [патч]: dwm пользователя (и свой патч поверх его dwm.c и config.h)
  rm -rf $1
  mkdir -p $1
  tar -xzf $CACHE/dwm-$DWM.tar.gz -C $1 --strip-components=1
  patch -d $1 -p1 -s < patches/dwm-dmitry.patch
  patch -d $1 -p1 -s < patches/dwm-grabkeys.patch
  cp config/dwm-config.h $1/config.h
  [ -z "$2" ] || patch -d $1 -p1 -s < $2
  make -C $1 -s CC="$CC" X11INC=$SR/usr/include X11LIB=$SR/usr/lib FREETYPEINC=$SR/usr/include/freetype2 \
    LDFLAGS="$LINK -lX11 -lXinerama -lfontconfig -lXft"
}
D=$B/dwm-$DWM
make_dwm $D
mkdir -p packages/dwm/usr/bin
cp $D/dwm packages/dwm/usr/bin/dwm
make_dwm $B/dwm-studio patches/dwm-studio.patch
mkdir -p packages/dwm-studio/usr/bin
cp $B/dwm-studio/dwm packages/dwm-studio/usr/bin/dwm-studio

S=$B/st-$ST
patch -d $S -p1 -s < patches/st-config.patch
cp $S/config.def.h $S/config.h
make -C $S -s CC="$CC" X11INC=$SR/usr/include X11LIB=$SR/usr/lib CFLAGS=-Os LDFLAGS="$LINK"
mkdir -p packages/st/usr/bin
cp $S/st packages/st/usr/bin/st

F=$B/feh-$FEH
CFLAGS="-Os -I$SR/usr/include" LDFLAGS="$LINK" make -C $F -s CC="$CC" PREFIX=/usr curl=0 magic=0 exif=0 xinerama=1
rm -rf packages/feh/usr
make -C $F -s PREFIX=/usr DESTDIR=$PWD/packages/feh install-bin install-font install-img install-applications > /dev/null
rm -f packages/feh/usr/share/feh/images/feh.svg  # значок для меню рабочих столов; feh.png рисует сам feh

for f in packages/dwm/usr/bin/dwm packages/dwm-studio/usr/bin/dwm-studio packages/st/usr/bin/st packages/feh/usr/bin/feh; do
  echo "$f $(du -h $f | cut -f1): $($TC/bin/i686-linux-musl-readelf -d $f | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' ')"
done
