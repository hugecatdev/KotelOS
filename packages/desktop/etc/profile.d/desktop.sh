# рабочий стол при входе в консоль, как startx на tty1: kt.exec (sh -c) и панели tmux - мимо
case $- in
  *i*) [ "$(tty 2>/dev/null)" = /dev/ttyS0 ] && desktop ;;
esac
