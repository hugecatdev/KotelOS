import datetime
import hashlib
import os
import pickle
import re
import sys
import time

import matplotlib
matplotlib.use("Agg")
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties

OUT = sys.argv[1]
TIME = "--time" in sys.argv
os.makedirs(OUT, exist_ok=True)
matplotlib.rcParams["svg.hashsalt"] = "kt"
rng = np.random.default_rng(1)
log = []


def new():
    fig = Figure(figsize=(5.6, 4.2), dpi=100)
    return fig, FigureCanvasAgg(fig)


def shot(fig, canvas, name, save=True):
    canvas.draw()
    log.append("%s %s" % (name, hashlib.md5(bytes(canvas.buffer_rgba())).hexdigest()))
    if save:
        fig.savefig(os.path.join(OUT, name + ".png"))


def timed(canvas, name, change=None):
    if not TIME:
        return
    best = None
    for i in range(3):
        if change:
            change(i)
        t = time.perf_counter()
        canvas.draw()
        d = time.perf_counter() - t
        best = d if best is None or d < best else best
    print("%-14s %7.1f мс" % (name, best * 1000))
    sys.stdout.flush()


def lines(fig):
    ax = fig.add_subplot()
    x = np.linspace(0, 2 * np.pi, 200)
    ax.plot(x, np.sin(x), label="sin x")
    ax.plot(x, np.cos(x), "--", label="cos x")
    ax.set_title("Синус и косинус")
    ax.set_xlabel("x, рад")
    ax.grid(alpha=0.3)
    ax.legend()


def grid4(fig):
    axs = fig.subplots(2, 2, sharex=True)
    x = np.linspace(0, 10, 100)
    for i, ax in enumerate(axs.flat):
        ax.plot(x, np.sin(x + i), label="кривая %d" % i)
        ax.set_ylabel("y%d" % i)
        ax.set_title("График %d" % i, loc="left")
        ax.legend(loc="upper right")
    fig.align_ylabels()


def constrained(fig):
    fig.set_layout_engine("constrained")
    axs = fig.subplots(1, 2)
    axs[0].plot([1, 10, 100, 1000], [1, 2, 3, 4])
    axs[0].set_xscale("log")
    axs[0].set_xlabel("лог")
    im = axs[1].imshow(rng.random((12, 12)), aspect="equal")
    fig.colorbar(im, ax=axs[1])
    axs[1].set_title("Картинка")


def tight(fig):
    fig.set_layout_engine("tight")
    axs = fig.subplots(2, 2)
    for i, ax in enumerate(axs.flat):
        ax.plot(rng.random(10) * 10 ** i)
        ax.set_title("t%d" % i)
        ax.set_xlabel("длинная подпись оси %d" % i)


def polar(fig):
    ax = fig.add_subplot(projection="polar")
    t = np.linspace(0, 2 * np.pi, 100)
    ax.plot(t, 1 + np.sin(3 * t))
    ax.set_thetamin(0)
    ax.set_thetamax(270)
    ax.set_title("Полярные")


def twin(fig):
    ax = fig.add_subplot()
    ax.plot([0, 1, 2], [1e6, 2e6, 4e6], "o-")
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_xlabel("сверху")
    ax.set_title("Заголовок над осью")
    ax2 = ax.twinx()
    ax2.plot([0, 1, 2], [3, 1, 2], "r")
    ax2.set_ylabel("вторая")
    ax.minorticks_on()
    ax.tick_params(axis="x", labelrotation=30)


def equal(fig):
    ax = fig.add_subplot()
    ax.plot([0, 3], [0, 1])
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title("Равный масштаб")
    ax.text(1, 0.5, r"формула $\alpha^2 + \beta$", fontsize=12)
    ax.annotate("точка", (2, 0.6), xytext=(0.5, 0.9), arrowprops=dict(arrowstyle="->"))


def bars(fig):
    ax = fig.add_subplot()
    ax.bar(["Пн", "Вт", "Ср", "Чт", "Пт"], [5, 7, 3, 8, 6], label="утро")
    ax.set_ylabel("задач закрыто")
    ax.legend(title="Смена", ncols=2)
    ax.tick_params(axis="x", labelsize=14, labelcolor="tab:red")


def subfig(fig):
    a, b = fig.subfigures(1, 2)
    ax = a.subplots()
    ax.plot([1, 2, 3])
    ax.set_title("Слева")
    ax = b.subplots()
    ax.scatter(rng.random(30), rng.random(30))
    ax.set_xlabel("справа")
    b.suptitle("Подфигура")


def dates(fig):
    ax = fig.add_subplot()
    d0 = datetime.datetime(2026, 1, 1)
    ax.plot([d0 + datetime.timedelta(days=i) for i in range(40)], np.cumsum(rng.normal(size=40)))
    fig.autofmt_xdate()


def double(x):
    return x * 2


def half(x):
    return x / 2


def cats(fig):
    ax = fig.add_subplot()
    ax.barh(["альфа", "бета", "гамма"], [3, 1, 2])
    sec = ax.secondary_xaxis("top", functions=(double, half))
    sec.set_xlabel("удвоенная")


def inset(fig):
    ax = fig.add_subplot()
    ax.plot(np.sin(np.linspace(0, 10, 100)))
    ins = ax.inset_axes([0.6, 0.6, 0.35, 0.35])
    ins.plot([1, 2, 1])
    ins.set_title("вставка", fontsize=8)
    ax.indicate_inset_zoom(ins)
    ax.set_title("слева", loc="left")
    ax.set_title("справа", loc="right")
    ax.set_title("центр")


def hexes(fig):
    ax = fig.add_subplot()
    h = ax.hexbin(rng.normal(size=500), rng.normal(size=500), gridsize=12)
    fig.colorbar(h, ax=ax, label="число")
    ax.pcolor(np.arange(4).reshape(2, 2), alpha=0.3)


for make in (lines, grid4, constrained, tight, polar, twin, equal, bars, subfig, dates, cats, inset, hexes):
    name = make.__name__
    fig, canvas = new()
    make(fig)
    shot(fig, canvas, name)
    shot(fig, canvas, name + "-again", False)
    ax = fig.axes[0]
    lim = ax.get_xlim()
    step = 0.1 * (lim[1] - lim[0])
    ax.set_xlim(lim[0] + step, lim[1] + step)
    shot(fig, canvas, name + "-shift")
    ax.set_xlim(lim)
    shot(fig, canvas, name + "-back", False)
    fig.savefig(os.path.join(OUT, name + "-tight.png"), bbox_inches="tight")
    svg = os.path.join(OUT, name + ".svg")
    fig.savefig(svg, metadata={"Date": None, "Creator": None})
    text = open(svg).read()
    for i, clip in enumerate(dict.fromkeys(re.findall(r'<clipPath id="(\w+)"', text))):
        text = text.replace(clip, "clip%d" % i)
    open(svg, "w").write(text)
    log.append("%s tightbbox %s" % (name, ",".join("%.6f" % v for v in fig.get_tightbbox().extents)))
    fig2 = pickle.loads(pickle.dumps(fig))
    shot(fig2, FigureCanvasAgg(fig2), name + "-pickle", False)
    timed(canvas, name, lambda i: ax.set_xlim(lim[0] + step * i / 4, lim[1] + step * i / 4))

fig, canvas = new()
ax = fig.add_subplot()
ax.plot([0, 1, 2], [3, 1, 2], label="a")
title = ax.set_title("Заголовок")
note = ax.text(0.5, 2, "две\nстроки", ha="center", linespacing=1.2)
ax.text(1.2, 2.6, r"$\sum_i x_i^2$ и текст")
ax.text(0.1, 1.2, "очень длинная строка, которая должна переноситься по ширине фигуры " * 2, wrap=True)
leg = ax.legend()
shot(fig, canvas, "text")
title.set_text("Другой заголовок")
shot(fig, canvas, "text-string")
title.set_fontsize(18)
shot(fig, canvas, "text-size")
title.set_fontweight("bold")
title.set_fontstyle("italic")
shot(fig, canvas, "text-weight")
note.set_rotation(30)
shot(fig, canvas, "text-rotation")
note.set_ha("right")
note.set_va("top")
note.set_linespacing(2.0)
shot(fig, canvas, "text-align")
note.set_rotation_mode("anchor")
shot(fig, canvas, "text-anchor")
fp = title.get_fontproperties()
fp.set_family("monospace")
shot(fig, canvas, "text-family")
fp.get_family().append("serif")
fp.get_family().reverse()
shot(fig, canvas, "text-family-inplace")
ax.tick_params(axis="x", labelsize=14, labelrotation=45)
shot(fig, canvas, "text-tickparams")
ax.xaxis.set_major_formatter(lambda v, pos: "%.2f м" % v)
shot(fig, canvas, "text-formatter")
ax.set_xscale("log")
ax.set_xlim(0.1, 100)
shot(fig, canvas, "text-log")
fig.set_size_inches(7, 3)
canvas = FigureCanvasAgg(fig)
shot(fig, canvas, "text-resize")
fig.set_dpi(150)
shot(fig, canvas, "text-dpi")
matplotlib.rcParams["text.hinting"] = "none"
shot(fig, canvas, "text-hinting")
matplotlib.rcParams["text.hinting"] = "force_autohint"
leg.get_texts()[0].set_text("новая подпись")
ax.set_ylabel("ось Y")
ax.yaxis.set_label_position("right")
ax.yaxis.tick_right()
shot(fig, canvas, "text-right")

a = FontProperties(family="serif", size=12)
b = a.copy()
assert hash(a) == hash(b) and a == b
b.set_size(13)
assert hash(a) != hash(b) and a != b
b.set_size(12)
assert a == b
c = pickle.loads(pickle.dumps(a))
assert c == a and hash(c) == hash(a)
a.set_weight("bold")
assert a != c
d = FontProperties()
h0 = hash(d)
d.get_family().append("x")
assert hash(d) != h0
d.get_family().pop()
assert hash(d) == h0
for setter, v in (("set_style", "italic"), ("set_variant", "small-caps"), ("set_stretch", "condensed"),
                  ("set_file", "/x.ttf"), ("set_math_fontfamily", "cm"), ("set_family", ["cursive"])):
    e = FontProperties()
    h = hash(e)
    getattr(e, setter)(v)
    assert hash(e) != h, setter


def surface(ax):
    x, y = np.meshgrid(np.linspace(-4, 4, 40), np.linspace(-4, 4, 40))
    r = np.sqrt(x ** 2 + y ** 2) + 0.01
    ax.plot_surface(x, y, np.sin(r) / r, cmap="viridis", linewidth=0)


def surface_edges(ax):
    x, y = np.meshgrid(np.linspace(-2, 2, 12), np.linspace(-2, 2, 12))
    ax.plot_surface(x, y, x * y, color="tab:orange", edgecolor="k", alpha=0.7, shade=False)


def flat(ax):
    x, y = np.meshgrid(np.arange(6.0), np.arange(6.0))
    ax.plot_surface(x, y, np.zeros_like(x), cmap="coolwarm", edgecolor="w")
    ax.view_init(90, -90)


def bars3d(ax):
    xs, ys = np.meshgrid(np.arange(4), np.arange(3))
    ax.bar3d(xs.ravel(), ys.ravel(), 0, 0.6, 0.6, rng.random(12) * 3, shade=True)


def trisurf(ax):
    t = rng.random((60, 2)) * 4 - 2
    ax.plot_trisurf(t[:, 0], t[:, 1], np.sin(t[:, 0]) * t[:, 1], cmap="plasma")


def wire_scatter(ax):
    x, y = np.meshgrid(np.linspace(-2, 2, 10), np.linspace(-2, 2, 10))
    ax.plot_wireframe(x, y, x ** 2 - y ** 2)
    ax.scatter(rng.random(30), rng.random(30), rng.random(30) * 4, c=rng.random(30))


def mixed(ax):
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    polys = [[(0, 0, 0), (1, 0, 0), (1, 1, 0)], [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
             [(0, 0, 2), (2, 0, 2), (2, 2, 2), (1, 3, 2), (0, 2, 2)]]
    ax.add_collection3d(Poly3DCollection(polys, facecolors=["r", "g", "b"], edgecolors="k", alpha=0.6))
    ax.set(xlim=(0, 2), ylim=(0, 3), zlim=(0, 2))


def nan_surface(ax):
    x, y = np.meshgrid(np.linspace(-2, 2, 10), np.linspace(-2, 2, 10))
    z = x + y
    z[3:5, 3:5] = np.nan
    ax.plot_surface(x, y, z, cmap="viridis")


def zsort_min(ax):
    x, y = np.meshgrid(np.linspace(-2, 2, 14), np.linspace(-2, 2, 14))
    ax.plot_surface(x, y, np.cos(x) * y, cmap="magma", edgecolor="k", linewidth=0.3).set_zsort("min")


def voxels(ax):
    v = np.zeros((4, 4, 4), bool)
    v[1:3, 1:3, :] = True
    v[0, 0, 0] = True
    ax.voxels(v, facecolors="tab:blue", edgecolor="k")


for make in (surface, surface_edges, flat, bars3d, trisurf, wire_scatter, mixed, nan_surface, zsort_min, voxels):
    fig, canvas = new()
    ax = fig.add_subplot(projection="3d")
    make(ax)
    for i, (elev, azim) in enumerate([(ax.elev, ax.azim), (10, 30), (75, -120), (-20, 200)]):
        ax.view_init(elev, azim)
        shot(fig, canvas, "%s-%d" % (make.__name__, i))
    timed(canvas, make.__name__, lambda i: ax.view_init(30 + i, -60 + 3 * i))

with open(os.path.join(OUT, "log.txt"), "w") as f:
    f.write("\n".join(log) + "\n")
print("кадров %d" % len(log))
