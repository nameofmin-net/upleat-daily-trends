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

// YYYY-MM-DD in KST, offset days back from today (0 = today)
function kstDateStr(offsetDays) {
  const now = new Date(Date.now() - offsetDays * 86400000 + 9 * 3600000);
  return now.toISOString().slice(0, 10);
}

async function fetchDayData(dateStr) {
  const url = `https://raw.githubusercontent.com/nameofmin-net/upleat-daily-trends/main/data/${dateStr}.json`;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// builds a compact Korean text block of recent articles for the model's context
async function buildTrendContext() {
  const days = [0, 1, 2, 3, 4];
  const lines = [];
  for (const offset of days) {
    const dateStr = kstDateStr(offset);
    const data = await fetchDayData(dateStr);
    if (!data) continue;
    for (const region of [data.intl, data.domestic]) {
      if (!region) continue;
      for (const cat of region.categories || []) {
        for (const item of cat.items || []) {
          const insight = String(item.insight || "").replace(/<[^>]+>/g, "").slice(0, 200);
          lines.push(`- [${dateStr} / ${region.region} / ${cat.label}] ${item.title}: ${insight} (출처: ${item.source || "?"})`);
        }
      }
    }
  }
  return lines.join("\n");
}

const ASK_DAILY_LIMIT = 20;

async function checkAndIncrementAskUsage(env, ip) {
  const day = kstDateStr(0);
  const row = await env.DB.prepare("SELECT count FROM ask_usage WHERE ip = ? AND day = ?").bind(ip, day).first();
  const current = row ? row.count : 0;
  if (current >= ASK_DAILY_LIMIT) return false;
  await env.DB.prepare(
    "INSERT INTO ask_usage (ip, day, count) VALUES (?, ?, 1) ON CONFLICT(ip, day) DO UPDATE SET count = count + 1"
  ).bind(ip, day).run();
  return true;
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

    // GET /api/comments/counts - public, { counts: { pageId: {n, latest}, ... } } for every page with >=1 visible comment
    // (latest = created_at of the newest comment on that page, used client-side to flag today's comments)
    if (path === "/api/comments/counts" && request.method === "GET") {
      const { results } = await env.DB.prepare(
        "SELECT page_id, COUNT(*) as n, MAX(created_at) as latest FROM comments WHERE hidden = 0 GROUP BY page_id"
      ).all();
      const counts = {};
      for (const row of results) counts[row.page_id] = { n: row.n, latest: row.latest };
      return json(request, { counts });
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

    // POST /api/ask {question} - public, AI Q&A over recent trend data (Workers AI, rate-limited per IP)
    if (path === "/api/ask" && request.method === "POST") {
      let data;
      try {
        data = await request.json();
      } catch {
        return json(request, { error: "invalid json" }, 400);
      }
      const question = String(data.question || "").trim();
      if (!question || question.length > 300) return json(request, { error: "invalid question" }, 400);

      const ip = request.headers.get("CF-Connecting-IP") || "unknown";
      const allowed = await checkAndIncrementAskUsage(env, ip);
      if (!allowed) return json(request, { error: "daily limit reached" }, 429);

      const context = await buildTrendContext();
      const systemPrompt = `당신은 "Nexty"라는 이름의, UPLEAT 데일리 트렌드 사이트의 AI 도우미입니다. 아래는 최근 며칠간 사이트에 올라온 AI/UX/디자인/테크비즈 트렌드 기사 목록입니다. 이 목록을 참고해서 방문자의 질문에 한국어로, 간결하고 정확하게 답하세요. 목록에 없는 내용은 모른다고 솔직히 답하고 절대 지어내지 마세요. 가능하면 어떤 기사를 참고했는지 기사 제목을 언급하세요. 스스로를 지칭할 일이 있으면 "저" 또는 "Nexty"라고 하세요.\n\n[최근 트렌드 기사 목록]\n${context || "(최근 데이터 없음)"}`;

      try {
        const aiResponse = await env.AI.run("@cf/qwen/qwen3-30b-a3b-fp8", {
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: question },
          ],
          max_tokens: 900,
        });
        const answer = aiResponse.response || "답변을 생성하지 못했습니다.";
        return json(request, { answer });
      } catch (e) {
        return json(request, { error: "ai request failed" }, 500);
      }
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
