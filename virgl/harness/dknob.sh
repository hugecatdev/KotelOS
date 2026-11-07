#!/bin/sh
# В машине (копировать в /usr/bin/dknob): вариант Designer - время до окна и тики (Designer, Xorg) за
# запуск и 40 смен размера окна (xresize). Варианты - переменные окружения:
#   dknob ИМЯ [ПЕРЕМЕННАЯ=ЗНАЧЕНИЕ ...]
export DISPLAY=:0
name=$1; shift
env "$@" designer > /tmp/d.log 2>&1 &
D=$!
printf '%-12s ' "$name"
xresize designer 20 $D $(pidof Xorg) | grep -v DONE | tr '\n' ' '
echo
kill $D; wait $D 2>/dev/null; sleep 3
