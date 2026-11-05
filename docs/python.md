# Python

## CPython (`minipython`, `python3`)

CPython 3.12.15 свой, собирает `scripts/build-python.sh`: тулчейн musl.cc,
`-march=pentium4`, PGO (профиль снимают тесты CPython, запущенные на хосте
через musl-загрузчик) и LTO, без PIC и без `libpython3.12.so`: интерпретатор и
63 встроенных C-модуля в одном бинарнике 4.0 МБ, символы экспортированы для расширений.
Замороженные модули (`os`, `site`, `importlib`...) перед сборкой проходят
`scripts/pymin.py` и замораживаются без колоночных позиций, а их marshal-копии из
`frozen.c` убраны: главный интерпретатор берёт deepfreeze-версию, а
субинтерпретаторов нет. Бинарник от этого на 0.5 МБ меньше (170 КБ в xz).
Версия и ABI те же, что у Alpine, поэтому питоновские пакеты Alpine
(`python-numpy`, `python-pandas`, `python-lxml`...) работают без пересборки.
Тем, что слинкованы с `libpython3.12.so.1.0` (обёртки SWIG и boost), `python3`
кладёт пустую библиотеку с этим именем: символы берутся из бинарника.

| | Alpine | свой |
|---|---|---|
| скачать / в памяти | 5.3 / 19.4 МБ | `minipython` 2.3 / 8.9 МБ, весь `python3` 4.0 / 15.3 МБ |
| `python3 -c pass` | 0.49 с | 0.28 с |
| импорт 16 модулей stdlib | 3.2 с | 1.7 с |
| счёт: рекурсия, строки, json, re, объекты, float | 4.5 с | 2.1 с (без PGO 2.5 с) |

Вдвое быстрее, видимо, из-за PIC: у Alpine весь интерпретатор в общей
библиотеке, на i386 это адресация через GOT и вызов `__x86.get_pc_thunk` в
каждой функции, а JIT v86 такое переводит плохо.

`minipython` - бинарник и ядро stdlib: `os`, `re`, `json`, `pathlib`,
`subprocess`, `argparse`, `logging`, `dataclasses`, `typing`, `datetime`,
`socket`, `threading`, `concurrent.futures`, `zipfile`, `tarfile`, `hashlib`,
`csv`, `email`, `importlib.metadata`, `unittest`, `pdb`, `cProfile`, `shelve`,
`decimal` (на питоне), ходовые кодировки (UTF, latin-1, кириллица, западные),
`readline` для REPL. numpy (`python-numpy`) хватает `minipython`. Крупные
модули - отдельными пакетами (скачать / в памяти, КБ):

| пакет | модули | размер |
|---|---|---|
| `python3-asyncio` | `asyncio` | 125 / 620 |
| `python3-ctypes` | `ctypes` | 64 / 200 |
| `python3-html` | `html` | 27 / 112 |
| `python3-http` | `http`, `urllib.request`, `wsgiref`, `mimetypes`; тянет `python3-html` | 92 / 388 |
| `python3-xml` | `xml`, `plistlib`; тянет `python3-http` (`xml.sax` импортирует `urllib.request`) | 180 / 648 |
| `python3-multiprocessing` | `multiprocessing`; тянет `python3-ctypes` (`Value`, `Array`) | 89 / 408 |
| `python3-venv` | `venv`: `python3 -m venv --without-pip`, ensurepip нет | 12 / 56 |
| `python3-sqlite` | `sqlite3` | 33 / 100 |
| `python3-curses` | `curses` | 32 / 140 |

`python3` - все они, кроме sqlite и curses, плюс остаток: `unicodedata` (1.1 МБ),
`bz2`, `lzma`, `_decimal` на C, `pydoc`, `xmlrpc`, почтовые протоколы, азиатские
и редкие кодировки. От `python3` зависят `pip` и питоновские пакеты Alpine
(`python-*`, кроме numpy). `unittest.mock` требует `python3-asyncio`. Команды
`python3` и `python` ставит `minipython`. Раскладку по пакетам задаёт `scripts/pysplit.py`.

Вырезано совсем: docstring'и C-функций (`--without-doc-strings`, ~330 КБ:
`help(len)` пустой, `inspect.signature` у встроенных функций не работает;
питоновские docstring'и и так снимает `scripts/pymin.py`), `_ssl` и `_hashlib` (TLS
делает браузер), `dbm`, `_uuid`, `_tkinter` и `tkinter`, `lib2to3`, `ensurepip`,
тесты, `audioop`, `crypt`, `nis`, `spwd`, `ossaudiodev`, субинтерпретаторы.
Вместо `tkinter` свой пакет `python-tkinter` (окна рисует страница), а `idlelib`,
`turtle` и `turtledemo` из CPython идут отдельными пакетами `python-idle`,
`python-turtle` и `python-turtledemo` (см. [Окна](gui.md)).

stdlib в zip (`python312.zip`) пробовал: в памяти на 2.6 МБ меньше, но импорт
в 1.5 раза медленнее (zipimport написан на питоне и распаковывает каждый
модуль), а скачивать на 0.6 МБ больше (xz плохо жмёт уже сжатое), поэтому
обычные `.pyc`.

### pyzygote

`pyzygote` - быстрый старт `python3`, стоит в стандартной сборке, выключается
`kt pkg rm pyzygote`. Пакет кладёт в `/usr/local/bin`
(в PATH раньше `/usr/bin`) маленький C-клиент `python3`/`python` и сервер
`/usr/sbin/pyzygote`: интерпретатор, который уже запущен и импортировал ходовую
stdlib (`json`, `re`, `subprocess`, `argparse`, `pathlib`, `datetime`...).
Клиент отдаёт серверу fd 0-2, argv, окружение, cwd и umask, сервер делает
`fork`, ребёнок становится лидером своей сессии и запускает скрипт. Клиент
пересылает ему сигналы (Ctrl-C, Ctrl-Z, `TERM`, `WINCH`...) и выходит с его
кодом или от того же сигнала. В v86:

| | без pyzygote | с pyzygote |
|---|---|---|
| `python3 -c pass` | 0.28 с | 0.05 с |
| `python3 -c 'import json, re, argparse'` | 0.63 с | 0.05 с |

MicroPython для сравнения - 0.015 с. Сервер держит 9 МБ памяти, в снимке
стандартной сборки это +1.2 МБ.

Сервер стартует при загрузке (`/etc/init.d/S90pyzygote`) и после
`kt pkg add pyzygote`. Пока он прогревается (около 3 с, с numpy и matplotlib 17 с,
под `nice 10`, чтобы не тормозить загрузку), `python3` работает как обычно. В бандле со снимком
сервер уже прогрет. Если сервер не запущен, его поднимает первый `python3`.
Если в каталогах `sys.path` что-то поменялось (`pip`, `kt pkg`), сервер
дожидается своих детей и перезапускается. После `kt pkg rm pyzygote` сервер
выходит в течение минуты.

Через сервер идут `python3 файл`, `-c`, `-m`, REPL (`python3` в терминале:
`code.InteractiveConsole` с readline и историей) и флаги `-u`, `-B`, из
терминала и из `kt.exec`. `TZ` ребёнок применяет сам (`time.tzset()`), сигналы
сбрасывает как у свежего python (сервер из init.d стартует с игнором `INT`).
Обычным запуском идут другие флаги, переменные `PYTHON*`, другая кодировка
(`LC_CTYPE`, пустая, `C` и `POSIX` считаются `C.UTF-8`), `.pyc`, zip и
каталоги; REPL тогда пишет `pyzygote: без ускорения (причина)`.
`#!/usr/bin/python3` сервер не видит. Отличия от обычного запуска:
- у скрипта нет управляющего терминала, `/dev/tty` не открывается (`getpass` читает stdin);
- передаются только fd 0-2;
- `os.getppid()` - сервер, в `ps` ребёнок виден как `pyzygote`;
- hash seed у всех запусков общий;
- на выходе выполняются потоки, `atexit` и сброс stdio, но модули не разбираются.

Тяжёлые библиотеки сервер прогревает по спискам из `/etc/pyzygote.d/`: по файлу
на библиотеку, в пакете лежат `numpy` и `matplotlib`, свои кладутся рядом. Список
срабатывает, только если его модули стоят в машине, так что в стандартной сборке
они ничего не стоят. Строки файла, `#` - комментарий:

| строка | что значит |
|---|---|
| `import модуль...` | импортировать заранее |
| `fork функция` | вызвать в каждом новом процессе: `numpy.random.seed` пересевает общий генератор numpy, иначе все запуски получали бы одни и те же случайные числа |
| `env ИМЯ ПРЕФИКС*` | переменные, которые модуль читает при импорте. Сервер берёт их такими, какими их выставляет `/etc/profile.d` (так к нему попадает `MPLBACKEND=TkAgg`), а запуск с другими значениями идёт обычным путём: `MPLBACKEND=Agg python3 ...` |
| `file путь...` | файлы настроек модуля. Относительный путь, найденный в каталоге запуска (`matplotlibrc`), отменяет ускорение этого запуска; смена файла по пути с `/` или `~` перезапускает сервер |

С matplotlib `import matplotlib.pyplot` занимает 0.2 с вместо 8, `mpldemo`
показывает график через 2 с вместо 10. Цена: сервер держит 45 МБ вместо 9.5 (в
машине занято на 20 МБ больше, вкладка с бандлом `python` - 280 МБ вместо 253,
файл бандла 47.6 МБ вместо 42.1), прогревается 17 с вместо 3, а любой `python3`
стартует за 0.15 с вместо 0.10: `fork` большого процесса дольше. Прогретый модуль
не увидит переменных, которые скрипт выставил сам до `import`
(`os.environ["MPLBACKEND"] = "Agg"` - вместо этого `matplotlib.use("Agg")`).
`tkinter` прогревать нельзя: у него номер сеанса и подписка на события страницы
свои у каждого процесса. Отключить прогрев библиотеки - убрать её файл из
`/etc/pyzygote.d/`.

## pip

`kt pkg add pip` - свой pip (шим) для python3: `pip install`, `uninstall`,
`list`, `freeze`, `show`, `-r requirements.txt`, `-U`, `--no-deps`. Версии
берутся из JSON API PyPI, колёса качаются через fetch браузера (у `pypi.org`
и `files.pythonhosted.org` CORS открыт), зависимости - из `METADATA` колеса с
маркерами (PEP 508) и extras, версии - по PEP 440. Ставит в
`site-packages`, консольные команды - в `/usr/bin`, удаляет по `RECORD`.
Файлы PyPI для пакета отбираются ещё на странице: JSON у крупных проектов
весит 2-12 МБ, в гостя уходят только подходящие колёса.

Подходят колёса `py3-none-any` и `musllinux_*_i686` для CPython 3.12. Сборки из
исходников (sdist) нет, `manylinux` (glibc) не годятся. Если подходящего колеса
нет или PyPI недоступен, pip ставит пакет из репозитория kt
(`kt pkg add python-...`): там лежат питоновские пакеты Alpine с C-кодом.
Соответствие имён PyPI и пакетов - `repo/pypi.txt`, его собирает `build.sh` из
`dist-info`/`egg-info` пакетов. Из 30 популярных пакетов с C-кодом в Alpine x86
есть 27 (numpy, pandas, scipy, lxml, cryptography, pillow, pyyaml...), а колёс
glibc i686 - только у 9, и все они тоже есть в Alpine, поэтому отдельный
Python на glibc ничего не добавил бы.

Пакеты, поставленные `kt pkg` (python-requests, python-telebot), pip видит,
но не трогает: шим `requests` описан своим `dist-info` (`INSTALLER` = `kt`),
поэтому `pip install requests` и зависимости вида `requests>=2` считаются
выполненными, а настоящий requests (он ходит в сеть сам и здесь не работает)
не ставится поверх шима. Шимы помечены локальной версией `+kt`
(`requests 2.32.0+kt`, `pip 24.0+kt`): такой пакет pip берёт из репозитория
и на PyPI не ищет. Проверено на PyPI: `cowsay` (8 с), `rich` с
зависимостями (12 с, импорт ~10 с).

## Telegram-боты (`python-telebot`)

`kt pkg add python-telebot` - pyTelegramBotAPI из Alpine (`import telebot`) на
python3, сеть через `python-requests`. Без асинхронной части (ей нужен aiohttp)
и с необязательным `ssl` (он нужен только вебхукам).

CORS у `api.telegram.org` проверен в Chromium с `file://` и `http://`: ответы
идут с `Access-Control-Allow-Origin: *`, а на preflight (OPTIONS) сервер отвечает
501, и браузер такой preflight не принимает. Поэтому проходят только «простые»
запросы:

| запрос | из браузера |
|---|---|
| GET с параметрами в адресе | работает |
| POST формой (`application/x-www-form-urlencoded`) | работает |
| POST multipart с файлом (`sendPhoto`, `sendDocument`) | работает |
| POST с JSON в теле | блокируется |
| любой свой заголовок | блокируется |

telebot шлёт ровно первые три вида, `python-requests` своих заголовков не
добавляет, поэтому `get_me`, `send_message`, `send_photo` доходят до Telegram -
проверено с неверным токеном (ответ 401 Unauthorized), и из фонового процесса
тоже. Работает только опрос (`bot.infinity_polling()`): вебхуки требуют
входящих соединений, их браузер не принимает. Бот живёт, пока открыта вкладка;
в свёрнутой вкладке браузер может притормаживать таймеры.
