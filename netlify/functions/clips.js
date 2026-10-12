// Netlify Function: pośrednik do nieoficjalnego API klipów Kicka.
// Wywołanie: /api/clips?channel=mamm0n&sort=date|view&time=day|week|month|all&cursor=...
//
// Jeśli Kick (Cloudflare) blokuje IP Netlify (403), ustaw w Netlify zmienną
// środowiskową KICK_PROXY_URL na adres własnego proxy (np. Cloudflare Worker),
// który przyjmie ten sam ciąg zapytania "?url=<zakodowany adres>".

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

const json = (statusCode, body, extra = {}) => ({
  statusCode,
  headers: {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "public, max-age=60",
    ...extra,
  },
  body: JSON.stringify(body),
});

exports.handler = async (event) => {
  const q = event.queryStringParameters || {};
  const channel = String(q.channel || "").trim().toLowerCase();
  const sort = q.sort === "view" ? "view" : "date";
  const time = ["day", "week", "month", "all"].includes(q.time) ? q.time : "all";
  const cursor = q.cursor || "";

  if (!/^[a-z0-9_\-]{2,40}$/.test(channel)) {
    return json(400, { error: "Nieprawidłowa nazwa kanału." });
  }

  const params = new URLSearchParams({ sort, time });
  if (cursor) params.set("cursor", cursor);
  const target = `https://kick.com/api/v2/channels/${channel}/clips?${params}`;

  const proxy = process.env.KICK_PROXY_URL;
  const url = proxy ? `${proxy}?url=${encodeURIComponent(target)}` : target;

  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": UA,
        Accept: "application/json, text/plain, */*",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        Referer: `https://kick.com/${channel}/clips`,
      },
    });

    if (res.status === 404) return json(404, { error: "Nie znaleziono kanału." });
    if (res.status === 403 || res.status === 429) {
      return json(502, {
        error:
          "Kick zablokował zapytanie z serwera (Cloudflare). Ustaw KICK_PROXY_URL – patrz README.",
      });
    }
    if (!res.ok) return json(502, { error: `Kick zwrócił błąd ${res.status}.` });

    const data = await res.json();
    const list = data.clips || data.data || [];

    const clips = list.map((c) => {
      const slug = (c.channel && c.channel.slug) || channel;
      return {
        id: c.id,
        title: c.title || "(bez tytułu)",
        thumbnail: c.thumbnail_url || null,
        duration: c.duration || 0,
        views: c.view_count ?? c.views ?? 0,
        createdAt: c.created_at || c.started_at || null,
        category: (c.category && c.category.name) || "",
        creator: (c.creator && (c.creator.username || c.creator.slug)) || "",
        url: `https://kick.com/${slug}/clips/${c.id}`,
      };
    });

    return json(200, {
      channel,
      clips,
      nextCursor: data.nextCursor || null,
    });
  } catch (err) {
    return json(502, { error: "Nie udało się połączyć z Kickiem." });
  }
};
