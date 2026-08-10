import glob
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from app.printing.raster import image_to_escpos_raster

# No thermal/dot-matrix printer firmware ships a Tamil glyph set in its built-in
# code-page font — sending Tamil as plain ESC/POS text prints as garbage or blank
# regardless of encoding. Rasterizing the text as a bitmap (same GS v 0 raster command
# already used for the UPI QR code, see printing/qr.py) is the only way to get real
# Tamil onto a physical receipt. The font itself ships via the OS (see
# backend/Dockerfile's `fonts-lohit-taml` package) rather than being bundled in the
# repo, so it's found by search rather than a hardcoded path.
_FONT_GLOBS = [
    "/usr/share/fonts/**/*Lohit*Tamil*.ttf",
    "/usr/share/fonts/**/*lohit*taml*.ttf",
    "/usr/share/fonts/**/*Tamil*.ttf",
    "/usr/share/fonts/**/*tamil*.ttf",
]


@lru_cache(maxsize=1)
def _tamil_font_path() -> str:
    for pattern in _FONT_GLOBS:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]
    raise RuntimeError(
        "No Tamil font found on this system — install a Tamil font package "
        "(e.g. 'fonts-lohit-taml', see backend/Dockerfile) to print Tamil item names."
    )


def render_tamil_text_to_escpos(text: str, font_size: int = 24, max_width_px: int = 384) -> bytes:
    """Rasterizes `text` (Tamil item/category names) as a small ESC/POS raster image.
    `max_width_px` defaults to 384 dots (58mm/203dpi's safely-printable width) but the
    thermal adapter passes a width scaled to the printer's actual `paper_width_mm`.

    `layout_engine=RAQM` is required, not optional, for Tamil: Pillow's default "basic"
    layout draws one glyph per Unicode codepoint with no reordering or ligature rules,
    which for Tamil (a complex script — vowel signs reposition around consonants,
    consonant clusters form conjunct ligatures) produces visibly wrong shapes even
    though every individual glyph exists in the font. Requires libraqm0 at the OS level
    (see backend/Dockerfile) — Pillow only uses it when both the library and this flag
    are present, silently falling back to "basic" (broken) shaping otherwise.
    """
    font = ImageFont.truetype(_tamil_font_path(), font_size, layout_engine=ImageFont.Layout.RAQM)
    measured = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=font)
    text_width = min(measured[2] - measured[0], max_width_px)
    text_height = measured[3] - measured[1]

    # Minimal 1px padding — this renders inline between two ordinary ESC/POS text
    # lines (CLAUDE.md §9's bilingual item lines), so it should read as "one compact
    # line," not leave a visible gap the way the un-tuned first pass did in testing.
    image = Image.new("L", (text_width + 2, text_height + 2), color=255)
    draw = ImageDraw.Draw(image)
    draw.text((1, 1 - measured[1]), text, font=font, fill=0)
    return image_to_escpos_raster(image, dither=False)
