"""Turn assets/portrait.png into assets/ascii.txt, which both themes draw. Run locally when the photo changes:
uv run --with pillow tools/make_ascii.py"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "portrait.png"

COLS = 46
CELL_ASPECT = 0.5  # glyph width / line height, must match build_card's ART_LINE
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"  # sparse to dense
SHADOW = 0.28  # tones below this become blank, which is what keeps the art airy
OUTLINE = 7  # ramp index drawn on subject cells that touch the backdrop
BG_TOLERANCE = 14  # the backdrop is one flat colour, so this can stay tight
BG_VOTE = 0.6  # share of a cell that must be backdrop to draw it blank
MARK = (255, 0, 255)
LOCAL_RADIUS = 6  # px on the source photo, about the size of an eye
LOCAL_GAIN = 1.2
CLIP = 0.02  # ignore this share of the darkest and brightest subject cells when stretching
GAMMA = 0.9


def distance(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    return sum(abs(x - y) for x, y in zip(a, b))


def backdrop_mask(img: Image.Image) -> Image.Image:
    """Flood the backdrop in from the border, so skin tones inside the face are never mistaken for it."""
    w, h = img.size
    bg = img.getpixel((2, 2))
    probe = img.copy()
    border = [(x, y) for x in range(0, w, 4) for y in (0, h - 1)] + [(x, y) for y in range(0, h, 4) for x in (0, w - 1)]
    for seed in border:
        px = probe.getpixel(seed)
        if px != MARK and distance(px, bg) < BG_TOLERANCE:
            ImageDraw.floodfill(probe, seed, MARK, thresh=BG_TOLERANCE)
    mask = Image.new("L", img.size, 0)
    mask.putdata([255 if px == MARK else 0 for px in probe.getdata()])
    return mask


def local_contrast(grey: Image.Image) -> Image.Image:
    """Push each pixel away from its neighbourhood mean, so eyes and mouth stand out from the cheeks."""
    blur = grey.filter(ImageFilter.GaussianBlur(LOCAL_RADIUS))
    return Image.blend(blur, grey, 1 + LOCAL_GAIN)  # alpha > 1 extrapolates past the original; PIL clips


def subject_box(mask: Image.Image) -> tuple[int, int, int, int]:
    return Image.eval(mask, lambda v: 255 - v).getbbox()


def convert() -> list[str]:
    img = Image.open(SRC).convert("RGB")
    full_mask = backdrop_mask(img)
    bbox = subject_box(full_mask)
    img = img.crop(bbox)
    rows = round(COLS * img.height / img.width * CELL_ASPECT)
    grey = local_contrast(img.convert("L")).resize((COLS, rows), Image.LANCZOS)
    mask = full_mask.crop(bbox).resize((COLS, rows), Image.BOX)

    cells = [(x, y) for y in range(rows) for x in range(COLS)]
    subject = {c: grey.getpixel(c) for c in cells if mask.getpixel(c) / 255 < BG_VOTE}
    # Stretch over the subject alone, so the backdrop never claims part of the tonal range.
    tones = sorted(subject.values())
    lo, hi = tones[int(len(tones) * CLIP)], tones[int(len(tones) * (1 - CLIP))]

    top = len(RAMP) - 1
    lines = []
    for y in range(rows):
        out = []
        for x in range(COLS):
            if (x, y) not in subject:
                out.append(" ")
                continue
            level = min(1.0, max(0.0, (subject[(x, y)] - lo) / (hi - lo))) ** GAMMA
            if level < SHADOW:
                edge = any(0 <= x + dx < COLS and 0 <= y + dy < rows and (x + dx, y + dy) not in subject
                           for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                out.append(RAMP[OUTLINE] if edge else " ")  # the outline keeps the head's shape where shadows go blank
                continue
            out.append(RAMP[round((level - SHADOW) / (1 - SHADOW) * top)])
        lines.append("".join(out).rstrip())
    return lines


def main() -> None:
    art = convert()
    out = ROOT / "assets" / "ascii.txt"
    out.write_text("\n".join(art) + "\n", encoding="utf-8")
    print(f"wrote {out.name}: {max(map(len, art))} cols x {len(art)} rows")


if __name__ == "__main__":
    main()
