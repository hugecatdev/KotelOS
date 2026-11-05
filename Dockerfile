FROM debian:bookworm

# Зависимости Buildroot
RUN apt-get update && apt-get install -y \
    build-essential wget cpio unzip rsync bc \
    libncurses-dev git file python3 \
    && rm -rf /var/lib/apt/lists/*

# Buildroot не собирается под root
RUN useradd -m builder
USER builder
WORKDIR /home/builder

# Buildroot LTS (та же версия, что у Darin755)
RUN wget -q https://buildroot.org/downloads/buildroot-2024.02.5.tar.gz \
    && tar xf buildroot-2024.02.5.tar.gz \
    && mv buildroot-2024.02.5 buildroot \
    && rm buildroot-2024.02.5.tar.gz

WORKDIR /home/builder/buildroot

# Конфиги и overlay с твоими командами
COPY --chown=builder buildroot.config  .config
COPY --chown=builder linux.config      linux.config
COPY --chown=builder busybox.fragment  /home/builder/busybox.fragment
COPY --chown=builder overlay/          /home/builder/overlay/

# Права на исполняемые скрипты overlay
USER root
RUN chmod +x /home/builder/overlay/usr/bin/* /home/builder/overlay/etc/init.d/* 2>/dev/null || true
USER builder

# Разворачиваем дефолты и собираем
RUN make olddefconfig && make -j"$(nproc)"

# Результат: output/images/bzImage
