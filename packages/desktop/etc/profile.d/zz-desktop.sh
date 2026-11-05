# рабочий стол при входе в консоль: только интерактивный шелл на ttyS0, kt.exec (sh -c) и панели tmux - мимо.
# zz - последним, после kt.sh: HOME, MICROPYPATH и прочее окружение стол и его программы берут отсюда
case $- in
  *i*) [ "$(tty 2>/dev/null)" = /dev/ttyS0 ] && desktop ;;
esac
