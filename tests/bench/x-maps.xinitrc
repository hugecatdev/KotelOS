#!/bin/sh
# сессия для tests/gprof.py: как x-twm, но по ходу печатает карты памяти Xorg, twm и xterm
twm -f /etc/X11/twmrc &
xeyes -geometry 180x135+560+40 &
xcalc -geometry +520+200 &
xterm -geometry 80x24+20+100 -e sh -c 'seq 1 6000; ls -lR /usr /etc; i=0; while [ $i -lt 40 ]; do clear; ls -l /usr/bin; i=$((i+1)); done' &
xp=$!
usleep 1500000
for p in Xorg twm; do
  echo "MAPS $p"
  cat /proc/$(pidof $p)/maps
done
echo "MAPS xterm"
cat /proc/$xp/maps
echo "MAPS -"
wait $xp
