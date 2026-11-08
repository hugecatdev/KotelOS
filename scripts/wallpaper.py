#!/usr/bin/env python3
"""Обои бандла dwm: кот в котле из neofetch в цветах логотипа (docs/img/logo.svg), прозрачный фон.

python3 scripts/wallpaper.py [файл.png] (по умолчанию bundles/dwm/logo.png); нужны Pillow на хосте и
моноширинный шрифт (JetBrains Mono или DejaVu Sans Mono). В машине его кладёт по центру
feh --bg-center --image-bg ЦВЕТ: остальное место - ровно цветом панели dwm, под любой экран."""
import glob
import sys

from PIL import Image, ImageDraw, ImageFont

STEAM, CAT, POT, FIRE = "#8e96aa", "#e3a72f", "#8e96aa", "#e0603a"
ROWS = [
    [(STEAM, "            (   )")],
    [(STEAM, "             ) (   )")],
    [(CAT, "       /\\_/\\ "), (STEAM, "  ( (")],
    [(CAT, "      ( o.o ) "), (STEAM, "  )")],
    [(POT, "  ____"), (CAT, '(")_(")'), (POT, "_______")],
    [(POT, " (__________________)")],
    [(POT, "  /                \\")],
    [(POT, " |                  |")],
    [(POT, " |                  |")],
    [(POT, "  \\                /")],
    [(POT, "   `-.__________.-'")],
    [(FIRE, "     ) )  ( (  ) )")],
    [(FIRE, "    ( (  ) )  ( (")],
]


def font(size):
    for pat in ("/usr/share/fonts/TTF/JetBrainsMono-Bold.ttf", "/usr/share/fonts/**/DejaVuSansMono-Bold.ttf",
                "/usr/share/fonts/**/*Mono*.ttf"):
        for path in glob.glob(pat, recursive=True):
            return ImageFont.truetype(path, size)
    sys.exit("нет моноширинного шрифта")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "bundles/dwm/logo.png"
    f = font(22)
    cw, lh = f.getlength("M"), 27
    w = int(cw * max(sum(len(t) for _, t in r) for r in ROWS)) + 8
    img = Image.new("RGBA", (w, lh * len(ROWS) + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, parts in enumerate(ROWS):
        x = 4
        for color, text in parts:
            d.text((x, 4 + i * lh), text, font=f, fill=color)
            x += cw * len(text)
    img.save(out, optimize=True)
    print(out, "%dx%d" % img.size)


if __name__ == "__main__":
    main()
