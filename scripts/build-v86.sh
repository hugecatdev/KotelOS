#!/bin/sh
# v86 из исходников: copy/v86 на коммите REV + patches/v86/*.patch -> vendor/v86/
# Нужны clang с целью wasm32 (той же мажорной версии LLVM, что у Rust ниже:
# softfloat и zstd собираются в LTO-биткод), java, node, make, curl.
# Rust с wasm32 и Closure Compiler скачиваются сами в .cache/.
set -e
cd "$(dirname "$0")/.."

REV=${REV:-315b2b0b758703ef0e6cc7b4088d6068f83f3c20}  # master 2026-10-30
RUST=1.99.1
CLOSURE_VER=v20210601  # Makefile v86: новее не брать, google/closure-compiler#3972
CACHE=.cache
SRC=$CACHE/v86-$REV
OUT=${OUT:-vendor/v86}
# устройства по выбору (patches/v86/06): floppy ide sound virtio 9p parallel acpi modem multiboot
# virtio_gpu, all - все; по умолчанию virtio_gpu (3D для программ OpenGL, patches/v86/10), остальные
# ядру не нужны. Пример: DEVICES="virtio_gpu ide sound" scripts/build-v86.sh, без них - DEVICES=
DEVICES=${DEVICES-virtio_gpu}
[ "$DEVICES" = all ] && DEVICES="floppy ide sound virtio 9p parallel acpi modem multiboot virtio_gpu"
case " $DEVICES " in *" floppy "* | *" sound "*) DEVICES="$DEVICES dma" ;; esac

mkdir -p $CACHE

export RUSTUP_HOME="$PWD/$CACHE/rust/rustup" CARGO_HOME="$PWD/$CACHE/rust/cargo" RUSTUP_TOOLCHAIN=$RUST
if [ ! -x "$CARGO_HOME/bin/rustup" ]; then
  mkdir -p $CACHE/rust
  curl -fsSL https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init -o $CACHE/rust/rustup-init
  chmod +x $CACHE/rust/rustup-init
  $CACHE/rust/rustup-init -y -q --no-modify-path --profile minimal --default-toolchain none
fi
"$CARGO_HOME/bin/rustup" toolchain list | grep -q "^$RUST-" ||
  "$CARGO_HOME/bin/rustup" -q toolchain install $RUST --profile minimal --target wasm32-unknown-unknown
export PATH="$CARGO_HOME/bin:$PATH"

JAR=$CACHE/closure-compiler-$CLOSURE_VER.jar
[ -f $JAR ] || curl -fsSL https://repo1.maven.org/maven2/com/google/javascript/closure-compiler/$CLOSURE_VER/closure-compiler-$CLOSURE_VER.jar -o $JAR

rm -rf $SRC
[ -f $CACHE/v86-$REV.tar.gz ] || curl -fsSL https://github.com/copy/v86/archive/$REV.tar.gz -o $CACHE/v86-$REV.tar.gz
tar -xzf $CACHE/v86-$REV.tar.gz -C $CACHE
for p in patches/v86/*.patch; do
  if [ -f "$p" ]; then patch -s -d $SRC -p1 < "$p"; fi
done
python3 cond.py "$DEVICES" $SRC/src/*.js $SRC/src/browser/*.js $SRC/lib/*.js
mkdir -p $SRC/closure-compiler
ln -f $JAR $SRC/closure-compiler/compiler.jar

# без отладки и секции имён: 1.6 МБ вместо 2.0, в бандле это gzip 300 КБ вместо 377
# PROFILER=1 - со счётчиками JIT и опкодов (profiler_stat_get, get_opstats_buffer; tests/jitprof.py):
# медленнее, только для замеров
# NAMES=1 - с секцией имён функций (профиль вкладки показывает имена Rust; wasm больше)
WASM=build/v86.wasm
[ -n "$PROFILER" ] && WASM=with-profiler
STRIP=symbols STRIP_DEBUG=true
[ -n "$NAMES" ] && STRIP=debuginfo STRIP_DEBUG=false
CARGO_PROFILE_RELEASE_STRIP=$STRIP make -C $SRC -j"$(nproc)" STRIP_DEBUG=$STRIP_DEBUG build/libv86.js $WASM \
  > $CACHE/v86-build.log 2>&1 || { tail -30 $CACHE/v86-build.log; exit 1; }

mkdir -p "$OUT"
cp $SRC/build/libv86.js $SRC/build/v86.wasm $SRC/bios/seabios.bin $SRC/bios/vgabios.bin "$OUT/"
echo "v86 ${REV%"${REV#????????}"} -> $OUT: libv86.js $(du -h "$OUT/libv86.js" | cut -f1), v86.wasm $(du -h "$OUT/v86.wasm" | cut -f1), устройства: ${DEVICES:-только нужные ядру}"
