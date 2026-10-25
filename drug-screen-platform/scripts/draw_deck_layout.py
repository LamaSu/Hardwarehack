"""
Draw the Flex deck layout from ``src/deck_layout.py`` as a printable PNG.

Usage
-----
    uv run --with pillow --with matplotlib python scripts/draw_deck_layout.py
    uv run --with pillow --with matplotlib python scripts/draw_deck_layout.py docs/deck_layout.png

matplotlib is only used for its bundled DejaVu fonts (Pillow's built-in font
has no µ); without it the script falls back to Pillow's font.

The deck is drawn as seen from the front of the robot: row A at the back
(top of the image), row D at the front.
"""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from deck_layout import (  # noqa: E402
    CATEGORY_FREE, CATEGORY_LIQUID, CATEGORY_PLATE, CATEGORY_TIPS, CATEGORY_WASTE,
    GRIPPER_NOTE, PIPETTE_NOTE, slot_map,
)

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "deck_layout.png"

WIDTH, HEIGHT = 2200, 1700
MARGIN = 80
SLOT_WIDTH, SLOT_HEIGHT, GAP = 520, 250, 28
STAGING_WIDTH = 230
DECK_LEFT, DECK_TOP = MARGIN + 60, 250

BACKGROUND = "#FFFFFF"
DECK_COLOR = "#F4F5F7"
TEXT = "#1D2430"
MUTED = "#5F6B7A"
# (fill, border) per category; light fills so it prints well.
CATEGORY_COLORS = {
    CATEGORY_TIPS: ("#E3EEFB", "#2F6FC6"),
    CATEGORY_LIQUID: ("#DFF3EF", "#16846F"),
    CATEGORY_PLATE: ("#FDEBD8", "#C8701E"),
    CATEGORY_WASTE: ("#ECECEE", "#6B6F76"),
    CATEGORY_FREE: ("#FFFFFF", "#9AA1AB"),
}
CATEGORY_NAMES = {
    CATEGORY_TIPS: "Tips", CATEGORY_LIQUID: "Liquids (reservoirs, tubes)",
    CATEGORY_PLATE: "Plates", CATEGORY_WASTE: "Waste", CATEGORY_FREE: "Free",
}


def _font_dir() -> Optional[Path]:
    try:
        import matplotlib
    except ImportError:
        return None
    return Path(matplotlib.get_data_path()) / "fonts" / "ttf"


_FONT_DIR = _font_dir()


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(str(_FONT_DIR / name), size) if _FONT_DIR else ImageFont.load_default(size=size)
    except OSError:
        return ImageFont.load_default(size=size)


def _fitting_font(draw: ImageDraw.ImageDraw, text: str, size: int, width: int) -> ImageFont.FreeTypeFont:
    font = _font(size)
    while size > 12 and draw.textlength(text, font=font) > width:
        size -= 1
        font = _font(size)
    return font


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    return lines + [current] if current else lines


def _dashed_rectangle(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: str,
                      width: int = 4, dash: int = 18) -> None:
    left, top, right, bottom = box
    for start in range(left, right, dash * 2):
        draw.line([(start, top), (min(start + dash, right), top)], fill=color, width=width)
        draw.line([(start, bottom), (min(start + dash, right), bottom)], fill=color, width=width)
    for start in range(top, bottom, dash * 2):
        draw.line([(left, start), (left, min(start + dash, bottom))], fill=color, width=width)
        draw.line([(right, start), (right, min(start + dash, bottom))], fill=color, width=width)


def _draw_slot(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], slot_name: str) -> None:
    item = slot_map().get(slot_name)
    category = item.category if item else CATEGORY_FREE
    fill, border = CATEGORY_COLORS[category]
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=18, fill=fill)
    if category == CATEGORY_FREE or (item and item.optional):
        _dashed_rectangle(draw, box, border)
    else:
        draw.rounded_rectangle(box, radius=18, outline=border, width=5)

    draw.text((left + 24, top + 14), slot_name, font=_font(48, bold=True), fill=border)
    if item and item.optional:
        tag_font = _font(22)
        tag_width = draw.textlength("optional", font=tag_font)
        draw.rounded_rectangle((right - tag_width - 44, top + 22, right - 20, top + 58), radius=10, fill=border)
        draw.text((right - tag_width - 32, top + 26), "optional", font=tag_font, fill="#FFFFFF")
    if item is None:
        return

    text_width = right - left - 48
    y = top + 86
    for line in _wrap(draw, item.title, _font(31, bold=True), text_width)[:2]:
        draw.text((left + 24, y), line, font=_font(31, bold=True), fill=TEXT)
        y += 40
    text_bottom = bottom - 48 if item.load_name else bottom - 12
    for line in _wrap(draw, item.purpose, _font(26), text_width):
        if y + 30 > text_bottom:
            break
        draw.text((left + 24, y), line, font=_font(26), fill=MUTED)
        y += 33
    if item.load_name:
        draw.text((left + 24, bottom - 40), item.load_name,
                  font=_fitting_font(draw, item.load_name, 21, text_width), fill=MUTED)


def draw_deck(output: Path) -> None:
    """
    Render the deck layout to ``output`` as PNG.

    Raises
    ------
    OSError
        If the image can't be written.
    """
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.text((MARGIN, 50), "Opentrons Flex — deck layout for the drug screen", font=_font(52, bold=True),
              fill=TEXT)
    draw.text((MARGIN, 125), "Seen from the front of the robot. Place each labware in its slot before the run.",
              font=_font(30), fill=MUTED)

    deck_right = DECK_LEFT + 3 * SLOT_WIDTH + 2 * GAP + GAP + STAGING_WIDTH
    deck_bottom = DECK_TOP + 4 * SLOT_HEIGHT + 3 * GAP
    draw.rounded_rectangle((DECK_LEFT - 30, DECK_TOP - 70, deck_right + 30, deck_bottom + 70),
                           radius=30, fill=DECK_COLOR)
    label_font = _font(28)
    back_text = "BACK OF ROBOT"
    draw.text(((DECK_LEFT + deck_right - draw.textlength(back_text, font=label_font)) / 2, DECK_TOP - 55),
              back_text, font=label_font, fill=MUTED)
    front_text = "FRONT — you stand here"
    draw.text(((DECK_LEFT + deck_right - draw.textlength(front_text, font=label_font)) / 2, deck_bottom + 22),
              front_text, font=label_font, fill=MUTED)

    for row_index, row in enumerate("ABCD"):
        top = DECK_TOP + row_index * (SLOT_HEIGHT + GAP)
        draw.text((DECK_LEFT - 75, top + SLOT_HEIGHT / 2 - 22), row, font=_font(40), fill=MUTED)
        for column in range(3):
            left = DECK_LEFT + column * (SLOT_WIDTH + GAP)
            _draw_slot(draw, (left, top, left + SLOT_WIDTH, top + SLOT_HEIGHT), f"{row}{column + 1}")

    staging_left = DECK_LEFT + 3 * (SLOT_WIDTH + GAP)
    _dashed_rectangle(draw, (staging_left, DECK_TOP, staging_left + STAGING_WIDTH, deck_bottom),
                      CATEGORY_COLORS[CATEGORY_FREE][1])
    y = DECK_TOP + 30
    for line in ["Staging", "area", "(column 4)", "", "optional:", "spare tip", "racks instead", "of D1 / D2"]:
        draw.text((staging_left + 22, y), line, font=_font(28), fill=MUTED)
        y += 38

    legend_top = deck_bottom + 120
    x = MARGIN
    for category, name in CATEGORY_NAMES.items():
        fill, border = CATEGORY_COLORS[category]
        draw.rounded_rectangle((x, legend_top, x + 40, legend_top + 40), radius=8, fill=fill, outline=border, width=4)
        draw.text((x + 54, legend_top + 4), name, font=_font(28), fill=TEXT)
        x += 54 + int(draw.textlength(name, font=_font(28))) + 60
    _dashed_rectangle(draw, (x, legend_top, x + 40, legend_top + 40), MUTED, width=3, dash=8)
    draw.text((x + 54, legend_top + 4), "dashed = optional / free", font=_font(28), fill=TEXT)

    draw.text((MARGIN, legend_top + 70), PIPETTE_NOTE, font=_font(30), fill=TEXT)
    draw.text((MARGIN, legend_top + 112), GRIPPER_NOTE, font=_font(30), fill=TEXT)

    output = Path(output)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output)
    except OSError as error:
        raise OSError(f"Could not write {output}: {error}") from error


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    try:
        draw_deck(output)
    except OSError as error:
        print(error)
        return 1
    print(f"Saved {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
