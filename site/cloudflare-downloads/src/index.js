import { DurableObject } from "cloudflare:workers";

function defaultCounters() {
  return {
    windowsDownloads: 0,
    macDownloads: 0,
    updatedAt: null,
  };
}

function corsHeaders(origin) {
  return {
    "access-control-allow-origin": origin || "*",
    "access-control-allow-methods": "GET, OPTIONS",
    "access-control-allow-headers": "Content-Type",
  };
}

function jsonResponse(data, origin, init = {}) {
  const headers = new Headers(init.headers || {});
  headers.set("content-type", "application/json; charset=utf-8");
  headers.set("cache-control", "no-store");
  for (const [key, value] of Object.entries(corsHeaders(origin))) {
    headers.set(key, value);
  }

  return new Response(JSON.stringify(data, null, 2), {
    ...init,
    headers,
  });
}

function redirectResponse(url, origin) {
  const headers = new Headers(corsHeaders(origin));
  headers.set("location", url);
  headers.set("cache-control", "no-store");

  return new Response(null, {
    status: 302,
    headers,
  });
}

export class DownloadCounter extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.ctx = ctx;
    this.counters = defaultCounters();

    this.ctx.blockConcurrencyWhile(async () => {
      const stored = await this.ctx.storage.get("counters");
      this.counters = {
        ...defaultCounters(),
        ...(stored || {}),
      };
    });
  }

  async fetch(request) {
    const url = new URL(request.url);

    if (url.pathname === "/stats") {
      return new Response(JSON.stringify(this.counters), {
        headers: {
          "content-type": "application/json; charset=utf-8",
          "cache-control": "no-store",
        },
      });
    }

    if (url.pathname.startsWith("/increment/")) {
      const platform = url.pathname.split("/").pop();
      if (platform === "windows") {
        this.counters.windowsDownloads += 1;
      } else if (platform === "mac") {
        this.counters.macDownloads += 1;
      } else {
        return new Response("Unknown platform.", { status: 400 });
      }

      this.counters.updatedAt = new Date().toISOString();
      await this.ctx.storage.put("counters", this.counters);

      return new Response(JSON.stringify(this.counters), {
        headers: {
          "content-type": "application/json; charset=utf-8",
          "cache-control": "no-store",
        },
      });
    }

    return new Response("Not found.", { status: 404 });
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = env.ALLOW_ORIGIN || "*";
    const counterId = env.DOWNLOAD_COUNTER.idFromName("global");
    const counter = env.DOWNLOAD_COUNTER.get(counterId);

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(origin),
      });
    }

    if (url.pathname === "/api/downloads/stats") {
      const storedResponse = await counter.fetch("https://counter/stats");
      const storedCounters = await storedResponse.json();

      return jsonResponse(
        {
          ...defaultCounters(),
          ...storedCounters,
          windowsBuildSize: env.WINDOWS_BUILD_SIZE || "7.9 MB",
          macBuildSize: env.MAC_BUILD_SIZE || "Coming soon",
        },
        origin,
      );
    }

    if (url.pathname === "/api/downloads/windows") {
      await counter.fetch("https://counter/increment/windows");
      return redirectResponse(
        env.WINDOWS_DOWNLOAD_URL ||
          "https://github.com/anclatechs/verse-listener/releases/latest",
        origin,
      );
    }

    if (url.pathname === "/api/downloads/mac") {
      if (!env.MAC_DOWNLOAD_URL) {
        return jsonResponse(
          {
            ok: false,
            status: "coming_soon",
            message: "The macOS build is coming soon.",
          },
          origin,
          { status: 409 },
        );
      }

      await counter.fetch("https://counter/increment/mac");
      return redirectResponse(env.MAC_DOWNLOAD_URL, origin);
    }

    return new Response("Not found.", {
      status: 404,
      headers: corsHeaders(origin),
    });
  },
};
