#!/bin/sh
# В машине: на что уходит процессор, пока идёт GL-программа (по умолчанию glxgears через virpipe).
# Тики процессов за 10 с и общее время процессора (user/system/idle) из /proc/stat.
#   cpu-split.sh [драйвер]
DRV=${1:-virpipe}
DISPLAY=:0 GALLIUM_DRIVER=$DRV glxgears -geometry 290x290+505+20 > /tmp/gears.log 2>&1 &
G=$!
sleep 4
snap() {
  for p in $G $(pidof Xorg) $(pidof vtest-bridge); do
    awk '{ print $2, $14 + $15 }' /proc/$p/stat
  done
  head -1 /proc/stat
}
snap > /tmp/cpu.a
sleep 10
snap > /tmp/cpu.b
kill $G
paste /tmp/cpu.a /tmp/cpu.b | awk '
  /^cpu/ { u = $13 - $2 + $14 - $3; s = $15 - $4 + $17 - $6 + $18 - $7; i = $16 - $5 + $17 * 0;
           printf "всего: user %d system %d idle %d (тиков)\n", u, s, i; next }
  { printf "%s %d\n", $1, $4 - $2 }'
tail -1 /tmp/gears.log
