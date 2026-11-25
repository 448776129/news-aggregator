const OWNER = "448776129";
const REPO = "news-aggregator";
const WORKFLOW = "daily-news.yml";
const REF = "main";

async function dispatch(env) {
  const res = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `token ${env.DISPATCH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "news-cron-worker",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: REF }),
    }
  );
  const text = await res.text();
  return { status: res.status, body: text.slice(0, 300), at: new Date().toISOString() };
}

export default {
  async scheduled(event, env, ctx) {
    const r = await dispatch(env);
    console.log(`cron=${event.cron} dispatch=${r.status} ${r.body}`);
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/run") {
      const r = await dispatch(env);
      return new Response(JSON.stringify(r, null, 2), {
        headers: { "content-type": "application/json; charset=utf-8" },
      });
    }
    return new Response(
      JSON.stringify({
        service: "news-cron-trigger",
        target: `${OWNER}/${REPO}:${WORKFLOW}`,
        usage: "GET /run 立即触发一次",
      }),
      { headers: { "content-type": "application/json; charset=utf-8" } }
    );
  },
};
