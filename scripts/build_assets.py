"""Build the SVG assets for the profile README ("Aurora" theme).

Every SVG is self-contained: the fonts it uses are subset to the glyphs it
draws and embedded as base64 WOFF2, because GitHub serves README images
through <img>, which cannot load external fonts or run scripts. Motion is
CSS keyframes and SMIL only, and switches off under prefers-reduced-motion.

    uv run --with fonttools --with brotli scripts/build_assets.py

Fonts (Inter, JetBrains Mono, both OFL) are downloaded from Fontsource into
scripts/.fonts on first run.
"""

from __future__ import annotations

import base64
import io
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT_DIR = Path(__file__).resolve().parent / ".fonts"

FONTS = {
    "sans400": ("inter", 400),
    "sans500": ("inter", 500),
    "sans600": ("inter", 600),
    "sans700": ("inter", 700),
    "mono500": ("jetbrains-mono", 500),
}

# Tailwind-style hues. `glow` paints light (blobs, auras); `ink` paints marks
# that must stay readable (text, numbers, strokes) on that theme's base.
HUES = {
    #           300        400        500        600
    "violet":  ("#C4B5FD", "#A78BFA", "#8B5CF6", "#7C3AED"),
    "pink":    ("#F9A8D4", "#F472B6", "#EC4899", "#DB2777"),
    "orange":  ("#FDBA74", "#FB923C", "#F97316", "#EA580C"),
    "amber":   ("#FCD34D", "#FBBF24", "#F59E0B", "#D97706"),
    "cyan":    ("#67E8F9", "#22D3EE", "#06B6D4", "#0891B2"),
    "blue":    ("#93C5FD", "#60A5FA", "#3B82F6", "#2563EB"),
    "emerald": ("#6EE7B7", "#34D399", "#10B981", "#059669"),
    "rose":    ("#FDA4AF", "#FB7185", "#F43F5E", "#E11D48"),
    "fuchsia": ("#F0ABFC", "#E879F9", "#D946EF", "#C026D3"),
}

THEMES = {
    "dark": dict(
        base="#07070A",
        text="#FAFAFA",
        muted="#B4B4BF",
        dim="#7A7A88",
        glass="#FFFFFF", glass_op=0.045,
        edge="#FFFFFF", edge_op=0.10,
        glow_i=2, ink_i=1,
        hero_op=0.50, card_op=0.30, soft_op=0.18,
        grain_op=0.08,
    ),
    "light": dict(
        base="#FFFFFF",
        text="#0A0A0F",
        muted="#45454F",
        dim="#6B6B78",
        glass="#FFFFFF", glass_op=0.72,
        edge="#0A0A0F", edge_op=0.09,
        glow_i=0, ink_i=3,
        hero_op=0.70, card_op=0.45, soft_op=0.30,
        grain_op=0.035,
    ),
}


def glow(t: dict, hue: str) -> str:
    return HUES[hue][t["glow_i"]]


def ink(t: dict, hue: str) -> str:
    return HUES[hue][t["ink_i"]]


# ---------------------------------------------------------------- fonts


def font_path(key: str) -> Path:
    family, weight = FONTS[key]
    path = FONT_DIR / f"{family}-{weight}.ttf"
    if not path.exists():
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        url = f"https://cdn.jsdelivr.net/fontsource/fonts/{family}@latest/latin-{weight}-normal.ttf"
        path.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    return path


_metrics: dict[str, tuple[dict[int, str], dict[str, tuple[int, int]], int]] = {}


def metrics(key: str):
    if key not in _metrics:
        f = TTFont(font_path(key))
        _metrics[key] = (f.getBestCmap(), f["hmtx"].metrics, f["head"].unitsPerEm)
    return _metrics[key]


def measure(s: str, key: str, size: float, tracking: float = 0) -> float:
    cmap, hmtx, upm = metrics(key)
    width = 0.0
    for ch in s:
        glyph = cmap.get(ord(ch))
        if glyph is None:
            raise ValueError(f"{key} has no glyph for {ch!r} in {s!r}")
        width += hmtx[glyph][0] * size / upm
    return width + tracking * len(s)


def wrap(s: str, key: str, size: float, max_width: float) -> list[str]:
    lines, line = [], ""
    for word in s.split():
        trial = f"{line} {word}".strip()
        if line and measure(trial, key, size) > max_width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def font_face(key: str, chars: set[str]) -> str:
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga", "calt", "tnum", "ss01", "cv11"]
    opts.name_IDs = []
    opts.notdef_outline = False
    font = TTFont(font_path(key))
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(chars | {" "})))
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    data = base64.b64encode(buf.getvalue()).decode()
    return f"@font-face{{font-family:'{key}';src:url(data:font/woff2;base64,{data}) format('woff2');}}"


# ---------------------------------------------------------------- svg doc


@dataclass
class Doc:
    w: int
    h: int
    t: dict
    title: str
    body: list[str] = field(default_factory=list)
    defs: list[str] = field(default_factory=list)
    css: dict[str, str] = field(default_factory=dict)
    glyphs: dict[str, set[str]] = field(default_factory=dict)
    _ids: int = 0

    def add(self, s: str) -> None:
        self.body.append(s)

    def uid(self, prefix: str) -> str:
        self._ids += 1
        return f"{prefix}{self._ids}"

    def style(self, key: str, rule: str) -> None:
        self.css[key] = rule

    def text(self, x, y, s, key="sans400", size=16, fill=None, tracking=0.0, anchor="start", cls="", extra=""):
        self.glyphs.setdefault(key, set()).update(s)
        fill = fill or self.t["text"]
        attrs = f'x="{x:.1f}" y="{y:.1f}" font-family="{key}" font-size="{size}" fill="{fill}"'
        if tracking:
            attrs += f' letter-spacing="{tracking}"'
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        if cls:
            attrs += f' class="{cls}"'
        self.add(f"<text {attrs} {extra}>{escape(s)}</text>")

    def render(self) -> str:
        faces = "".join(font_face(k, v) for k, v in sorted(self.glyphs.items()))
        style = faces + "".join(self.css.values()) + (
            "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        )
        fallback = "text{font-family:Inter,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.title)}">'
            f"<title>{escape(self.title)}</title>"
            f"<style>{fallback}{style}</style>"
            f"<defs>{''.join(self.defs)}</defs>"
            f"{''.join(self.body)}</svg>\n"
        )


# ---------------------------------------------------------------- primitives


def linear(d: Doc, colors: list[str], x1=0.0, y1=0.0, x2=1.0, y2=0.0, user=False, ops=None) -> str:
    """A linear gradient; with user=True the coordinates are in user space."""
    gid = d.uid("lg")
    units = ' gradientUnits="userSpaceOnUse"' if user else ""
    n = len(colors) - 1
    stops = "".join(
        f'<stop offset="{i / n:.3f}" stop-color="{c}"'
        + (f' stop-opacity="{ops[i]}"' if ops else "")
        + "/>"
        for i, c in enumerate(colors)
    )
    d.defs.append(f'<linearGradient id="{gid}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"{units}>{stops}</linearGradient>')
    return f"url(#{gid})"


def shimmer(d: Doc, colors: list[str], x: float, width: float, dur: float = 9) -> str:
    """A horizontal gradient that slides forever; colors loop seamlessly."""
    gid = d.uid("sh")
    seq = colors + [colors[0]]
    n = len(seq) - 1
    stops = "".join(f'<stop offset="{i / n:.3f}" stop-color="{c}"/>' for i, c in enumerate(seq))
    d.defs.append(
        f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{x}" y1="0" x2="{x + width}" y2="0" spreadMethod="repeat">'
        f"{stops}"
        f'<animateTransform attributeName="gradientTransform" type="translate" from="0 0" to="{width} 0" dur="{dur}s" repeatCount="indefinite"/>'
        f"</linearGradient>"
    )
    return f"url(#{gid})"


def blob(d: Doc, cx: float, cy: float, r: float, color: str, op: float, drift: tuple[float, float] = (0, 0), dur: float = 16) -> None:
    gid = d.uid("rg")
    d.defs.append(
        f'<radialGradient id="{gid}"><stop offset="0" stop-color="{color}" stop-opacity="{op}"/>'
        f'<stop offset="0.55" stop-color="{color}" stop-opacity="{op * 0.35:.3f}"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>'
    )
    if drift == (0, 0):
        d.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{gid})"/>')
        return
    cls = d.uid("dr")
    d.style(cls, f"@keyframes {cls}{{to{{transform:translate({drift[0]}px,{drift[1]}px) scale(1.08)}}}}"
                 f".{cls}{{transform-box:fill-box;transform-origin:center;animation:{cls} {dur}s ease-in-out infinite alternate}}")
    d.add(f'<circle class="{cls}" cx="{cx}" cy="{cy}" r="{r}" fill="url(#{gid})"/>')


def grain(d: Doc) -> None:
    d.defs.append(
        '<filter id="grain" x="0" y="0" width="100%" height="100%">'
        '<feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch"/>'
        '<feColorMatrix type="saturate" values="0"/></filter>'
    )
    d.add(f'<rect width="{d.w}" height="{d.h}" filter="url(#grain)" opacity="{d.t["grain_op"]}"/>')


def panel(d: Doc, x, y, w, h, r, stroke: str | None = None, stroke_w: float = 1, fill: str | None = None) -> str:
    """Base-colored rounded panel. Returns a clip-path url for its interior."""
    t = d.t
    cid = d.uid("clip")
    d.defs.append(f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}"/></clipPath>')
    d.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill or t["base"]}"/>')
    d._pending_stroke = (x, y, w, h, r, stroke, stroke_w)  # drawn last by close_panel
    return f"url(#{cid})"


def close_panel(d: Doc) -> None:
    x, y, w, h, r, stroke, sw = d._pending_stroke
    t = d.t
    if stroke:
        d.add(f'<rect x="{x + sw / 2}" y="{y + sw / 2}" width="{w - sw}" height="{h - sw}" rx="{r}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>')
    else:
        d.add(f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{w - 1}" height="{h - 1}" rx="{r}" fill="none" stroke="{t["edge"]}" stroke-opacity="{t["edge_op"]}"/>')


def glass(d: Doc, x, y, w, h, r, stroke: str | None = None, stroke_op: float | None = None) -> None:
    t = d.t
    d.add(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{t["glass"]}" fill-opacity="{t["glass_op"]}" '
        f'stroke="{stroke or t["edge"]}" stroke-opacity="{stroke_op if stroke_op is not None else t["edge_op"] * 1.4:.2f}"/>'
    )


def live_dot(d: Doc, cx: float, cy: float, r: float = 4, color: str | None = None) -> None:
    color = color or ink(d.t, "emerald")
    d.style("ping", "@keyframes ping{0%{r:4px;opacity:.6}80%,100%{r:12px;opacity:0}}"
                    ".ping{animation:ping 2.4s cubic-bezier(0,0,.2,1) infinite}")
    d.add(f'<circle class="ping" cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')
    d.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')


def arrow_ne(d: Doc, x: float, y: float, s: float, color: str, sw: float = 1.6) -> None:
    """A north-east arrow whose bounding box starts at (x, y) with side s."""
    d.add(
        f'<path d="M{x} {y + s} L{x + s} {y} M{x + s * 0.3} {y} H{x + s} V{y + s * 0.7}" '
        f'fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def fade_in(d: Doc) -> None:
    d.style("up", "@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
                  ".a{animation:up .9s cubic-bezier(.2,.7,.2,1) both}")


# ---------------------------------------------------------------- hero


def hero(t: dict) -> Doc:
    W, H = 1200, 460
    d = Doc(W, H, t, "Rohit Kumar — AI Engineer")
    fade_in(d)
    border = shimmer(d, [ink(t, "violet"), ink(t, "pink"), ink(t, "orange"), ink(t, "cyan")], 0, W, 10)
    clip = panel(d, 0, 0, W, H, 22, stroke=border, stroke_w=1.5)
    d.add(f'<g clip-path="{clip}">')
    op = t["hero_op"]
    blob(d, 1010, 40, 420, glow(t, "violet"), op, (-60, 40), 18)
    blob(d, 760, 330, 300, glow(t, "pink"), op * 0.8, (50, -30), 14)
    blob(d, 1180, 430, 280, glow(t, "orange"), op * 0.7, (-40, -40), 20)
    blob(d, 90, 500, 380, glow(t, "cyan"), op * 0.6, (60, -20), 22)
    grain(d)
    d.add("</g>")

    x = 72
    # eyebrow
    label = "OPEN TO AI ENGINEERING ROLES"
    lw = measure(label, "mono500", 13.5, 1.6)
    d.add('<g class="a" style="animation-delay:.05s">')
    glass(d, x, 62, lw + 50, 34, 17)
    live_dot(d, x + 18, 79, 4)
    d.text(x + 34, 83.8, label, "mono500", 13.5, t["text"], tracking=1.6)
    d.add("</g>")

    name = "Rohit Kumar"
    nw = measure(name, "sans700", 96, -3.8)
    fill = shimmer(d, [ink(t, "violet"), ink(t, "pink"), ink(t, "orange"), ink(t, "pink")], x, nw * 1.4, 8)
    d.add('<g class="a" style="animation-delay:.15s">')
    d.text(x - 4, 202, name, "sans700", 96, fill, tracking=-3.8)
    d.add("</g>")
    d.add('<g class="a" style="animation-delay:.28s">')
    role = "AI Engineer"
    rw = measure(role, "sans600", 34, -0.8)
    d.text(x, 256, role, "sans600", 34, linear(d, [ink(t, "cyan"), ink(t, "blue"), ink(t, "violet")], x, 0, x + rw, 0, user=True), tracking=-0.8)
    d.add("</g>")
    d.add('<g class="a" style="animation-delay:.4s">')
    d.text(x, 318, "I build retrieval systems that cite their sources,", "sans400", 22, t["muted"], tracking=-0.25)
    d.text(x, 350, "multi-agent pipelines, and the evals that keep them honest.", "sans400", 22, t["muted"], tracking=-0.25)
    d.add("</g>")

    # tags separated by colored dots
    d.add('<g class="a" style="animation-delay:.55s">')
    tags = [("RAG", "violet"), ("MULTI-AGENT", "pink"), ("EVALS", "orange"), ("COMPUTER VISION", "emerald"), ("INDIA", "cyan")]
    tx = x
    for i, (tag, hue) in enumerate(tags):
        d.add(f'<circle cx="{tx + 4}" cy="{404}" r="4" fill="{ink(t, hue)}"/>')
        d.text(tx + 16, 409, tag, "mono500", 14, t["muted"], tracking=1.4)
        tx += 16 + measure(tag, "mono500", 14, 1.4) + 26
    d.add("</g>")

    # pipeline motif: an answer only ships after it is retrieved, generated and judged
    steps = [
        ("query", "what the user asked", "cyan"),
        ("retrieve", "hybrid dense + BM25", "blue"),
        ("generate", "from passages only", "violet"),
        ("judge", "groundedness check", "pink"),
        ("answer", "with citations", "emerald"),
    ]
    bx, by, bw, bh, gap = 800, 64, 150, 46, 24
    sx = bx + 22
    top, bottom = by + bh / 2, by + (len(steps) - 1) * (bh + gap) + bh / 2
    spine = linear(d, [ink(t, h) for _, _, h in steps], 0, top, 0, bottom, user=True)
    d.add(f'<line x1="{sx}" y1="{top}" x2="{sx}" y2="{bottom}" stroke="{spine}" stroke-width="2" stroke-opacity="0.8"/>')
    d.defs.append(f'<path id="spine" d="M{sx} {top} V{bottom}"/>')
    pulse_colors = ";".join(ink(t, h) for _, _, h in steps)
    motion = (
        f'<animateMotion dur="5s" repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.8;1" calcMode="linear"><mpath href="#spine"/></animateMotion>'
        f'<animate attributeName="fill" values="{pulse_colors}" dur="5s" repeatCount="indefinite" calcMode="discrete" keyTimes="0;0.16;0.36;0.56;0.76"/>'
        f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.06;0.74;0.8;1" dur="5s" repeatCount="indefinite"/>'
    )
    d.add(f'<circle r="10" fill-opacity="0.25">{motion}</circle>')
    d.add(f'<circle r="4">{motion}</circle>')
    for i, (step, note, hue) in enumerate(steps):
        y = by + i * (bh + gap)
        c = ink(t, hue)
        d.add(f'<g class="a" style="animation-delay:{0.3 + i * 0.12:.2f}s">')
        glass(d, bx, y, bw, bh, 12, stroke=c, stroke_op=0.55)
        d.add(f'<circle cx="{sx}" cy="{y + bh / 2}" r="9" fill="{c}" fill-opacity="0.18"/>')
        d.add(f'<circle cx="{sx}" cy="{y + bh / 2}" r="4.5" fill="{c}"/>')
        d.text(bx + 40, y + bh / 2 + 5.3, step, "mono500", 15, t["text"], tracking=0.3)
        d.text(bx + bw + 18, y + bh / 2 + 5.6, note, "sans400", 16, t["muted"])
        if step == "answer":
            cx, cy = bx + bw - 22, y + bh / 2
            d.add(f'<path d="M{cx - 5} {cy} l3.5 3.5 l6.5 -7" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
        d.add("</g>")
    close_panel(d)
    return d


# ---------------------------------------------------------------- ticker


TICKER = [
    ("6,423", "bird species named", "emerald"),
    ("14", "Indic languages, one voice RAG", "cyan"),
    ("0.58", "recall@5, multilingual", "blue"),
    ("75", "real CI failures mined", "orange"),
    ("79%", "top-1 on unseen birds", "amber"),
    ("65", "tests passing", "violet"),
    ("4", "agents, one of them a Judge", "pink"),
    ("7", "agents in the codegen graph", "fuchsia"),
]


def ticker(t: dict) -> Doc:
    W, H = 1200, 72
    d = Doc(W, H, t, "Highlights: " + "; ".join(f"{v} {l}" for v, l, _ in TICKER))
    clip = panel(d, 0, 0, W, H, 36)
    d.add(f'<g clip-path="{clip}">')
    for i, (_, _, hue) in enumerate(TICKER[:4]):
        blob(d, 150 + i * 300, 36, 220, glow(t, hue), t["soft_op"] * 0.8)
    d.add("</g>")

    # one sequence, drawn twice, slides left by exactly its own width
    items, x = [], 0.0
    for value, label, hue in TICKER:
        items.append((x, value, label, hue))
        x += 22 + measure(value, "sans600", 20, -0.4) + 10 + measure(label, "sans400", 18) + 44
    seq_w = x
    d.defs.append(
        '<linearGradient id="edge"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset="0.08" stop-color="#fff"/><stop offset="0.92" stop-color="#fff"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<mask id="fade"><rect width="{W}" height="{H}" fill="url(#edge)"/></mask>'
    )
    d.add('<g mask="url(#fade)"><g>')
    d.add(f'<animateTransform attributeName="transform" type="translate" from="0 0" to="-{seq_w:.1f} 0" '
          f'dur="{seq_w / 38:.1f}s" repeatCount="indefinite"/>')
    for copy in (0, seq_w):
        for ix, value, label, hue in items:
            ox = 28 + copy + ix
            c = ink(t, hue)
            d.add(f'<circle cx="{ox + 5}" cy="36" r="9" fill="{c}" fill-opacity="0.2"/><circle cx="{ox + 5}" cy="36" r="4" fill="{c}"/>')
            vw = measure(value, "sans600", 20, -0.4)
            d.text(ox + 22, 43, value, "sans600", 20, c, tracking=-0.4)
            d.text(ox + 22 + vw + 10, 42.5, label, "sans400", 18, t["muted"])
    d.add("</g></g>")
    close_panel(d)
    return d


# ---------------------------------------------------------------- pills


PILLS = [
    ("linkedin", "LinkedIn", "link", ("blue", "cyan")),
    ("huggingface", "Hugging Face", "link", ("amber", "orange")),
    ("aria-live", "ARIA — live demo", "live", ("rose", "violet")),
    ("birdid-live", "BirdID — live demo", "live", ("amber", "emerald")),
]


def pill(t: dict, label: str, kind: str, hues: tuple[str, str]) -> Doc:
    size, h = 15, 44
    tw = measure(label, "sans500", size, -0.1)
    lead = 32 if kind == "live" else 22
    w = int(lead + tw + 14 + 12 + 22)
    d = Doc(w, h, t, label)
    a, b = ink(t, hues[0]), ink(t, hues[1])
    clip = panel(d, 0, 0, w, h, h / 2, stroke=linear(d, [a, b]), stroke_w=1.5)
    d.add(f'<g clip-path="{clip}">')
    blob(d, 0, h / 2, w * 0.7, glow(t, hues[0]), t["soft_op"])
    blob(d, w, h / 2, w * 0.6, glow(t, hues[1]), t["soft_op"])
    d.add("</g>")
    if kind == "live":
        live_dot(d, 20, h / 2, 3.8)
    d.text(lead, h / 2 + 5.3, label, "sans500", size, t["text"], tracking=-0.1)
    arrow_ne(d, lead + tw + 12, h / 2 - 5, 10, b, 1.7)
    close_panel(d)
    return d


# ---------------------------------------------------------------- section header


SECTIONS = [
    ("work", "SELECTED WORK", "06", ("violet", "pink")),
    ("also", "ALSO BUILT", "06", ("orange", "pink")),
    ("stack", "STACK", "05", ("cyan", "blue")),
    ("principles", "HOW I WORK", "03", ("emerald", "cyan")),
    ("activity", "ACTIVITY", "", ("pink", "orange")),
]


def section(t: dict, label: str, count: str, hues: tuple[str, str]) -> Doc:
    d = Doc(1200, 64, t, label.title())
    a, b = ink(t, hues[0]), ink(t, hues[1])
    d.defs.append('<filter id="bl" x="-50%" y="-300%" width="200%" height="700%"><feGaussianBlur stdDeviation="4"/></filter>')
    bar = linear(d, [a, b])
    d.add(f'<rect x="0" y="29" width="34" height="5" rx="2.5" fill="{bar}" filter="url(#bl)" opacity="0.9"/>')
    d.add(f'<rect x="0" y="29.5" width="34" height="4" rx="2" fill="{bar}"/>')
    d.text(50, 37.5, label, "mono500", 15, t["text"], tracking=2.6)
    lw = measure(label, "mono500", 15, 2.6)
    end = 1200 - (measure(count, "mono500", 15, 1.5) + 18 if count else 0)
    x1 = 50 + lw + 18
    d.add(f'<line x1="{x1}" y1="32" x2="{end}" y2="32" stroke="{linear(d, [b, b], x1, 0, end, 0, user=True, ops=[0.6, 0.05])}" stroke-width="1.2"/>')
    if count:
        d.text(1200, 37.5, count, "mono500", 15, a, tracking=1.5, anchor="end")
    return d


# ---------------------------------------------------------------- project cards


@dataclass
class Project:
    slug: str
    name: str
    kind: str
    pitch: str
    metrics: list[tuple[str, str]]
    chips: list[str]
    hues: tuple[str, str]
    motif: str
    live: bool = False


PROJECTS = [
    Project(
        "aria", "ARIA", "CLINICAL RAG · MULTI-AGENT",
        "A clinical pharmacotherapy assistant where a Judge agent scores groundedness before any answer reaches the user.",
        [("4", "agents, one of them a Judge"), ("Page-level", "citation on every claim")],
        ["LangGraph", "Qdrant", "FastAPI", "React"], ("rose", "violet"), "shield", live=True,
    ),
    Project(
        "birdid", "BirdID", "COMPUTER VISION · AUDIO",
        "Identifies birds by photo or call. An open-set gate lets a 200-class model say “not one of mine” — then BioCLIP names it.",
        [("6,423", "species via BioCLIP"), ("79%", "top-1 on unseen species")],
        ["PyTorch", "BioCLIP", "BirdNET", "FastAPI"], ("amber", "emerald"), "rings", live=True,
    ),
    Project(
        "voice-rag", "Voice RAG", "MULTILINGUAL · SPEECH",
        "Ask by voice in any of 14 Indic languages and get a grounded answer. Hybrid dense + BM25 with server-side RRF.",
        [("14", "Indic languages"), ("0.58", "recall@5 · 65 tests")],
        ["Sarvam STT", "Qdrant", "Rerankers", "Groq"], ("cyan", "blue"), "wave",
    ),
    Project(
        "ci-triage", "CI Triage Agent", "AGENTS · DEVELOPER TOOLS",
        "Investigates failed GitHub Actions runs: gathers evidence, verifies a root-cause hypothesis, proposes a fix a human approves.",
        [("75", "real CI failures mined"), ("50 / 25", "dev / held-out split")],
        ["LangGraph", "uv", "pytest", "GitHub API"], ("orange", "rose"), "branch",
    ),
    Project(
        "finstock", "FinStock", "FINTECH · MULTI-AGENT",
        "Research assistant for NSE/BSE and US markets. Parallel-fanout LangGraph that cites every data point and refuses to give advice.",
        [("5", "LangGraph nodes"), ("2", "markets · India + US")],
        ["LangGraph", "SSE", "ChromaDB", "React"], ("emerald", "cyan"), "chart",
    ),
    Project(
        "codegen", "Multi-agent Codegen", "CODE GENERATION",
        "Turns a prompt into a running React + FastAPI app, then executes, tests and self-repairs it in a fixer loop.",
        [("7", "specialised agents"), ("3×", "self-repair attempts")],
        ["LangGraph", "Ollama", "SQLite", "FastAPI"], ("violet", "fuchsia"), "code",
    ),
]


def motif(d: Doc, kind: str, x: float, y: float, s: float, stroke: str, a: str, b: str) -> None:
    """A small line-drawn emblem in an s×s box at (x, y)."""
    sw = 2.2
    common = f'fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"'
    cx, cy = x + s / 2, y + s / 2
    if kind == "shield":
        d.add(f'<path d="M{cx} {y + 3} L{x + s - 6} {y + 11} V{cy + 2} C{x + s - 6} {y + s - 12} {cx + 8} {y + s - 4} {cx} {y + s - 2} '
              f'C{cx - 8} {y + s - 4} {x + 6} {y + s - 12} {x + 6} {cy + 2} V{y + 11} Z" {common}/>')
        d.add(f'<path d="M{cx - 8} {cy + 1} l6 6 l11 -12" {common}/>')
    elif kind == "rings":
        for r in (s / 2 - 2, s / 3, s / 6):
            d.add(f'<circle cx="{cx}" cy="{cy}" r="{r:.1f}" {common}/>')
        live_dot(d, cx, cy, 3.5, b)
    elif kind == "wave":
        d.style("eq", "@keyframes eq{0%,100%{transform:scaleY(.35)}50%{transform:scaleY(1)}}"
                      ".eq{transform-box:fill-box;transform-origin:center;animation:eq 1.4s ease-in-out infinite}")
        heights = [0.35, 0.7, 1.0, 0.55, 0.85, 0.45, 0.65]
        step = s / len(heights)
        for i, hf in enumerate(heights):
            bh = s * hf
            d.add(f'<rect class="eq" style="animation-delay:{i * -0.17:.2f}s" x="{x + i * step + step / 2 - 2:.1f}" y="{cy - bh / 2:.1f}" '
                  f'width="4" height="{bh:.1f}" rx="2" fill="{stroke}"/>')
    elif kind == "branch":
        p1, p2, p3 = (x + 12, y + 8), (x + 12, y + s - 8), (x + s - 10, y + 18)
        d.add(f'<path d="M{p1[0]} {p1[1] + 5} V{p2[1] - 5} M{p3[0]} {p3[1] + 5} C{p3[0]} {cy + 10} {p1[0]} {cy + 4} {p1[0]} {p2[1] - 8}" {common}/>')
        for px, py in (p1, p2, p3):
            d.add(f'<circle cx="{px}" cy="{py}" r="5" {common}/>')
    elif kind == "chart":
        pts = [(x + 3, y + s - 10), (x + s * 0.3, y + s * 0.6), (x + s * 0.5, y + s * 0.72), (x + s - 6, y + 10)]
        d.add(f'<polyline points="{" ".join(f"{px:.1f},{py:.1f}" for px, py in pts)}" {common}/>')
        d.add(f'<path d="M{x + s - 18} {y + 9} H{x + s - 5} V{y + 22}" {common}/>')
        d.add(f'<line x1="{x + 2}" y1="{y + s - 1}" x2="{x + s - 2}" y2="{y + s - 1}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-opacity="0.4"/>')
    elif kind == "code":
        d.add(f'<path d="M{x + 14} {y + 12} L{x + 3} {cy} L{x + 14} {y + s - 12}" {common}/>')
        d.add(f'<path d="M{x + s - 14} {y + 12} L{x + s - 3} {cy} L{x + s - 14} {y + s - 12}" {common}/>')
        d.add(f'<path d="M{cx + 6} {y + 6} L{cx - 6} {y + s - 6}" {common}/>')


def card(t: dict, i: int, p: Project) -> Doc:
    W, H, pad = 580, 400, 36
    d = Doc(W, H, t, f"{p.name} — {p.pitch}")
    a_hue, b_hue = p.hues
    a, b = ink(t, a_hue), ink(t, b_hue)
    edge = linear(d, [a, t["edge"], b], 0, 0, 1, 1, ops=[0.75, t["edge_op"], 0.5])
    clip = panel(d, 0, 0, W, H, 20, stroke=edge, stroke_w=1.3)
    d.add(f'<g clip-path="{clip}">')
    blob(d, W - 40, -10, 320, glow(t, a_hue), t["card_op"], (-30, 30), 16)
    blob(d, 60, H + 30, 280, glow(t, b_hue), t["card_op"] * 0.75, (40, -20), 19)
    grain(d)
    d.add(f'<rect x="0" y="0" width="{W}" height="4" fill="{linear(d, [a, b])}"/>')
    d.add("</g>")

    d.text(pad, 58, f"{i:02d}", "mono500", 15, a, tracking=1.5)
    d.text(pad + 36, 58, p.kind, "mono500", 15, t["dim"], tracking=1.5)
    if p.live:
        label = "LIVE"
        lw = measure(label, "mono500", 14, 1.5)
        em = ink(t, "emerald")
        x1 = W - pad - lw - 34
        d.add(f'<rect x="{x1}" y="37" width="{lw + 34}" height="30" rx="15" fill="{em}" fill-opacity="0.12" stroke="{em}" stroke-opacity="0.5"/>')
        live_dot(d, x1 + 15, 52, 3.8, em)
        d.text(x1 + 25, 57, label, "mono500", 14, em, tracking=1.5)
    else:
        arrow_ne(d, W - pad - 14, 45, 14, b, 1.8)

    d.text(pad - 2, 120, p.name, "sans600", 38, t["text"], tracking=-1.3)
    nw = measure(p.name, "sans600", 38, -1.3)
    motif(d, p.motif, pad + nw + 16, 90, 34, linear(d, [a, b], 0, 0, 1, 1), a, b)

    for j, line in enumerate(wrap(p.pitch, "sans400", 20, W - 2 * pad)[:3]):
        d.text(pad, 162 + j * 29, line, "sans400", 20, t["muted"], tracking=-0.15)

    d.add(f'<line x1="{pad}" y1="252" x2="{W - pad}" y2="252" stroke="{linear(d, [a, b], ops=[0.5, 0.1])}"/>')
    col = (W - 2 * pad) / 2
    for j, (value, label) in enumerate(p.metrics):
        mx = pad + j * col
        vw = measure(value, "sans700", 30, -1)
        d.text(mx, 296, value, "sans700", 30, linear(d, [a, b], mx, 0, mx + max(vw, 40), 0, user=True), tracking=-1)
        d.text(mx, 322, label, "sans400", 16, t["dim"])

    cx = pad
    for chip in p.chips:
        cw = measure(chip, "mono500", 14, 0.2) + 22
        d.add(f'<rect x="{cx}" y="342" width="{cw:.1f}" height="32" rx="8" fill="{a}" fill-opacity="0.10" stroke="{a}" stroke-opacity="0.35"/>')
        d.text(cx + 11, 363, chip, "mono500", 14, a, tracking=0.2)
        cx += cw + 8
    assert cx <= W - pad + 8, f"chips overflow on {p.name}"
    close_panel(d)
    return d


# ---------------------------------------------------------------- stack


STACK = [
    ("MODELS", "violet", ["PyTorch", "Hugging Face", "BioCLIP · BirdNET", "Ollama · Groq"]),
    ("RETRIEVAL", "cyan", ["Qdrant", "BM25 + RRF", "Cross-encoders", "ChromaDB"]),
    ("AGENTS", "pink", ["LangGraph", "Guardrails", "LLM-as-judge", "Eval harnesses"]),
    ("SERVING", "orange", ["FastAPI · SSE", "Docker", "PostgreSQL", "Flask"]),
    ("INTERFACE", "emerald", ["TypeScript", "React · Next.js", "Tailwind", "Streamlit"]),
]


def stack(t: dict) -> Doc:
    W, H, gap = 1200, 262, 16
    d = Doc(W, H, t, "Stack: " + "; ".join(f"{k.title()}: {', '.join(v)}" for k, _, v in STACK))
    cw = (W - gap * (len(STACK) - 1)) / len(STACK)
    for i, (head, hue, items) in enumerate(STACK):
        x = i * (cw + gap)
        c = ink(t, hue)
        clip = panel(d, x, 0, cw, H, 18, stroke=linear(d, [c, t["edge"]], 0, 0, 0.6, 1, ops=[0.6, t["edge_op"]]), stroke_w=1.2)
        d.add(f'<g clip-path="{clip}">')
        blob(d, x + cw * 0.15, -20, 190, glow(t, hue), t["card_op"])
        d.add(f'<rect x="{x}" y="0" width="{cw}" height="3" fill="{c}"/>')
        d.add("</g>")
        d.text(x + 24, 46, head, "mono500", 14, c, tracking=2)
        for j, item in enumerate(items):
            iy = 98 + j * 42
            d.add(f'<circle cx="{x + 28}" cy="{iy - 6.5}" r="3.5" fill="{c}"/>')
            d.text(x + 42, iy, item, "sans500", 19, t["text"], tracking=-0.3)
            assert 42 + measure(item, "sans500", 19, -0.3) < cw - 12, f"stack item overflows: {item}"
        close_panel(d)
    return d


# ---------------------------------------------------------------- principles


PRINCIPLES = [
    ("Ground it", "Every answer traces back to a source — a page, a passage, a log line.", ("cyan", "blue")),
    ("Measure it", "Recall, latency, held-out splits. A number before a claim.", ("violet", "fuchsia")),
    ("Ship it", "A live demo, tests that pass, and decisions written down.", ("pink", "orange")),
]


def principles(t: dict) -> Doc:
    W, H, gap = 1200, 240, 20
    d = Doc(W, H, t, "How I work: " + " ".join(f"{a}. {b}" for a, b, _ in PRINCIPLES))
    w = (W - 2 * gap) / 3
    for i, (head, body, (ha, hb)) in enumerate(PRINCIPLES):
        x = i * (w + gap)
        a, b = ink(t, ha), ink(t, hb)
        clip = panel(d, x, 0, w, H, 20, stroke=linear(d, [a, t["edge"], b], 0, 0, 1, 1, ops=[0.65, t["edge_op"], 0.45]), stroke_w=1.2)
        d.add(f'<g clip-path="{clip}">')
        blob(d, x + w, 0, 240, glow(t, ha), t["card_op"], (-20, 20), 15 + i * 2)
        blob(d, x, H, 200, glow(t, hb), t["card_op"] * 0.6)
        d.add("</g>")
        num = f"{i + 1:02d}"
        d.text(x + 32, 58, num, "sans700", 30, linear(d, [a, b], x + 32, 0, x + 70, 0, user=True), tracking=-0.5)
        d.text(x + 32, 108, head, "sans600", 32, t["text"], tracking=-0.9)
        for j, line in enumerate(wrap(body, "sans400", 20, w - 64)):
            d.text(x + 32, 150 + j * 29, line, "sans400", 20, t["muted"], tracking=-0.1)
        close_panel(d)
    return d


# ---------------------------------------------------------------- footer


def footer(t: dict) -> Doc:
    W = 1200
    d = Doc(W, 104, t, "Rohit Kumar · AI Engineer")
    hues = ["cyan", "violet", "pink", "orange"]
    line = linear(d, [ink(t, h) for h in hues], ops=None)
    fade = linear(d, ["#fff"] * 5, ops=[0, 1, 1, 1, 0])
    d.defs.append(f'<mask id="m"><rect width="{W}" height="104" fill="{fade}"/></mask>')
    d.defs.append('<filter id="bl" x="-10%" y="-400%" width="120%" height="900%"><feGaussianBlur stdDeviation="6"/></filter>')
    d.add(f'<g mask="url(#m)"><rect x="0" y="22" width="{W}" height="6" fill="{line}" filter="url(#bl)" opacity="0.7"/>'
          f'<rect x="0" y="24" width="{W}" height="2" fill="{line}"/></g>')
    label = "ROHIT KUMAR  ·  AI ENGINEER  ·  2026"
    lw = measure(label, "mono500", 14, 2.4)
    fill = shimmer(d, [ink(t, h) for h in hues], W / 2 - lw / 2, lw, 7)
    d.text(W / 2, 78, label, "mono500", 14, fill, tracking=2.4, anchor="middle")
    return d


# ---------------------------------------------------------------- main


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    out: dict[str, Doc] = {}
    for mode, t in THEMES.items():
        out[f"hero-{mode}"] = hero(t)
        out[f"ticker-{mode}"] = ticker(t)
        out[f"stack-{mode}"] = stack(t)
        out[f"principles-{mode}"] = principles(t)
        out[f"footer-{mode}"] = footer(t)
        for slug, label, count, hues in SECTIONS:
            out[f"section-{slug}-{mode}"] = section(t, label, count, hues)
        for slug, label, kind, hues in PILLS:
            out[f"pill-{slug}-{mode}"] = pill(t, label, kind, hues)
        for i, p in enumerate(PROJECTS, 1):
            out[f"card-{p.slug}-{mode}"] = card(t, i, p)
    for name, doc in out.items():
        svg = doc.render()
        (ASSETS / f"{name}.svg").write_text(svg)
        print(f"{name:32s} {len(svg) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
