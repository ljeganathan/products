# Pamphlet source

`pamphlet-en.html` / `pamphlet-ta.html` are the source for
`../KOTMate-TN-Pamphlet.pdf` / `../KOTMate-TN-Pamphlet-Tamil.pdf`. Edit the HTML,
then regenerate both PDFs:

```
npm install playwright
npx playwright install chromium
node render.js
```

This writes `KOTMate-TN-Pamphlet.pdf` and `KOTMate-TN-Pamphlet-Tamil.pdf` into this
folder — copy them up into `docs/` to replace the published pamphlets.

Keep the tier-comparison table (page 3 of each) in sync with
`../subscription-tiers.md`, which is the source of truth for what's actually
shipped per tier.
