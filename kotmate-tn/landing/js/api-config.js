// API base URL for the "Demos & Blog" page's two read-only calls
// (GET /api/v1/public/blog-posts, GET /api/v1/public/demo-videos).
//
// This is a static site with no build step, so — same convention as
// analytics-config.js — this plain file IS the environment config. Nothing here
// is a secret; these are public, unauthenticated read endpoints. Defaults to the
// backend on the same host when running locally (docker compose up landing, or
// python -m http.server) so this works out of the box in local testing; edit
// KOTMATE_API_BASE directly if that guess is ever wrong for your setup.
(function () {
  const isLocal = /^(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)$/.test(location.hostname);
  window.KOTMATE_API_BASE = isLocal ? `http://${location.hostname}:8000` : "https://app.kotmatetn.in";
})();
