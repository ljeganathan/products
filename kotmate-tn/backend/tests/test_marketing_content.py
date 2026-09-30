"""Phase 29 — landing-site "Demos & Blog" content: product_owner-only admin CRUD,
public read-only endpoints, and the published/draft boundary between them.
"""

import io
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _create_post(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {"title": "How KOTMate Speeds Up Billing", "body_markdown": "# Hello\n\nSome **text**."}
    payload.update(overrides)
    resp = await client.post("/api/v1/platform/content/blog-posts", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_video(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {"title": "2-minute POS demo", "video_url": "https://www.youtube.com/watch?v=abc123"}
    payload.update(overrides)
    resp = await client.post("/api/v1/platform/content/demo-videos", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_non_owner_cannot_reach_admin_content_routes(client: AsyncClient, tenant_admin: dict):
    resp = await client.get("/api/v1/platform/content/blog-posts", headers=tenant_admin["headers"])
    assert resp.status_code == 403

    # FastAPI's HTTPBearer returns 403 (not 401) for a request with no Authorization
    # header at all — same convention every other route in this app already follows.
    anon = await client.get("/api/v1/platform/content/blog-posts")
    assert anon.status_code == 403


async def test_blog_post_slug_derived_and_unique(client: AsyncClient, owner_headers: dict):
    title = f"Great Filter Coffee, Faster Billing {uuid.uuid4().hex[:8]}!"
    base_slug = title.lower().rstrip("!").replace(", ", "-").replace(" ", "-")

    first = await _create_post(client, owner_headers, title=title)
    assert first["slug"] == base_slug

    second = await _create_post(client, owner_headers, title=title)
    assert second["slug"] == f"{base_slug}-2"


async def test_draft_post_invisible_to_public_but_visible_to_owner(client: AsyncClient, owner_headers: dict):
    draft = await _create_post(client, owner_headers, title="Unfinished Draft Post", is_published=False)
    assert draft["published_at"] is None

    public_list = await client.get("/api/v1/public/blog-posts")
    assert draft["slug"] not in [p["slug"] for p in public_list.json()]

    public_detail = await client.get(f"/api/v1/public/blog-posts/{draft['slug']}")
    assert public_detail.status_code == 404

    owner_list = await client.get("/api/v1/platform/content/blog-posts", headers=owner_headers)
    assert draft["id"] in [p["id"] for p in owner_list.json()]


async def test_publishing_a_post_sets_published_at_and_exposes_it_publicly(
    client: AsyncClient, owner_headers: dict
):
    post = await _create_post(client, owner_headers, title="Now Live Post", is_published=False)
    assert post["published_at"] is None

    published = await client.patch(
        f"/api/v1/platform/content/blog-posts/{post['id']}",
        json={"is_published": True},
        headers=owner_headers,
    )
    assert published.status_code == 200
    assert published.json()["published_at"] is not None

    public_detail = await client.get(f"/api/v1/public/blog-posts/{post['slug']}")
    assert public_detail.status_code == 200, public_detail.text
    body = public_detail.json()
    assert body["title"] == "Now Live Post"
    assert body["body_markdown"].startswith("# Hello")
    # Admin-only fields never leak through the public shape.
    assert "is_published" not in body


async def test_deleting_a_post(client: AsyncClient, owner_headers: dict):
    post = await _create_post(client, owner_headers)
    deleted = await client.delete(f"/api/v1/platform/content/blog-posts/{post['id']}", headers=owner_headers)
    assert deleted.status_code == 204
    remaining = await client.get("/api/v1/platform/content/blog-posts", headers=owner_headers)
    assert post["id"] not in [p["id"] for p in remaining.json()]


async def test_demo_videos_ordered_and_draft_hidden_from_public(client: AsyncClient, owner_headers: dict):
    await _create_video(client, owner_headers, title="Second", display_order=2, is_published=True)
    await _create_video(client, owner_headers, title="First", display_order=1, is_published=True)
    await _create_video(client, owner_headers, title="Hidden draft", display_order=0, is_published=False)

    public = await client.get("/api/v1/public/demo-videos")
    titles = [v["title"] for v in public.json()]
    assert titles.index("First") < titles.index("Second")
    assert "Hidden draft" not in titles


async def test_update_and_delete_demo_video(client: AsyncClient, owner_headers: dict):
    video = await _create_video(client, owner_headers)
    updated = await client.patch(
        f"/api/v1/platform/content/demo-videos/{video['id']}",
        json={"title": "Renamed demo"},
        headers=owner_headers,
    )
    assert updated.status_code == 200 and updated.json()["title"] == "Renamed demo"

    deleted = await client.delete(
        f"/api/v1/platform/content/demo-videos/{video['id']}", headers=owner_headers
    )
    assert deleted.status_code == 204


async def test_cover_image_upload_rejects_bad_type_and_accepts_good_one(
    client: AsyncClient, owner_headers: dict
):
    bad = await client.post(
        "/api/v1/platform/content/blog-posts/cover-image",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=owner_headers,
    )
    assert bad.status_code == 400

    good = await client.post(
        "/api/v1/platform/content/blog-posts/cover-image",
        files={"file": ("cover.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 100), "image/png")},
        headers=owner_headers,
    )
    assert good.status_code == 200, good.text
    url = good.json()["url"]
    assert "/uploads/_platform/blog-covers/" in url

    # The uploaded URL actually has to be saved onto the post, not just returned.
    post = await _create_post(client, owner_headers, cover_image_url=url)
    assert post["cover_image_url"] == url
