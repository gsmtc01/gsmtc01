"""Build assets/profile/hero.svg: an animated terminal card for the profile README.

Usage:
    python3 scripts/build_hero.py --font-medium IBMPlexMono-Medium.ttf \
        --font-bold IBMPlexMono-Bold.ttf

The fonts (IBM Plex Mono, SIL OFL 1.1) are subset to printable ASCII and
embedded as WOFF so every viewer gets the same monospace metrics.
Icon paths in stack_icons.json come from simple-icons (CC0-1.0).
The SVG follows the embedding page's color scheme, or the browser preference
when viewed directly, without JavaScript or separate image files.
"""
import argparse
import base64
import io
import json
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

import logo3d

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "profile" / "hero.svg"
_ICON_DATA = json.loads((Path(__file__).parent / "stack_icons.json").read_text())
ICONS = _ICON_DATA["icons"]
EVENODD = set(_ICON_DATA.get("evenodd", []))
# icons drawn with a gradient instead of a flat brand colour (official Codex mark)
GRADIENTS = {
    "codex": '<linearGradient id="g-codex" x1="0" y1="0" x2="0" y2="1">'
             '<stop stop-color="#b1a7ff"/><stop offset=".5" stop-color="#7a9dff"/>'
             '<stop offset="1" stop-color="#3941ff"/></linearGradient>',
}

# Window controls in the macOS 27 Liquid Glass style, sampled from a real
# macOS 27.2 title bar: the body is darkest about 40% down and brightens
# toward the bottom, light gathers in a soft glow near the lower edge, and a
# thin bright rim shows at the top and bottom but fades out at the sides.
# (name, centre x, top, darkest, bottom, rim)
TRAFFIC = [
    ("close", 24, "#f86458", "#f45145", "#ef6962", "#ffd3cb"),
    ("min", 43, "#fab500", "#fcb400", "#fece32", "#fff27a"),
    ("zoom", 62, "#3ec208", "#00bc00", "#52c33c", "#bdf8a4"),
]
TL_R = 6.0
TL_CY = 15


def traffic_defs():
    out = []
    for name, _, top, mid, bottom, rim in TRAFFIC:
        out.append(
            f'<linearGradient id="tl-{name}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop stop-color="{top}"/><stop offset=".4" stop-color="{mid}"/>'
            f'<stop offset="1" stop-color="{bottom}"/></linearGradient>'
            f'<radialGradient id="tl-{name}-glow" cx=".5" cy=".86" r=".5">'
            f'<stop stop-color="{rim}" stop-opacity=".55"/>'
            f'<stop offset="1" stop-color="{rim}" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="tl-{name}-rim" x1="0" y1="0" x2="0" y2="1">'
            f'<stop stop-color="{rim}" stop-opacity=".95"/><stop offset=".28" stop-color="{rim}" stop-opacity="0"/>'
            f'<stop offset=".72" stop-color="{rim}" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="{rim}" stop-opacity=".85"/></linearGradient>'
        )
    return "".join(out)


def traffic_lights():
    out = []
    for name, cx, *_ in TRAFFIC:
        out.append(
            f'<circle cx="{cx}" cy="{TL_CY}" r="{TL_R}" fill="url(#tl-{name})"/>'
            f'<circle cx="{cx}" cy="{TL_CY}" r="{TL_R}" fill="url(#tl-{name}-glow)"/>'
            f'<circle cx="{cx}" cy="{TL_CY}" r="{TL_R - 0.35}" fill="none" stroke="url(#tl-{name}-rim)" stroke-width=".7"/>'
            # hairline so the glass edge still reads on the light title bar
            f'<circle cx="{cx}" cy="{TL_CY}" r="{TL_R + 0.25}" fill="none" stroke="#000" stroke-opacity=".07" stroke-width=".5"/>'
        )
    return "".join(out)


W = 846
ADV = 0.6  # IBM Plex Mono advance width in em

# Theme variables also cover the typing masks, so they match the background.
BG = "var(--bg)"
BAR = "var(--bar)"
LINE = "var(--line)"
HEAD = "var(--head)"
BODY = "var(--body)"
DIM = "var(--dim)"
ACCENT = "var(--accent)"
PALETTES = {
    "light": {
        "bg": "#ffffff", "bar": "#f6f8fa", "line": "#d1d9e0",
        "head": "#1f2328", "body": "#424a53", "dim": "#656d76",
        "accent": "#0969da", "prompt-line": "#afb8c1",
        "glow-center": ".12", "glow-mid": ".055",
    },
    "dark": {
        "bg": "#0b0e13", "bar": "#121720", "line": "#26303c",
        "head": "#e8eef4", "body": "#9aa6b2", "dim": "#8b98a6",
        "accent": "#2aa9f2", "prompt-line": "#3a4655",
        "glow-center": ".30", "glow-mid": ".14",
    },
}
# deep navy -> logo blue -> sky blue, taken from the logo artwork (no white)
LOGO = {1: "#0b3d7e", 2: "#0e55a4", 3: "#136cc4", 4: "#1a88dc", 5: "#27a6ee", 6: "#4cc4f8"}

HANDLE = "gsmtc01"

# (label, slug or None, badge color from the README badges)
# Kept to what says something about the work; everyday tools every engineer
# uses (git, GitHub, Slack, Notion, Jira, Homebrew, iTerm2, Markdown ...), web
# basics (HTML5, CSS, JavaScript, npm, PWA) and items implied by another entry
# (NumPy/Pandas/Jupyter under Python, Tailscale over WireGuard) are left out.
STACK = [
    ("Infra", [
        ("Red Hat", "redhat", "EE0000"), ("Rocky Linux", "rockylinux", "10B981"),
        ("Cisco", "cisco", "1BA0D7"), ("VMware", "vmware", "607078"),
        ("Docker", "docker", "2496ED"), ("Kubernetes", "kubernetes", "326CE5"),
        ("Nginx", "nginx", "009639"),
    ]),
    ("Security", [
        ("Wireshark", "wireshark", "1679A7"), ("WireGuard", "wireguard", "88171A"),
        ("Okta", "okta", "007DC1"), ("Kali Linux", "kalilinux", "557C94"),
        ("OWASP", "owasp", "30363D"),
    ]),
    ("AI / LLM", [
        ("Claude", "claude", "D97757"), ("ChatGPT", "openai", "74AA9C"),
        ("Hugging Face", "huggingface", "FFD21E"), ("Ollama", "ollama", "30363D"),
        ("LM Studio", "lmstudio", "5C33F6"), ("vLLM", "vllm", "30A2FF"), ("MCP", "modelcontextprotocol", "30363D"),
        ("WebGPU", "webgpu", "005A9C"),
    ]),
    ("Data", [
        ("Python", "python", "3776AB"), ("PyTorch", "pytorch", "EE4C2C"),
        ("Kaggle", "kaggle", "20BEFF"),
    ]),
    ("Web", [
        ("TypeScript", "typescript", "3178C6"), ("React", "react", "61DAFB"),
        ("Tailwind CSS", "tailwindcss", "06B6D4"), ("Vite", "vite", "646CFF"),
        ("Node.js", "nodedotjs", "5FA04E"), ("Tauri", "tauri", "24C8D8"),
        ("WebAssembly", "webassembly", "654FF0"),
    ]),
    ("Tools", [
        ("GitHub Actions", "githubactions", "2088FF"), ("Claude Code", "claudecode", "D97757"),
        ("Codex", "codex", "412991"), ("Cursor", "cursor", "30363D"),
        ("Xcode", "xcode", "147EFB"),
    ]),
]

COMMANDS = [
    'kubectl get pods -A',
    'tshark -i en0 -Y "tls.handshake"',
    'ollama run gemma4 "explain this alert"',
    'claude "harden my nginx config"',
]

# logo animation
N_FRAMES = 144
LOOP_S = 12.0
COLS, ROWS = 52, 30
FS_LOGO = 9.6


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def woff_b64(path):
    f = TTFont(path)
    opts = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = []
    opts.name_IDs = []
    opts.hinting = False
    opts.desubroutinize = True
    s = subset.Subsetter(opts)
    s.populate(text="".join(chr(c) for c in range(0x20, 0x7F)))
    s.subset(f)
    buf = io.BytesIO()
    f.flavor = "woff"
    f.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def lift(hexcol):
    """Brighten brand colours that would vanish on the dark background."""
    r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    if lum >= 0.10:
        return "#" + hexcol.lower()
    k = 0.62 if lum < 0.03 else 0.45
    r, g, b = (c + (1 - c) * k for c in (r, g, b))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def theme_css():
    """An embedded SVG inherits the host element's color-scheme preference."""
    rules = {}
    for theme, palette in PALETTES.items():
        values = dict(palette)
        for _, items in STACK:
            for _, slug, col in items:
                if slug and slug not in GRADIENTS:
                    values[f"icon-{slug}"] = lift(col) if theme == "dark" else "#" + col.lower()
        rules[theme] = ":root{" + ";".join(f"--{key}:{value}" for key, value in values.items()) + "}"
    return rules["light"] + "@media (prefers-color-scheme:dark){" + rules["dark"] + "}"


# ---------------------------------------------------------------- logo frames

def logo_frames(ox, oy):
    cw = FS_LOGO * ADV
    out = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        grid = logo3d.frame(t, cols=COLS, rows=ROWS, scale=114.0, cw=cw, ch=FS_LOGO)
        rows = []
        for r, row in enumerate(grid):
            line = "".join(c for c, _ in row)
            if not line.strip():
                continue
            start = len(line) - len(line.lstrip())
            end = len(line.rstrip())
            parts, cur, buf = [], None, ""
            for c, lvl in row[start:end]:
                key = lvl if c != " " else cur
                if key != cur and buf:
                    parts.append((cur, buf))
                    buf = ""
                cur = key
                buf += c
            if buf:
                parts.append((cur, buf))
            inner = "".join(f'<tspan class="l{k}">{esc(s)}</tspan>' for k, s in parts)
            rows.append(f'<tspan x="{ox + start * cw:.1f}" y="{oy + r * FS_LOGO:.1f}">{inner}</tspan>')
        cls = "f f0" if i == 0 else "f"
        delay = -LOOP_S + i * LOOP_S / N_FRAMES
        # 5 decimals: with 3, rounding left sub-millisecond gaps between frames
        # in which no frame was visible, and the logo blinked
        out.append(f'<text class="{cls}" style="animation-delay:{delay:.5f}s">{"".join(rows)}</text>')
    return "".join(out)


# ---------------------------------------------------------------- stack rows

def stack_block(x0, y0, right, delay0, lh=21.0, gap=7.0):
    """Lay out the stack rows; returns (svg, y after the block, last delay, row count)."""
    fs = 12
    cw = fs * ADV
    label_w = 10 * cw
    parts, y, d, nrows = [], y0, delay0, 1
    for label, items in STACK:
        parts.append(f'<g class="in" style="animation-delay:{d:.2f}s"><text x="{x0}" y="{y:.1f}" font-size="{fs}" fill="{ACCENT}">{esc(label)}</text></g>')
        x = x0 + label_w
        line_items = []
        for name, slug, col in items:
            w = 15 + len(name) * cw
            if x + w > right and line_items:
                parts.append(f'<g class="in" style="animation-delay:{d:.2f}s">{"".join(line_items)}</g>')
                d += 0.07
                line_items, x, y = [], x0 + label_w, y + lh
                nrows += 1
            c = f"var(--icon-{slug})" if slug else "#" + col.lower()
            if slug:
                icon = (f'<path transform="translate({x:.1f} {y - 10:.1f}) scale({11 / 24:.4f})" '
                        + ('fill-rule="evenodd" ' if slug in EVENODD else "")
                        + f'fill="{"url(#g-" + slug + ")" if slug in GRADIENTS else c}" d="{ICONS[slug]}"/>')
            else:
                icon = f'<rect x="{x + 1.5:.1f}" y="{y - 8.5:.1f}" width="8" height="8" rx="2" fill="{c}"/>'
            line_items.append(icon + f'<text x="{x + 15:.1f}" y="{y:.1f}" font-size="{fs}" fill="{BODY}">{esc(name)}</text>')
            x += w + 13
        parts.append(f'<g class="in" style="animation-delay:{d:.2f}s">{"".join(line_items)}</g>')
        d += 0.07
        y += lh + gap
        nrows += 1
    return "".join(parts), y, d, nrows - 1


# ---------------------------------------------------------------- prompt typing

def typing(x, y, box, fs=13.5, slot=5.0):
    cw = fs * ADV
    total = slot * len(COMMANDS)
    pct = lambda s: f"{100 * s / total:.3f}%"
    css, texts = [], []
    cur_frames = []
    for i, cmd in enumerate(COMMANDS):
        n = len(cmd)
        s0 = i * slot + 0.3
        t_typed = s0 + n * 0.055
        t_erase = i * slot + slot - 0.75
        t_gone = t_erase + 0.3
        dx = n * cw
        kf = (f"@keyframes c{i}{{0%{{transform:translateX(0)}}"
              f"{pct(s0)}{{transform:translateX(0);animation-timing-function:steps({n},end)}}"
              f"{pct(t_typed)}{{transform:translateX({dx:.1f}px)}}"
              f"{pct(t_erase)}{{transform:translateX({dx:.1f}px);animation-timing-function:steps({n},end)}}"
              f"{pct(t_gone)}{{transform:translateX(0)}}100%{{transform:translateX(0)}}}}"
              f".c{i}{{animation:c{i} {total}s linear 3s infinite both}}")
        css.append(kf)
        cur_frames.append((s0, t_typed, t_erase, t_gone, n, dx))
        a, b = pct(i * slot), pct((i + 1) * slot)
        vis = (f"0%{{opacity:1}}{b}{{opacity:0}}" if i == 0 else f"0%{{opacity:0}}{a}{{opacity:1}}{b}{{opacity:0}}")
        css.append(f"@keyframes v{i}{{{vis}100%{{opacity:0}}}}.v{i}{{animation:v{i} {total}s step-end 3s infinite both}}")
        texts.append(f'<g class="v{i}"><text x="{x}" y="{y}" font-size="{fs}" fill="{HEAD}" xml:space="preserve">{esc(cmd)}</text>'
                     f'<rect class="c{i}" x="{x - 1}" y="{y - 14}" width="{box[2]}" height="19" fill="{BG}"/></g>')
    # cursor follows whichever command is active
    steps = ["0%{transform:translateX(0)}"]
    for s0, t_typed, t_erase, t_gone, n, dx in cur_frames:
        steps.append(f"{pct(s0)}{{transform:translateX(0);animation-timing-function:steps({n},end)}}")
        steps.append(f"{pct(t_typed)}{{transform:translateX({dx:.1f}px)}}")
        steps.append(f"{pct(t_erase)}{{transform:translateX({dx:.1f}px);animation-timing-function:steps({n},end)}}")
        steps.append(f"{pct(t_gone)}{{transform:translateX(0)}}")
    steps.append("100%{transform:translateX(0)}")
    css.append("@keyframes cu{" + "".join(steps) + f"}}.cu{{animation:cu {total}s linear 3s infinite both}}")
    bx, by, bw, bh = box
    svg = (f'<clipPath id="pbox"><rect x="{bx + 2}" y="{by + 2}" width="{bw - 4}" height="{bh - 4}"/></clipPath>'
           f'<g clip-path="url(#pbox)">{"".join(texts)}</g>'
           f'<g class="cu"><rect x="{x}" y="{y - 12.5}" width="{cw:.1f}" height="16" fill="{HEAD}" class="bl"/></g>')
    return "".join(css), svg


# ---------------------------------------------------------------- assemble

def build(font_medium, font_bold):
    fm, fb = woff_b64(font_medium), woff_b64(font_bold)

    rx = 354
    stack_head_y = 80
    # spread the rows so the stack column ends level with the logo column
    logo_bottom = 46 + ROWS * FS_LOGO + 40
    first = stack_head_y + 28
    *_, nrows = stack_block(rx, first, 806, 1.45)
    cats = len(STACK)
    lh = 21.0
    gap = min(30.0, (logo_bottom - 24 - first - (nrows - 1) * lh) / (cats - 1))
    stack_svg, stack_end, d_end, _ = stack_block(rx, first, 806, 1.45, lh=lh, gap=gap)
    split = 330
    logo_ox = 24 + (split - 24 - COLS * FS_LOGO * ADV) / 2
    bottom = max(stack_end - lh - gap + 24, logo_bottom)
    logo_cx = 24 + (split - 24) / 2
    logo_cy = (46 + bottom) / 2
    logo_oy = logo_cy - (ROWS - 1) * FS_LOGO / 2 + 0.3 * FS_LOGO
    panel = (24, 46, 798, bottom - 46)  # x, y, w, h
    H = panel[1] + panel[3] + 14 + 38 + 36

    prompt_box = (24, panel[1] + panel[3] + 14, 798, 38)
    px, py = 56, prompt_box[1] + 24
    type_css, type_svg = typing(px, py, prompt_box)

    css = (
        f"@font-face{{font-family:PM;font-weight:500;src:url(data:font/woff;base64,{fm}) format('woff')}}"
        f"@font-face{{font-family:PM;font-weight:700;src:url(data:font/woff;base64,{fb}) format('woff')}}"
        + theme_css()
        + "text{font-family:PM,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-weight:500;white-space:pre}"
        + "".join(f".l{k}{{fill:{c}}}" for k, c in LOGO.items())
        + f".f{{font-size:{FS_LOGO}px;opacity:0;animation:fr {LOOP_S}s step-end infinite}}.f0{{opacity:1}}"
        # each frame stays up a hair longer than the frame spacing (about 8
        # microseconds), so consecutive frames always meet and never leave a gap
        f"@keyframes fr{{0%{{opacity:1}}{100 / N_FRAMES * 1.0001:.5f}%{{opacity:0}}100%{{opacity:0}}}}"
        ".in{animation:in .55s cubic-bezier(.2,.8,.2,1) both}"
        "@keyframes in{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}"
        ".fd{animation:fd .5s ease-out both}@keyframes fd{from{opacity:0}to{opacity:1}}"
        ".dr{stroke-dasharray:1;animation:dr .9s cubic-bezier(.65,0,.35,1) .45s both}"
        "@keyframes dr{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}"
        ".lg{animation:lg 1.1s cubic-bezier(.2,.8,.2,1) .7s both}"
        "@keyframes lg{from{opacity:0;transform:scale(.55) rotate(-8deg)}to{opacity:1;transform:none}}"
        ".vl{animation:vl .7s cubic-bezier(.2,.8,.2,1) 1.2s both}@keyframes vl{from{transform:scaleY(0)}to{transform:none}}"
        ".gw{animation:gi 1.4s ease-out .8s both,gb 6s ease-in-out 2.2s infinite alternate}"
        "@keyframes gi{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:none}}"
        "@keyframes gb{from{opacity:1;transform:none}to{opacity:.6;transform:scale(.92)}}"
        ".bl{animation:bl 1.05s steps(1) infinite}@keyframes bl{50%{opacity:0}}"
        + "".join(type_css)
        + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    )

    glow = (
        f'<radialGradient id="glow" cx="{logo_cx}" cy="{logo_cy}" r="150" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" stop-color="#0f86d2" stop-opacity="var(--glow-center)"/>'
        '<stop offset=".45" stop-color="#07a5ec" stop-opacity="var(--glow-mid)"/>'
        '<stop offset="1" stop-color="#03b2f0" stop-opacity="0"/></radialGradient>'
        f'<g class="gw" style="transform-origin:{logo_cx}px {logo_cy}px">'
        f'<circle cx="{logo_cx}" cy="{logo_cy}" r="150" fill="url(#glow)"/></g>'
    )

    aria = (f"Terminal card for {HANDLE} with a rotating ASCII rendering of the blue wave logo. "
            "Stack: " + "; ".join(f"{lab}: " + ", ".join(n for n, _, _ in items) for lab, items in STACK) + ".")

    label_w = len(HANDLE) * 13 * ADV + 14
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(aria)}">'
        f"<title>{HANDLE}</title><defs><clipPath id=\"win\"><rect x=\"5\" y=\"0\" width=\"836\" height=\"{H - 4}\" rx=\"12\"/></clipPath>" + "".join(GRADIENTS.values()) + traffic_defs() + "</defs>"
        f"<style>{css}</style>"
        f'<rect x="5" y="0" width="836" height="{H - 4}" rx="12" fill="{BG}" stroke="{LINE}"/>'
        f'<g clip-path="url(#win)">'
        # title bar
        f'<g class="fd"><path d="M5 12a12 12 0 0 1 12-12h812a12 12 0 0 1 12 12v18H5z" fill="{BAR}"/>'
        + traffic_lights() + "</g>"
        + glow
        # panel
        + f'<rect x="{panel[0]}" y="{panel[1]}" width="{panel[2]}" height="{panel[3]}" rx="8" fill="none" stroke="{LINE}" stroke-width="1.2" pathLength="1" class="dr"/>'
        f'<g class="in" style="animation-delay:1.05s"><rect x="38" y="38" width="{label_w:.1f}" height="16" fill="{BG}"/>'
        f'<text x="45" y="50.5" font-size="13" fill="{BODY}">{HANDLE}</text></g>'
        f'<path d="M{split} 66V{panel[1] + panel[3] - 20}" stroke="{LINE}" stroke-width="1.2" class="vl" style="transform-origin:{split}px {panel[1] + panel[3] / 2}px"/>'
        # left column
        f'<g class="lg" style="transform-origin:{logo_cx}px {logo_cy}px">{logo_frames(logo_ox, logo_oy)}</g>'
        # right column
        + f'<g class="in" style="animation-delay:1.35s"><text x="{rx}" y="{stack_head_y}" font-size="13" fill="{HEAD}" font-weight="700">Stack</text></g>'
        + stack_svg
        # prompt
        + f'<g class="in" style="animation-delay:{d_end + 0.1:.2f}s">'
        f'<rect x="{prompt_box[0]}" y="{prompt_box[1]}" width="{prompt_box[2]}" height="{prompt_box[3]}" rx="6" fill="none" stroke="var(--prompt-line)" stroke-width="1.2"/>'
        f'<text x="38" y="{py}" font-size="13.5" fill="{ACCENT}">&gt;</text>{type_svg}</g>'
        f'<g class="in" style="animation-delay:{d_end + 0.2:.2f}s"><text x="38" y="{H - 14}" font-size="12" fill="{DIM}">? for shortcuts</text>'
        f'<text x="808" y="{H - 14}" font-size="12" fill="{DIM}" text-anchor="end">github.com/{HANDLE}</text></g>'
        "</g></svg>"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(svg) / 1024:.0f} KiB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-medium", required=True)
    ap.add_argument("--font-bold", required=True)
    a = ap.parse_args()
    build(a.font_medium, a.font_bold)
