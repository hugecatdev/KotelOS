#!/bin/sh
set -e
cd "$(dirname "$0")"

BASE=base/rootfs.base.cpio
OUT=images
PKG=site/repo

if [ ! -f "$BASE" ]; then
  echo "Нет $BASE - положи туда rootfs.cpio из Buildroot (output/images/rootfs.cpio)"
  exit 1
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

minify() {
  find "$1" -type f ! -path "$1/root/*" | while read -r f; do
    case "$f" in
      */usr/lib/kt.sh|*/etc/profile|*/etc/profile.d/*) ;;
      *) head -c 9 "$f" | grep -q '^#!/bin/sh' || continue ;;
    esac
    sed -i -e '1!{/^[[:space:]]*#/d;/^[[:space:]]*$/d;s/^[[:space:]]*//}' "$f"
  done
  find "$1" -type f -name '*.py' ! -path "$1/root/*" ! -path "*/site-packages/*" -print0 | xargs -0 -r python3 pymin.py
  find "$1" -type f -path '*/usr/lib/kt-*.js' | while read -r f; do
    case $(head -c 5 "$f") in
      async|"("*) { printf 'var __f='; cat "$f"; } > "$f.in"; w=1 ;;
      *) cp "$f" "$f.in"; w= ;;
    esac
    npx --yes terser@5 "$f.in" -c -m > "$f.min" 2>/dev/null || : > "$f.min"
    if [ -n "$w" ]; then sed -i '1s/^var __f=//; $s/;$//' "$f.min"; fi
    if [ -s "$f.min" ]; then mv "$f.min" "$f"; fi
    rm -f "$f.in" "$f.min"
  done
}

overlay/bin/busybox --list-full > "$tmp/applets"
python3 cpio-filter.py filter "$BASE" base.exclude "$tmp/applets" > "$tmp/base.cpio"

mkdir "$tmp/root"
cp -a overlay/. "$tmp/root/"
chmod -R u+rwX,go+rX,go-w "$tmp/root"
for d in sbin usr/bin usr/sbin etc/init.d; do
  [ -d "$tmp/root/$d" ] && find "$tmp/root/$d" -type f -exec chmod 755 {} +
done
minify "$tmp/root"
find "$tmp/root" -exec touch -h -d @1767225600 {} +
( cd "$tmp/root" && { echo .; find . -mindepth 1 -printf "%P\n" | LC_ALL=C sort; } \
    | cpio -o -H newc -R 0:0 --reproducible --quiet ) > "$tmp/overlay.cpio"

hash=$(cat "$tmp/base.cpio" "$tmp/overlay.cpio" | sha256sum | cut -c1-10)
mkdir -p "$tmp/ver/usr/lib" "$tmp/ver/var/lib/kt/pkg"
printf 'NAME=KotelOS\nID=kotelos\nVERSION_ID=%s\nPRETTY_NAME="KotelOS %s"\n' "$hash" "$hash" > "$tmp/ver/usr/lib/os-release"
: > "$tmp/ver/var/lib/kt/pkg/base"
python3 cpio-filter.py list "$tmp/base.cpio" "$tmp/overlay.cpio" > "$tmp/own"
( cd "$tmp/ver" && find . -mindepth 1 \( -type d -printf '%P/\n' -o -printf '%P\n' \) ) >> "$tmp/own"
LC_ALL=C sort -u "$tmp/own" > "$tmp/ver/var/lib/kt/pkg/base"
find "$tmp/ver" -exec touch -h -d @1767225600 {} +
( cd "$tmp/ver" && find . -mindepth 1 -printf '%P\n' | LC_ALL=C sort \
    | cpio -o -H newc -R 0:0 --reproducible --quiet ) > "$tmp/ver.cpio"
cat "$tmp/base.cpio" "$tmp/overlay.cpio" "$tmp/ver.cpio" > "$OUT/rootfs.cpio"
printf '{"build":"%s"}\n' "$hash" > "$OUT/build.json"

PYLIBS=$(ls -d "$PWD"/packages/*/usr/lib "$PWD"/packages/*/lib 2>/dev/null | tr '\n' ':')
pyc() {
  [ -d "$1/usr/lib/python3.12" ] && [ -x packages/minipython/usr/bin/python3.12 ] || return 0
  PYTHONDONTWRITEBYTECODE=1 PYTHONHOME=packages/minipython/usr PYTHONPATH=packages/python3/usr/lib/python3.12/lib-dynload \
    packages/musl/lib/ld-musl-i386.so.1 --library-path "$PYLIBS" packages/minipython/usr/bin/python3.12 \
    -X no_debug_ranges -m compileall -b -q -s "$1" -p / "$1/usr/lib/python3.12" > /dev/null || :
  find "$1/usr/lib/python3.12" -name '*.py' | while read -r f; do
    if [ -f "${f}c" ]; then rm "$f"; fi
  done
}

ktpyc() {
  [ -d "$1/usr/lib/kt-python" ] && [ -x packages/minipython/usr/bin/python3.12 ] || return 0
  PYTHONHOME=packages/minipython/usr packages/musl/lib/ld-musl-i386.so.1 \
    --library-path "$PYLIBS" packages/minipython/usr/bin/python3.12 -X no_debug_ranges -m compileall \
    --invalidation-mode checked-hash -q -s "$1" -p / "$1/usr/lib/kt-python" > /dev/null || return 0
}

NEW=$PKG.new
rm -rf "$NEW"
mkdir -p "$NEW"
PC=.cache/pkg
mkdir -p $PC
tools=$( { sed -n '/^minify()/,/^}/p; /^pyc()/,/^}/p; /xz --check/p' build.sh; cat pymin.py; } | sha256sum | cut -c1-16)
printf 'base\t0/%s\t\n' "$(( $(stat -c %s "$OUT/rootfs.cpio") / 1024 ))" > "$tmp/index"
: > "$tmp/pypi"
for d in packages/*/; do
  n=$(basename "$d")
  key=$( { echo "$tools"; cd "$d" && find . -printf '%P %s %T@ %m %l\n' | LC_ALL=C sort; } | sha256sum | cut -c1-32)
  if [ "$(cat $PC/$n.key 2>/dev/null)" = "$key" ] && [ -f $PC/$n.tar.xz ] && [ -f $PC/$n.kb ]; then
    ln -f $PC/$n.tar.xz "$NEW/$n.tar.xz"
  else
    rm -rf "$tmp/pkg"
    cp -a "$d" "$tmp/pkg"
    rm -f "$tmp/pkg/.deps"
    if [ -f "$tmp/pkg/.src" ]; then
      rm -f "$tmp/pkg/.src"
    else
      minify "$tmp/pkg"
      pyc "$tmp/pkg"
      ktpyc "$tmp/pkg"
    fi
    ( cd "$tmp/pkg" && find . -mindepth 1 -printf '%P\n' | LC_ALL=C sort \
        | tar -cf - --owner=0 --group=0 --numeric-owner --mtime=@1767225600 --no-recursion -T - ) \
      | xz --check=crc32 --lzma2=preset=9e,dict=1MiB > "$NEW/$n.tar.xz"
    ln -f "$NEW/$n.tar.xz" $PC/$n.tar.xz
    du -sk "$tmp/pkg" | cut -f1 > $PC/$n.kb
    echo "$key" > $PC/$n.key
  fi
  printf '%s\t%s/%s\t%s\n' "$n" "$(( $(stat -c %s "$NEW/$n.tar.xz") / 1024 + 1 ))" \
    "$(cat $PC/$n.kb)" "$(cat "$d/.deps" 2>/dev/null)" >> "$tmp/index"
  for m in "$d"usr/lib/python3.12/site-packages/*.dist-info/METADATA "$d"usr/lib/python3.12/site-packages/*.egg-info/PKG-INFO; do
    [ -f "$m" ] && awk -v p="$n" -v OFS='\t' '/^Name:/ && !nm { nm = $2 } /^Version:/ && !v { v = $2 } /^$/ { exit } END { if (nm != "") print nm, v, p }' "$m" >> "$tmp/pypi"
  done
done
cp "$tmp/pypi" "$NEW/pypi.txt"
awk -F'\t' -v OFS='\t' '
  FILENAME == ARGV[1] {
    n = d = $0
    sub(/ .*/, "", n)
    sub(/^[^ ]+ ?/, "", d)
    desc[n] = d
    order[++no] = n
    next
  }
  { line[$1] = $0; names[++nn] = $1 }
  END {
    for (i = 1; i <= no; i++) if (order[i] in line) { print line[order[i]], desc[order[i]]; done[order[i]] = 1 }
    for (i = 1; i <= nn; i++) if (!(names[i] in done)) print line[names[i]], ""
  }
' programs.txt "$tmp/index" > "$NEW/index.txt"
if ! python3 alpine.py --kt-index "$NEW/alpine.txt.gz" --desc "$NEW/index.txt" --alias py3-requests=python-requests --alias py3-pip=pip --rename py3-:python- 2> "$tmp/alpine.err"; then
  cat "$tmp/alpine.err" >&2
  if [ -f "$PKG/alpine.txt.gz" ]; then cp "$PKG/alpine.txt.gz" "$NEW/"; echo "alpine: беру прошлый индекс" >&2; fi
fi
rm -rf "$PKG.old"
if [ -d "$PKG" ]; then mv "$PKG" "$PKG.old"; fi
mv "$NEW" "$PKG"
rm -rf "$PKG.old"

echo "образ $hash, rootfs.cpio $(du -h "$OUT/rootfs.cpio" | cut -f1), пакетов: $(wc -l < "$PKG/index.txt"), $(du -sh "$PKG" | cut -f1)"
