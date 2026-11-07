#!/bin/sh
# Пробный бандл с virtio-gpu (VirGL): v86 с устройством (DEVICES=virtio_gpu -> build/v86-gpu), ядро
# с virtio-gpu (в config/kernel.fragment; ядро - build/kernel-virtio, собрать заранее:
#   scripts/build-kernel.sh build/kernel-virtio/bzImage),
# virglrenderer (scripts/build-virgl.sh -> build/virgl), дерево гостя build/virgl-guest/fs.
# GUEST=дерево гостя (по умолчанию build/virgl-guest/fs), PKGS=пакеты. Общие images/ и site/ только
# читаются.
#   virgl/harness/gpu-bundle.sh [--no-v86] [ключи bundle.py ...]  -> build/virgl-serve/gpu.html
set -e
cd "$(dirname "$0")/../.."
if [ "$1" = --no-v86 ]; then
  shift
else
  DEVICES=virtio_gpu OUT=build/v86-gpu ./scripts/build-v86.sh | tail -1
fi
python3 bundle.py -o build/virgl-serve/gpu.html -n virgl-gpu --virtio-gpu --mem 256 --v86 build/v86-gpu \
  --kernel build/kernel-virtio/bzImage --file ${GUEST:-build/virgl-guest/fs}:/ "$@" \
  ${PKGS:-fun nano kt-ttyd xorg xeyes libstdc++ libgcc libx11 libxext zlib} | cut -c1-70
