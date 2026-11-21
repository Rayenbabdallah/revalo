# Revalo web

React app for workshops: upload a CNC job, see the sheet in 3D with its
remnants and scrap, then review and approve the leftover records.

```bash
pnpm install
pnpm dev        # http://localhost:5173, proxies /api to the backend on :8000
pnpm build
```

Set `REVALO_API_URL` to point the dev proxy at another backend.
