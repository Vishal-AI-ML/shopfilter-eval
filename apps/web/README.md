# ShopFilter Eval web

Next.js operator interface for the ShopFilter Eval API.

## Local development

From `E:\shopfilter-eval\apps\web`:

```powershell
pnpm install
pnpm dev
```

The server-side API client defaults to `http://localhost:8000`. Override
`SHOPFILTER_API_INTERNAL_URL` only in a local environment file or process
environment. Do not expose credentials through `NEXT_PUBLIC_*` variables.

The browser talks to same-origin Next.js auth route handlers. Those handlers
forward only the fixed authentication endpoints and relay the API's HttpOnly
session cookie; passwords and session tokens are never persisted by the web app.
