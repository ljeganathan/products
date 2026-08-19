"""Renders a raw ESC/POS byte stream to a PNG image — a dev/test-only stand-in for
real thermal-printer hardware, used by agent.py's `--emulate` mode.

Understands exactly the command subset KOTMate's backend ever emits (see
backend/app/printing/escpos_thermal.py, qr.py, tamil_raster.py, raster.py, and the
plain-text-only report_print.py): ESC @ (init), ESC E (bold), GS ! (character size),
ESC a (align), ESC 3 / ESC 2 (line spacing — visually ignored, thermal-firmware-specific
and not meaningful on a rendered image), GS v 0 (raster bit-image — logo/QR/Tamil name
all use this one mechanism), ESC i (cut), and plain UTF-8 text lines terminated by \n.
Anything outside this subset is copied into the current text buffer byte-for-byte rather
than raising, since a best-effort render is more useful for visual testing than a hard
failure on an unrecognized sequence.

Requires Pillow — NOT a dependency of agent.py's normal (real-printer) code path, only
imported lazily when --emulate is used (see print-agent/README.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

_ESC = 0x1B
_GS = 0x1D
_LF = 0x0A

_MARGIN = 12
_BG = "white"
_FG = "black"

# Mirrors backend/app/printing/base.py's line_chars_for_paper_width and
# escpos_thermal.py's _PX_PER_CHAR exactly (duplicated rather than imported — print-agent
# is a standalone deployable, not a package the backend container is available to). The
# backend already sizes every raster image (logo/QR/Tamil name) to fit this same pixel
# width, so matching it here means the preview image is the same physical width as what
# the printer's configured paper size (Settings > Printers) would actually produce.
_PAPER_WIDTH_PRESETS_MM = {58: 32, 80: 48, 241: 128}
_DEFAULT_LINE_CHARS = 32
_PX_PER_CHAR = 12


def _line_chars_for_paper_width(paper_width_mm: int | None) -> int:
    if paper_width_mm is None:
        return _DEFAULT_LINE_CHARS
    if paper_width_mm in _PAPER_WIDTH_PRESETS_MM:
        return _PAPER_WIDTH_PRESETS_MM[paper_width_mm]
    return max(24, round(paper_width_mm * _DEFAULT_LINE_CHARS / 58))


def printable_width_px(paper_width_mm: int | None) -> int:
    return _line_chars_for_paper_width(paper_width_mm) * _PX_PER_CHAR


@dataclass
class TextLine:
    text: str
    bold: bool
    size: int  # raw GS ! n value: 0x00 normal, 0x01 double-height, 0x11 double-both
    align: str  # "left" | "center"


@dataclass
class ImageBlock:
    image: Image.Image
    align: str


CutMarker = object()
Op = TextLine | ImageBlock | object


def _font_candidates(bold: bool) -> list[str]:
    if bold:
        return ["consolab.ttf", "Consolas-Bold.ttf", "cambriab.ttf", "arialbd.ttf", "DejaVuSansMono-Bold.ttf"]
    return ["consola.ttf", "Consolas.ttf", "cour.ttf", "arial.ttf", "DejaVuSansMono.ttf"]


def _load_font(size: int, bold: bool) -> ImageFont.FreeTypeFont:
    for name in _font_candidates(bold):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Older Pillow without the `size` kwarg on load_default().
        return ImageFont.load_default()


def parse_escpos(data: bytes) -> list[Op]:
    """Walks the byte stream and returns a flat list of draw operations in order —
    kept separate from rendering so canvas size can be computed from the parsed ops in
    one pass before drawing anything.
    """
    ops: list[Op] = []
    bold = False
    size = 0x00
    align = "left"
    buf = bytearray()
    i = 0
    n = len(data)

    def flush_line() -> None:
        nonlocal buf
        ops.append(TextLine(text=buf.decode("utf-8", errors="replace"), bold=bold, size=size, align=align))
        buf = bytearray()

    while i < n:
        b = data[i]
        if b == _ESC and data[i + 1 : i + 2] == b"@":
            if buf:
                flush_line()
            bold, size, align = False, 0x00, "left"
            i += 2
        elif b == _ESC and data[i + 1 : i + 2] == b"E" and i + 2 < n:
            if buf:
                flush_line()
            bold = data[i + 2] == 1
            i += 3
        elif b == _ESC and data[i + 1 : i + 2] == b"a" and i + 2 < n:
            if buf:
                flush_line()
            align = "center" if data[i + 2] == 1 else "left"
            i += 3
        elif b == _ESC and data[i + 1 : i + 2] == b"3" and i + 2 < n:
            i += 3  # tight line spacing — no visual equivalent needed on a static image
        elif b == _ESC and data[i + 1 : i + 2] == b"2":
            i += 2  # default line spacing — ditto
        elif b == _ESC and data[i + 1 : i + 2] == b"i":
            if buf:
                flush_line()
            ops.append(CutMarker)
            i += 2
        elif b == _GS and data[i + 1 : i + 2] == b"!" and i + 2 < n:
            if buf:
                flush_line()
            size = data[i + 2]
            i += 3
        elif b == _GS and data[i + 1 : i + 4] == b"v0" + bytes([0]) and i + 7 < n:
            if buf:
                flush_line()
            xl, xh, yl, yh = data[i + 4], data[i + 5], data[i + 6], data[i + 7]
            width_bytes = xl | (xh << 8)
            height = yl | (yh << 8)
            body_len = width_bytes * height
            body = data[i + 8 : i + 8 + body_len]
            ops.append(ImageBlock(image=_raster_to_image(body, width_bytes, height), align=align))
            i += 8 + body_len
        elif b == _LF:
            flush_line()
            i += 1
        else:
            buf.append(b)
            i += 1

    if buf:
        flush_line()
    return ops


def _raster_to_image(body: bytes, width_bytes: int, height: int) -> Image.Image:
    """Inverse of raster.py's `image_to_escpos_raster` — unpacks the 1-bit-per-pixel
    GS v 0 body back into a viewable image (logo, QR code, or Tamil name rasters all
    arrive through this one command).
    """
    width = width_bytes * 8
    img = Image.new("1", (max(width, 1), max(height, 1)), 1)  # 1 = white
    pixels = img.load()
    for y in range(height):
        row = body[y * width_bytes : (y + 1) * width_bytes]
        for x_byte, byte_val in enumerate(row):
            if not byte_val:
                continue
            for bit in range(8):
                if byte_val & (0x80 >> bit):
                    x = x_byte * 8 + bit
                    if x < width:
                        pixels[x, y] = 0  # black
    return img.convert("L")


def _text_size(font: ImageFont.FreeTypeFont, text: str) -> tuple[int, int]:
    bbox = font.getbbox(text or " ")
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _fit_font_size(target_px_per_char: int) -> int:
    """Picks a point size for whichever monospace font actually resolved on this host
    (Consolas, DejaVu Sans Mono, the PIL bitmap fallback, ...) so that one character is
    `target_px_per_char` wide — i.e. `_PX_PER_CHAR`, the same figure the backend used to
    size raster images against the printer's line width. Without this, a line that's
    exactly `line_chars_for_paper_width` characters long (every plain-text line already
    is) could render narrower or wider than the fixed paper-width canvas depending on
    which font file happened to be available.
    """
    trial_size = 24
    trial_width, _ = _text_size(_load_font(trial_size, bold=False), "0")
    if trial_width <= 0:
        return trial_size
    return max(6, round(trial_size * target_px_per_char / trial_width))


def render_escpos_to_image(data: bytes, paper_width_mm: int | None = None) -> Image.Image:
    """Renders the given raw ESC/POS byte stream to a single PNG image.

    Canvas width is fixed to the printer's actual configured paper width (58/80/241mm
    preset or a custom mm value — the same `paper_width_mm` the printer was registered
    with in Settings > Printers), not auto-sized to content, so the preview is physically
    proportioned the way the real paper roll would be — a 58mm printer's preview looks
    narrow, an 80mm printer's looks wider, matching what production feedback asked to be
    able to visually verify. `None` (no printer width configured yet) falls back to the
    same 58mm/32-col default the backend itself falls back to.
    """
    ops = parse_escpos(data)
    font_size = _fit_font_size(_PX_PER_CHAR)
    font_normal = _load_font(font_size, bold=False)
    font_normal_bold = _load_font(font_size, bold=True)

    def render_text_op(op: TextLine) -> Image.Image:
        """Renders at the normal (single-size) font first, then scales — GS ! 0x01 is
        double-HEIGHT-only (width unchanged, per escpos_thermal.py's own
        `_SIZE_DOUBLE_HEIGHT` comment: doubling width too would overflow the printable
        area), while 0x11 doubles both. Scaling a correctly-monospaced normal-size render
        is the only way to reproduce that distinction — a single bigger font size doubles
        both dimensions together and would make 0x01 rows overflow their column widths,
        exactly the bug this function replaces.
        """
        font = font_normal_bold if op.bold else font_normal
        w, h = _text_size(font, op.text)
        w, h = max(w, 1), max(h, 1)
        base = Image.new("RGB", (w, h), _BG)
        ImageDraw.Draw(base).text((0, 0), op.text, font=font, fill=_FG)
        if op.size == 0x01:
            return base.resize((w, h * 2), Image.LANCZOS)
        if op.size == 0x11:
            return base.resize((w * 2, h * 2), Image.LANCZOS)
        return base

    content_width = printable_width_px(paper_width_mm)
    canvas_width = content_width + 2 * _MARGIN

    text_images: dict[int, Image.Image] = {}
    row_heights: list[int] = []
    for i, op in enumerate(ops):
        if isinstance(op, TextLine):
            img = render_text_op(op)
            text_images[i] = img
            row_heights.append(img.height + 6)
        elif isinstance(op, ImageBlock):
            row_heights.append(op.image.height + 4)
        else:
            row_heights.append(14)

    total_height = sum(row_heights) + 2 * _MARGIN
    canvas = Image.new("RGB", (canvas_width, max(total_height, 40)), _BG)
    draw = ImageDraw.Draw(canvas)

    y = _MARGIN
    for i, (op, row_h) in enumerate(zip(ops, row_heights, strict=True)):
        if isinstance(op, TextLine):
            img = text_images[i]
            x = _MARGIN if op.align == "left" else _MARGIN + max(0, (content_width - img.width) / 2)
            canvas.paste(img, (round(x), round(y)))
        elif isinstance(op, ImageBlock):
            x = _MARGIN if op.align == "left" else _MARGIN + max(0, (content_width - op.image.width) / 2)
            canvas.paste(op.image.convert("RGB"), (round(x), round(y)))
        else:
            dash_y = y + 6
            for dx in range(0, content_width, 8):
                draw.line([(_MARGIN + dx, dash_y), (_MARGIN + dx + 4, dash_y)], fill=(90, 90, 90), width=2)
        y += row_h

    return canvas
