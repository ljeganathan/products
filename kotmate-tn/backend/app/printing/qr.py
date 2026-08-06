import qrcode

_GS = b"\x1d"


def _scaled_matrix(data: str, box_size: int) -> list[list[bool]]:
    """QR module matrix (already includes the quiet-zone border), each module repeated
    `box_size` times in both directions so it prints large enough to scan on a ~203dpi
    thermal head — a single dot per module is well below reliably-scannable size.
    """
    qr = qrcode.QRCode(border=4)
    qr.add_data(data)
    qr.make(fit=True)
    modules = qr.get_matrix()
    return [[cell for cell in row for _ in range(box_size)] for row in modules for _ in range(box_size)]


def generate_qr_escpos(data: str, box_size: int = 4) -> bytes:
    """ESC/POS GS v 0 raster bit image command embedding a QR code for `data` (e.g. a
    `upi://pay?...` deep link) — CLAUDE.md §10: "QR code ... generated server-side as an
    image for thermal printers." Dot-matrix has no image support (CLAUDE.md §10), so this
    is thermal-only; the dot-matrix bill adapter prints the UPI id as plain text instead.
    """
    pixels = _scaled_matrix(data, box_size)
    height = len(pixels)
    width = len(pixels[0])
    width_bytes = (width + 7) // 8

    body = bytearray()
    for row in pixels:
        row_bytes = bytearray(width_bytes)
        for x, on in enumerate(row):
            if on:
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
