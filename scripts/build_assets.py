"""Build the SVG assets for the profile README.

Every SVG is self-contained: the fonts it uses are subset to the glyphs it
draws and embedded as base64 WOFF2, because GitHub serves README images
through <img>, which cannot load external fonts.

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

THEMES = {
    "dark": dict(
        panel="#0B0B0E",
        raised="#131317",
        border="#24242B",
        hair="#1C1C22",
        text="#FAFAFA",
        muted="#A1A1AA",
        dim="#6B6B76",
        accent="#8B91FF",
        accent2="#5EEAD4",
        glow_opacity="0.22",
        grid="#FFFFFF",
        grid_opacity="0.07",
    ),
    "light": dict(
        panel="#FCFCFD",
        raised="#FFFFFF",
        border="#E4E4E9",
        hair="#EDEDF1",
        text="#09090B",
        muted="#52525B",
        dim="#8E8E99",
        accent="#4F46E5",
        accent2="#0D9488",
        glow_opacity="0.10",
        grid="#09090B",
        grid_opacity="0.07",
    ),
}


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
    css: list[str] = field(default_factory=list)
    glyphs: dict[str, set[str]] = field(default_factory=dict)

    def add(self, s: str) -> None:
        self.body.append(s)

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
        style = faces + "".join(self.css) + (
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


def frame(d: Doc, radius=18) -> None:
    t = d.t
    d.add(
        f'<rect x="0.5" y="0.5" width="{d.w - 1}" height="{d.h - 1}" rx="{radius}" '
        f'fill="{t["panel"]}" stroke="{t["border"]}"/>'
    )


def gradient(d: Doc, gid: str) -> None:
    t = d.t
    d.defs.append(
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{t["accent"]}"/><stop offset="1" stop-color="{t["accent2"]}"/>'
        f"</linearGradient>"
    )


def live_dot(d: Doc, cx: float, cy: float, r: float = 4, color: str | None = None) -> None:
    color = color or d.t["accent2"]
    d.css.append(
        "@keyframes ping{0%{r:4px;opacity:.55}80%,100%{r:11px;opacity:0}}"
        ".ping{animation:ping 2.4s cubic-bezier(0,0,.2,1) infinite}"
    )
    d.add(f'<circle class="ping" cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')
    d.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')


def arrow_ne(d: Doc, x: float, y: float, s: float, color: str, sw: float = 1.6) -> None:
    """A north-east arrow whose bounding box starts at (x, y) with side s."""
    d.add(
        f'<path d="M{x} {y + s} L{x + s} {y} M{x + s * 0.3} {y} H{x + s} V{y + s * 0.7}" '
        f'fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>'
    )


# ---------------------------------------------------------------- hero


def hero(t: dict) -> Doc:
    d = Doc(1200, 440, t, "Rohit Kumar — AI Engineer")
    gradient(d, "g")
    d.defs.append(
        f'<radialGradient id="glow" cx="0.82" cy="0.18" r="0.6">'
        f'<stop offset="0" stop-color="{t["accent"]}" stop-opacity="{t["glow_opacity"]}"/>'
        f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></radialGradient>'
        f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
        f'<circle cx="1" cy="1" r="1" fill="{t["grid"]}" fill-opacity="{t["grid_opacity"]}"/></pattern>'
        f'<radialGradient id="fade" cx="0.8" cy="0.4" r="0.55">'
        f'<stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<mask id="m"><rect width="1200" height="440" fill="url(#fade)"/></mask>'
        f'<clipPath id="clip"><rect x="0.5" y="0.5" width="1199" height="439" rx="18"/></clipPath>'
    )
    d.css.append(
        "@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
        ".a{animation:up .9s cubic-bezier(.2,.7,.2,1) both}"
        ".a1{animation-delay:.05s}.a2{animation-delay:.18s}.a3{animation-delay:.3s}.a4{animation-delay:.42s}.a5{animation-delay:.6s}"
        "@keyframes draw{from{stroke-dashoffset:260}to{stroke-dashoffset:0}}"
        ".rule{stroke-dasharray:260;animation:draw 1.4s .5s cubic-bezier(.2,.7,.2,1) both}"
    )
    frame(d)
    d.add('<g clip-path="url(#clip)">')
    d.add('<rect width="1200" height="440" fill="url(#glow)"/>')
    d.add('<rect width="1200" height="440" fill="url(#dots)" mask="url(#m)"/>')
    d.add("</g>")

    x = 72
    # eyebrow
    d.add('<g class="a a1">')
    live_dot(d, x + 5, 86)
    d.text(x + 22, 91, "OPEN TO AI ENGINEERING ROLES", "mono500", 14, t["muted"], tracking=1.8)
    d.add("</g>")
    d.add('<g class="a a2">')
    d.text(x - 4, 188, "Rohit Kumar", "sans700", 92, t["text"], tracking=-3.6)
    d.add("</g>")
    d.add('<g class="a a3">')
    d.text(x, 240, "AI Engineer", "sans500", 30, "url(#g)", tracking=-0.6)
    d.add("</g>")
    d.add(f'<line class="rule" x1="{x}" y1="270" x2="{x + 260}" y2="270" stroke="url(#g)" stroke-width="1.5"/>')
    d.add('<g class="a a4">')
    d.text(x, 312, "I build retrieval systems that cite their sources,", "sans400", 21, t["muted"], tracking=-0.2)
    d.text(x, 342, "multi-agent pipelines, and the evals that keep them honest.", "sans400", 21, t["muted"], tracking=-0.2)
    d.add("</g>")
    d.add('<g class="a a5">')
    d.text(x, 392, "RAG  ·  MULTI-AGENT  ·  EVALUATION  ·  COMPUTER VISION  ·  INDIA", "mono500", 14, t["dim"], tracking=1.4)
    d.add("</g>")

    # the pipeline motif: an answer only ships after it is retrieved, generated, and judged
    steps = [
        ("query", "what the user asked"),
        ("retrieve", "hybrid dense + BM25"),
        ("generate", "from passages only"),
        ("judge", "groundedness check"),
        ("answer", "with citations"),
    ]
    bx, by, bw, bh, gap = 800, 60, 148, 44, 26
    spine_x = bx + 20
    top, bottom = by + bh / 2, by + (len(steps) - 1) * (bh + gap) + bh / 2
    d.add(f'<line x1="{spine_x}" y1="{top}" x2="{spine_x}" y2="{bottom}" stroke="{t["border"]}" stroke-width="1.5"/>')
    d.defs.append(f'<path id="spine" d="M{spine_x} {top} V{bottom}"/>')
    d.add(
        f'<circle r="3.5" fill="{t["accent"]}"><animateMotion dur="4.8s" repeatCount="indefinite" '
        f'keyPoints="0;1;1" keyTimes="0;0.8;1" calcMode="linear"><mpath href="#spine"/></animateMotion>'
        f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.06;0.74;0.8;1" dur="4.8s" repeatCount="indefinite"/></circle>'
    )
    for i, (name, note) in enumerate(steps):
        y = by + i * (bh + gap)
        last = i == len(steps) - 1
        judge = name == "judge"
        stroke = "url(#g)" if (last or judge) else t["border"]
        d.add(f'<g class="a" style="animation-delay:{0.35 + i * 0.12:.2f}s">')
        d.add(f'<rect x="{bx}" y="{y}" width="{bw}" height="{bh}" rx="10" fill="{t["raised"]}" stroke="{stroke}" stroke-width="{1.5 if (last or judge) else 1}"/>')
        dot = t["accent2"] if last else (t["accent"] if judge else t["dim"])
        d.add(f'<circle cx="{spine_x}" cy="{y + bh / 2}" r="4" fill="{dot}"/>')
        d.text(bx + 36, y + bh / 2 + 5, name, "mono500", 15, t["text"], tracking=0.3)
        d.text(bx + bw + 18, y + bh / 2 + 5.5, note, "sans400", 16, t["dim"])
        if last:
            cx = bx + bw - 20
            cy = y + bh / 2
            d.add(
                f'<path d="M{cx - 5} {cy} l3.5 3.5 l6.5 -7" fill="none" stroke="{t["accent2"]}" '
                f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
            )
        d.add("</g>")
    return d


# ---------------------------------------------------------------- pills


PILLS = [
    ("linkedin", "LinkedIn", "link"),
    ("huggingface", "Hugging Face", "link"),
    ("aria-live", "ARIA — live demo", "live"),
    ("birdid-live", "BirdID — live demo", "live"),
]


def pill(t: dict, label: str, kind: str) -> Doc:
    size, h = 15, 44
    tw = measure(label, "sans500", size, -0.1)
    lead = 30 if kind == "live" else 20
    w = int(lead + tw + 16 + 12 + 20)
    d = Doc(w, h, t, label)
    d.add(f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="{h / 2 - 0.5}" fill="{t["raised"]}" stroke="{t["border"]}"/>')
    if kind == "live":
        live_dot(d, 20, h / 2, 3.5)
    d.text(lead, h / 2 + 5.3, label, "sans500", size, t["text"], tracking=-0.1)
    arrow_ne(d, lead + tw + 12, h / 2 - 5, 10, t["muted"], 1.5)
    return d


# ---------------------------------------------------------------- section header


SECTIONS = [
    ("work", "SELECTED WORK", "06"),
    ("also", "ALSO BUILT", "06"),
    ("stack", "STACK", ""),
    ("principles", "HOW I WORK", "03"),
    ("activity", "ACTIVITY", ""),
]


def section(t: dict, label: str, count: str) -> Doc:
    d = Doc(1200, 64, t, label.title())
    gradient(d, "g")
    d.add('<rect x="0" y="31" width="28" height="2" rx="1" fill="url(#g)"/>')
    d.text(44, 37.5, label, "mono500", 15, t["text"], tracking=2.6)
    lw = measure(label, "mono500", 15, 2.6)
    end = 1200 - (measure(count, "mono500", 14, 1.5) + 18 if count else 0)
    d.add(f'<line x1="{44 + lw + 18}" y1="32" x2="{end}" y2="32" stroke="{t["border"]}"/>')
    if count:
        d.text(1200, 37, count, "mono500", 14, t["dim"], tracking=1.5, anchor="end")
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
    live: bool = False


PROJECTS = [
    Project(
        "aria", "ARIA", "CLINICAL RAG · MULTI-AGENT",
        "A clinical pharmacotherapy assistant where a Judge agent scores groundedness before any answer reaches the user.",
        [("4", "agents, one of them a Judge"), ("Page-level", "citation on every claim")],
        ["LangGraph", "Qdrant", "FastAPI", "React"], live=True,
    ),
    Project(
        "birdid", "BirdID", "COMPUTER VISION · AUDIO",
        "Identifies birds by photo or call. An open-set gate lets a 200-class model say “not one of mine” — then BioCLIP names it.",
        [("6,423", "species via BioCLIP"), ("79%", "top-1 on unseen species")],
        ["PyTorch", "BioCLIP", "BirdNET", "FastAPI"], live=True,
    ),
    Project(
        "voice-rag", "Voice RAG", "MULTILINGUAL · SPEECH",
        "Ask by voice in any of 14 Indic languages and get a grounded answer. Hybrid dense + BM25 with server-side RRF.",
        [("14", "Indic languages"), ("0.58", "recall@5 · 65 tests")],
        ["Sarvam STT", "Qdrant", "Rerankers", "Groq"],
    ),
    Project(
        "ci-triage", "CI Triage Agent", "AGENTS · DEVELOPER TOOLS",
        "Investigates failed GitHub Actions runs: gathers evidence, verifies a root-cause hypothesis, proposes a fix a human approves.",
        [("75", "real CI failures mined"), ("50 / 25", "dev / held-out split")],
        ["LangGraph", "uv", "pytest", "GitHub API"],
    ),
    Project(
        "finstock", "FinStock", "FINTECH · MULTI-AGENT",
        "Research assistant for NSE/BSE and US markets. Parallel-fanout LangGraph that cites every data point and refuses to give advice.",
        [("5", "LangGraph nodes"), ("2", "markets · India + US")],
        ["LangGraph", "SSE", "ChromaDB", "React"],
    ),
    Project(
        "codegen", "Multi-agent Codegen", "CODE GENERATION",
        "Turns a prompt into a running React + FastAPI app, then executes, tests and self-repairs it in a fixer loop.",
        [("7", "specialised agents"), ("3×", "self-repair attempts")],
        ["LangGraph", "Ollama", "SQLite", "FastAPI"],
    ),
]


def card(t: dict, i: int, p: Project) -> Doc:
    W, H, pad = 580, 400, 36
    d = Doc(W, H, t, f"{p.name} — {p.pitch}")
    gradient(d, "g")
    frame(d, 16)
    d.add(f'<rect x="{pad}" y="0" width="56" height="2" fill="url(#g)"/>')

    d.text(pad, 58, f"{i:02d}", "mono500", 15, t["accent"], tracking=1.5)
    d.text(pad + 36, 58, p.kind, "mono500", 15, t["dim"], tracking=1.5)
    if p.live:
        label = "LIVE"
        lw = measure(label, "mono500", 14, 1.5)
        x1 = W - pad - lw - 32
        d.add(f'<rect x="{x1}" y="38" width="{lw + 32}" height="28" rx="14" fill="none" stroke="{t["border"]}"/>')
        live_dot(d, x1 + 14, 52, 3.5)
        d.text(x1 + 24, 57, label, "mono500", 14, t["accent2"], tracking=1.5)
    else:
        arrow_ne(d, W - pad - 14, 45, 14, t["dim"], 1.6)

    d.text(pad - 2, 118, p.name, "sans600", 36, t["text"], tracking=-1.2)
    for j, line in enumerate(wrap(p.pitch, "sans400", 20, W - 2 * pad)[:3]):
        d.text(pad, 160 + j * 29, line, "sans400", 20, t["muted"], tracking=-0.15)

    d.add(f'<line x1="{pad}" y1="250" x2="{W - pad}" y2="252" stroke="{t["hair"]}"/>')
    col = (W - 2 * pad) / 2
    for j, (value, label) in enumerate(p.metrics):
        mx = pad + j * col
        d.text(mx, 293, value, "sans600", 28, t["text"], tracking=-0.8)
        d.text(mx, 320, label, "sans400", 16, t["dim"])

    cx = pad
    for chip in p.chips:
        cw = measure(chip, "mono500", 14, 0.2) + 22
        d.add(f'<rect x="{cx}" y="342" width="{cw:.1f}" height="32" rx="7" fill="{t["raised"]}" stroke="{t["border"]}"/>')
        d.text(cx + 11, 363, chip, "mono500", 14, t["muted"], tracking=0.2)
        cx += cw + 8
    assert cx <= W - pad + 8, f"chips overflow on {p.name}"
    return d


# ---------------------------------------------------------------- stack


STACK = [
    ("MODELS", ["PyTorch", "Hugging Face", "BioCLIP · BirdNET", "Ollama · Groq"]),
    ("RETRIEVAL", ["Qdrant", "BM25 + RRF", "Cross-encoders", "ChromaDB"]),
    ("AGENTS", ["LangGraph", "Guardrails", "LLM-as-judge", "Eval harnesses"]),
    ("SERVING", ["FastAPI · SSE", "Docker", "PostgreSQL", "Flask"]),
    ("INTERFACE", ["TypeScript", "React · Next.js", "Tailwind", "Streamlit"]),
]


def stack(t: dict) -> Doc:
    d = Doc(1200, 226, t, "Stack: " + "; ".join(f"{k.title()}: {', '.join(v)}" for k, v in STACK))
    col = 1200 / len(STACK)
    for i, (head, items) in enumerate(STACK):
        x = i * col + (0 if i == 0 else 28)
        if i:
            d.add(f'<line x1="{i * col}" y1="14" x2="{i * col}" y2="212" stroke="{t["border"]}"/>')
        d.text(x, 34, head, "mono500", 14, t["accent"], tracking=2)
        for j, item in enumerate(items):
            d.text(x, 84 + j * 40, item, "sans500", 21, t["text"], tracking=-0.3)
    return d


# ---------------------------------------------------------------- principles


PRINCIPLES = [
    ("Ground it", "Every answer traces back to a source — a page, a passage, a log line."),
    ("Measure it", "Recall, latency, held-out splits. A number before a claim."),
    ("Ship it", "A live demo, tests that pass, and decisions written down."),
]


def principles(t: dict) -> Doc:
    d = Doc(1200, 236, t, "How I work: " + " ".join(f"{a}. {b}" for a, b in PRINCIPLES))
    gradient(d, "g")
    gap = 24
    w = (1200 - 2 * gap) / 3
    for i, (head, body) in enumerate(PRINCIPLES):
        x = i * (w + gap)
        d.add(f'<rect x="{x + 0.5}" y="0.5" width="{w - 1}" height="235" rx="16" fill="{t["panel"]}" stroke="{t["border"]}"/>')
        d.text(x + 32, 52, f"{i + 1:02d}", "mono500", 15, t["accent"], tracking=1.5)
        d.text(x + 32, 98, head, "sans600", 32, t["text"], tracking=-0.8)
        for j, line in enumerate(wrap(body, "sans400", 20, w - 64)):
            d.text(x + 32, 142 + j * 29, line, "sans400", 20, t["muted"], tracking=-0.1)
    return d


# ---------------------------------------------------------------- footer


def footer(t: dict) -> Doc:
    d = Doc(1200, 96, t, "Rohit Kumar · AI Engineer")
    gradient(d, "g")
    d.add(f'<line x1="0" y1="24" x2="1200" y2="24" stroke="{t["border"]}"/>')
    d.add('<rect x="572" y="23" width="56" height="2" fill="url(#g)"/>')
    d.text(600, 72, "ROHIT KUMAR  ·  AI ENGINEER  ·  2026", "mono500", 14, t["dim"], tracking=2.4, anchor="middle")
    return d


# ---------------------------------------------------------------- main


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    out: dict[str, Doc] = {}
    for mode, t in THEMES.items():
        out[f"hero-{mode}"] = hero(t)
        out[f"stack-{mode}"] = stack(t)
        out[f"principles-{mode}"] = principles(t)
        out[f"footer-{mode}"] = footer(t)
        for slug, label, count in SECTIONS:
            out[f"section-{slug}-{mode}"] = section(t, label, count)
        for slug, label, kind in PILLS:
            out[f"pill-{slug}-{mode}"] = pill(t, label, kind)
        for i, p in enumerate(PROJECTS, 1):
            out[f"card-{p.slug}-{mode}"] = card(t, i, p)
    for name, doc in out.items():
        svg = doc.render()
        (ASSETS / f"{name}.svg").write_text(svg)
        print(f"{name:32s} {len(svg) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
