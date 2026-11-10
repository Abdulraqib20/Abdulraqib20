"""Render the last year's contribution calendar with a Pac-Man eating it: pacman_<theme>.svg.
Every animation shares one duration and starts at 0, so the board loops in lock-step with no script."""

from __future__ import annotations

import datetime as dt
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from build_card import ADVANCE, CARD_W, FONT_FACE, FONT_STACK, THEMES

ROOT = Path(__file__).resolve().parent.parent
CALENDAR = ROOT / "cache" / "calendar.json"

CELL, PITCH, RADIUS = 14, 18, 3
MARGIN, LABEL_COL = 15, 36
HEADER_FONT, LABEL_FONT = 14, 12
STEP = 0.07  # seconds per day crossed
INTRO, OUTRO = 1.2, 2.0
PAC_R = 8
CHOMP = 0.26

# GitHub's own contribution greens, so the board still reads as the graph it replaces.
LEVELS = {
    "dark": ("#21262d", "#0e4429", "#006d32", "#26a641", "#39d353"),
    "light": ("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"),
}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
WEEKDAYS = {1: "Mon", 3: "Wed", 5: "Fri"}


def mouth(deg: float) -> str:
    a = math.radians(deg)
    x, y = PAC_R * math.cos(a), PAC_R * math.sin(a)
    return f"M0 0L{x:.2f} {-y:.2f}A{PAC_R} {PAC_R} 0 1 0 {x:.2f} {y:.2f}Z"


class Route:
    """Pac-Man sweeps the seven weekday rows in a zigzag, one day per STEP seconds."""

    def __init__(self, weeks: int, left: float, top: float) -> None:
        self.left, self.top, self.weeks = left, top, weeks
        self.points: list[tuple[float, float, float]] = []  # (t, x, y)
        t = INTRO
        for row in range(7):
            a, b = (0, weeks - 1) if row % 2 == 0 else (weeks - 1, 0)
            if row:
                t += STEP
            self.points.append((t, self.cx(a), self.cy(row)))
            t += (weeks - 1) * STEP
            self.points.append((t, self.cx(b), self.cy(row)))
        exit_t = t + 3 * STEP  # row 6 runs left to right, so he leaves off the right edge
        self.points.append((exit_t, self.cx(weeks + 2), self.cy(6)))
        self.total = exit_t + OUTRO

    def cx(self, col: float) -> float:
        return self.left + col * PITCH + CELL / 2

    def cy(self, row: int) -> float:
        return self.top + row * PITCH + CELL / 2

    def key(self, t: float) -> str:
        return f"{min(max(t / self.total, 0.0), 1.0):.5f}"

    def eaten_at(self, col: int, row: int) -> float:
        start = self.points[2 * row][0]
        steps = col if row % 2 == 0 else self.weeks - 1 - col
        return start + steps * STEP

    def translate(self) -> str:
        pts = [(0.0, self.points[0][1], self.points[0][2])] + self.points + [(self.total, *self.points[-1][1:])]
        values = ";".join(f"{x:g},{y:g}" for _, x, y in pts)
        times = ";".join(self.key(t) for t, _, _ in pts)
        return (f'<animateTransform attributeName="transform" type="translate" values="{values}" '
                f'keyTimes="{times}" dur="{self.total:.3f}s" repeatCount="indefinite"/>')

    def facing(self) -> str:
        flips = [(0.0, 1)] + [(self.points[2 * r][0], 1 if r % 2 == 0 else -1) for r in range(1, 7)]
        values = ";".join(f"{s},1" for _, s in flips)
        times = ";".join(self.key(t) for t, _ in flips)
        return (f'<animateTransform attributeName="transform" type="scale" values="{values}" '
                f'keyTimes="{times}" dur="{self.total:.3f}s" calcMode="discrete" repeatCount="indefinite"/>')


def month_labels(weeks: list[list]) -> list[tuple[int, str]]:
    labels, last = [], None
    for i, week in enumerate(weeks):
        day = next((d for d in week if d), None)
        if day and (m := dt.date.fromisoformat(day["date"]).month) != last:
            labels.append((i, MONTHS[m - 1]))
            last = m
    return [lab for j, lab in enumerate(labels) if j + 1 == len(labels) or labels[j + 1][0] - lab[0] >= 3]


def build(theme: str, cal: dict) -> str:
    c, ramp = THEMES[theme], LEVELS[theme]
    weeks = cal["weeks"]
    left = MARGIN + LABEL_COL
    header_y = MARGIN + HEADER_FONT
    months_y = header_y + 26
    top = months_y + 8
    legend_y = top + 6 * PITCH + CELL + 22
    height = legend_y + MARGIN
    route = Route(len(weeks), left, top)

    base, food = [], []
    for col, week in enumerate(weeks):
        for row, day in enumerate(week):
            if not day:
                continue
            x, y = left + col * PITCH, top + row * PITCH
            base.append(f'<use href="#d" x="{x}" y="{y}"/>')
            if day["level"]:
                k = route.key(route.eaten_at(col, row))
                food.append(f'<use href="#d" x="{x}" y="{y}" fill="{ramp[day["level"]]}">'
                            f'<animate attributeName="visibility" values="visible;hidden" keyTimes="0;{k}" '
                            f'dur="{route.total:.3f}s" calcMode="discrete" repeatCount="indefinite"/></use>')

    chomp = (f'<path fill="{c["key"]}" d="{mouth(40)}"><animate attributeName="d" '
             f'values="{mouth(40)};{mouth(3)};{mouth(40)}" dur="{CHOMP}s" repeatCount="indefinite"/></path>')
    pacman = f'<g>{route.translate()}<g>{route.facing()}{chomp}</g></g>'

    months = "".join(f'<text x="{left + col * PITCH}" y="{months_y}">{name}</text>'
                     for col, name in month_labels(weeks))
    days = "".join(f'<text x="{MARGIN}" y="{route.cy(row) + LABEL_FONT * 0.35:g}">{name}</text>'
                   for row, name in WEEKDAYS.items())
    grid_right = left + (len(weeks) - 1) * PITCH + CELL
    more_x = grid_right - 4 * LABEL_FONT * ADVANCE
    swatch_x = more_x - 6 - 5 * PITCH + (PITCH - CELL)
    swatches = "".join(f'<rect x="{swatch_x + i * PITCH:g}" y="{legend_y - CELL + 3}" width="{CELL}" '
                       f'height="{CELL}" rx="{RADIUS}" fill="{ramp[i]}"/>' for i in range(5))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_W}" height="{height}" viewBox="0 0 {CARD_W} {height}" font-family="{FONT_STACK}">
<style>
{FONT_FACE}
text {{white-space: pre;}}
</style>
<defs><rect id="d" width="{CELL}" height="{CELL}" rx="{RADIUS}"/></defs>
<rect width="100%" height="100%" rx="12" fill="{c['bg']}"/>
<text x="{MARGIN}" y="{header_y}" font-size="{HEADER_FONT}px" fill="{c['fg']}"><tspan fill="{c['value']}">{cal['total']:,}</tspan> contributions in the last year</text>
<g font-size="{LABEL_FONT}px" fill="{c['dots']}">{months}{days}
<text x="{swatch_x - 6:g}" y="{legend_y}" text-anchor="end">Less</text>
<text x="{more_x:g}" y="{legend_y}">More</text></g>
{swatches}
<g fill="{ramp[0]}">{"".join(base)}</g>
{"".join(food)}
{pacman}
</svg>
"""


def check_smil(svg: str) -> int:
    """Browsers silently drop a malformed animation, so fail the build on one instead."""
    count = 0
    for el in ET.fromstring(svg.split("?>", 1)[1]).iter():
        if el.tag.split("}")[-1] not in ("animate", "animateTransform") or "keyTimes" not in el.attrib:
            continue
        keys = [float(k) for k in el.get("keyTimes").split(";")]
        values = el.get("values").split(";")
        if len(keys) != len(values) or keys[0] != 0 or keys != sorted(keys) or keys[-1] > 1:
            raise SystemExit(f"bad keyTimes on {el.get('attributeName')}: {keys[:4]}... for {len(values)} values")
        if el.get("calcMode") != "discrete" and keys[-1] != 1:
            raise SystemExit(f"interpolated {el.get('attributeName')} must end at keyTime 1")
        count += 1
    return count


def main() -> None:
    if not CALENDAR.exists():
        raise SystemExit("cache/calendar.json missing, run tools/fetch_stats.py first")
    cal = json.loads(CALENDAR.read_text())
    for theme in THEMES:
        svg = build(theme, cal)
        out = ROOT / f"pacman_{theme}.svg"
        out.write_text(svg, encoding="utf-8")
        print(f"wrote {out.name} ({out.stat().st_size:,} bytes, {check_smil(svg)} animations checked)")


if __name__ == "__main__":
    main()
