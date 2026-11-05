# Сборка и тесты

## Сборка

С нуля, по порядку (всё скачанное и собранное ложится в `.cache/`, `build/`,
`images/` и `site/`, в git этого нет):

```sh
scripts/build-busybox.sh  # тулчейн musl.cc, статический busybox с юникодом -> overlay/bin/busybox, kt-seed, kt-net, pyzygote
scripts/build-kernel.sh   # ядро по config/linux.config + config/kernel.fragment -> images/bzImage
scripts/get-packages.sh   # пакеты из Alpine x86, свой CPython, openblas, jdk8 -> build/packages/
./build.sh                # base/ + overlay/ -> images/rootfs.cpio, packages/ + build/packages/ -> site/repo/ (без sudo)
python3 bundle.py         # images/ + vendor/v86/ + site/repo/ + page.html -> site/index.html
```

По отдельности:

```sh
scripts/build-python.sh         # свой CPython -> build/packages/minipython, python3, python3-* (его зовёт get-packages.sh)
scripts/build-openblas.sh       # openblas без SSSE3 -> build/packages/openblas (его зовёт get-packages.sh)
python3 scripts/jdk8.py --cds   # архив классов CDS для jdk8: снимается в госте (после build.sh, потом build.sh ещё раз)
python3 tests/run.py            # тесты моста в headless Chromium (--build - сначала собрать, -k имя - выборочно)
python3 tests/mpl.py            # matplotlib с patches/matplotlib.patch против исходного: те же картинки (--time - время кадров на хосте)
./release.py                    # бандлы сайта из bundles/ (standard, micro, python) -> site/ИМЯ/index.html
python3 tests/mem.py site/standard/index.html  # память вкладки с бандлом (--save - всплеск при kt save, --profile папка - возврат из сохранения)
```

- `build.sh` собирает репозиторий в `site/repo.new` и подменяет `site/repo` в
  самом конце: сервер, который раздаёт `site/`, во время сборки отдаёт старые
  пакеты, а не 404. Упакованные пакеты кэшируются в `.cache/pkg` по хэшу
  файлов пакета, `build.sh` и `scripts/pymin.py`: перепаковывается только изменённое.
- `base/rootfs.base.cpio` - rootfs из Buildroot (`config/buildroot/`);
  `config/base.exclude` - что из него выкинуть (перекрыто overlay или не
  нужно). Ссылки на апплеты, которых нет в нашем busybox, выкидываются сами.
- `config/busybox.fragment` / `config/kernel.fragment` - что включено и выключено поверх
  конфигов Buildroot: без железа, модулей, блочных устройств, крипто и т.п.
  В busybox добавлены `timeout`, `pgrep` и `pkill` (последние два - пара КБ).
- `overlay/` - всё своё: `kt`, модули, агент, init-скрипты, `kt.py`.
- `images/` - собранные bzImage, rootfs.cpio, build.json; `vendor/v86/` -
  libv86.js, v86.wasm и BIOS из проекта v86. Из них и собирается бандл.
- `src/kt-seed.c`, `src/kt-net.c` - свои бинарники (4 и 11 КБ, собираются в
  `scripts/build-busybox.sh`), см. [internals.md](internals.md).
- Минификация при сборке, на копии во временной папке: исходники в `overlay/` и
  `packages/` не трогаются. Шелл-скрипты - без комментариев и отступов,
  `.py` - через `scripts/pymin.py` (всё, кроме `/root`, где лежат примеры для чтения):
  AST без докстрингов, `pass`, пустых выражений и `return None`, склеенные
  `import`, затем `ast.unparse` и сжатие на токенах (отступ 1 пробел, простые
  операторы через `;`, тело блока в одну строку с заголовком). Результат
  сверяется с AST, при расхождении файл остаётся как был. CPython и так
  держит stdlib рабочей под `-OO`, где докстрингов нет.
- Наши браузерные куски (`/usr/lib/kt-*.js`: `kt-notify.js`, `kt-pack.js`, `kt-sync.js`) жмутся
  terser'ом (`npx terser`); файл-функция на время оборачивается в `var __f=`.
- Потом пакеты с `usr/lib/python3.12` компилируются в `.pyc` настоящим python3.12 из `minipython`
  (запускается на хосте через musl-загрузчик, нужен i386 в ядре хоста), и `.py`
  удаляются (и в `site-packages`: telebot стартует за 10 с вместо 17). Первый запуск тяжёлого скрипта в машине -
  10 с вместо 38, `__pycache__` в памяти не копится. Компилятору подложен `unicodedata` из пакета `python3`:
  без него не собирался ни один файл с `\N{...}`, а из-за одного такого файла в пакете оставались все исходники -
  matplotlib, setuptools, websockets и pyparsing везли по два набора (9 МБ лишних) и компилировались при первом импорте. Компиляция идёт с
  `-X no_debug_ranges`: в `.pyc` нет колоночных позиций, по которым трейсбек рисует
  `^^^^`, но без исходников их и так не из чего рисовать. Позиции плохо жмутся:
  stdlib в xz от этого на треть меньше, весь репозиторий - на 8.5 МБ. Цена: весь
  python3 - 4.0 МБ скачать / 15.3 МБ в памяти (с исходниками было 3.5 / 14.8).
- `alpine.py <pkg>...` - скачивает пакеты Alpine с зависимостями в `build/packages/`,
  `--skip` - не тянуть зависимость, `--drop`/`--keep` - фильтр файлов.
- Ядро и busybox собираются тулчейном musl.cc в `.cache/`, Docker не нужен.
  Патчи и конфиг busybox `scripts/build-busybox.sh` берёт из архива Buildroot.

## Тесты

`python3 tests/run.py` собирает два тестовых бандла (с python3, micropython,
pack, sync, notify и маленький со снимком), поднимает локальный http-сервер и
гоняет в headless Chromium 44 проверки, ~3.5 минуты: `kt js` во всех формах и из
фона, `kt.exec`, `kt.read`/`kt.write` с md5 и скоростью, `kt dl` (файл, папка,
stdin), `kt up` через кнопку и сразу после Enter, буфер обмена, события,
MicroPython, CPython в 8 потоков, `requests`/`curl`, alert/confirm/prompt,
`kt notify`, pack, sync (через OPFS), свои ключи `kt cfg`, `ai` с сервером-заглушкой
(инструменты, файлы, канал, неверный ключ, сжатие контекста, диалог с
подтверждением и кириллицей, переход на `/responses`, `/model`), pip с
заглушкой PyPI (зависимости, маркеры, пре-релизы, sdist, glibc, шим requests,
переход на `python-yaml` из репозитория), `kt pkg` из Alpine с заглушкой
зеркала (поиск и `search -r`, мёртвое первое зеркало, устаревшая версия через
`APKINDEX`, отказ без частичной установки, список `kt pkg`, зависимость, уборка
`.PKGINFO`, удаление), `kt save` с перезагрузкой страницы,
`kt reset`, Ctrl+Alt+End при замороженном агенте и CTRL ALT END кнопками,
убийство `kt-netd` и агента, повтор сегмента TCP, когда читатель в госте
остановлен (агент и ответ на команду), переключение `term.render`, бандл со снимком
(часовой пояс, разные случайные числа, версия в `kt info`). Плюс что агент
ровно один, в терминале нет мусора
(`signal`, `Terminated`), в `/run/kt` не остаётся `events`, `ev.*` и `reply.*`,
а данных бандла после загрузки нет в DOM и
подменённый `zero_memory` обнуляет ровно то, что просили (с ядра и со снимка).
Код выхода 1, если что-то упало; `TRACE=1` -
трассировки.
