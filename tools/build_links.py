"""Render the link buttons under the card: link_<name>_<theme>.svg, each exactly a third of the card's width.
GitHub shows README SVGs as <img>, so each button must be its own image inside its own link."""

from __future__ import annotations

from pathlib import Path

from build_card import ADVANCE, CARD_W, FONT_FACE, FONT_STACK, THEMES

ROOT = Path(__file__).resolve().parent.parent

GAP = 12
SLOT_W = CARD_W / 3
BUTTON_W = (CARD_W - 2 * GAP) / 3
HEIGHT = 52
FONT = 17

LINKS = (
    ("portfolio", "raqib.codes", "key"),
    ("linkedin", "linkedin", "value"),
    ("email", "email", "add"),
)


def build(theme: str, slot: int) -> str:
    c = THEMES[theme]
    _, label, accent = LINKS[slot]
    x = slot * GAP / 3  # gaps live inside the images, so the row's outer edges meet the card's
    text = f"$ open {label}"
    text_x = x + (BUTTON_W - len(text) * FONT * ADVANCE) / 2
    prompt_w = 2 * FONT * ADVANCE
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{SLOT_W:.2f}" height="{HEIGHT}" viewBox="0 0 {SLOT_W:.2f} {HEIGHT}" font-family="{FONT_STACK}">
<style>
{FONT_FACE}
text, tspan {{white-space: pre;}}
</style>
<rect x="{x + 0.5:.2f}" y="0.5" width="{BUTTON_W - 1:.2f}" height="{HEIGHT - 1}" rx="10" fill="{c['bg']}" stroke="{c['dots']}" stroke-opacity="0.45"/>
<rect x="{x + 12:.2f}" y="{HEIGHT - 5}" width="{BUTTON_W - 24:.2f}" height="2" rx="1" fill="{c[accent]}"/>
<text x="{text_x:.2f}" y="{HEIGHT / 2 + FONT * 0.35:.2f}" font-size="{FONT}px" fill="{c['fg']}"><tspan fill="{c['dots']}">$ </tspan><tspan x="{text_x + prompt_w:.2f}">open </tspan><tspan fill="{c[accent]}">{label}</tspan></text>
</svg>
"""


def main() -> None:
    for theme in THEMES:
        for slot, (name, *_) in enumerate(LINKS):
            out = ROOT / f"link_{name}_{theme}.svg"
            out.write_text(build(theme, slot), encoding="utf-8")
            print(f"wrote {out.name}")


if __name__ == "__main__":
    main()
