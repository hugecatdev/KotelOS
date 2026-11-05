KT_RUN=/run/kt
KT_ID=$$
KT_REPLY=$KT_RUN/reply.$KT_ID
KT_PAGE="192.168.86.1 7771"
mkdir -p $KT_RUN

kt_meta() {
  case "$3" in
    --about) printf '%s - %s\n' "$1" "$2"; exit 0 ;;
    -h|--help)
      printf 'kt %s %s - %s\n' "${0##*/}" "$1" "$2"
      [ -z "$KT_HELP" ] || printf '%s\n' "$KT_HELP" | sed 's/^/  /'
      exit 0 ;;
  esac
}

kt_usage() {
  printf 'usage: kt %s %s\n' "${0##*/}" "$1" >&2
  exit 1
}

kt_b64() {
  if [ $# -gt 0 ]; then printf '%s' "$*"; else cat; fi | base64 | tr -d '\n'
}

kt_send() {
  rm -f "$KT_REPLY"
  printf '%s %s - %s\n' "$1" "$KT_ID" "$2" | kt-net $KT_PAGE > "$KT_REPLY.part"
  case $? in
    0) mv "$KT_REPLY.part" "$KT_REPLY" ;;
    2) rm -f "$KT_REPLY.part"; echo "kt: нет связи с браузером" >&2; exit 1 ;;
    *) rm -f "$KT_REPLY.part" ;;
  esac
}

kt_waitfile() {
  n=0
  while [ ! -f "$KT_REPLY" ]; do
    usleep 100000
    n=$((n + 1))
    if [ $n -ge "${1:-300}" ]; then
      echo "kt: браузер не ответил" >&2
      return 1
    fi
  done
}

kt_wait() {
  kt_waitfile "$1" || return 1
  cat "$KT_REPLY"
  rm -f "$KT_REPLY"
}

kt_status() {
  kt_waitfile "$1" || return 1
  st=$(head -c 1 "$KT_REPLY")
  if [ "$st" = 0 ]; then
    tail -c +2 "$KT_REPLY"
  else
    tail -c +2 "$KT_REPLY" >&2
  fi
  rm -f "$KT_REPLY"
  [ "$st" = 0 ]
}

kt_call() {
  kt_send "$1" "$2"
  kt_wait "$3"
}

kt_receive() {
  KT_DIR=$KT_RUN/in.$KT_ID.d
  rm -rf "$KT_DIR"
  mkdir -p "$KT_DIR"
  rm -f $KT_RUN/upload.done
  echo "$KT_DIR" > $KT_RUN/upload.dir
  trap 'rm -rf "$KT_DIR" $KT_RUN/upload.dir "$KT_REPLY" "$KT_REPLY.part"; exit 130' INT TERM
  kt_send "$1" "$2"
  while [ ! -f $KT_RUN/upload.done ]; do usleep 100000; done
  rm -f $KT_RUN/upload.done
  KT_FILE=$(find "$KT_DIR" -type f | head -n 1)
  KT_ERR=$(tail -c +2 "$KT_REPLY" 2>/dev/null)
  rm -f "$KT_REPLY"
}

kt_files() {
  case $(($1 % 100)) in
    11|12|13|14) echo "$1 файлов"; return ;;
  esac
  case $(($1 % 10)) in
    1) echo "$1 файл" ;;
    2|3|4) echo "$1 файла" ;;
    *) echo "$1 файлов" ;;
  esac
}

kt_get() {
  kt_receive fetch "$(kt_b64 "$1")"
  if [ -z "$KT_FILE" ]; then
    [ -z "$KT_ERR" ] || printf '%s\n' "$KT_ERR" >&2
    rm -rf "$KT_DIR"
    return 1
  fi
  mv "$KT_FILE" "$2"
  rm -rf "$KT_DIR"
}

kt_cd() {
  [ -n "$KT_SHELL" ] && echo "$1" > $KT_RUN/cd.$KT_SHELL
}
