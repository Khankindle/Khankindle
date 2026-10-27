# Hosting the CloudyAI site

Research notes, October 2026. Prices and limits checked against vendor docs and
recent comparisons; re-check before you buy, since several hosts changed terms
in the last year.

## What this site needs

| Requirement | Value | Why it matters |
|---|---|---|
| Runtime | None | Pure HTML/CSS/JS. No build step, no database, no API calls. |
| Files | 40 | 5 pages, 1 stylesheet, 2 scripts, 20 images, 6 PDFs, 6 covers. |
| Size | 5.1 MB | Largest single file is a 513 KB PDF. |
| Bandwidth | Modest | A heavy month is likely 5–20 GB, driven by PDF downloads. |
| Custom domain | `.co.zw` | Registered separately; the host just needs to point at it. |
| TLS | Required | Free on every option below. |
| Backend | None | Forms open the visitor's mail client; the spend audit runs in-browser. |
| Commercial use | Yes | This is a business site. It rules out two popular free tiers. |

## Shortlist

| Host | Free tier | Bandwidth | Commercial OK? | Verdict |
|---|---|---|---|---|
| **Cloudflare Pages** | $0 | **Unlimited** static requests & bandwidth | Yes | **Best fit.** |
| Netlify | $0 | ~15 GB (300 credits @ 20/GB) | Yes | Fine, but the 2025 credit change gutted the old 100 GB. |
| Surge.sh | $0 | Undocumented / generous | Yes | Works, but CLI-only and no Git deploys. |
| Render | $0 | **5 GB** since Apr 2026 | Yes | Too small for a PDF library. |
| GitHub Pages | $0 | 100 GB soft, 1 GB site | **No** | Terms forbid "your online business". |
| Vercel Hobby | $0 | 100 GB | **No** | Hobby is "non-commercial personal use only". |

### Why Cloudflare Pages wins here

- Static assets are free and unlimited on the free plan; only builds are metered
  (500/month, one concurrent, 20 min timeout). We do not need builds.
- Limits that do exist are structural and we are nowhere near them: 20,000 files
  per site, 25 MiB per file, 100 custom domains per project.
- **There is a Cloudflare PoP in Harare**, plus Johannesburg, Durban, Cape Town,
  Gaborone, Lusaka and Maputo. For a Zimbabwean audience that is the shortest
  possible path to the visitor, and it beats any host whose nearest edge is
  London.
- Free plan needs no card, which avoids the usual ZW card-acceptance friction.
- Custom domain + automatic TLS on the free plan; DNS can live there too.
- No personal-use restriction, unlike Vercel Hobby.

## Costs

| Line item | Cost |
|---|---|
| Cloudflare Pages (hosting, TLS, CDN) | $0 |
| `.co.zw` domain, local registrar | $5–10 / year |
| **Total** | **≈ $5–10 / year** |

`.co.zw` prices vary wildly by registrar — $4.95–9.99 locally (GetHost,
Webdev, name.co.zw, Tremhost, uhost.africa), but $140–440/yr at some
international registrars. Register locally, and pay in USD/ZiG where possible;
a few accept EcoCash or InnBucks.

### If you want real mailboxes

The site publishes `sales@`, `research@` and `careers@cloudyai.co.zw`.

- **Cloudflare Email Routing — free.** Forward any address on the domain to a
  Gmail inbox. 200 rules per domain, unlimited forwarding. Caveat: inbound only
  — replies come from your personal address, not from `@cloudyai.co.zw`.
- **Namecheap Stellar — from ~$2/mo first year, renews ~$4.48/mo.** 3 sites,
  20 GB SSD, 30 mailboxes. Cheapest way to get proper `@cloudyai.co.zw` sending.
- **Hostinger Premium — from ~$2.49/mo on a long term, renews ~$10.99/mo.**
  More storage and speed; mailboxes included.

If mail matters more than the last dollar, Namecheap or Hostinger is the
simpler answer — you get hosting and mail in one bill. If hosting is all you
need, Cloudflare plus Email Routing gets you to ~$5/yr.

## Deploying

The site currently sits at the repository root next to `pocketledger/` and
`tools/`, so a naive "publish the repo root" would put unrelated code on the
internet. Stage only the public files.

### Option A — Cloudflare Pages, Git-connected

Set in the Pages project:

- Build command: `mkdir -p _site && cp -r index.html research.html contact.html careers.html leak-audit.html assets _site/`
- Build output directory: `_site`

Then point the custom domain at the project and let Cloudflare issue the
certificate.

### Option B — Cloudflare Pages, direct upload

```bash
mkdir -p _site
cp -r index.html research.html contact.html careers.html leak-audit.html assets _site/
npx wrangler pages deploy _site --project-name cloudyai
```

### Option C — any static host / cPanel

Upload the same six items (five pages + `assets/`) to `public_html`. This works
on Namecheap, Hostinger or a local Zimbabwean cPanel host unchanged.

## Things to check before going live

1. **Canonical URLs and `og:image`** are currently relative. Once the domain is
   fixed, make them absolute — `og:image` in particular must be a full URL for
   link previews to work.
2. Add `robots.txt` and a `sitemap.xml` listing the five pages.
3. Set a caching header for `/assets/*` (long max-age; the filenames are stable
   enough for a small site, or add a query string when they change).
4. Decide where the forms actually go. Right now they hand off to `mailto:`,
   which works everywhere but depends on the visitor having a mail client
   configured. Cloudflare Pages Functions or a form endpoint would capture
   submissions server-side if that matters.
5. Cloudflare's dashboard now steers new projects toward Workers Static Assets
   rather than Pages. Either works for a site this simple; Pages is the more
   familiar path.

## Sources

- Cloudflare Pages limits — developers.cloudflare.com/pages/platform/limits
- Cloudflare network locations — cloudflare.com/network
- Cloudflare Email Routing limits — developers.cloudflare.com/email-service
- Netlify pricing (300-credit model) — netlify.com/pricing
- Vercel Fair Use Guidelines — vercel.com/docs/limits/fair-use-guidelines
- GitHub Additional Product Terms (Pages) — docs.github.com/site-policy
- GitHub Pages limits — docs.github.com/pages
- Render plan changes, Apr 2026 — render.com
