#!/bin/sh
set -e
cd "$(dirname "$0")"

VER=3.12.15
CACHE=$PWD/.cache
TC=$CACHE/i686-linux-musl-cross
SRC=$CACHE/Python-$VER
HOST=$CACHE/cpython-host
SR=$CACHE/pysysroot
B=$CACHE/cpython-build
LD=$PWD/packages/musl/lib/ld-musl-i386.so.1
ARCH="-march=pentium4 -mtune=generic -mfpmath=sse -fno-asynchronous-unwind-tables -fno-unwind-tables"
LTO="-fno-semantic-interposition -flto -ffat-lto-objects -flto-partition=none"

[ -x $TC/bin/i686-linux-musl-gcc ] || { echo "нет тулчейна, сначала ./build-busybox.sh"; exit 1; }
[ -x $LD ] || { echo "нет packages/musl, сначала ./get-packages.sh"; exit 1; }
[ -f $CACHE/Python-$VER.tar.xz ] || curl -fsSL https://www.python.org/ftp/python/$VER/Python-$VER.tar.xz -o $CACHE/Python-$VER.tar.xz
rm -rf $SRC
tar -xJf $CACHE/Python-$VER.tar.xz -C $CACHE
sed -i 's/case "$build_os" in/case "$host_os" in/' $SRC/configure
python3 - $SRC/Lib/encodings/idna.py <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read()
old = "import stringprep, re, codecs\nfrom unicodedata import ucd_3_2_0 as unicodedata\n"
assert old in s and "def nameprep(label):\n" in s
s = s.replace(old, "import re, codecs\n").replace(
    "def nameprep(label):\n", "def nameprep(label):\n    import stringprep\n    from unicodedata import ucd_3_2_0 as unicodedata\n")
open(p, "w").write(s)
EOF
python3 pymin.py $SRC/Modules/getpath.py $(for m in importlib/_bootstrap importlib/_bootstrap_external zipimport abc codecs io \
  _collections_abc _sitebuiltins genericpath ntpath posixpath os site stat importlib/util importlib/machinery runpy; do echo $SRC/Lib/$m.py; done)
python3 - $SRC <<'EOF'
import re
import sys
p = sys.argv[1] + "/configure"
s = open(p).read()
old = "'$(PYTHON_FOR_FREEZE) $(srcdir)/Programs/_freeze_module.py'"
assert s.count(old) == 2
open(p, "w").write(s.replace(old, "'$(PYTHON_FOR_FREEZE) -X no_debug_ranges $(srcdir)/Programs/_freeze_module.py'"))
p = sys.argv[1] + "/Python/frozen.c"
s = open(p).read()
s, n = re.subn(r'#include "frozen_modules/[^"]+\.h"\n', "", s)
s, m = re.subn(r"(_Py_M__\w+), \(int\)sizeof\(\1\)", "NULL, 0", s)
assert n == 23 and m == 29 and "_Py_M__" not in s.split("/* End includes */")[1]
open(p, "w").write(s)
EOF

if [ ! -x $HOST/inst/bin/python3.12 ]; then
  rm -rf $HOST
  mkdir -p $HOST
  ( cd $HOST && $SRC/configure --prefix=$HOST/inst --without-ensurepip > conf.log 2>&1 \
    && make -j"$(nproc)" > make.log 2>&1 && make install > inst.log 2>&1 ) || { tail -30 $HOST/make.log; exit 1; }
fi

rm -rf $SR
python3 - "$SR" <<'EOF'
import sys
import alpine
pkgs, _ = alpine.index()
for n in ("zlib-dev zlib-static bzip2-dev bzip2-static xz-dev xz-static libffi-dev readline-dev readline libhistory "
          "ncurses-dev libncursesw libpanelw sqlite-dev sqlite-libs").split():
    f = f"{n}-{pkgs[n]['ver']}.apk"
    alpine.extract(alpine.fetch(f"{alpine.MIRROR}/{pkgs[n]['repo']}/x86/{f}", f"{alpine.CACHE}/apk/{f}"), sys.argv[1], [], [])
EOF
rm -f $SR/usr/lib/libz.so $SR/usr/lib/libbz2.so $SR/usr/lib/liblzma.so $SR/usr/lib/libffi.so

rm -rf $B
mkdir -p $B/Modules
cat > $B/Modules/Setup.local <<'EOF'
*shared*
readline readline.c
unicodedata unicodedata.c
_multibytecodec cjkcodecs/multibytecodec.c
_codecs_cn cjkcodecs/_codecs_cn.c
_codecs_hk cjkcodecs/_codecs_hk.c
_codecs_iso2022 cjkcodecs/_codecs_iso2022.c
_codecs_jp cjkcodecs/_codecs_jp.c
_codecs_kr cjkcodecs/_codecs_kr.c
_codecs_tw cjkcodecs/_codecs_tw.c
pyexpat pyexpat.c
_elementtree _elementtree.c
_ctypes _ctypes/_ctypes.c _ctypes/callbacks.c _ctypes/callproc.c _ctypes/stgdict.c _ctypes/cfield.c
_decimal _decimal/_decimal.c
_asyncio _asynciomodule.c
_multiprocessing _multiprocessing/multiprocessing.c _multiprocessing/semaphore.c
_posixshmem _multiprocessing/posixshmem.c
_lsprof _lsprof.c rotatingtree.c
_bz2 _bz2module.c
_lzma _lzmamodule.c
_curses _cursesmodule.c
_curses_panel _curses_panel.c
_sqlite3 _sqlite/blob.c _sqlite/connection.c _sqlite/cursor.c _sqlite/microprotocols.c _sqlite/module.c _sqlite/prepare_protocol.c _sqlite/row.c _sqlite/statement.c _sqlite/util.c
*disabled*
_xxsubinterpreters
_xxinterpchannels
audioop
_crypt
nis
spwd
ossaudiodev
_dbm
_gdbm
_uuid
_ssl
_hashlib
_tkinter
xxsubtype
_scproxy
xxlimited
xxlimited_35
EOF
printf 'ac_cv_file__dev_ptmx=yes\nac_cv_file__dev_ptc=no\nac_cv_working_tzset=yes\nac_cv_broken_sem_getvalue=no\n' > $B/config.site

export PATH="$TC/bin:$PATH"
cd $B
CONFIG_SITE=$B/config.site MODULE_BUILDTYPE=static \
PKG_CONFIG_LIBDIR=$SR/usr/lib/pkgconfig PKG_CONFIG_SYSROOT_DIR=$SR \
ZLIB_LIBS="-lz -lssp_nonshared" BZIP2_LIBS="-lbz2 -lssp_nonshared" LIBLZMA_LIBS="-llzma -lssp_nonshared" \
LIBFFI_LIBS="-lffi -lssp_nonshared" \
CC=i686-linux-musl-gcc AR=i686-linux-musl-gcc-ar RANLIB=i686-linux-musl-gcc-ranlib READELF=i686-linux-musl-readelf \
OPT="-DNDEBUG -O2 -Wall" CFLAGS="$ARCH -fno-pie" CPPFLAGS="-I$SR/usr/include" \
LDFLAGS="$ARCH -L$SR/usr/lib -Wl,-rpath-link,$SR/usr/lib" \
$SRC/configure --prefix=/usr --host=i686-linux-musl --build=x86_64-pc-linux-gnu --with-build-python=$HOST/inst/bin/python3.12 \
  --disable-shared --without-static-libpython --without-ensurepip --disable-test-modules --without-doc-strings \
  --with-computed-gotos --enable-ipv6 --enable-loadable-sqlite-extensions --enable-optimizations --with-lto \
  > conf.log 2>&1 || { tail -30 conf.log; exit 1; }
make -j"$(nproc)" profile-opt \
  PGO_PROF_GEN_FLAG="-fprofile-generate -Wl,--dynamic-linker=$LD -Wl,-rpath,$SR/usr/lib" \
  LINKFORSHARED="-Xlinker -export-dynamic -no-pie" CONFIGURE_LDFLAGS_NODIST="$LTO" \
  CONFIGURE_CFLAGS_NODIST="$LTO -std=c11 -Wextra -Wno-unused-parameter -Wno-missing-field-initializers -Wstrict-prototypes -Werror=implicit-function-declaration -fvisibility=hidden" \
  > make.log 2>&1 || { tail -30 make.log; exit 1; }
rm -rf stage
make install DESTDIR=$B/stage LINKFORSHARED="-Xlinker -export-dynamic -no-pie" > inst.log 2>&1 || { tail -30 inst.log; exit 1; }
cd - > /dev/null

python3 pysplit.py $B/stage --strip $TC/bin/i686-linux-musl-strip
printf '' | i686-linux-musl-gcc -shared -nostdlib -Wl,-soname,libpython3.12.so.1.0 -o packages/python3/usr/lib/libpython3.12.so.1.0 -x c -
i686-linux-musl-strip packages/python3/usr/lib/libpython3.12.so.1.0
