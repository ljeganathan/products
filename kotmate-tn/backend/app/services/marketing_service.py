"""Landing-site "Demos & Blog" content (Phase 29). Writes are product_owner-only
(enforced by the /platform router this is mounted under); the public read functions
here are the only ones the landing site's unauthenticated API calls ever reach, and
they filter to `is_published` themselves so a draft can never leak through.
"""

import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BlogPost, DemoVideo
from app.schemas.marketing import (
    BlogPostCreateRequest,
    BlogPostUpdateRequest,
    DemoVideoCreateRequest,
    DemoVideoUpdateRequest,
)
from app.services.storage import get_storage

_SLUG_INVALID = re.compile(r"[^a-z0-9]+")
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def slugify(title: str) -> str:
    slug = _SLUG_INVALID.sub("-", title.lower()).strip("-")
    return slug or "post"


async def _unique_slug(session: AsyncSession, base: str, *, exclude_id: uuid.UUID | None = None) -> str:
    candidate = base
    suffix = 2
    while True:
        query = select(BlogPost.id).where(BlogPost.slug == candidate)
        if exclude_id is not None:
            query = query.where(BlogPost.id != exclude_id)
        existing = (await session.execute(query)).scalar_one_or_none()
        if existing is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


# --- Blog posts (admin) -------------------------------------------------------------


async def list_blog_posts_admin(session: AsyncSession) -> list[BlogPost]:
    return list(
        (await session.execute(select(BlogPost).order_by(BlogPost.updated_at.desc()))).scalars().all()
    )


async def get_blog_post_or_404(session: AsyncSession, post_id: uuid.UUID) -> BlogPost:
    post = (await session.execute(select(BlogPost).where(BlogPost.id == post_id))).scalar_one_or_none()
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return post


async def create_blog_post(session: AsyncSession, req: BlogPostCreateRequest) -> BlogPost:
    slug = await _unique_slug(session, slugify(req.slug or req.title))
    post = BlogPost(
        title=req.title,
        slug=slug,
        cover_image_url=req.cover_image_url,
        excerpt=req.excerpt,
        body_markdown=req.body_markdown,
        is_published=req.is_published,
        published_at=datetime.now(UTC) if req.is_published else None,
    )
    session.add(post)
    await session.flush()
    return post


async def update_blog_post(session: AsyncSession, post: BlogPost, req: BlogPostUpdateRequest) -> BlogPost:
    data = req.model_dump(exclude_unset=True)
    if "slug" in data:
        data["slug"] = await _unique_slug(session, slugify(data["slug"]), exclude_id=post.id)
    was_published = post.is_published
    for field, value in data.items():
        setattr(post, field, value)
    if post.is_published and not was_published:
        post.published_at = datetime.now(UTC)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "That slug is already in use") from exc
    return post


async def delete_blog_post(session: AsyncSession, post: BlogPost) -> None:
    await session.delete(post)
    await session.flush()


async def upload_blog_cover_image(file: UploadFile) -> str:
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only JPEG, PNG or WEBP images are allowed")
    content = await file.read()
    if len(content) > _MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image must be 5MB or smaller")
    storage = get_storage()
    return await storage.save_platform(
        subfolder="blog-covers", filename=file.filename or "cover.jpg", content=content
    )


# --- Demo videos (admin) -------------------------------------------------------------


async def list_demo_videos_admin(session: AsyncSession) -> list[DemoVideo]:
    return list(
        (
            await session.execute(select(DemoVideo).order_by(DemoVideo.display_order, DemoVideo.created_at))
        )
        .scalars()
        .all()
    )


async def get_demo_video_or_404(session: AsyncSession, video_id: uuid.UUID) -> DemoVideo:
    video = (await session.execute(select(DemoVideo).where(DemoVideo.id == video_id))).scalar_one_or_none()
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")
    return video


async def create_demo_video(session: AsyncSession, req: DemoVideoCreateRequest) -> DemoVideo:
    video = DemoVideo(**req.model_dump())
    session.add(video)
    await session.flush()
    return video


async def update_demo_video(
    session: AsyncSession, video: DemoVideo, req: DemoVideoUpdateRequest
) -> DemoVideo:
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(video, field, value)
    await session.flush()
    return video


async def delete_demo_video(session: AsyncSession, video: DemoVideo) -> None:
    await session.delete(video)
    await session.flush()


# --- Public (landing site) -----------------------------------------------------------


async def list_published_blog_posts(session: AsyncSession) -> list[BlogPost]:
    return list(
        (
            await session.execute(
                select(BlogPost)
                .where(BlogPost.is_published.is_(True))
                .order_by(BlogPost.published_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def get_published_blog_post_or_404(session: AsyncSession, slug: str) -> BlogPost:
    post = (
        await session.execute(
            select(BlogPost).where(BlogPost.slug == slug, BlogPost.is_published.is_(True))
        )
    ).scalar_one_or_none()
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return post


async def list_published_demo_videos(session: AsyncSession) -> list[DemoVideo]:
    return list(
        (
            await session.execute(
                select(DemoVideo)
                .where(DemoVideo.is_published.is_(True))
                .order_by(DemoVideo.display_order, DemoVideo.created_at)
            )
        )
        .scalars()
        .all()
    )

