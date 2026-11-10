"""Build the neofetch-style card (dark_mode.svg, light_mode.svg) from assets/ascii.txt and cache/stats.json.
Every row is padded to exactly PANEL_COLS characters, and a row that doesn't fit stops the build."""

from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "cache" / "stats.json"

# First ML repo (99-ML-Learning-Projects); the Uptime line counts from here.
STARTED_ML = dt.date(2022, 10, 13)

# Consolas advances 0.55em, other monospace fonts 0.60em; scaling Consolas by 109% makes them agree.
ADVANCE = 0.6
FONT_STACK = "ConsolasFallback,Consolas,Menlo,'DejaVu Sans Mono',monospace"
FONT_FACE = """@font-face {
  src: local('Consolas'), local('Consolas Bold');
  font-family: 'ConsolasFallback';
  size-adjust: 109%;
}"""

ART_WIDTH = 414.0
ART_LINE = 1.2  # line height in em; with ADVANCE gives the 0.5 cell aspect make_ascii samples at
PANEL_FONT = 16.0
PANEL_LINE = 20.0
PANEL_COLS = 58
MARGIN = 15
GUTTER = 22
CARD_W = round(MARGIN + ART_WIDTH + GUTTER + PANEL_COLS * PANEL_FONT * ADVANCE + MARGIN)

# GitHub's own Primer colours, so the card sits naturally on either profile theme.
THEMES = {
    "dark": {"bg": "#161b22", "fg": "#c9d1d9", "key": "#ffa657", "value": "#a5d6ff",
             "add": "#3fb950", "del": "#f85149", "dots": "#6e7681"},
    "light": {"bg": "#f6f8fa", "fg": "#24292f", "key": "#953800", "value": "#0a3069",
              "add": "#1a7f37", "del": "#cf222e", "dots": "#6e7781"},
}

TITLE = "abdulraqib@omotosho"
INFO = [
    ("OS", "macOS, Ubuntu"),
    ("Uptime", None),
    ("Host", "Bujeti (YC W23), Lagos"),
    ("Kernel", "Applied AI Engineer"),
    ("IDE", "VS Code, Cursor, Claude Code"),
    None,
    ("Languages.Programming", "Python, JavaScript, SQL, Bash"),
    ("Languages.Real", "English, Yoruba"),
    None,
    ("Focus.LLM", "Agents, RAG, tool calling, MCP"),
    ("Focus.ML", "PyTorch, Transformers, QLoRA"),
    ("Stack", "FastAPI, Celery, Redis, Postgres, AWS"),
]
CONTACT = [
    ("Email", "omotosho.raqib@gmail.com"),
    ("LinkedIn", "abdulraqib-omotosho"),
    ("Portfolio", "raqib.codes"),
]


def esc(text: str) -> str:
    return html.escape(text, quote=False)


class Row:
    """A panel row of fixed text segments plus elastic fills that stretch it to an exact width."""

    def __init__(self) -> None:
        self.segs: list[tuple[str, str, str | None]] = []  # (kind, text-or-fill-char, css class)

    def text(self, value: str, cls: str | None = None) -> "Row":
        self.segs.append(("text", str(value), cls))
        return self

    def key(self, name: str) -> "Row":
        for i, part in enumerate(name.split(".")):
            if i:
                self.text(".")
            self.text(part, "key")
        return self

    def fill(self, char: str = ".", cls: str | None = "dots") -> "Row":
        self.segs.append(("fill", char, cls))
        return self

    def render(self, x: float, y: float, width: int) -> str:
        fixed = sum(len(v) for k, v, _ in self.segs if k == "text")
        fills = [i for i, (k, _, _) in enumerate(self.segs) if k == "fill"]
        slack = width - fixed
        if fills and slack < len(fills) or not fills and slack:
            raise SystemExit(f"row is {fixed} cols, panel is {width}: {''.join(v for _, v, _ in self.segs)!r}")
        base, extra = divmod(slack, len(fills)) if fills else (0, 0)
        parts, total = [], 0
        for i, (kind, value, cls) in enumerate(self.segs):
            body = value if kind == "text" else value * (base + (fills.index(i) < extra))
            total += len(body)
            parts.append(f'<tspan class="{cls}">{esc(body)}</tspan>' if cls else esc(body))
        assert total == width
        return f'<tspan x="{x:g}" y="{y:.2f}">{"".join(parts)}</tspan>'


def info(key: str, value: str) -> Row:
    return Row().text(". ", "dots").key(key).text(":").text(" ").fill().text(" ").text(value, "value")


def rule(label: str, title: bool = False) -> Row:
    return Row().text(label, "title" if title else None).text(" -").fill("—", None).text("-")


def uptime(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    months = (today.year - STARTED_ML.year) * 12 + today.month - STARTED_ML.month
    days = today.day - STARTED_ML.day
    if days < 0:
        months -= 1
        days += (today.replace(day=1) - dt.timedelta(days=1)).day
    years, months = divmod(months, 12)

    def unit(n: int, word: str) -> str:
        return f"{n} {word}{'' if n == 1 else 's'}"

    return f"{unit(years, 'year')}, {unit(months, 'month')}, {unit(days, 'day')}"


def stats() -> dict[str, str]:
    keys = ("repos", "contributed", "stars", "commits", "followers", "loc", "added", "deleted")
    raw = json.loads(STATS.read_text()) if STATS.exists() else {}
    return {k: f"{raw[k]:,}" if isinstance(raw.get(k), int) else "--" for k in keys}


def load_art() -> list[str]:
    lines = [l.rstrip() for l in (ROOT / "assets" / "ascii.txt").read_text().split("\n")]
    used = [i for i, l in enumerate(lines) if l.strip()]
    return lines[used[0]: used[-1] + 1]


def panel_rows() -> list[Row | None]:
    st = stats()
    rows: list[Row | None] = [rule(TITLE, title=True)]
    rows += [None if item is None else info(item[0], uptime() if item[0] == "Uptime" else item[1]) for item in INFO]
    rows += [None, rule("- Contact")] + [info(k, v) for k, v in CONTACT]
    rows += [None, rule("- GitHub Stats")]
    rows.append(Row().text(". ", "dots").key("Repos").text(": ").fill().text(" ").text(st["repos"], "value")
                .text(" {").key("Contributed").text(": ").text(st["contributed"], "value").text("}")
                .text(" | ").key("Stars").text(": ").fill().text(" ").text(st["stars"], "value"))
    rows.append(Row().text(". ", "dots").key("Commits").text(": ").fill().text(" ").text(st["commits"], "value")
                .text(" | ").key("Followers").text(": ").fill().text(" ").text(st["followers"], "value"))
    rows.append(Row().text(". ", "dots").key("Lines of Code").text(": ").fill().text(" ").text(st["loc"], "value")
                .text(" ( ").text(f"{st['added']}++", "add").text(", ").text(f"{st['deleted']}--", "del").text(" )"))
    return rows


def build(theme: str) -> str:
    c = THEMES[theme]
    art = load_art()
    art_font = ART_WIDTH / (max(map(len, art)) * ADVANCE)
    art_line = art_font * ART_LINE
    rows = panel_rows()

    # Centre both blocks on one axis; a line's glyphs reach ~0.65em beyond its baseline span.
    panel_h = (len(rows) - 1) * PANEL_LINE + 1.3 * PANEL_FONT
    art_h = (len(art) - 1) * art_line + 1.3 * art_font
    height = 2 * MARGIN + max(panel_h, art_h)
    mid = height / 2
    panel_y = mid - panel_h / 2 + PANEL_FONT
    art_y = mid - art_h / 2 + art_font
    panel_x = MARGIN + ART_WIDTH + GUTTER
    width = CARD_W

    art_spans = "\n".join(f'<tspan x="{MARGIN}" y="{art_y + i * art_line:.2f}">{esc(l)}</tspan>'
                          for i, l in enumerate(art))
    panel_spans = "\n".join(
        f'<tspan x="{panel_x:g}" y="{panel_y + i * PANEL_LINE:.2f}" class="dots">.</tspan>' if row is None
        else row.render(panel_x, panel_y + i * PANEL_LINE, PANEL_COLS)
        for i, row in enumerate(rows))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" font-family="{FONT_STACK}">
<style>
{FONT_FACE}
.key {{fill: {c['key']};}}
.value {{fill: {c['value']};}}
.title {{fill: {c['key']}; font-weight: bold;}}
.add {{fill: {c['add']};}}
.del {{fill: {c['del']};}}
.dots {{fill: {c['dots']};}}
text, tspan {{white-space: pre;}}
</style>
<rect width="100%" height="100%" fill="{c['bg']}" rx="12"/>
<text fill="{c['fg']}" font-size="{art_font:.2f}px">
{art_spans}
</text>
<text fill="{c['fg']}" font-size="{PANEL_FONT:g}px">
{panel_spans}
</text>
</svg>
"""


def main() -> None:
    print(f"uptime: {uptime()}  stats: {'cache/stats.json' if STATS.exists() else 'placeholders'}")
    for theme in THEMES:
        out = ROOT / f"{theme}_mode.svg"
        out.write_text(build(theme), encoding="utf-8")
        print(f"wrote {out.name} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
