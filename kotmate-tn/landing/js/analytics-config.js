// Analytics configuration for kotmatetn.in.
//
// This is a static site with no build step, so there is no real ".env" to
// bake values into at build time — this plain, gitignore-free config file
// IS the "environment variable" file: edit the IDs below directly on the
// server (or before deploying) and reload nginx. Nothing here is a secret —
// GA4 Measurement IDs and Meta Pixel IDs are public by design (they ship in
// every page's HTML/JS regardless of platform), so committing placeholders
// is safe; leave them blank to keep analytics fully disabled.
window.KOTMATE_ANALYTICS_CONFIG = {
  // e.g. "G-XXXXXXXXXX" — from Google Analytics 4 → Admin → Data Streams.
  ga4MeasurementId: "",

  // e.g. "1234567890123456" — from Meta Events Manager → Data Sources.
  metaPixelId: "",

  // Google Ads conversion id + label for the "start_trial_click" and
  // "demo_click" events, e.g. { id: "AW-123456789", label: "AbCdEfGhIjK" }.
  // Leave label blank to skip Ads conversion firing even if id is set.
  googleAdsConversion: { id: "", label: "" },
};
