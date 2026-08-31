# Landing Page — kotmatetn.in

The marketing/landing site for KOTMate, separate from the application itself
(`app.kotmatetn.in`, built from `frontend/`). Built per the brief in
`docs/KOTMate Landing Page.docx`, using real screenshots exported from that
same document and real copy grounded in `CLAUDE.md`'s actual feature/pricing
tables — see §7 "Assumptions" below for the couple of places the brief and
the current app/CLAUDE.md disagree.

It's a **static site** — plain HTML/CSS/vanilla JS, no framework, no build
step — served by its own `nginx:alpine` container (`landing/Dockerfile`),
deployed as a **separate Docker service** alongside the existing `backend`/
`nginx` (app frontend)/`postgres` stack, routed by the shared Traefik
instance to the apex domain `kotmatetn.in` (+ `www.kotmatetn.in`) instead of
the `app.` subdomain. It never talks to the KOTMate API/database — every
"Login"/"Start Free Trial" action links out to `https://app.kotmatetn.in` or
to WhatsApp/email.

## 1. Files created

```
landing/
├── Dockerfile              # nginx:alpine, explicit COPY (no build step)
├── nginx.conf              # static-file serving, caching, security headers
├── robots.txt
├── sitemap.xml
├── index.html               # the landing page itself
├── privacy.html
├── terms.html
├── 404.html
├── css/styles.css           # full design system + component styles
├── js/
│   ├── analytics-config.js  # editable GA4/Meta Pixel/Google Ads IDs (blank by default)
│   ├── analytics.js          # loads GA4/Pixel only if configured; exposes window.kotmateTrack()
│   └── main.js                # mobile nav, FAQ accordion, showcase tabs, pricing toggle, click tracking
└── assets/
    ├── logo-full.png, logo-mark.png, favicon.png   # copied from frontend/src/assets + frontend/public
    ├── og-image.jpg                                  # generated social-share card
    ├── hero/pos-tablet-printer.jpg, printed-bill.jpg # from the docx, re-compressed
    └── screenshots/*.png, mobile-pos.jpg              # 9 real product screenshots from the docx, re-compressed
```

All 12 images embedded in `docs/KOTMate Landing Page.docx` were extracted,
resized and re-compressed (PNG `optimize=True` for UI screenshots, JPEG q82
for the two photographic hero shots) — total image weight dropped from
~3.3MB to ~1MB. The doc's `og-image.jpg` and the mockup/screenshot mapping
are documented in the commit; nothing in `landing/assets/` is a placeholder
or stock photo — it's all real product UI.

## 2. Files changed (existing repo files)

| File | Change |
|---|---|
| `docker-compose.yml` | Added `landing` service (dev: port 8080, no profile — runs by default) |
| `docker-compose.prod.yml` | Added `landing` override (drops the dev host port; Traefik reaches it over the internal network) |
| `docker-compose.traefik.yml` | Added a second Traefik router (`kotmate-landing`) + labels routing `Host(kotmatetn.in) \|\| Host(www.kotmatetn.in)` to the `landing` service, separate from the existing `kotmate` router on `app.kotmatetn.in` |
| `.env.example` | Added `LANDING_DOMAIN=kotmatetn.in` |
| `scripts/deploy.sh` | `up -d --build` now also names `landing`; header comment updated |
| `docs/DEPLOYMENT.md` | §2 DNS now asks for apex + `www` A records (previously said the apex "stays free for a future page" — that page is this one); §4 first-launch command and TLS note now cover `landing`; §8 smoke-test checklist has 3 new landing-site checks |

Nothing under `frontend/` or `backend/` was touched — the landing site
only *reads* two existing frontend assets (the logo files) as static
copies; it doesn't share a build pipeline with the app.

## 3. How to run locally

No build step — just serve the folder:

```bash
cd landing
python -m http.server 8080
# → http://localhost:8080/index.html
```

Or via Docker, matching how it'll actually run in production:

```bash
docker compose up --build landing
# → http://localhost:8080 (docker-compose.yml maps host 8080 -> container 80)
```

## 4. How to build for production

No build step here either — the "build" is just the Docker image:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  -f docker-compose.traefik.yml up -d --build landing
```

(`scripts/deploy.sh` already does this as part of a full redeploy — see
`docs/DEPLOYMENT.md` §4/§5, updated as part of this change.)

## 5. Environment variables required

| Variable | Where | Purpose |
|---|---|---|
| `LANDING_DOMAIN` | root `.env` (VPS only, gitignored) | e.g. `kotmatetn.in` — drives the Traefik `Host()` rule for both the apex and `www.` |
| `TRAEFIK_NETWORK`, `TRAEFIK_CERT_RESOLVER` | root `.env` | Already existed for the app; reused as-is for the landing site's own Traefik router |

There is **no build-time env var** for the landing site itself (unlike
`frontend`'s `VITE_API_URL`) — it's plain static files, nothing is baked in
at build time.

### DNS (one-time, Hostinger hPanel)

Add two **A records** under `kotmatetn.in` pointing at the VPS IP: host `@`
(apex) and host `www`. See `docs/DEPLOYMENT.md` §2.

## 6. Analytics configuration required

Static site ⇒ no real `.env` to bake IDs into at build time. Instead, edit
`landing/js/analytics-config.js` directly (on the server, or before
deploying) and reload nginx:

```js
window.KOTMATE_ANALYTICS_CONFIG = {
  ga4MeasurementId: "G-XXXXXXXXXX",       // Google Analytics 4
  metaPixelId: "1234567890123456",         // Meta Pixel
  googleAdsConversion: { id: "AW-...", label: "..." },
};
```

Leaving an ID blank disables that provider entirely (no script is even
loaded) — safe to commit with blank defaults since none of these IDs are
secret. Events wired up in `js/main.js`/`js/analytics.js`, matching the
brief's list: `page_view`, `pricing_view` (fires once, via
`IntersectionObserver` on the pricing section), `start_trial_click`,
`login_click`, `demo_click`, `whatsapp_click`, `contact_click`.

## 7. Login / free-trial URL configuration

- Every **Login** control → `https://app.kotmatetn.in` (hardcoded — this is
  a static site, there's no runtime config layer, and the brief is explicit
  that this must never be a fake login page).
- **Start Free Trial** / **Book a Free Demo** / the floating WhatsApp button
  → `https://wa.me/919916652135` with a pre-filled message. **Assumption**
  (see §8): the app has no public self-service signup endpoint today
  (tenants are provisioned by the platform admin, `CLAUDE.md` §3/§5), so
  these CTAs open a real, working conversation instead of a non-functional
  signup form. Swap the `href`s in `index.html` to a real signup URL later
  if one is built.

## 8. Assumptions made

1. **Pro Max price**: the docx brief specifies **₹1,999/month** for Pro Max.
   `CLAUDE.md` §7 currently documents Pro Max at **₹1,499/month** (and Pro at
   ₹799 vs. the docx's ₹999). The landing page follows the docx brief's
   numbers (₹499 / ₹999 / ₹1,999) since that's the explicit instruction for
   this page — **but this is a real pricing discrepancy between two source
   documents that should be reconciled** (either update `CLAUDE.md` §7 to
   match the new public prices, or update the landing page back down) before
   this goes live for real customers.
2. **Annual pricing** = monthly × 10 (2 months free), per the docx's own
   formula — this gives ₹4,990 / ₹9,990 / ₹19,990/year, which differs
   slightly from `CLAUDE.md` §7's existing ₹4,999/₹7,999/₹14,999 figures
   (rounder numbers, same "2 months free" concept, different base prices).
3. **No self-service signup exists yet** (see §7 above) — "Start Free
   Trial"/"Book a Free Demo" route to WhatsApp instead of a form, avoiding
   a fake/non-functional signup flow per the brief's own instruction not to
   create misleading claims or fake auth.
4. **Contact form**: the brief mentions sanitizing "contact forms," but this
   static site has no backend to receive a form submission safely. Contact
   is handled via `mailto:`, `tel:`, and WhatsApp links instead — all real,
   working channels, none of them a fake form that goes nowhere.
5. **Privacy Policy / Terms & Conditions**: written as reasonable, honest
   boilerplate for a small restaurant-tech SaaS (so the footer links aren't
   broken) — both pages say plainly that they're a template and should be
   reviewed against real data-handling practice / by counsel before being
   relied on for compliance.
6. **Testimonials/case studies**: the brief asks for placeholders since none
   exist yet — `.testimonial-slot` in the Trust section is a clearly-labeled
   placeholder, easy to swap for real reviews later (§9 "Future
   Scalability" in the brief).
7. Feature/comparison-table content was cross-checked against `CLAUDE.md`
   §6 line by line — every row on the landing page's comparison table and
   every pricing-card bullet matches a real, currently-shipped feature; none
   of the not-yet-built roadmap items (add-on marketplace, KDS beyond Pro
   Max, etc.) are claimed.

## 9. Final QA (per the brief's own checklist)

- [x] Desktop responsiveness — verified in-browser at 1400×900 (hero, problem
      cards, audience grid, pricing cards, comparison table all render
      correctly with intended shadows/spacing).
- [x] Mobile nav/CSS logic verified by reading the compiled rule
      (`.nav-desktop{display:none}` by default, `flex` only ≥960px;
      `.nav-toggle` inversely hidden ≥960px) — this environment's browser
      tool could not reliably force a narrow viewport to screenshot, so this
      was confirmed by inspecting the CSS rule directly rather than visually;
      worth a real-device check before go-live.
- [x] Broken links — every `assets/...` path referenced in `index.html`,
      `privacy.html`, `terms.html`, `404.html` verified to exist on disk;
      internal anchors (`#features`, `#pricing`, etc.) match real section
      `id`s.
- [x] CTA / Login links — all point to `https://app.kotmatetn.in` or a real
      `wa.me`/`mailto:`/`tel:` link, none are dead `#` placeholders.
- [x] Pricing section — verified Lite/Pro/Pro Max monthly↔annual toggle and
      the FAQ accordion both work correctly (tested via the live DOM).
- [x] SEO metadata — title, meta description, canonical, Open Graph/Twitter
      card (with a generated `og-image.jpg`), `SoftwareApplication` +
      `FAQPage` JSON-LD, `robots.txt`, `sitemap.xml` all present.
- [x] Accessibility — semantic headings, `alt` text on every image,
      `:focus-visible` outline, `aria-expanded`/`aria-selected`/`role`
      attributes on the accordion/tabs/switch, `prefers-reduced-motion`
      respected.
- [x] Performance — no JS framework, no icon-font library (inline SVGs
      instead), images optimized (~1MB total across 12 images), fonts
      loaded via `preconnect` + a single Google Fonts request, `loading="lazy"`
      on every below-the-fold image.
- [ ] **Console errors** and a real Lighthouse run — not executed against a
      live HTTPS deployment in this environment; do this once DNS/Traefik
      are live (§8 of `docs/DEPLOYMENT.md`).
