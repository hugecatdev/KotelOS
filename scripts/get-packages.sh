#!/bin/sh
set -e
cd "$(dirname "$0")/.."
P=usr/lib/python3.12

V=usr/share/vim/vim91
K=
for f in syntax synload syncolor nosyntax manual python sh c cpp lua javascript typescript json html css \
  markdown vim yaml toml sql make diff conf dosini awk sed xml help text go rust java ruby php perl \
  dockerfile gitcommit gitconfig gitrebase man; do
  K="$K --keep $V/syntax/$f.vim"
done

python3 alpine.py micropython sqlite libpanelw jq htop bash nano nano-syntax micro lua5.4 tcc tcc-libs-static tcc-dev musl-dev \
  vim helix tmux fzf make ruby php83 perl janet \
  nodejs cmatrix sl figlet cbonsai nyancat \
  --skip mpdecimal --skip so:libmpdec.so.4 \
  --skip gdbm --skip so:libgdbm_compat.so.4 --skip so:libgdbm.so.6 --skip pkgconfig \
  --keep "usr/lib/tcc/*" \
  --drop "$V/doc/*" --drop "$V/spell/*" --drop "$V/pack/*" --drop "$V/tutor/*" --drop "$V/lang/*" \
  --drop "$V/print/*" --drop "$V/tools/*" --drop "$V/macros/*" --drop "$V/keymap/*" --drop "$V/syntax/*" \
  --drop "$V/*menu.vim" --drop "$V/mswin.vim" --drop "$V/evim.vim" --drop "$V/gvimrc_example.vim" \
  --keep "$V/syntax/shared/*" $K

python3 alpine.py musl-dev --keep "usr/lib/lib[!c]*.a" --keep "usr/lib/libcrypt.a"

scripts/build-python.sh

python3 alpine.py py3-pytelegrambotapi --skip py3-requests --skip python3
T=build/packages/py3-pytelegrambotapi/$P/site-packages/telebot
rm -rf $T/async_telebot.py $T/asyncio_* $T/ext/aio
sed -i 's/^import ssl$/try:\n    import ssl\nexcept ImportError:\n    ssl = None/' $T/__init__.py
rm -rf build/packages/python-telebot
mv build/packages/py3-pytelegrambotapi build/packages/python-telebot
echo "python3 python-requests" > build/packages/python-telebot/.deps

ln -sf micropython build/packages/micropython/usr/bin/py
echo "musl libffi" > build/packages/micropython/.deps
ln -sf lua5.4 build/packages/lua5.4/usr/bin/lua
echo "musl tcc-libs tcc-libs-static tcc-dev musl-dev" > build/packages/tcc/.deps
mkdir -p build/packages/tcc/usr/lib
ln -sfn . build/packages/tcc/usr/lib/i386-linux-gnu
mkdir -p build/packages/nano/etc/profile.d build/packages/nano/usr/share
rm -rf build/packages/nano/usr/share/nano
mv build/packages/nano-syntax/usr/share/nano build/packages/nano/usr/share/nano
rm -rf build/packages/nano-syntax build/packages/nano/usr/share/nano/extra
sed -i 's|^# include /usr/share/nano/\*\.nanorc$|include /usr/share/nano/*.nanorc|' build/packages/nano/etc/nanorc
echo "export EDITOR=nano" > build/packages/nano/etc/profile.d/nano.sh
mkdir -p build/packages/micro/etc/profile.d
echo "export EDITOR=micro" > build/packages/micro/etc/profile.d/micro.sh
ln -sf php83 build/packages/php83/usr/bin/php
rm -f build/packages/libevent/usr/lib/libevent_openssl*
echo "musl" > build/packages/libevent/.deps

# chawan есть только с v3.24. Его http/https/gemini/sftp - cgi-bin/ssl на openssl
# и сырых сокетах, а наружу из v86 ходит только fetch браузера: ssl и его библиотеки
# (~6 МБ в памяти) не берём, http и https даёт пакет chawan-fetch
C=usr/libexec/chawan/cgi-bin
python3 alpine.py chawan --branch v3.24 \
  --skip so:libssl.so.3 --skip so:libcrypto.so.3 --skip so:libssh2.so.1 --skip so:libbrotlidec.so.1 \
  --drop $C/ssl --drop $C/http --drop $C/https --drop $C/gemini --drop $C/sftp
echo "musl chawan-fetch" > build/packages/chawan/.deps

python3 alpine.py $(python3 scripts/pyset.py --skip py3-requests --skip py3-pip) py3-numpy py3-pandas py3-scipy py3-matplotlib \
  --keep-existing --alias py3-requests=python-requests --alias py3-pip=pip --rename py3-:python-
sed -i 's/\bpython3\b/minipython/' build/packages/python-numpy/.deps
mpl=build/packages/python-matplotlib/usr/lib/python3.12/site-packages
patch -d $mpl -p1 -R -s -f --dry-run < patches/matplotlib.patch > /dev/null 2>&1 || patch -d $mpl -p1 -s < patches/matplotlib.patch
scripts/build-openblas.sh
python3 scripts/jdk8.py
