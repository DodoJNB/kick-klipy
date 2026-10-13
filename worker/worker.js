// Cloudflare Worker: proxy do klipów Kicka.
// Wywołanie: https://TWOJ-WORKER.workers.dev/?url=<zakodowany adres API Kicka>
// Przepuszcza tylko adresy klipów kick.com, żeby nie był otwartym proxy.

const ALLOWED = /^https:\/\/kick\.com\/api\/v2\/channels\/[a-z0-9_\-]{2,40}\/clips(\?.*)?$/i;

export default {
  async fetch(request) {
    const target = new URL(request.url).searchParams.get("url") || "";

    if (!ALLOWED.test(target)) {
      return new Response(JSON.stringify({ error: "Niedozwolony adres." }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    const res = await fetch(target, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        Accept: "application/json, text/plain, */*",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        Referer: "https://kick.com/",
      },
    });

    return new Response(res.body, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
    });
  },
};
