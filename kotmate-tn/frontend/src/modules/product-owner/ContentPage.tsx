import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";

import {
  type BlogPostAdmin,
  type BlogPostInput,
  type DemoVideo,
  type DemoVideoInput,
  createBlogPost,
  createDemoVideo,
  deleteBlogPost,
  deleteDemoVideo,
  listBlogPosts,
  listDemoVideos,
  updateBlogPost,
  updateDemoVideo,
  uploadBlogCoverImage,
} from "@/modules/product-owner/marketingApi";

// The landing site's "Demos & Blog" page content — managed here, inside the private
// Product Owner Console, and never linked from anywhere a customer or tenant can reach.
// The public page itself lives on kotmatetn.in and only ever sees published rows.

const inputClass = "min-h-9 w-full rounded-md border border-border bg-background px-2.5 text-sm";
const labelClass = "text-xs font-medium text-foreground/70";

function errorText(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && typeof err.response?.data?.detail === "string") return err.response.data.detail;
  return fallback;
}

export function ContentPage() {
  const [tab, setTab] = useState<"posts" | "videos">("posts");

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <div className="flex gap-2">
        {(["posts", "videos"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${
              tab === t ? "border-accent bg-accent/10 text-accent" : "border-border text-foreground/70"
            }`}
          >
            {t === "posts" ? "Blog Posts" : "Demo Videos"}
          </button>
        ))}
      </div>
      {tab === "posts" ? <BlogPostsPanel /> : <DemoVideosPanel />}
    </div>
  );
}

// --- Blog posts ----------------------------------------------------------------------

function BlogPostsPanel() {
  const queryClient = useQueryClient();
  const { data: posts = [], isLoading } = useQuery({ queryKey: ["marketing-blog-posts"], queryFn: listBlogPosts });
  const [editingId, setEditingId] = useState<string | "new" | null>(null);

  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["marketing-blog-posts"] });
  const del = useMutation({ mutationFn: deleteBlogPost, onSuccess: invalidate });

  const editing = editingId === "new" ? null : (posts.find((p) => p.id === editingId) ?? null);

  if (editingId !== null) {
    return (
      <BlogPostEditor
        post={editing}
        onDone={() => {
          setEditingId(null);
          invalidate();
        }}
        onCancel={() => setEditingId(null)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        onClick={() => setEditingId("new")}
        className="self-start rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-accent-foreground"
      >
        + New post
      </button>
      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {!isLoading && posts.length === 0 && <p className="text-sm text-foreground/60">No posts yet.</p>}
      <div className="flex flex-col gap-2">
        {posts.map((post) => (
          <div key={post.id} className="flex items-center gap-3 rounded-lg border border-border p-3">
            {post.cover_image_url && (
              <img src={post.cover_image_url} alt="" className="h-12 w-16 flex-none rounded object-cover" />
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{post.title}</p>
              <p className="truncate text-xs text-foreground/60">/{post.slug}</p>
            </div>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                post.is_published ? "bg-veg/15 text-veg" : "bg-surface-3 text-foreground/60"
              }`}
            >
              {post.is_published ? "Published" : "Draft"}
            </span>
            <button
              type="button"
              onClick={() => setEditingId(post.id)}
              className="rounded-md border border-border px-2.5 py-1 text-xs font-semibold hover:bg-accent/10"
            >
              Edit
            </button>
            <button
              type="button"
              onClick={() => {
                if (confirm(`Delete "${post.title}"? This can't be undone.`)) del.mutate(post.id);
              }}
              className="rounded-md border border-border px-2.5 py-1 text-xs font-semibold text-chili hover:bg-chili-soft"
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function BlogPostEditor({
  post,
  onDone,
  onCancel,
}: {
  post: BlogPostAdmin | null;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<BlogPostInput>({
    title: post?.title ?? "",
    slug: post?.slug ?? "",
    cover_image_url: post?.cover_image_url ?? null,
    excerpt: post?.excerpt ?? "",
    body_markdown: post?.body_markdown ?? "",
    is_published: post?.is_published ?? false,
  });
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => (post ? updateBlogPost(post.id, form) : createBlogPost(form)),
    onSuccess: onDone,
    onError: (err) => setError(errorText(err, "Couldn't save — please try again.")),
  });

  async function handleCoverChange(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const url = await uploadBlogCoverImage(file);
      setForm((f) => ({ ...f, cover_image_url: url }));
    } catch (err) {
      setError(errorText(err, "Couldn't upload that image."));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border p-4">
      <h2 className="text-sm font-bold uppercase tracking-wide">{post ? "Edit Post" : "New Post"}</h2>

      <label className={labelClass}>
        Title
        <input
          className={`${inputClass} mt-1`}
          value={form.title}
          onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
        />
      </label>

      <label className={labelClass}>
        URL slug {!post && <span className="text-foreground/50">(leave blank to generate from the title)</span>}
        <input
          className={`${inputClass} mt-1`}
          value={form.slug ?? ""}
          placeholder="auto-generated-from-title"
          onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
        />
      </label>

      <label className={labelClass}>
        Excerpt <span className="text-foreground/50">(shown on the post list, optional)</span>
        <input
          className={`${inputClass} mt-1`}
          maxLength={300}
          value={form.excerpt ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, excerpt: e.target.value }))}
        />
      </label>

      <label className={labelClass}>
        Cover image
        <div className="mt-1 flex items-center gap-2">
          {form.cover_image_url && (
            <img src={form.cover_image_url} alt="" className="h-12 w-16 rounded object-cover" />
          )}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => void handleCoverChange(e.target.files?.[0])}
            className="text-xs"
          />
          {uploading && <span className="text-xs text-foreground/60">Uploading…</span>}
        </div>
      </label>

      <label className={labelClass}>
        Body <span className="text-foreground/50">(Markdown — headings, **bold**, *italic*, links, lists)</span>
        <textarea
          className={`${inputClass} mt-1 min-h-56 py-2 font-mono`}
          value={form.body_markdown}
          onChange={(e) => setForm((f) => ({ ...f, body_markdown: e.target.value }))}
        />
      </label>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.is_published}
          onChange={(e) => setForm((f) => ({ ...f, is_published: e.target.checked }))}
        />
        Published (visible on the public site)
      </label>

      {error && <p className="text-xs font-semibold text-chili">{error}</p>}

      <div className="flex gap-2">
        <button
          type="button"
          disabled={save.isPending || uploading || !form.title}
          onClick={() => save.mutate()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-50"
        >
          {save.isPending ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-md border border-border px-4 py-2 text-sm">
          Cancel
        </button>
      </div>
    </div>
  );
}

// --- Demo videos -----------------------------------------------------------------------

function DemoVideosPanel() {
  const queryClient = useQueryClient();
  const { data: videos = [], isLoading } = useQuery({ queryKey: ["marketing-demo-videos"], queryFn: listDemoVideos });
  const [editingId, setEditingId] = useState<string | "new" | null>(null);
  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["marketing-demo-videos"] });
  const del = useMutation({ mutationFn: deleteDemoVideo, onSuccess: invalidate });

  const editing = editingId === "new" ? null : (videos.find((v) => v.id === editingId) ?? null);

  if (editingId !== null) {
    return (
      <DemoVideoEditor
        video={editing}
        onDone={() => {
          setEditingId(null);
          invalidate();
        }}
        onCancel={() => setEditingId(null)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        onClick={() => setEditingId("new")}
        className="self-start rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-accent-foreground"
      >
        + New video
      </button>
      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {!isLoading && videos.length === 0 && <p className="text-sm text-foreground/60">No videos yet.</p>}
      <div className="flex flex-col gap-2">
        {videos.map((video) => (
          <div key={video.id} className="flex items-center gap-3 rounded-lg border border-border p-3">
            <span className="w-6 flex-none text-center text-xs font-bold text-foreground/50">
              {video.display_order}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{video.title}</p>
              <p className="truncate text-xs text-foreground/60">{video.video_url}</p>
            </div>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                video.is_published ? "bg-veg/15 text-veg" : "bg-surface-3 text-foreground/60"
              }`}
            >
              {video.is_published ? "Published" : "Draft"}
            </span>
            <button
              type="button"
              onClick={() => setEditingId(video.id)}
              className="rounded-md border border-border px-2.5 py-1 text-xs font-semibold hover:bg-accent/10"
            >
              Edit
            </button>
            <button
              type="button"
              onClick={() => {
                if (confirm(`Delete "${video.title}"? This can't be undone.`)) del.mutate(video.id);
              }}
              className="rounded-md border border-border px-2.5 py-1 text-xs font-semibold text-chili hover:bg-chili-soft"
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function DemoVideoEditor({
  video,
  onDone,
  onCancel,
}: {
  video: DemoVideo | null;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<DemoVideoInput>({
    title: video?.title ?? "",
    video_url: video?.video_url ?? "",
    description: video?.description ?? "",
    display_order: video?.display_order ?? 0,
    is_published: video?.is_published ?? false,
  });
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => (video ? updateDemoVideo(video.id, form) : createDemoVideo(form)),
    onSuccess: onDone,
    onError: (err) => setError(errorText(err, "Couldn't save — please try again.")),
  });

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border p-4">
      <h2 className="text-sm font-bold uppercase tracking-wide">{video ? "Edit Video" : "New Video"}</h2>

      <label className={labelClass}>
        Title
        <input
          className={`${inputClass} mt-1`}
          value={form.title}
          onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
        />
      </label>

      <label className={labelClass}>
        YouTube or Vimeo link
        <input
          className={`${inputClass} mt-1`}
          placeholder="https://www.youtube.com/watch?v=..."
          value={form.video_url}
          onChange={(e) => setForm((f) => ({ ...f, video_url: e.target.value }))}
        />
      </label>

      <label className={labelClass}>
        Description <span className="text-foreground/50">(optional)</span>
        <input
          className={`${inputClass} mt-1`}
          maxLength={300}
          value={form.description ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
        />
      </label>

      <label className={labelClass}>
        Display order <span className="text-foreground/50">(lower shows first)</span>
        <input
          type="number"
          className={`${inputClass} mt-1 max-w-24`}
          value={form.display_order}
          onChange={(e) => setForm((f) => ({ ...f, display_order: Number(e.target.value) }))}
        />
      </label>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.is_published}
          onChange={(e) => setForm((f) => ({ ...f, is_published: e.target.checked }))}
        />
        Published (visible on the public site)
      </label>

      {error && <p className="text-xs font-semibold text-chili">{error}</p>}

      <div className="flex gap-2">
        <button
          type="button"
          disabled={save.isPending || !form.title || !form.video_url}
          onClick={() => save.mutate()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-50"
        >
          {save.isPending ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-md border border-border px-4 py-2 text-sm">
          Cancel
        </button>
      </div>
    </div>
  );
}
