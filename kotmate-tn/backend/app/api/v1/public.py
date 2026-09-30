from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.marketing import PublicBlogPostDetail, PublicBlogPostSummary, PublicDemoVideo
from app.services.marketing_service import (
    get_published_blog_post_or_404,
    list_published_blog_posts,
    list_published_demo_videos,
)

# No auth, no tenant scope — these are the only endpoints the landing site's static
# JS calls cross-origin (kotmatetn.in -> app.kotmatetn.in, allowed via CORS_ORIGINS).
# Every function behind these routes filters to is_published itself, so a draft post or
# video can never be reached from here regardless of what the client asks for.
router = APIRouter(prefix="/public", tags=["public"])


@router.get("/blog-posts", response_model=list[PublicBlogPostSummary])
async def list_public_blog_posts(db: AsyncSession = Depends(get_db)) -> list[PublicBlogPostSummary]:
    return await list_published_blog_posts(db)


@router.get("/blog-posts/{slug}", response_model=PublicBlogPostDetail)
async def get_public_blog_post(slug: str, db: AsyncSession = Depends(get_db)) -> PublicBlogPostDetail:
    return await get_published_blog_post_or_404(db, slug)


@router.get("/demo-videos", response_model=list[PublicDemoVideo])
async def list_public_demo_videos(db: AsyncSession = Depends(get_db)) -> list[PublicDemoVideo]:
    return await list_published_demo_videos(db)
