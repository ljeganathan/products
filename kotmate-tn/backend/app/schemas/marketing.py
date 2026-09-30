import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# --- Admin (product_owner) shapes — full detail, draft posts included -------------


class BlogPostCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    # Blank -> derived from the title (see marketing_service.slugify). Editable so an
    # owner can fix a URL after the title changes without breaking a link already shared.
    slug: str | None = Field(default=None, max_length=200)
    cover_image_url: str | None = None
    excerpt: str | None = Field(default=None, max_length=300)
    body_markdown: str = ""
    is_published: bool = False


class BlogPostUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=200)
    cover_image_url: str | None = None
    excerpt: str | None = Field(default=None, max_length=300)
    body_markdown: str | None = None
    is_published: bool | None = None


class BlogPostAdminResponse(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    cover_image_url: str | None
    excerpt: str | None
    body_markdown: str
    is_published: bool
    published_at: datetime | None


class DemoVideoCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    video_url: str = Field(min_length=1)
    thumbnail_url: str | None = None
    description: str | None = Field(default=None, max_length=300)
    display_order: int = 0
    is_published: bool = False


class DemoVideoUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    video_url: str | None = Field(default=None, min_length=1)
    thumbnail_url: str | None = None
    description: str | None = Field(default=None, max_length=300)
    display_order: int | None = None
    is_published: bool | None = None


class DemoVideoResponse(BaseModel):
    id: uuid.UUID
    title: str
    video_url: str
    thumbnail_url: str | None
    description: str | None
    display_order: int
    is_published: bool


class UploadedImageResponse(BaseModel):
    url: str


# --- Public (landing site) shapes — published rows only, no admin-only fields -----


class PublicBlogPostSummary(BaseModel):
    slug: str
    title: str
    excerpt: str | None
    cover_image_url: str | None
    published_at: datetime | None


class PublicBlogPostDetail(PublicBlogPostSummary):
    body_markdown: str


class PublicDemoVideo(BaseModel):
    title: str
    video_url: str
    thumbnail_url: str | None
    description: str | None
