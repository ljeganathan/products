# Landing site "Demos & Blog" content (Phase 29)

Lets the marketing site (kotmatetn.in) show demo videos and blog posts, managed from a
screen only `product_owner` can reach — never linked from anywhere public.

## Where things live

| Piece | Location |
|---|---|
| Tables | `marketing_blog_posts`, `marketing_demo_videos` (migration `f1a3c8e2b567`) — platform-wide, no `tenant_id`, same precedent as `plans`/`roles` |
| Admin CRUD (product_owner-only) | `backend/app/api/v1/platform/content.py`, mounted under the existing `/platform` router, which already gates every route on `product_owner` |
| Public read API (no login) | `backend/app/api/v1/public.py` — `GET /api/v1/public/blog-posts`, `/blog-posts/{slug}`, `/demo-videos`; every function behind these filters to `is_published` itself |
| Business logic | `backend/app/services/marketing_service.py` |
| Owner admin screen | `frontend/src/modules/product-owner/ContentPage.tsx`, at `/platform/content` — a new tab in the existing Product Owner Console, alongside Tenants/Plans/etc. |
| Public pages | `landing/resources.html` (video + post grid) and `landing/blog-post.html` (single post) — plain static HTML/JS, no build step, matching the rest of `landing/` |

## Why the landing site now calls the app's API

`docs/LANDING_PAGE.md` originally said the landing site "never talks to the KOTMate
API/database" — this feature is the one deliberate exception. Building a fully separate
CMS (its own service, its own database) just to avoid two read-only cross-origin `GET`
calls wasn't worth the ongoing cost of a second system to run and patch. The isolation
that mattered — a bug here can't touch tenant data or billing — is still true: this is a
different table, gated by a different check (product_owner login), from everything else
in the app.

`CORS_ORIGINS` (`.env`) includes `https://kotmatetn.in`/`https://www.kotmatetn.in` for
exactly this. `landing/js/api-config.js` points at the production API by default and
auto-detects `localhost`/`192.168.*` for local testing.

## Content model

- **Blog posts**: title, slug (auto-derived from the title, editable, unique — a
  collision appends `-2`, `-3`, ...), optional cover image, optional excerpt (shown on
  the list), Markdown body, published/draft. `published_at` is set the first time a post
  is published and never recomputed after.
- **Demo videos**: title, a YouTube or Vimeo **link** (not a self-hosted file —
  storage/bandwidth/streaming complexity isn't worth it here), optional thumbnail,
  optional description, a display order, published/draft.

## Markdown rendering

`landing/js/resources.js` has a small hand-rolled renderer (headings, **bold**, *italic*,
links, paragraphs, unordered lists) instead of a third-party library — post bodies are
only ever written by the site owner in the admin screen, so full CommonMark support was
never needed, and this avoids adding a dependency to a page whose whole point is being a
plain, dependency-free static site.

## Images

Blog cover images reuse the existing local-disk upload service
(`app/services/storage.py`), via a new `save_platform()` method alongside the existing
per-tenant `save()` — platform content has no `tenant_id` to key by, so it's stored
under `uploads/_platform/blog-covers/` instead.

## What's NOT in the sitemap

Only `resources.html` is listed in `landing/sitemap.xml`. Individual blog posts are
discovered by search engines through links from that page instead — the site has no
build step to regenerate the sitemap every time a post is published, and a hand-maintained
list of post URLs would inevitably go stale.

## Adding content

1. Log in to the Product Owner Console → **Content** tab.
2. **Blog Posts**: "+ New post" → title, optional cover image, optional excerpt, Markdown
   body, tick "Published" when ready → Save.
3. **Demo Videos**: "+ New video" → title, a YouTube or Vimeo link, optional description,
   a display order (lower shows first), tick "Published" → Save.

Nothing here needs a deploy or a rebuild — it's ordinary data, editable any time.
