"""Tests for print-agent/escpos_render.py — the ESC/POS-to-PNG renderer behind agent.py's
--emulate mode. Builds byte streams using the exact same control-code helpers the
backend's real adapters use (see backend/app/printing/escpos_thermal.py, raster.py) so a
parser bug here would also have meant a real receipt render bug there.
"""

from PIL import Image

import escpos_render as render

_ESC = b"\x1b"
_GS = b"\x1d"
_INIT = _ESC + b"@"
_BOLD_ON = _ESC + b"E\x01"
_BOLD_OFF = _ESC + b"E\x00"
_CENTER = _ESC + b"a\x01"
_LEFT = _ESC + b"a\x00"
_CUT = _ESC + b"i"
_SIZE_NORMAL = _GS + b"!" + bytes([0x00])
_SIZE_DOUBLE = _GS + b"!" + bytes([0x11])


def _text(s: str) -> bytes:
    return s.encode("utf-8") + b"\n"


def _raster(width_px: int, height_px: int, all_black: bool = True) -> bytes:
    """Builds a GS v 0 block the same way raster.py's image_to_escpos_raster does, for
    a solid black (or white) rectangle — enough to test the raster round-trip without
    needing a real logo/QR image file.
    """
    width_bytes = (width_px + 7) // 8
    row = bytes([0xFF if all_black else 0x00]) * width_bytes
    body = row * height_px
    header = (
        _GS
        + b"v0"
        + bytes([0])
        + bytes([width_bytes & 0xFF, (width_bytes >> 8) & 0xFF])
        + bytes([height_px & 0xFF, (height_px >> 8) & 0xFF])
    )
    return header + body


def test_parse_plain_text_lines():
    data = _text("Hello") + _text("World")
    ops = render.parse_escpos(data)
    assert [op.text for op in ops] == ["Hello", "World"]
    assert all(op.align == "left" and not op.bold and op.size == 0x00 for op in ops)


def test_parse_tracks_bold_size_align_state():
    data = _INIT + _CENTER + _BOLD_ON + _SIZE_DOUBLE + _text("KOTMate TN") + _SIZE_NORMAL + _BOLD_OFF + _LEFT + _text(
        "Test Print"
    )
    ops = render.parse_escpos(data)
    assert len(ops) == 2
    first, second = ops
    assert first.text == "KOTMate TN"
    assert first.bold is True
    assert first.size == 0x11
    assert first.align == "center"
    assert second.text == "Test Print"
    assert second.bold is False
    assert second.size == 0x00
    assert second.align == "left"


def test_esc_init_resets_state_mid_stream():
    data = _BOLD_ON + _CENTER + _INIT + _text("Reset")
    (op,) = render.parse_escpos(data)
    assert op.bold is False
    assert op.align == "left"


def test_parse_raster_block_produces_image_op():
    # Real usage always follows a raster block with a trailing "\n" (e.g. render_bill's
    # `logo_raster + b"\n"`) to advance the paper past the image — that LF flushes a
    # second, empty TextLine op, which is expected and harmless to render.
    data = _CENTER + _raster(16, 8) + b"\n"
    ops = render.parse_escpos(data)
    assert isinstance(ops[0], render.ImageBlock)
    assert ops[0].align == "center"
    assert ops[0].image.size == (16, 8)


def test_raster_to_image_round_trips_black_pixels():
    # A fully "on" (black) 8x1 raster should decode to an image with a black (0) pixel
    # at every position — image_to_escpos_raster's "0 = black" convention (raster.py).
    body = bytes([0xFF])
    img = render._raster_to_image(body, width_bytes=1, height=1)
    assert img.size == (8, 1)
    assert img.getpixel((0, 0)) == 0
    assert img.getpixel((7, 0)) == 0


def test_raster_to_image_white_pixels_stay_white():
    body = bytes([0x00])
    img = render._raster_to_image(body, width_bytes=1, height=1)
    assert img.getpixel((0, 0)) == 255


def test_parse_cut_marker():
    data = _text("Last line") + _CUT
    ops = render.parse_escpos(data)
    assert ops[-1] is render.CutMarker


def test_parse_report_plain_text_no_control_codes():
    # report_print.py never emits any ESC/POS control bytes at all — just centered
    # titles and plain rows joined with "\n" (CLAUDE.md §10) — confirm the parser
    # handles pure text with no init/align/size commands at all.
    data = "Item Wise Sales\n--------\nFilter Coffee   45   Rs.1,250.00\n".encode()
    ops = render.parse_escpos(data)
    assert [op.text for op in ops] == ["Item Wise Sales", "--------", "Filter Coffee   45   Rs.1,250.00"]


def test_render_escpos_to_image_returns_valid_png_sized_image(tmp_path):
    data = _INIT + _CENTER + _BOLD_ON + _SIZE_DOUBLE + _text("KOTMate TN") + _SIZE_NORMAL + _BOLD_OFF
    data += _LEFT + _text("Test Print") + _text("-" * 32) + _raster(64, 20) + b"\n" + _CUT

    image = render.render_escpos_to_image(data)
    assert isinstance(image, Image.Image)
    assert image.width > 0
    assert image.height > 0

    out = tmp_path / "receipt.png"
    image.save(out)
    assert out.exists() and out.stat().st_size > 0
    # Round-trips through Pillow's own PNG decoder without error.
    with Image.open(out) as reopened:
        reopened.load()
        assert reopened.size == image.size


def test_printable_width_px_matches_backend_presets():
    # Mirrors backend/app/printing/base.py's line_chars_for_paper_width * _PX_PER_CHAR
    # exactly — 58mm/32-col, 80mm/48-col, 241mm/128-col, all at 12px/char.
    assert render.printable_width_px(58) == 32 * 12
    assert render.printable_width_px(80) == 48 * 12
    assert render.printable_width_px(241) == 128 * 12
    assert render.printable_width_px(None) == 32 * 12  # same default as the backend


def test_render_escpos_to_image_width_matches_configured_paper_width():
    # Canvas width must reflect the *printer's* configured paper size, not the content —
    # a wide raster block (e.g. a logo already scaled to fill a wider paper) must not
    # balloon a 58mm preview past its real physical width, and a genuinely wider printer
    # (80mm/241mm) must render visibly wider so the two are easy to tell apart at a
    # glance (production feedback: "the image should also create in the same size what i
    # have selected in the settings").
    data = _text("hello") + _raster(200, 10) + b"\n"

    narrow = render.render_escpos_to_image(data, paper_width_mm=58)
    wide = render.render_escpos_to_image(data, paper_width_mm=80)
    widest = render.render_escpos_to_image(data, paper_width_mm=241)

    assert narrow.width == render.printable_width_px(58) + 2 * render._MARGIN
    assert wide.width == render.printable_width_px(80) + 2 * render._MARGIN
    assert widest.width == render.printable_width_px(241) + 2 * render._MARGIN
    assert narrow.width < wide.width < widest.width


def test_render_escpos_to_image_custom_width_scales_proportionally():
    custom = render.render_escpos_to_image(_text("x"), paper_width_mm=112)
    assert custom.width == render.printable_width_px(112) + 2 * render._MARGIN
    assert render.printable_width_px(112) > render.printable_width_px(80)


def test_render_escpos_to_image_none_width_falls_back_to_58mm_default():
    default = render.render_escpos_to_image(_text("x"))
    explicit_58 = render.render_escpos_to_image(_text("x"), paper_width_mm=58)
    assert default.width == explicit_58.width
