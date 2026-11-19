# Checkpoint C preview (2026-11-10)
- URL: https://economy-preview.jiteshkprasad.workers.dev (private: HTTP Basic Auth, user `preview`; the password is the Worker
  secret `PREVIEW_PASS`. Every response is `X-Robots-Tag: noindex`;
  robots.txt disallows all.)
- Built from `phase3-map` (`npm run build`, Node 24) and served by `web/preview-worker/` (static assets, Worker first for auth).
  Redeploy: build, then `wrangler deploy` in `web/preview-worker/`.
- Live since 2026-11-10 at https://indianeconomy.jitesh.app (Worker `indianeconomy`, `web/site-worker/`; deploy build: `SITE_URL=https://indianeconomy.jitesh.app CF_BEACON_TOKEN=<site tag> npm run build`, then `wrangler deploy` in `web/site-worker/`). The preview stays private.
- Screenshots: `docs/phase3/screens-2026-11-10/` (phone 375 px and desktop 1440 px: map, flow, series, three stories, methodology).
