const ALLOWED_ORIGINS = ["https://nameofmin-net.github.io"];

function corsHeaders(request) {
  const origin = request.headers.get("Origin") || "";
  const allowOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
  };
}

function json(request, data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(request) },
  });
}

function isAdmin(request, env) {
  const auth = request.headers.get("Authorization") || "";
  return auth === `Bearer ${env.ADMIN_TOKEN}`;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(request) });
    }

    // GET /api/comments?page=<id> - public, only non-hidden
    if (path === "/api/comments" && request.method === "GET") {
      const page = url.searchParams.get("page") || "";
      if (!page || page.length > 200) return json(request, { error: "invalid page" }, 400);
      const { results } = await env.DB.prepare(
        "SELECT id, name, body, created_at FROM comments WHERE page_id = ? AND hidden = 0 ORDER BY created_at ASC LIMIT 500"
      ).bind(page).all();
      return json(request, { comments: results });
    }

    // POST /api/comments - public, create a comment
    if (path === "/api/comments" && request.method === "POST") {
      let data;
      try {
        data = await request.json();
      } catch {
        return json(request, { error: "invalid json" }, 400);
      }
      const page = String(data.page || "").trim();
      const name = String(data.name || "").trim();
      const body = String(data.body || "").trim();

      if (!page || page.length > 200) return json(request, { error: "invalid page" }, 400);
      if (!name || name.length > 40) return json(request, { error: "invalid name" }, 400);
      if (!body || body.length > 2000) return json(request, { error: "invalid body" }, 400);

      await env.DB.prepare(
        "INSERT INTO comments (page_id, name, body) VALUES (?, ?, ?)"
      ).bind(page, name, body).run();

      return json(request, { ok: true });
    }

    // GET /api/admin/comments?page=<id or omit for all> - admin only, includes hidden
    if (path === "/api/admin/comments" && request.method === "GET") {
      if (!isAdmin(request, env)) return json(request, { error: "unauthorized" }, 401);
      const page = url.searchParams.get("page");
      const stmt = page
        ? env.DB.prepare(
            "SELECT id, page_id, name, body, created_at, hidden FROM comments WHERE page_id = ? ORDER BY created_at DESC LIMIT 1000"
          ).bind(page)
        : env.DB.prepare(
            "SELECT id, page_id, name, body, created_at, hidden FROM comments ORDER BY created_at DESC LIMIT 1000"
          );
      const { results } = await stmt.all();
      return json(request, { comments: results });
    }

    // POST /api/admin/hide {id, hidden} - admin only
    if (path === "/api/admin/hide" && request.method === "POST") {
      if (!isAdmin(request, env)) return json(request, { error: "unauthorized" }, 401);
      let data;
      try {
        data = await request.json();
      } catch {
        return json(request, { error: "invalid json" }, 400);
      }
      const id = Number(data.id);
      const hidden = data.hidden ? 1 : 0;
      if (!id) return json(request, { error: "invalid id" }, 400);
      await env.DB.prepare("UPDATE comments SET hidden = ? WHERE id = ?").bind(hidden, id).run();
      return json(request, { ok: true });
    }

    // DELETE /api/admin/comments/:id - admin only
    if (path.startsWith("/api/admin/comments/") && request.method === "DELETE") {
      if (!isAdmin(request, env)) return json(request, { error: "unauthorized" }, 401);
      const id = Number(path.split("/").pop());
      if (!id) return json(request, { error: "invalid id" }, 400);
      await env.DB.prepare("DELETE FROM comments WHERE id = ?").bind(id).run();
      return json(request, { ok: true });
    }

    return json(request, { error: "not found" }, 404);
  },
};
