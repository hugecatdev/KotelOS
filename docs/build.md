# Сборка и тесты

## Сборка

С нуля, по порядку (всё скачанное и собранное ложится в `.cache/`, `build/`,
`images/` и `site/`, в git этого нет):

```sh
scripts/build-busybox.sh  # тулчейн musl.cc, статический busybox с юникодом -> overlay/bin/busybox, kt-seed, kt-net, pyzygote
scripts/build-kernel.sh   # ядро по config/linux.config + config/kernel.fragment -> images/bzImage
scripts/get-packages.sh   # пакеты из Alpine x86, свой CPython, openblas, numpy, jdk8, doom, Xorg, dwm -> build/packages/
./build.sh                # base/ + overlay/ -> images/rootfs.cpio, packages/ + build/packages/ -> site/repo/ (без sudo)
python3 bundle.py         # images/ + vendor/v86/ + site/repo/ + page.html -> site/index.html
```

По отдельности:

```sh
scripts/build-python.sh         # свой CPython -> build/packages/minipython, python3, python3-* (его зовёт get-packages.sh)
scripts/build-openblas.sh       # openblas под SSE2, LAPACK на C -> build/packages/openblas (его зовёт get-packages.sh)
scripts/build-numpy.sh          # numpy под SSE2 с этим openblas -> build/packages/python-numpy (его зовёт get-packages.sh)
scripts/build-doom.sh           # doom -> packages/doom, doom1.wad -> build/packages/doom-shareware (его зовёт get-packages.sh)
scripts/build-xorg.sh           # Xorg без OpenGL -> packages/xorg (его зовёт get-packages.sh)
scripts/build-mesa.sh           # libGL без LLVM (softpipe через Xlib) -> packages/mesa-xlib (его зовёт get-packages.sh)
scripts/build-dwm.sh            # dwm, st, feh -> packages/..., dwm-studio -> bundles/qt (его зовёт get-packages.sh)
scripts/check-isa.sh ФАЙЛ...    # нет ли в ELF инструкций, которых v86 не умеет (SSSE3, SSE4, AVX, addsubps/pd, lddqu)
scripts/build-v86.sh            # v86 из исходников + patches/v86/ -> vendor/v86/ (Rust с wasm32 и Closure Compiler качает в .cache/)
python3 scripts/jdk8.py --cds   # архив классов CDS для jdk8: снимается в госте (после build.sh, потом build.sh ещё раз)
python3 tests/run.py            # тесты моста в headless Chromium (--build - сначала собрать, -k имя - выборочно)
python3 tests/mpl.py            # matplotlib с patches/matplotlib.patch против исходного: те же картинки (--time - время кадров на хосте)
./release.py                    # бандлы сайта из bundles/ (standard, micro, python, vga, dwm) -> site/ИМЯ/index.html
python3 tests/mem.py site/standard/index.html  # память вкладки с бандлом (--save - всплеск при kt save, --profile папка - возврат из сохранения)
python3 tests/bench.py vendor/v86 ПАПКА...     # скорость сборок v86: одни нагрузки в госте, время и процессор вкладки (-k имя, -n кругов)
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
  В ядре включён `CONFIG_SECCOMP` (с ним `SECCOMP_FILTER`, +4 КБ к bzImage): без
  него chawan не запускает процессы страниц.
- `overlay/` - всё своё: `kt`, модули, агент, init-скрипты, `kt.py`.
- `images/` - собранные bzImage, rootfs.cpio, build.json; `vendor/v86/` -
  libv86.js, v86.wasm и BIOS из проекта v86. Из них и собирается бандл
  (`bundle.py --v86 ПАПКА` - взять другую сборку).
- `vendor/v86/` собирает `scripts/build-v86.sh`: архив copy/v86 на
  закреплённом коммите (`REV` в скрипте, `REV=... scripts/build-v86.sh` -
  другой), сверху `patches/v86/*.patch` по порядку, `make build/libv86.js
  build/v86.wasm` без отладки и секции имён. Rust 1.99.1 с wasm32 (rustup) и
  Closure Compiler скрипт кладёт в `.cache/`; clang с целью wasm32 нужен свой,
  той же мажорной версии LLVM, что у Rust (сейчас 23): softfloat и zstd
  собираются в LTO-биткод, и чужой версии rust-lld его не прочтёт. Готовые
  файлы лежат в git, так что для `bundle.py` Rust не нужен. Патчи (что и
  почему - в шапке каждого):
  - `01-tcp-window.patch` - окно и повтор сегментов в TCP страница -> гость,
    см. [internals.md](internals.md);
  - `02-yield-channel.patch` - отдавать управление браузеру сообщением самому
    себе, без круга через воркер;
  - `03-jit-small-modules.patch` - модули JIT по одной странице: в разы меньше
    фоновой компиляции в V8;
  - `04-jit-page-tail.patch` - JIT компилирует и последние 16 байт страницы,
    если инструкция там помещается (раньше их всегда исполнял интерпретатор,
    цикл с телом в хвосте шёл в 6-10 раз медленнее). Инструкции поперёк
    границы - по-прежнему интерпретатор;
  - `05-debug-svga-assert.patch` - чтобы debug-сборка v86 (`make
    build/libv86-debug.js build/v86-debug.wasm` в дереве из `.cache/`)
    запускалась с видеопамятью 256 КБ из `page.html`;
  - `06-optional-devices.patch` - устройства по выбору при сборке: блоки
    `/* #if имя */` в исходниках v86 (те же, что на странице, см. ниже), Closure
    берёт только модули, до которых доходят импорты;
  - `07-lazy-zero-memory.patch` - `zero_memory` пишет только в ненулевые
    страницы, видеопамять выделяется обнулённой (раньше обе вещи делала
    `page.html`, в Web Worker ей до них не дотянуться);
  - `08-worker.patch` - опция `worker`: процессор и устройства в Web Worker,
    адаптеры и экран на странице (`boot.worker`, см. [internals.md](internals.md));
  - `09-tcp-fin-with-data.patch` - TCP страницы не теряет данные, пришедшие
    в одном сегменте с FIN (с воркером так было на каждом длинном `kt js`).

  Устройства, которые нашему ядру не нужны, в `libv86.js` не попадают: 192 КБ
  вместо 361 (gzip 54 вместо 94). Вернуть - `DEVICES="ide sound"
  scripts/build-v86.sh`, все - `DEVICES=all`. Имена: `floppy`, `ide` (диски и
  CD-ROM), `sound` (SB16 и звук в браузере), `virtio` (сеть, консоль, balloon),
  `9p` (файловая система), `parallel`, `acpi` (с ним и APIC), `modem`,
  `multiboot` (загрузка ELF); DMA скрипт добавит сам для `floppy` и `sound`.
  Устройство, которого нет в сборке, но которое просят в настройках v86
  (`fda`, `cdrom`, `filesystem`, сеть `virtio`...), - ошибка «v86 built without
  ...». Ядру для них нужны и свои драйверы (`config/kernel.fragment`). Всегда
  есть PCI, PIT, RTC, PIC, UART, PS/2, vmmouse, VGA и ne2k. Сохранения от
  сборки с устройствами восстанавливаются: лишнее v86 пропускает.

  После смены `REV` или патчей: `scripts/build-v86.sh`, `python3 tests/run.py`
  и `KT_WORKER=1 python3 tests/run.py` (все тестовые бандлы с `--worker`),
  `python3 tests/bench.py СТАРАЯ_ПАПКА vendor/v86`; правки JIT ещё и в
  debug-сборке: там срабатывают `dbg_assert`.
  Что пробовали и не взяли (2026-11-06, `tests/bench.py`): `wasm-opt` -O2..-O4
  над `v86.wasm` (скорость в пределах шума, gzip бандла -15 КБ),
  `JIT_THRESHOLD` 100k и 50k вместо 200k (так же и хуже, процессора +10-25%),
  `MAX_PAGES` 2 и 3 (больше фоновой компиляции), `MAX_EXTRA_BASIC_BLOCKS` 30
  (горячие циклы через диспетчер, +30-40%).
- `tests/bench.py` собирает бандл с каждой сборкой v86 (загрузка с ядра) и
  гоняет в свежем headless Chromium одни и те же нагрузки в госте: fork,
  арифметика шелла, sha256, gzip, lua, micropython, запуск и импорт CPython,
  мост в обе стороны. Варианты идут по кругам, и в каждом круге порядок
  сдвигается: место в круге само по себе даёт 3-5% (первый быстрее, третий
  медленнее). В конце медианы и отношения. Три числа: время по часам,
  процессор основного потока (сам v86) и всей вкладки (с фоновой компиляцией
  wasm в V8) - последние два почти не зависят от занятости хоста, поэтому при
  соседях по хосту смотреть на них. Разница меньше ~5% одним прогоном не
  различается: две копии одной сборки дают до 1.02 в среднем и до 1.09 на
  отдельной нагрузке.
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
  `--skip` - не тянуть зависимость, `--drop`/`--keep` - фильтр файлов, `--alias A=B` -
  вместо пакета Alpine свой, `--max-age ЧАСОВ` - свой свежий индекс (общий бывает
  давним, а старых версий на зеркале уже нет).
- Условные блоки, как `#if` в C (`cond.py`, им же собирается v86 - см. выше):
  `bundle.py` вырезает из `page.html`
  то, чего в бандле нет. В JS и CSS - `/* #if имя */ ... /* #endif */`, в HTML -
  `<!-- #if имя -->...<!-- #endif -->`, `#if !имя` - если нет, блоки можно
  вкладывать; пометка одна на строке уходит вместе со строкой. Непарные пометки
  останавливают сборку. Сам `page.html` -
  «всё включено»: пометки - просто комментарии. Сейчас имя одно, `vga`
  (`--vga`): экран - его код, стили и ключи `kt cfg` (без него скрипт страницы
  после terser 44.9 КБ, с ним 49.8). Новая функция - имя в `template()` в
  `main()` `bundle.py` и блоки на странице.
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
