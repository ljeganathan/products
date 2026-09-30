import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.marketing import (
    BlogPostAdminResponse,
    BlogPostCreateRequest,
    BlogPostUpdateRequest,
    DemoVideoCreateRequest,
    DemoVideoResponse,
    DemoVideoUpdateRequest,
    UploadedImageResponse,
)
from app.services.marketing_service import (
    create_blog_post,
    create_demo_video,
    delete_blog_post,
    delete_demo_video,
    get_blog_post_or_404,
    get_demo_video_or_404,
    list_blog_posts_admin,
    list_demo_videos_admin,
    update_blog_post,
    update_demo_video,
    upload_blog_cover_image,
)

# Mounted under /platform (app/api/v1/platform/__init__.py), which already gates every
# route here on product_owner — the landing site's own admin screen for its "Demos &
# Blog" page (Phase 29). Never linked from anywhere public; that page lives inside the
# same private Product Owner Console every other platform screen does.
router = APIRouter(prefix="/content", tags=["platform-content"])


@router.get("/blog-posts", response_model=list[BlogPostAdminResponse])
async def list_blog_posts(db: AsyncSession = Depends(get_db)) -> list[BlogPostAdminResponse]:
    return await list_blog_posts_admin(db)


@router.post("/blog-posts", response_model=BlogPostAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_blog_post_route(
    payload: BlogPostCreateRequest, db: AsyncSession = Depends(get_db)
) -> BlogPostAdminResponse:
    post = await create_blog_post(db, payload)
    await db.commit()
    return post


@router.patch("/blog-posts/{post_id}", response_model=BlogPostAdminResponse)
async def update_blog_post_route(
    post_id: uuid.UUID, payload: BlogPostUpdateRequest, db: AsyncSession = Depends(get_db)
) -> BlogPostAdminResponse:
    post = await get_blog_post_or_404(db, post_id)
    post = await update_blog_post(db, post, payload)
    await db.commit()
    return post


@router.delete("/blog-posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blog_post_route(post_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    post = await get_blog_post_or_404(db, post_id)
    await delete_blog_post(db, post)
    await db.commit()


@router.post("/blog-posts/cover-image", response_model=UploadedImageResponse)
async def upload_cover_image_route(file: UploadFile = File(...)) -> UploadedImageResponse:
    url = await upload_blog_cover_image(file)
    return UploadedImageResponse(url=url)


@router.get("/demo-videos", response_model=list[DemoVideoResponse])
async def list_demo_videos(db: AsyncSession = Depends(get_db)) -> list[DemoVideoResponse]:
    return await list_demo_videos_admin(db)


@router.post("/demo-videos", response_model=DemoVideoResponse, status_code=status.HTTP_201_CREATED)
async def create_demo_video_route(
    payload: DemoVideoCreateRequest, db: AsyncSession = Depends(get_db)
) -> DemoVideoResponse:
    video = await create_demo_video(db, payload)
    await db.commit()
    return video


@router.patch("/demo-videos/{video_id}", response_model=DemoVideoResponse)
async def update_demo_video_route(
    video_id: uuid.UUID, payload: DemoVideoUpdateRequest, db: AsyncSession = Depends(get_db)
) -> DemoVideoResponse:
    video = await get_demo_video_or_404(db, video_id)
    video = await update_demo_video(db, video, payload)
    await db.commit()
    return video


@router.delete("/demo-videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_demo_video_route(video_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    video = await get_demo_video_or_404(db, video_id)
    await delete_demo_video(db, video)
    await db.commit()
