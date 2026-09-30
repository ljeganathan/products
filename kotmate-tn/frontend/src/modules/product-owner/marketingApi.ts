import { api } from "@/lib/api";

// Phase 29 — the landing site's "Demos & Blog" content, managed from the (private,
// login-only) Product Owner Console. Never linked from anywhere public.

export interface BlogPostAdmin {
  id: string;
  title: string;
  slug: string;
  cover_image_url: string | null;
  excerpt: string | null;
  body_markdown: string;
  is_published: boolean;
  published_at: string | null;
}

export interface BlogPostInput {
  title?: string;
  slug?: string;
  cover_image_url?: string | null;
  excerpt?: string | null;
  body_markdown?: string;
  is_published?: boolean;
}

export interface DemoVideo {
  id: string;
  title: string;
  video_url: string;
  thumbnail_url: string | null;
  description: string | null;
  display_order: number;
  is_published: boolean;
}

export interface DemoVideoInput {
  title?: string;
  video_url?: string;
  thumbnail_url?: string | null;
  description?: string | null;
  display_order?: number;
  is_published?: boolean;
}

export async function listBlogPosts(): Promise<BlogPostAdmin[]> {
  return (await api.get<BlogPostAdmin[]>("/api/v1/platform/content/blog-posts")).data;
}

export async function createBlogPost(payload: BlogPostInput): Promise<BlogPostAdmin> {
  return (await api.post<BlogPostAdmin>("/api/v1/platform/content/blog-posts", payload)).data;
}

export async function updateBlogPost(id: string, payload: BlogPostInput): Promise<BlogPostAdmin> {
  return (await api.patch<BlogPostAdmin>(`/api/v1/platform/content/blog-posts/${id}`, payload)).data;
}

export async function deleteBlogPost(id: string): Promise<void> {
  await api.delete(`/api/v1/platform/content/blog-posts/${id}`);
}

export async function uploadBlogCoverImage(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<{ url: string }>("/api/v1/platform/content/blog-posts/cover-image", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data.url;
}

export async function listDemoVideos(): Promise<DemoVideo[]> {
  return (await api.get<DemoVideo[]>("/api/v1/platform/content/demo-videos")).data;
}

export async function createDemoVideo(payload: DemoVideoInput): Promise<DemoVideo> {
  return (await api.post<DemoVideo>("/api/v1/platform/content/demo-videos", payload)).data;
}

export async function updateDemoVideo(id: string, payload: DemoVideoInput): Promise<DemoVideo> {
  return (await api.patch<DemoVideo>(`/api/v1/platform/content/demo-videos/${id}`, payload)).data;
}

export async function deleteDemoVideo(id: string): Promise<void> {
  await api.delete(`/api/v1/platform/content/demo-videos/${id}`);
}
