if [ "$HOME" = / ]; then
  export HOME=/root USER=root LOGNAME=root
  [ "$PWD" = / ] && cd /root
fi
export KT_SHELL=$$
export MICROPYPATH=":/usr/lib/micropython:.frozen:~/.micropython/lib"
kt() {
  command kt "$@"
  set -- $? /run/kt/cd.$$
  if [ -f "$2" ]; then
    cd "$(cat "$2")"
    rm -f "$2"
  fi
  return $1
}
alias ll='ls -la'
alias la='ls -A'
alias help='kt'
