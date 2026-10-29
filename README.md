# phonerepairnearme.com.au

Static, multi-page phone-repair directory for Greater Sydney. Every suburb,
region and service has its own crawlable URL — no client-side router, no
build step at request time. GitHub Pages serves the files in this repo as-is.

## Structure

- `index.html`, `about/`, `contact/`, `privacy/`, `list-your-shop/` — top-level pages
- `sydney/<suburb>/` — one page per suburb (594), ranked by distance to listed stores
- `sydney/<region>/` — one hub page per region (17), linking every suburb in it
- `services/<service>/` — one page per repair type (6)
- `assets/` — shared `style.css`, `main.js` (mobile nav, live open/closed status, suburb search), `favicon.svg`, `suburbs.json` (client-side search index)
- `robots.txt`, `sitemap.xml`, `llms.txt`, `CNAME`, `.nojekyll` — site-level SEO/hosting files
- `legacy-artifact/` — original Claude Artifact export this site replaced (kept for reference, excluded from the sitemap and disallowed in robots.txt)

## Regenerating the site

All HTML/CSS/JS/SEO files above are **generated** from `tools/data.py`
(suburb/region/service/store data) by `tools/build.py`. Never hand-edit a
generated file — edit the data or the generator and rebuild:

```
python tools/build.py
```

This wipes and rewrites every published directory/file listed above.

## Deploying

1. Push this repo to GitHub.
2. Repo Settings → Pages → deploy from the branch root.
3. At your domain registrar, point `phonerepairnearme.com.au` at GitHub Pages
   (A records to GitHub's IPs, or an ALIAS/ANAME record) — the `CNAME` file
   in this repo is already set for that domain.
