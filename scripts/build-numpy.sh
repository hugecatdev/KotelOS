#!/bin/sh
set -e
cd "$(dirname "$0")/.."

# numpy под процессор v86: база SSE и SSE2, без вариантов кода под SSSE3..AVX-512. У Alpine база та же,
# но рядом лежат варианты под 18 наборов инструкций, а CPUID v86 даёт только MMX, SSE, SSE2, SSE3 и POPCNT:
# эти варианты никогда не выполняются, а занимают половину _multiarray_umath. Отдельных вариантов под SSE3
# у numpy нет, так что код в v86 тот же, что у сборки Alpine.
# -falign-loops=32: JIT v86 компилирует код постранично, и цикл через границу 4 КБ идёт в v86 в ~7 раз
# медленнее. Короткий цикл с адреса, кратного 32, на две страницы не ляжет (так было с cumsum: 30 мс -> 220).
VER=2.2.4
SHA=9ba03692a45d3eef66559efe1d1096c4b9b75c0986b5dff5530c378fb8331d4f
CYTHON=3.1.8
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SRC=$CACHE/numpy-$VER
B=$CACHE/numpy-build
TOOLS=$CACHE/numpy-tools  # Cython для хоста
ST=$CACHE/cpython-build/stage  # CPython из scripts/build-python.sh: заголовки и sysconfig цели
BLAS=$CACHE/openblas-dev  # из scripts/build-openblas.sh
LD=$PWD/build/packages/musl/lib/ld-musl-i386.so.1
OUT=$PWD/build/packages/python-numpy
SP=usr/lib/python3.12/site-packages

[ -x $TC/bin/i686-linux-musl-g++ ] || { echo "нет тулчейна, сначала scripts/build-busybox.sh"; exit 1; }
[ -x $ST/usr/bin/python3.12 ] || { echo "нет $ST, сначала scripts/build-python.sh"; exit 1; }
[ -f $BLAS/lib/pkgconfig/openblas.pc ] || { echo "нет $BLAS, сначала scripts/build-openblas.sh"; exit 1; }
[ -x $LD ] || { echo "нет build/packages/musl, сначала scripts/get-packages.sh"; exit 1; }
[ -f $CACHE/numpy-$VER.tar.gz ] || curl -fsSL https://files.pythonhosted.org/packages/source/n/numpy/numpy-$VER.tar.gz -o $CACHE/numpy-$VER.tar.gz
echo "$SHA  $CACHE/numpy-$VER.tar.gz" | sha256sum -c --quiet
if [ "$($TOOLS/bin/cython --version 2>&1)" != "Cython version $CYTHON" ]; then
  rm -rf $TOOLS
  python3 -m venv $TOOLS
  $TOOLS/bin/pip install -q "cython==$CYTHON"
fi
rm -rf $SRC $B
tar -xzf $CACHE/numpy-$VER.tar.gz -C $CACHE
mkdir -p $B

# питон цели запускается на хосте через загрузчик musl: meson берёт из него расширение имён, пути и Python.h
cat > $B/python <<EOF
#!/bin/sh
PYTHONHOME=$ST/usr exec $LD $ST/usr/bin/python3.12 "\$@"
EOF
chmod +x $B/python
cat > $B/cross.ini <<EOF
[binaries]
c = '$TC/bin/i686-linux-musl-gcc'
cpp = '$TC/bin/i686-linux-musl-g++'
ar = '$TC/bin/i686-linux-musl-gcc-ar'
strip = '$TC/bin/i686-linux-musl-strip'
pkg-config = 'pkg-config'
python = '$B/python'

[built-in options]
c_args = ['-march=pentium4', '-mtune=generic', '-mfpmath=sse', '-falign-loops=32']
cpp_args = ['-march=pentium4', '-mtune=generic', '-mfpmath=sse', '-falign-loops=32']
pkg_config_path = '$BLAS/lib/pkgconfig'

[properties]
longdouble_format = 'INTEL_EXTENDED_12_BYTES_LE'
needs_exe_wrapper = true

[host_machine]
system = 'linux'
cpu_family = 'x86'
cpu = 'i686'
endian = 'little'
EOF
printf "[binaries]\ncython = '%s'\n" "$TOOLS/bin/cython" > $B/native.ini

meson() { python3 $SRC/vendored-meson/meson/meson.py "$@"; }
meson setup $B/build $SRC --cross-file $B/cross.ini --native-file $B/native.ini --prefix=/usr --buildtype=release -Db_ndebug=if-release \
  -Dblas=openblas -Dlapack=openblas -Dallow-noblas=false -Dcpu-baseline="sse sse2" -Dcpu-dispatch=none \
  -Dtest-simd=[] -Dpython.bytecompile=-1 > $B/setup.log 2>&1 || { tail -40 $B/setup.log; exit 1; }
meson compile -C $B/build > $B/compile.log 2>&1 || { grep -m5 -A5 -i error $B/compile.log; tail -20 $B/compile.log; exit 1; }
# без тестов, _simd (он только для тестов) и заголовков: как пакет Alpine
meson install -C $B/build --destdir $B/stage --tags runtime,python-runtime > $B/install.log 2>&1 || { tail -20 $B/install.log; exit 1; }

rm -rf $OUT
mkdir -p $OUT/$SP
cp -a $B/stage/$SP/numpy $OUT/$SP/
rm -rf $OUT/$SP/numpy/_core/include $OUT/$SP/numpy/f2py/src
# numpy.testing при импорте берёт pd_NA из тестов numpy (а его импортирует scipy)
install -D -m 644 $SRC/numpy/_core/tests/_natype.py $OUT/$SP/numpy/_core/tests/_natype.py
find $OUT/$SP -name '*.pyi' -o -name py.typed | xargs -r rm -f
find $OUT/$SP -name '*.so' | while read -r f; do $TC/bin/i686-linux-musl-strip --strip-unneeded "$f"; done
find $OUT/$SP -name '*.so' -print0 | xargs -0 scripts/check-isa.sh || { echo "в numpy код, которого нет в v86"; exit 1; }

D=$OUT/$SP/numpy-$VER.dist-info
mkdir -p $D
cp $SRC/PKG-INFO $D/METADATA
cp $SRC/LICENSE.txt $D/
printf 'Wheel-Version: 1.0\nGenerator: meson\nRoot-Is-Purelib: false\nTag: cp312-cp312-linux_i686\n\n' > $D/WHEEL
printf '[array_api]\nnumpy = numpy\n\n[pyinstaller40]\nhook-dirs = numpy:_pyinstaller_hooks_dir\n\n[console_scripts]\nf2py = numpy.f2py.f2py2e:main\nnumpy-config = numpy._configtool:main\n' > $D/entry_points.txt
python3 - $OUT/$SP numpy-$VER.dist-info <<'EOF'
import base64, hashlib, os, sys
root, info = sys.argv[1:]
rows = []
for d, _, fs in os.walk(root):
    for f in sorted(fs):
        p = os.path.join(d, f)
        data = open(p, "rb").read()
        h = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append("%s,sha256=%s,%d" % (os.path.relpath(p, root), h, len(data)))
rows.append(info + "/RECORD,,")
open(os.path.join(root, info, "RECORD"), "w").write("\n".join(sorted(rows)) + "\n")
EOF
echo "minipython musl libgcc libstdc++ openblas" > $OUT/.deps
echo "numpy $VER (SSE2, без вариантов под AVX) -> build/packages/python-numpy ($(du -sh $OUT | cut -f1), _multiarray_umath $(du -h $OUT/$SP/numpy/_core/_multiarray_umath.*.so | cut -f1))"
