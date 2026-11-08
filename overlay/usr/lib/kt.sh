KT_RUN=/run/kt
KT_ID=$$
KT_REPLY=$KT_RUN/reply.$KT_ID
KT_PAGE="192.168.86.1 7771"
KT_MOD=${0##*/}
# ответ страницы kt ждёт, пока соединение с ней живо. Оборвалось (машину восстановили из сохранения
# посреди запроса, новый агент гасит kt-net) - ответ придёт через агента, его - не дольше KT_WAIT секунд
KT_WAIT=30
mkdir -p $KT_RUN

# kt_meta "<аргументы>" "описание" "$@": --help печатает KT_HELP - строки «форма  что делает» (между ними
# два пробела и больше), колонки выравниваются сами; строка без двойного пробела - примечание
kt_meta() {
  case "$3" in
    --about) printf '%s - %s\n' "$1" "$2"; exit 0 ;;
    -h|--help)
      printf 'kt %s%s - %s\n' "$KT_MOD" "${1:+ $1}" "$2"
      [ -z "$KT_HELP" ] || printf '%s\n' "$KT_HELP" | awk '
        function len(s, t) { t = s; return length(s) - gsub(/[\200-\277]/, "", t) }
        { l[NR] = $0; if (match($0, /  +/)) { a[NR] = substr($0, 1, RSTART - 1); b[NR] = substr($0, RSTART + RLENGTH); if (len(a[NR]) > w) w = len(a[NR]) } }
        END {
          for (i = 1; i <= NR; i++) {
            if (!(i in a)) { print "  " l[i]; continue }
            p = ""
            for (j = len(a[i]); j < w + 2; j++) p = p " "
            print "  " a[i] p b[i]
          }
        }'
      exit 0 ;;
  esac
}

kt_usage() {
  printf 'usage: kt %s%s\n' "$KT_MOD" "${1:+ $1}" >&2
  exit 1
}

# ошибка - в stderr с именем модуля: «kt cfg: ...»
kt_err() {
  printf 'kt %s: %s\n' "$KT_MOD" "$*" >&2
}

kt_die() {
  kt_err "$@"
  exit 1
}

kt_b64() {
  if [ $# -gt 0 ]; then printf '%s' "$*"; else cat; fi | base64 | tr -d '\n'
}

# kt_send команда арг [-]: запрос к странице, с - тело запроса из stdin; ответ - в $KT_REPLY
kt_send() {
  rm -f "$KT_REPLY"
  if [ "$3" = - ]; then
    { printf '%s %s - %s\n' "$1" "$KT_ID" "$2"; cat; }
  else
    printf '%s %s - %s\n' "$1" "$KT_ID" "$2"
  fi | kt-net $KT_PAGE > "$KT_REPLY.part"
  case $? in
    0) mv "$KT_REPLY.part" "$KT_REPLY" ;;
    2) rm -f "$KT_REPLY.part"; kt_die "нет связи с браузером" ;;
    *) rm -f "$KT_REPLY.part" ;;
  esac
}

# kt_until файл: ждать файл от агента, не дольше KT_WAIT секунд
kt_until() {
  local n=$((KT_WAIT * 10))
  while [ ! -f "$1" ]; do
    n=$((n - 1))
    [ $n -gt 0 ] || kt_die "браузер не ответил"
    usleep 100000
  done
}

# ответ страницы: первый байт 0 - успех, текст - в stdout; иначе ошибка - в stderr (без «Error: »), код 1
kt_status() {
  local st msg
  kt_until "$KT_REPLY"
  st=$(head -c 1 "$KT_REPLY")
  if [ "$st" = 0 ]; then
    tail -c +2 "$KT_REPLY"
  else
    msg=$(tail -c +2 "$KT_REPLY")
    msg=${msg#Error: }
    [ -n "$msg$st" ] || msg="браузер не ответил"
    [ -z "$msg" ] || kt_err "$msg"
  fi
  rm -f "$KT_REPLY"
  [ "$st" = 0 ]
}

# kt_page команда [арг]: запрос и ответ со статусом
kt_page() {
  kt_send "$1" "$2"
  kt_status
}

# kt_js код [аргумент...]: код - выражение или функция JavaScript, аргументы уходят в функцию строками
kt_js() {
  local a x
  a=$(kt_b64 "$1")
  shift
  for x in "$@"; do a="$a $(kt_b64 "$x")"; done
  kt_page js "$a"
}

# kt_ask вопрос: да - код 0; ответ читается со stdin, конец ввода - нет
kt_ask() {
  local a
  printf '%s [y/N] ' "$1" >&2
  read -r a || echo >&2
  case "$a" in y|Y|yes|д|Д|да) return 0 ;; esac
  return 1
}

# kt_name имя [длина]: имя снимка, архива, машины kt share
kt_name() {
  case $1 in
    ""|-*|*[!A-Za-z0-9._-]*) ;;
    *) [ ${#1} -le "${2:-32}" ] && return 0 ;;
  esac
  kt_die "имя - латинские буквы, цифры, . _ -, до ${2:-32} знаков: $1"
}

kt_size() {
  awk -v n="$1" 'BEGIN { if (n < 1048576) printf "%d КБ\n", (n + 1023) / 1024; else printf "%.1f МБ\n", n / 1048576 }'
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

# kt_receive команда арг: страница присылает файл в $KT_DIR (paste, fetch); $KT_FILE - он,
# ошибка - в stderr и код 1
kt_receive() {
  KT_DIR=$KT_RUN/in.$KT_ID.d
  rm -rf "$KT_DIR"
  mkdir -p "$KT_DIR"
  rm -f $KT_RUN/upload.done
  echo "$KT_DIR" > $KT_RUN/upload.dir
  trap 'rm -rf "$KT_DIR" $KT_RUN/upload.dir "$KT_REPLY" "$KT_REPLY.part"; exit 130' INT TERM
  kt_send "$1" "$2"
  kt_until $KT_RUN/upload.done
  rm -f $KT_RUN/upload.done
  KT_FILE=$(find "$KT_DIR" -type f | head -n 1)
  kt_status > /dev/null && [ -n "$KT_FILE" ]
}

kt_get() {
  if ! kt_receive fetch "$(kt_b64 "$1")"; then
    rm -rf "$KT_DIR"
    return 1
  fi
  mv "$KT_FILE" "$2"
  rm -rf "$KT_DIR"
}

kt_cd() {
  [ -n "$KT_SHELL" ] && echo "$1" > $KT_RUN/cd.$KT_SHELL
}
