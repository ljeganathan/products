// Shared logic for resources.html (listing) and blog-post.html (single post).
// Talks only to the two public, read-only endpoints — no login, no write calls.
// A tiny hand-rolled Markdown renderer instead of pulling in a third-party library:
// post bodies are only ever written by the site owner in the Product Owner Console,
// so full CommonMark support isn't needed — headings, bold/italic, links, paragraphs
// and lists cover everything the admin editor's own hint text promises.
(function () {
  function apiBase() {
    return window.KOTMATE_API_BASE || "https://app.kotmatetn.in";
  }

  async function fetchJson(path) {
    const res = await fetch(`${apiBase()}${path}`);
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return res.json();
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }

  // Inline spans: bold, italic, links — applied to an already-escaped string.
  function renderInline(text) {
    return text
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/\[(.+?)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }

  function renderMarkdown(markdown) {
    const lines = (markdown || "").replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let listOpen = false;

    function closeList() {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
    }

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) {
        closeList();
        continue;
      }
      const heading = /^(#{1,3})\s+(.*)$/.exec(line);
      if (heading) {
        closeList();
        const level = heading[1].length;
        html.push(`<h${level}>${renderInline(escapeHtml(heading[2]))}</h${level}>`);
        continue;
      }
      const item = /^[-*]\s+(.*)$/.exec(line);
      if (item) {
        if (!listOpen) {
          html.push("<ul>");
          listOpen = true;
        }
        html.push(`<li>${renderInline(escapeHtml(item[1]))}</li>`);
        continue;
      }
      closeList();
      html.push(`<p>${renderInline(escapeHtml(line))}</p>`);
    }
    closeList();
    return html.join("\n");
  }

  function formatDate(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  }

  // youtube.com/watch?v=, youtu.be/, and vimeo.com/ links -> an embeddable player URL.
  // Anything else (an already-an-embed link, or an unrecognized host) passes through
  // unchanged so a valid embed URL pasted directly by the owner still works.
  function toEmbedUrl(url) {
    try {
      const u = new URL(url);
      if (u.hostname.includes("youtube.com") && u.searchParams.get("v")) {
        return `https://www.youtube.com/embed/${u.searchParams.get("v")}`;
      }
      if (u.hostname === "youtu.be") {
        return `https://www.youtube.com/embed${u.pathname}`;
      }
      if (u.hostname.includes("vimeo.com")) {
        const id = u.pathname.split("/").filter(Boolean).pop();
        return `https://player.vimeo.com/video/${id}`;
      }
    } catch {
      /* not a full URL — fall through */
    }
    return url;
  }

  window.KOTMateResources = { fetchJson, renderMarkdown, formatDate, toEmbedUrl, escapeHtml };
})();
