#!/bin/sh
# как x-twm, но в конце - кто сколько работал: тики (1/100 с) user и sys у Xorg, twm и xterm с детьми
twm -f /etc/X11/twmrc &
xeyes -geometry 180x135+560+40 &
xcalc -geometry +520+200 &
read u0 _ < /proc/uptime
time xterm -geometry 80x24+20+100 -e sh -c 'seq 1 6000; ls -lR /usr /etc; i=0; while [ $i -lt 40 ]; do clear; ls -l /usr/bin; i=$((i+1)); done'
read u1 _ < /proc/uptime
echo "xterm от $u0 до $u1"
for p in Xorg twm xeyes xcalc; do
  set -- $(cat /proc/$(pidof $p)/stat)
  echo "$p user ${14} sys ${15}"
done
