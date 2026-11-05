# Сторонний код

Свой код KotelOS - под MIT (`LICENSE`). Ниже - чужое: что лежит в репозитории
и что попадает в бандлы при сборке. У каждого своя лицензия.

## В репозитории

| что | где | лицензия | откуда |
|---|---|---|---|
| v86 | `vendor/v86/libv86.js`, `vendor/v86/v86.wasm` | BSD-2-Clause | https://github.com/copy/v86 |
| SeaBIOS | `vendor/v86/seabios.bin`, `vendor/v86/vgabios.bin` | LGPL-3.0 | сборка из проекта v86, https://www.seabios.org |
| tkinter из CPython 3.12.15 | `packages/python-tkinter/usr/lib/kt-python/tkinter` | PSF-2.0 | изменён: окна рисует страница через `kt-tk.js` |
| бэкенд tk из matplotlib | `packages/python-matplotlib-tk/usr/lib/python3.12/site-packages/matplotlib/backends` | Matplotlib License (PSF-based) | https://matplotlib.org, изменён |
| правки matplotlib | `patches/matplotlib.patch` | Matplotlib License (PSF-based) | патч к пакету Alpine `py3-matplotlib` |
| neofetch 7.1.0 | `packages/neofetch/usr/bin/neofetch` | MIT | https://github.com/dylanaraps/neofetch, изменён: логотип KotelOS, счёт пакетов `kt` |
| базовый rootfs | `base/rootfs.base.cpio` | GPL-2.0 и другие (Buildroot) | Buildroot 2024.02.5, `config/buildroot/` |

## Скачивается при сборке

| что | лицензия | кто качает |
|---|---|---|
| Linux 6.6.32 | GPL-2.0 | `scripts/build-kernel.sh` (cdn.kernel.org), конфиг - `config/linux.config` + `config/kernel.fragment` |
| BusyBox 1.36.1 | GPL-2.0 | `scripts/build-busybox.sh` (busybox.net), патчи и конфиг - из Buildroot 2024.02.5 + `config/busybox.fragment` |
| CPython 3.12.15, в том числе IDLE, turtle и turtledemo без изменений | PSF-2.0 | `scripts/build-python.sh` (python.org) |
| OpenBLAS 0.3.28 | BSD-3-Clause | `scripts/build-openblas.sh` (GitHub) |
| пакеты Alpine Linux 3.22 | у каждого своя | `scripts/get-packages.sh`, `alpine.py`; `kt pkg add` в машине - тоже |
| xterm.js и аддоны | MIT | `bundle.py` (cdn.jsdelivr.net), встраивается в бандл |
| тулчейн musl.cc | - | `scripts/build-*.sh`, только для сборки, в бандлы не попадает |

Бандл (`site/*/index.html`) - это v86, BIOS, ядро, busybox и пакеты в одном
файле, поэтому, раздавая бандлы, раздаёшь и всё перечисленное.
