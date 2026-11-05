#include <stdio.h>
#include <stdlib.h>

static void put32(unsigned char *p, unsigned v) {
    p[0] = v; p[1] = v >> 8; p[2] = v >> 16; p[3] = v >> 24;
}

int main(int argc, char **argv) {
    int w = argc > 1 ? atoi(argv[1]) : 480, h = w * 2 / 3, depth = 80;
    int row = (w * 3 + 3) & ~3;
    unsigned char hdr[54] = {'B', 'M'};
    put32(hdr + 2, 54 + row * h);
    put32(hdr + 10, 54);
    put32(hdr + 14, 40);
    put32(hdr + 18, w);
    put32(hdr + 22, h);
    hdr[26] = 1;
    hdr[28] = 24;
    fwrite(hdr, 1, 54, stdout);

    unsigned char *line = calloc(row, 1);
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            double cr = -2.2 + 3.1 * x / w, ci = -1.2 + 2.4 * y / h, zr = 0, zi = 0;
            int n = 0;
            while (n < depth && zr * zr + zi * zi < 4) {
                double t = zr * zr - zi * zi + cr;
                zi = 2 * zr * zi + ci;
                zr = t;
                n++;
            }
            unsigned char v = n == depth ? 0 : 255 - n * 255 / depth;
            line[x * 3] = line[x * 3 + 1] = line[x * 3 + 2] = v;
        }
        fwrite(line, 1, row, stdout);
    }
    return 0;
}
