#!/bin/sh
# kt-xclipd (src/kt-xclipd.c) - общий буфер обмена X и браузера: тулчейном musl против libxcb из Alpine
# (заголовки и .so - в свой sysroot, индекс - свой и свежий, как у scripts/build-dwm.sh). libxcb в машине
# есть у любой программы X, отдельной библиотеки для XFixes не нужно - libxcb-xfixes в том же пакете.
# Результат -> packages/kt-xclipd/usr/bin/kt-xclipd (бинарник в git не идёт)
set -e
cd "$(dirname "$0")/.."

TC=$PWD/.cache/i686-linux-musl-cross
SR=$PWD/.cache/xclipd-sysroot
OUT=packages/kt-xclipd/usr/bin/kt-xclipd

[ -x $TC/bin/i686-linux-musl-gcc ] || { echo "нет тулчейна, сначала scripts/build-busybox.sh"; exit 1; }
rm -rf $SR
python3 - "$SR" <<'EOF'
import sys
import alpine
pkgs, provides = alpine.index(tag="xorg-", max_age=7 * 86400)
for n in alpine.resolve(["libxcb-dev"], pkgs, provides, {"python3", "linux-headers"}):
    f = f"{n}-{pkgs[n]['ver']}.apk"
    alpine.extract(alpine.fetch(f"{alpine.MIRROR}/{pkgs[n]['repo']}/x86/{f}", f"{alpine.CACHE}/apk/{f}"), sys.argv[1], [], [])
EOF

mkdir -p "$(dirname $OUT)"
$TC/bin/i686-linux-musl-gcc -march=pentium4 -mtune=generic -Os -Wall -Wextra -s -I$SR/usr/include \
  -L$SR/usr/lib -Wl,-rpath-link,$SR/usr/lib -Wl,--as-needed -o $OUT src/kt-xclipd.c -lxcb-xfixes -lxcb
echo "$OUT $(du -h $OUT | cut -f1): $($TC/bin/i686-linux-musl-readelf -d $OUT | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | tr '\n' ' ')"
