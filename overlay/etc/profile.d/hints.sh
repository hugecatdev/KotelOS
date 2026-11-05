w=7
[ -d /root/examples ] || w=20
hint() {
  printf "  \033[36m%-${w}s\033[0m\033[90m%s\033[0m\n" "$1" "$2"
}
hint kt "команды браузера"
hint "kt pkg" "пакеты"
[ $w = 20 ] && hint "kt pkg add examples" "примеры"
echo
unset w
unset -f hint
