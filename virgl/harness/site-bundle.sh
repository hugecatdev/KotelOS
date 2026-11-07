#!/bin/sh
# Бандл сайта по описанию bundles/ИМЯ.txt, как release.py, но в build/virgl-serve/ИМЯ.html, а не в
# site/ (общие images/, site/repo и vendor/ только читаются). Раздаёт его сервер build/virgl-serve
# (ссылка repo -> site/repo: в машине работает kt pkg add).
#   virgl/harness/site-bundle.sh ИМЯ [ключи bundle.py ...]
set -e
cd "$(dirname "$0")/../.."
name=$1
shift
python3 - "$name" "$@" <<'EOF'
import shlex
import subprocess
import sys

name, extra = sys.argv[1], sys.argv[2:]
args = shlex.split(open("bundles/%s.txt" % name).read(), comments=True)
sys.exit(subprocess.run([sys.executable, "-B", "bundle.py"] + args + extra +
                        ["-n", name, "-o", "build/virgl-serve/%s.html" % name]).returncode)
EOF
