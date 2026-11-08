#!/bin/sh
# В машине: куда уходит процессор гостя, пока идёт GL-программа (10 с после 6 с разгона): её user
# (сама программа и Mesa, которая кодирует команды), её system (ядро и синхронная работа vrend на
# странице - выход в порт уведомления virtio ждёт её), Xorg (кадр картинкой: XPutImage), прочее и
# простой (ожидание заборов WebGL), в % от прошедшего времени (/proc/uptime): тики /proc/stat под
# нагрузкой хоста теряются (таймер v86 опаздывает), а время процессов ядро считает по точным часам.
#   glsplit ПРОГРАММА [аргументы]   (запуск из /usr/share/mesa-demos; копировать в /usr/bin/glsplit)
cd /usr/share/mesa-demos 2>/dev/null
DISPLAY=:0 "$@" > /tmp/glsplit.log 2>&1 &
P=$!
sleep 6
X=$(pidof Xorg)
snap() {
  cut -d' ' -f1 /proc/uptime
  awk '{ print $14, $15 }' /proc/$P/stat
  awk '{ print $14, $15 }' /proc/$X/stat
}
snap > /tmp/glsplit.a
sleep 10
snap > /tmp/glsplit.b
kill $P
paste -d' ' /tmp/glsplit.a /tmp/glsplit.b | awk '
  NR == 1 { t = ($2 - $1) * 100 }
  NR == 2 { au = $3 - $1; as = $4 - $2 }
  NR == 3 { x = $3 + $4 - $1 - $2 }
  END { if (!t) t = 1
        printf "программа user %d%% system %d%% | Xorg %d%% | остальное и простой %d%%\n",
               100 * au / t, 100 * as / t, 100 * x / t, 100 * (t - au - as - x) / t }'
grep -iE "fps|frame rate" /tmp/glsplit.log | tail -1
