#!/bin/sh
set -e
cd "$(dirname "$0")"
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

./build-python.sh

python3 alpine.py py3-pytelegrambotapi --skip py3-requests --skip python3
T=packages/py3-pytelegrambotapi/$P/site-packages/telebot
rm -rf $T/async_telebot.py $T/asyncio_* $T/ext/aio
sed -i 's/^import ssl$/try:\n    import ssl\nexcept ImportError:\n    ssl = None/' $T/__init__.py
rm -rf packages/python-telebot
mv packages/py3-pytelegrambotapi packages/python-telebot
echo "python3 python-requests" > packages/python-telebot/.deps

ln -sf micropython packages/micropython/usr/bin/py
echo "musl libffi" > packages/micropython/.deps
ln -sf lua5.4 packages/lua5.4/usr/bin/lua
echo "musl tcc-libs tcc-libs-static tcc-dev musl-dev" > packages/tcc/.deps
mkdir -p packages/tcc/usr/lib
ln -sfn . packages/tcc/usr/lib/i386-linux-gnu
mkdir -p packages/nano/etc/profile.d packages/nano/usr/share
rm -rf packages/nano/usr/share/nano
mv packages/nano-syntax/usr/share/nano packages/nano/usr/share/nano
rm -rf packages/nano-syntax packages/nano/usr/share/nano/extra
sed -i 's|^# include /usr/share/nano/\*\.nanorc$|include /usr/share/nano/*.nanorc|' packages/nano/etc/nanorc
echo "export EDITOR=nano" > packages/nano/etc/profile.d/nano.sh
mkdir -p packages/micro/etc/profile.d
echo "export EDITOR=micro" > packages/micro/etc/profile.d/micro.sh
ln -sf php83 packages/php83/usr/bin/php
rm -f packages/libevent/usr/lib/libevent_openssl*
echo "musl" > packages/libevent/.deps

python3 alpine.py $(python3 pyset.py --skip py3-requests --skip py3-pip) py3-numpy py3-pandas py3-scipy py3-matplotlib \
  --keep-existing --alias py3-requests=python-requests --alias py3-pip=pip --rename py3-:python-
sed -i 's/\bpython3\b/minipython/' packages/python-numpy/.deps
mpl=packages/python-matplotlib/usr/lib/python3.12/site-packages
patch -d $mpl -p1 -R -s -f --dry-run < matplotlib.patch > /dev/null 2>&1 || patch -d $mpl -p1 -s < matplotlib.patch
./build-openblas.sh
python3 jdk8.py
