import io

from PIL import Image

_GS = b"\x1d"


def image_to_escpos_raster(image: Image.Image, dither: bool = False) -> bytes:
    """ESC/POS `GS v 0` raster bit-image command for an arbitrary 1-bit image — shared
    by the Tamil text rasterizer (printing/tamil_raster.py) and the hotel logo
    rasterizer below. `dither` off (hard threshold) suits crisp text glyphs; on
    (Floyd-Steinberg, PIL's own default) suits photographic/gradient logo art, which
    reads better dithered than flatly thresholded on a 1-bit thermal head.
    """
    bitmap = image.convert("1", dither=Image.FLOYDSTEINBERG if dither else Image.NONE)
    width, height = bitmap.size
    width_bytes = (width + 7) // 8
    pixels = bitmap.load()

    body = bytearray()
    for y in range(height):
        row_bytes = bytearray(width_bytes)
        for x in range(width):
            # PIL's "1" mode: 0 = black. We want a thermal dot ("on") wherever the
            # source pixel is dark.
            if pixels[x, y] == 0:
                row_bytes[x // 8] |= 0x80 >> (x % 8)
        body.extend(row_bytes)

    header = (
        _GS
        + b"v0"
        + bytes([0])
        + bytes([width_bytes & 0xFF, (width_bytes >> 8) & 0xFF])
        + bytes([height & 0xFF, (height >> 8) & 0xFF])
    )
    return header + bytes(body)


def render_logo_to_escpos(image_bytes: bytes, max_width_px: int, max_height_px: int = 400) -> bytes | None:
    """Rasterizes an uploaded hotel logo (`hotel_master.logo_url`, any Pillow-readable
    format) to an ESC/POS raster image scaled to *fill* the printer's line width —
    always scaled to `max_width_px` (upscaling a small source image if needed, not just
    downscaling a large one), since a logo printed smaller than the paper is wasted
    header space on a receipt. `max_height_px` is a sanity cap only (~50mm at 203dpi):
    it takes over as the limiting dimension for an unusually tall/narrow source image
    instead of letting fit-to-width stretch it into an excessively long print.

    Returns None on any decode failure (corrupt file, unsupported format) so the caller
    can fall back to printing the hotel name as text instead of failing the whole print
    job over a bad logo file.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception:
        return None

    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        # Flatten transparency onto white — a thermal head has no alpha channel, and an
        # unflattened transparent background would otherwise convert to solid black.
        background = Image.new("RGB", image.size, "white")
        background.paste(image.convert("RGBA"), mask=image.convert("RGBA").split()[3])
        image = background
    image = image.convert("L")

    width, height = image.size
    if not width or not height:
        return None

    scale = max_width_px / width
    if height * scale > max_height_px:
        scale = max_height_px / height

    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    if new_size != (width, height):
        image = image.resize(new_size, Image.LANCZOS)

    return image_to_escpos_raster(image, dither=True)
