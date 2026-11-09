#!/usr/bin/env python3
"""Обои GreenOS из картинки с кубиком (wallpaper-src.jpg) -> fs/usr/share/backgrounds/:
greenos.jpg - для широкого экрана: снизу продолжен пол, чтобы кубик стоял выше панели задач;
greenos-tall.jpg - для телефона стоя: кубик на ~80% ширины ниже середины (сверху - значки), фон продолжен вверх и
вниз (повтор крайних строк и размытие - фон на картинке плавный). Где кубик в greenos.jpg, пишется в
greenos-wallpaper (CUBE_X): на экране уже картинки кадр - вокруг кубика. Нужен Pillow:
python3 bundles/greenos/wallpaper.py"""
import os

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "wallpaper-src.jpg")
OUT = os.path.join(HERE, "fs/usr/share/backgrounds")


def cube(im):
    """рамка зелёных граней кубика"""
    px = im.load()
    xs, ys = [], []
    for y in range(0, im.height, 2):
        for x in range(0, im.width, 2):
            r, g, b = px[x, y]
            if g > r + 40 and g > b + 40:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def extend(im, top, bottom):
    """холст выше на top и bottom точек: крайние строки картинки тянутся наружу, шов размыт"""
    out = Image.new("RGB", (im.width, im.height + top + bottom))
    out.paste(im, (0, top))
    if top:
        out.paste(im.crop((0, 0, im.width, 1)).resize((im.width, top)), (0, 0))
    if bottom:
        out.paste(im.crop((0, im.height - 1, im.width, im.height)).resize((im.width, bottom)), (0, top + im.height))
    soft = out.filter(ImageFilter.GaussianBlur(24))
    mask = Image.new("L", out.size, 0)
    band = 60
    for y0 in ([top] if top else []) + ([top + im.height] if bottom else []):
        for d in range(-band, band):
            y = y0 + d
            if 0 <= y < out.height:
                mask.paste(round(255 * (1 - abs(d) / band)), (0, y, out.width, y + 1))
    return Image.composite(soft, out, mask)


def main():
    src = Image.open(SRC).convert("RGB")
    x0, y0, x1, y1 = cube(src)
    os.makedirs(OUT, exist_ok=True)

    wide = extend(src, 0, round(src.height * 0.12)).resize((1920, round(1920 * (src.height * 1.12) / src.width)), Image.LANCZOS)
    k = 1920 / src.width
    wide.save(os.path.join(OUT, "greenos.jpg"), quality=88, optimize=True)
    print("greenos.jpg %dx%d, кубик x %d..%d (CUBE_X=%d)" % (wide.width, wide.height, x0 * k, x1 * k, (x0 + x1) / 2 * k))

    W, H = 1080, 2340
    s = 0.8 * W / ((x1 - x0) * 1.08)  # с белой рамкой граней
    im = src.resize((round(src.width * s), round(src.height * s)), Image.LANCZOS)
    cx, cy = (x0 + x1) / 2 * s, (y0 + y1) / 2 * s
    left = round(min(max(cx - W / 2, 0), im.width - W))
    im = im.crop((left, 0, left + W, im.height))
    top = max(0, round(H * 0.58 - cy))  # выше - место под значки рабочего стола
    tall = extend(im, top, max(0, H - top - im.height))
    tall.save(os.path.join(OUT, "greenos-tall.jpg"), quality=88, optimize=True)
    print("greenos-tall.jpg %dx%d" % tall.size)


if __name__ == "__main__":
    main()
