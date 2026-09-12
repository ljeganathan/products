import QRCode from "qrcode";
import { useEffect, useRef, useState } from "react";

// Renders the scannable QR image itself (not just its link) below a QR code modal's
// copy-link row, with a "Download" button so staff can save the PNG to print/laminate
// without needing a phone camera pointed at the screen. Generated entirely client-side
// (the `qrcode` package) — no backend round-trip, no image ever leaves the browser.
export function QrCodeImage({ value, downloadName }: { value: string; downloadName: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [dataUrl, setDataUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let cancelled = false;
    setDataUrl(null);
    setError(false);
    QRCode.toCanvas(canvas, value, { width: 200, margin: 2 })
      .then(() => {
        if (cancelled) return;
        setDataUrl(canvas.toDataURL("image/png"));
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [value]);

  return (
    <div className="flex flex-col items-center gap-2.5 py-2">
      <canvas ref={canvasRef} className="rounded-md border border-border" />
      {error && <p className="text-xs text-chili">Couldn't generate the QR image.</p>}
      <a
        href={dataUrl ?? undefined}
        download={dataUrl ? `${downloadName}.png` : undefined}
        aria-disabled={!dataUrl}
        className={`rounded-md border border-border px-3 py-1.5 text-xs font-semibold hover:bg-accent/10 ${
          dataUrl ? "" : "pointer-events-none opacity-40"
        }`}
      >
        ⬇ Download QR Code
      </a>
    </div>
  );
}
