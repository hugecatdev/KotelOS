#!/bin/sh
cd "$(dirname "$0")"
tcc -o /tmp/mandelbrot mandelbrot.c
time /tmp/mandelbrot "${1:-480}" > /tmp/mandelbrot.bmp
if command -v micropython > /dev/null; then
  micropython -X heapsize=16M show.py /tmp/mandelbrot.bmp
else
  python3 show.py /tmp/mandelbrot.bmp
fi
