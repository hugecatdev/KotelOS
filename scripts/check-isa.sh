#!/bin/sh
# Есть ли в ELF-файлах инструкции, которых v86 не умеет: SSSE3, SSE4, AVX и три из SSE3 -
# addsubps, addsubpd и lddqu (CPUID v86 сообщает SSE3, но на этих трёх процесс падает с SIGILL).
# Для своих сборок под один процессор, где кода «на выбор по CPUID» нет. Код выхода 1 - нашлись.
[ $# -gt 0 ] || { echo "использование: $0 файл..." >&2; exit 2; }
found=$(objdump -d --no-show-raw-insn "$@" | awk -F'\t' '
  NF >= 2 && $1 ~ /:$/ {
    split($2, w, " "); m = w[1]
    if (m ~ /^(addsubp[sd]|lddqu|palignr|pshufb|ph(add|sub)(w|d|sw)|pmaddubsw|pmulhrsw|pabs[bwd]|psign[bwd])$/ ||
        m ~ /^(pblendvb|blendvp[sd]|pblendw|blendp[sd]|dpp[sd]|insertps|extractps|pextr[bdq]|pinsr[bdq])$/ ||
        m ~ /^(pm(ax|in)(sb|sd|ud|uw)|pmov[sz]x(bw|bd|bq|wd|wq|dq)|pmuldq|pmulld|ptest|round[ps][sd])$/ ||
        m ~ /^(mpsadbw|phminposuw|packusdw|pcmp(eq|gt)q|crc32[bwlq]?|pcmp[ei]str[im]|movntdqa)$/ ||
        m ~ /^v/ || $2 ~ /%[yz]mm/)
      n[m]++
  }
  END { for (m in n) printf " %s(%d)", m, n[m] }')
[ -z "$found" ] && exit 0
echo "нет в v86:$found" >&2
exit 1
