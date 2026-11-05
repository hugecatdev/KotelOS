NORMAL = "normal"
ROMAN = "roman"
BOLD = "bold"
ITALIC = "italic"

_n = [0]


class Font:
    def __init__(self, root=None, font=None, name=None, exists=False, **options):
        self._o = {"family": "TkDefaultFont", "size": 10, "weight": "normal", "slant": "roman", "underline": 0,
                   "overstrike": 0}
        if font is not None:
            a = list(font) if isinstance(font, (tuple, list)) else str(font).split()
            if a:
                self._o["family"] = str(a[0])
            if len(a) > 1:
                self._o["size"] = int(a[1])
            for s in a[2:]:
                s = str(s)
                if s in ("bold", "normal"):
                    self._o["weight"] = s
                elif s in ("italic", "roman"):
                    self._o["slant"] = s
                elif s in ("underline", "overstrike"):
                    self._o[s] = 1
        self._o.update(options)
        _n[0] += 1
        self.name = name or "font%d" % _n[0]

    def _spec(self):
        o = self._o
        st = []
        if o["weight"] == "bold":
            st.append("bold")
        if o["slant"] == "italic":
            st.append("italic")
        if o["underline"]:
            st.append("underline")
        if o["overstrike"]:
            st.append("overstrike")
        return [str(o["family"]), str(o["size"])] + st

    def __str__(self):
        return self.name

    def configure(self, **kw):
        if not kw:
            return dict(self._o)
        self._o.update(kw)

    config = configure

    def cget(self, option):
        return self._o[option]

    def __getitem__(self, option):
        return self._o[option]

    def __setitem__(self, option, value):
        self._o[option] = value

    def actual(self, option=None, displayof=None):
        return self._o[option] if option else dict(self._o)

    def copy(self):
        return Font(**self._o)

    def _px(self):
        s = int(self._o["size"])
        return -s if s < 0 else s * 4 / 3 if s else 13

    def measure(self, text, displayof=None):
        return int(len(str(text)) * self._px() * 0.6 + 0.5)

    def metrics(self, *options, **kw):
        px = self._px()
        d = {"ascent": int(px * 0.8), "descent": int(px * 0.2 + 0.5), "linespace": int(px * 1.4), "fixed": 1}
        return d[options[0]] if options else d


def families(root=None, displayof=None):
    return ("monospace", "sans-serif", "serif", "Courier", "Helvetica", "Times")


def names(root=None):
    return ("TkDefaultFont", "TkTextFont", "TkFixedFont", "TkHeadingFont", "TkMenuFont", "TkCaptionFont")


def nametofont(name, root=None):
    return Font(name=name, family=name, exists=True)
