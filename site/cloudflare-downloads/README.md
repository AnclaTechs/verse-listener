# VerseListener Cloudflare Download Metrics

This worker gives the landing page two things:

- `GET /api/downloads/stats` for the live download count and build size
- `GET /api/downloads/windows` and `GET /api/downloads/mac` redirect routes that increment the counter before sending people to the real download

## Endpoints

- `/api/downloads/stats`
- `/api/downloads/windows`
- `/api/downloads/mac`

## Deploy

1. `cd site/cloudflare-downloads`
2. `npm install`
3. Update `wrangler.jsonc`:
   - `WINDOWS_DOWNLOAD_URL`
   - `MAC_DOWNLOAD_URL`
   - `ALLOW_ORIGIN`
   - build size values if needed
4. Run `npm run deploy`

## Hooking it into the landing page

If the worker is mounted on the same domain as the site, you do not need to change anything.

If the worker lives on a separate Cloudflare subdomain, set this before the module script in `site/index.html`:

```html
<script>
  window.VERSELISTENER_SITE_CONFIG = {
    metricsBaseUrl: "",
    windowsBuildSize: "",
    macBuildSize: "",
  };
</script>
```

When the stats route is reachable, the landing page automatically:

- shows the live download count
- swaps the main download button over to the tracked Cloudflare route
- falls back to the GitHub release link if the worker is unavailable
