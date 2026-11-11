#!/bin/sh
# сессия для tests/xpair.py --load tk: программы на тулкитах (FOX: calculator и adie, GTK 3: galculator).
# Каждая: запуск до видимого окна, потом окно пять раз меняет размер (перерисовка; ждём, пока
# программа затихнет) и закрывается. Всё - дважды: второй раз файлы уже в кэше страниц
twm -f /etc/X11/twmrc &
# программа затихла: спит и не набрала процессорного времени за два опроса подряд
settle() {
  last=
  while :; do
    set -- $(cat /proc/$pid/stat 2>/dev/null) || return
    [ "$3" = S ] && [ "${14} ${15}" = "$last" ] && return
    last="${14} ${15}"
    usleep 30000
  done
}
run() {
  class=$1
  shift
  "$@" &
  pid=$!
  win=$(timeout 25 xdotool search --sync --onlyvisible "$class" | head -n 1)
  [ -n "$win" ] || echo "$class: окна нет"
  settle
  i=0
  while [ $i -lt 5 ] && [ -n "$win" ]; do
    xdotool windowsize $win $((420 + i * 40)) $((360 + i * 30))
    settle
    i=$((i + 1))
  done
  read t _ < /proc/uptime
  echo "$class $t"
  kill $pid
  wait $pid 2>/dev/null
}
for n in 1 2; do
  run calculator calculator
  run adie adie /etc/X11/twmrc
  run galculator galculator
done
true
