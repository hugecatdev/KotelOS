#!/bin/sh
# сессия для tests/bench.py --x: всё, что делает бандл xorg при открытии, плюс прокрутка и
# перерисовка в xterm; xterm закончил - сессия закрывается, startx возвращается
twm -f /etc/X11/twmrc &
xeyes -geometry 180x135+560+40 &
xcalc -geometry +520+200 &
xterm -geometry 80x24+20+100 -e sh -c 'seq 1 6000; ls -lR /usr /etc; i=0; while [ $i -lt 40 ]; do clear; ls -l /usr/bin; i=$((i+1)); done'
