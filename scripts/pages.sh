#!/bin/sh
# Сборки сайта на GitHub Pages: ветка gh-pages каждый раз с нуля (без истории: иначе каждая выкладка
# копила бы в репозитории сотни МБ бинарников) и push --force.
#   scripts/pages.sh [REMOTE]     # по умолчанию origin; сначала ./release.py
#   scripts/pages.sh -n           # только собрать build/pages, без отправки
# В ветке: сборки из bundles/*.txt (site/ИМЯ/), репозиторий пакетов (site/repo/), index.html - переход на
# сборку ROOT (по умолчанию python), .nojekyll (Jekyll не трогает файлы). Сборки ищут пакеты по ../repo
# (release.py), поэтому сайт работает и как https://<пользователь>.github.io/<репозиторий>/.
# На GitHub один раз: Settings -> Pages -> Deploy from a branch -> gh-pages, / (root).
# Пределы GitHub: файл до 100 МБ (от 50 - предупреждение), сайт до 1 ГБ.
set -e
cd "$(dirname "$0")/.."
dry= remote=${1:-origin}
[ "$remote" != -n ] || dry=1
root=${ROOT:-python}
[ -n "$dry" ] || url=$(git remote get-url "$remote") || { echo "pages: нет remote $remote (git remote add $remote git@github.com:<пользователь>/<репозиторий>.git)" >&2; exit 1; }
[ -f "site/$root/index.html" ] || { echo "pages: нет site/$root/index.html - сначала ./release.py" >&2; exit 1; }

out=build/pages
rm -rf "$out"
mkdir -p "$out"
for f in bundles/*.txt; do
  n=$(basename "$f" .txt)
  if [ -f "site/$n/index.html" ]; then
    mkdir "$out/$n"
    cp -l "site/$n/index.html" "$out/$n/" 2>/dev/null || cp "site/$n/index.html" "$out/$n/"
  else
    echo "pages: нет site/$n/index.html, пропускаю" >&2
  fi
done
# жёсткие ссылки вместо копии: репозиторий - сотни МБ
cp -al site/repo "$out/repo" 2>/dev/null || cp -a site/repo "$out/repo"
touch "$out/.nojekyll"
cat > "$out/index.html" <<EOF
<!doctype html>
<meta charset="utf-8">
<title>KotelOS</title>
<meta http-equiv="refresh" content="0; url=$root/">
<a href="$root/">KotelOS</a>
EOF

big=$(find "$out" -type f -size +100M)
[ -z "$big" ] || { echo "pages: больше 100 МБ, GitHub не примет: $big" >&2; exit 1; }
find "$out" -type f -size +50M -printf "pages: %P больше 50 МБ - GitHub предупредит, но примет\n"

du -sh "$out" | sed 's/^/pages: /'
[ -z "$dry" ] || exit 0
cd "$out"
git init -q -b gh-pages
git add -A
git commit -q -m "KotelOS: сборки образа $(sed 's/.*"build":"\([^"]*\)".*/\1/' ../../images/build.json)"
git push -f "$url" gh-pages
