# KotelOS - Linux в браузере (v86)

Маленький Linux-мультитул: ядро 1.2 МБ + rootfs 0.4 МБ, загрузка ~4 с.
Всё взаимодействие с браузером - через одно API `kt`, одинаковое в шелле,
MicroPython и на странице.

Машина для браузера - всегда один html-файл (бандл): v86, BIOS, xterm.js,
ядро, rootfs с нужными пакетами и, если надо, готовый снимок запущенной
машины. Работает и с сайта, и двойным кликом через `file://` без сети.
Остальные пакеты `kt pkg add` берёт из общего репозитория.

## Сборка

Нужны Linux x86-64 (ядро с поддержкой i386: собранный CPython запускается на
хосте), `python3` (с `venv`), `curl`, `xz`, `zstd`, `cpio`, `patch`, `make`, `gcc`,
`ninja` и `pkg-config` (сборка numpy); Chromium - для `--snap` и тестов, `npx` - для
сжатия js (без него остаётся как есть). Тулчейн musl.cc, исходники и Cython
скачиваются сами в `.cache/`.

```sh
scripts/build-busybox.sh   # busybox, kt-net, kt-seed, pyzygote
scripts/build-kernel.sh    # ядро -> images/bzImage
scripts/get-packages.sh    # пакеты из Alpine, свой CPython, openblas, jdk8 -> build/packages/
./build.sh                 # rootfs -> images/, репозиторий пакетов -> site/repo/
python3 bundle.py          # бандл -> site/index.html
```

Дальше `site/` раздаётся любым http-сервером (`python3 -m http.server -d site`),
а `site/index.html` открывается и просто из файла. Подробно - в
[docs/build.md](docs/build.md), про бандлы и их ключи - в
[docs/bundles.md](docs/bundles.md).

## Документация

- [Бандлы и сохранения](docs/bundles.md) - `bundle.py`, `release.py`, `kt save`, публикация
- [API, встраивание и настройки](docs/api.md) - `kt` в шелле, Python и на странице, `kt cfg`
- [Пакеты](docs/packages.md) - `kt pkg`, репозиторий, свои пакеты, пакеты Alpine
- [Python](docs/python.md) - свой CPython, `pyzygote`, pip, Telegram-боты
- [Окна](docs/gui.md) - tkinter, IDLE, turtle, matplotlib, рабочий стол
- [Файлы](docs/files.md) - `kt sync` и `kt pack`
- [ИИ-ассистент](docs/ai.md) - `ai`
- [Сборка и тесты](docs/build.md)
- [Как устроено](docs/internals.md) - мост гость <-> страница, сеть, снимки, память

## Структура

```
build.sh  bundle.py  release.py   сборка образа, бандла и всех бандлов сайта
alpine.py                         индекс и пакеты Alpine (для bundle.py и скриптов)
page.html                         шаблон страницы бандла
overlay/                          своё в rootfs: kt, агент, init-скрипты, kt.py
packages/                         свои пакеты репозитория (папка = пакет)
src/                              свои бинарники на C: kt-net, kt-seed, pyzygote
base/rootfs.base.cpio             базовый rootfs из Buildroot
config/                           конфиги ядра и busybox, base.exclude, описания пакетов, Buildroot
scripts/                          сборка ядра, busybox, CPython, openblas, загрузка пакетов
patches/                          правки сторонних пакетов (matplotlib, v86)
vendor/v86/                       libv86.js, v86.wasm, BIOS - собирает scripts/build-v86.sh
bundles/                          описания бандлов сайта для release.py
docs/                             документация
tests/                            тесты в headless Chromium

не в git:
.cache/                           загрузки, исходники и деревья сборки
build/packages/                   пакеты из Alpine и собранные скриптами
images/                           собранные bzImage, rootfs.cpio, build.json
site/                             бандлы и репозиторий пакетов для публикации
```

## Лицензия

MIT, см. [LICENSE](LICENSE). Сторонний код и его лицензии - в
[THIRD_PARTY.md](THIRD_PARTY.md).
