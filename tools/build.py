# -*- coding: utf-8 -*-
"""Static site generator for phonerepairnearme.com.au.

Run with: python tools/build.py
Regenerates the entire published site (every file this script writes is
derived output — edit data.py or this script, not the generated HTML).
"""
import json
import math
import os
import re
import shutil
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
import data as D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = date.today().isoformat()

# Everything at repo root is generated output EXCEPT these — a flat URL
# structure means suburb/region/service folders (600+ of them) live at the
# root too, so clean_output() wipes anything not explicitly protected rather
# than naming each generated folder.
PROTECTED = {'tools', 'legacy-artifact', '.git', '.gitignore', 'README.md'}


def clean_output():
    for name in os.listdir(ROOT):
        if name in PROTECTED:
            continue
        p = os.path.join(ROOT, name)
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)


def slugify(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def write(rel_path, content):
    full = os.path.join(ROOT, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def haversine(a, b):
    R = 6371
    r = math.pi / 180
    dla = (b[0] - a[0]) * r
    dlo = (b[1] - a[1]) * r
    x = math.sin(dla / 2) ** 2 + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin(dlo / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


# ---- derive slugs for FLAT root-level URLs (no /sydney/, no /services/) ----
# Suburbs claim the plain slug first (that's what people actually search for);
# regions/services fall back to a suffixed slug on collision (e.g. the
# "Penrith" region vs. the "Penrith" suburb both slugify to "penrith").
RESERVED_SLUGS = {'about', 'contact', 'privacy', 'list-your-shop', 'assets',
                   'tools', 'legacy-artifact', 'sitemap', 'robots', 'llms', '404'}
_used = set(RESERVED_SLUGS)

for s in D.SUBURBS:
    slug = slugify(s['name'])
    if slug in _used:
        slug = slug + "-" + s['postcode']
    _used.add(slug)
    s['slug'] = slug

REGION_SLUG = {}
for r in D.REGIONS:
    slug = slugify(r)
    if slug in _used:
        slug = slug + "-region"
    _used.add(slug)
    REGION_SLUG[r] = slug

for sh in D.SHOPS:
    sh['slug'] = slugify(sh['name'])

for svc in D.SERVICES:
    if svc['slug'] in _used:
        svc['slug'] = svc['slug'] + "-repair"
    _used.add(svc['slug'])

ALL_URLS = []  # (path, lastmod) for sitemap.xml, path is root-relative with leading /


def register(path):
    ALL_URLS.append(path)
    return path


# ---------------------------------------------------------------------------
# Shared HTML fragments
# ---------------------------------------------------------------------------

def esc(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


NAV_LINKS = [
    ("Repairs", "/#repairs"),
    ("Suburbs", "/#suburbs"),
    ("iPhone", "/#repairs"),
    ("Samsung", "/#repairs"),
    ("For shops", "#"),
]


def head(title, description, canonical_path, extra_jsonld=None):
    canonical = D.DOMAIN + canonical_path
    jsonld = ""
    if extra_jsonld:
        for block in extra_jsonld:
            jsonld += f'<script type="application/ld+json">{json.dumps(block, ensure_ascii=False)}</script>\n'
    return f"""<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
<meta property="og:site_name" content="{esc(D.SITE_NAME)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="/assets/style.css">
{jsonld}</head>
<body>
"""


def header_html():
    links = "".join(f'<a href="{href}">{esc(label)}</a>' for label, href in NAV_LINKS)
    return f"""<header class="site-header">
  <nav class="nav-wrap" aria-label="Primary">
    <a href="/" class="brand"><span class="brand-mark">P</span><span>phonerepair<span class="muted">nearme</span></span></a>
    <div class="nav-links" id="nav-links">{links}</div>
    <div class="nav-right">
      <a class="btn-primary btn-pill" href="/#search">Find a repairer</a>
      <button class="nav-toggle" aria-controls="nav-links" aria-expanded="false" aria-label="Menu">&#9776;</button>
    </div>
  </nav>
</header>
"""


def footer_html():
    cols = [
        ("Repairs", [(s['name'], f"/{s['slug']}/") for s in D.SERVICES]),
        ("Brands", [(b, "/#repairs") for b in D.BRANDS]),
        ("Regions", [(r, f"/{REGION_SLUG[r]}/") for r in D.REGIONS[:6]]),
        ("Company", [("About", None), ("List your shop", None), ("Contact", None), ("Privacy", None)]),
    ]
    cols_html = ""
    for title, items in cols:
        li = "".join(f'<li><a href="{href or "#"}">{esc(label)}</a></li>' for label, href in items)
        cols_html += f'<div><h4>{esc(title)}</h4><ul>{li}</ul></div>'
    return f"""<footer class="site-footer">
  <div class="wrap">
    <div class="footer-cols">{cols_html}</div>
    <div class="footer-bottom">
      <span>&copy; 2026 phonerepairnearme.com.au &middot; Independent directory, not affiliated with any manufacturer.</span>
      <span>Sydney, NSW</span>
    </div>
  </div>
</footer>
"""


def breadcrumb(items):
    """items: list of (label, path-or-None-for-current)."""
    parts = []
    ld_items = []
    for i, (label, href) in enumerate(items):
        if href:
            parts.append(f'<a href="{href}">{esc(label)}</a>')
        else:
            parts.append(f'<span aria-current="page">{esc(label)}</span>')
        ld_items.append({
            "@type": "ListItem", "position": i + 1, "name": label,
            "item": D.DOMAIN + href if href else None,
        })
    html = '<nav class="breadcrumb" aria-label="Breadcrumb">' + '<span class="sep">&rsaquo;</span>'.join(parts) + '</nav>'
    jsonld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": ld_items}
    return html, jsonld


def page(title, description, canonical_path, main_html, extra_jsonld=None):
    return head(title, description, canonical_path, extra_jsonld) + header_html() + f'<main>{main_html}</main>' + footer_html() + '<script src="/assets/main.js"></script>\n</body>\n</html>\n'


# ---------------------------------------------------------------------------
# Shop ranking per suburb
# ---------------------------------------------------------------------------

def shop_coord(shop):
    return shop['ll']


def suburb_coord(suburb):
    return D.SUBURB_LL.get(suburb['name']) or D.PC.get(int(suburb['postcode'])) or D.PC[2000]


def ranked_shops(suburb):
    here = suburb_coord(suburb)
    out = []
    for sh in D.SHOPS:
        dist = haversine(here, shop_coord(sh))
        out.append((dist, sh))
    out.sort(key=lambda t: t[0])
    return out


def shop_card_html(shop, dist, rank, suburb_name):
    badge = '<span class="badge-nearest">Nearest</span>' if rank == 1 else ''
    if shop['hours']:
        hours_js = json.dumps(shop['hours'])
        opens_attr = ''
    else:
        hours_js = 'null'
        opens_attr = f' data-opens="{shop["opens"]}"'
    dist_label = f"In {esc(suburb_name)}" if dist < 1 else f"&asymp; {dist:.1f} km away"
    if shop['phone']:
        call_html = f'<a class="btn-primary" href="tel:{shop["phone"].replace(" ", "")}">Call {esc(shop["phone"])}</a>'
    else:
        call_html = f'<a class="btn-primary" href="{shop["url"]}" target="_blank" rel="noopener">Store info</a>'
    book_html = '<a class="btn-dark" href="https://zoom-fones.com.au/book" target="_blank" rel="noopener">Book online</a>'
    return f"""<article class="shop-card" data-reveal="1">
  <div class="shop-head">
    <div class="shop-rank">{rank}</div>
    <div class="shop-main">
      <h2>{esc(shop['name'])} {badge}</h2>
      <p class="shop-dist">{dist_label}</p>
      <p class="shop-addr">{esc(shop['address'])}</p>
      <p class="shop-note">{esc(shop['note'])}</p>
    </div>
  </div>
  <div class="shop-actions">
    <p class="shop-status js-status" data-hours='{hours_js}'{opens_attr}>{esc(shop['hoursText'])}</p>
    <div class="shop-buttons">
      {call_html}
      {book_html}
      <a class="btn-outline" href="{shop['maps']}" target="_blank" rel="noopener">Directions</a>
    </div>
  </div>
</article>"""


INTRO_VARIANTS = [
    "Most repairers covering {region} handle screen and battery jobs while you wait. Water damage and board-level repairs usually take one to two business days.",
    "Across {region}, screen and battery repairs are typically same-day or while-you-wait jobs. Water damage and board-level repairs usually need one to two business days.",
    "In the {region} area, screen and battery replacements are usually done on the spot. Water damage and board-level repairs tend to take one to two business days.",
    "Repairers serving {region} generally turn around screens and batteries the same visit. Water damage and board-level work usually takes one to two business days.",
]


def suburb_intro(suburb):
    return INTRO_VARIANTS[suburb['id'] % len(INTRO_VARIANTS)].format(region=suburb['region'])


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def build_suburb_page(suburb):
    path = f"/{suburb['slug']}/"
    register(path)
    ranked = ranked_shops(suburb)
    nearest_dist, nearest_shop = ranked[0]
    cards = "\n".join(shop_card_html(sh, d, i + 1, suburb['name']) for i, (d, sh) in enumerate(ranked))

    same_region = [s for s in D.SUBURBS if s['region'] == suburb['region'] and s['id'] != suburb['id']]
    same_region.sort(key=lambda s: abs(int(s['postcode']) - int(suburb['postcode'])))
    nearby = same_region[:12]
    nearby_html = "".join(f'<a class="chip" href="/{n["slug"]}/">{esc(n["name"])}</a>' for n in nearby)

    services_li = "".join(
        f'<li><span>{esc(s["name"])}</span><span class="muted">{"From $" + str(s["price"]) if s["price"] else "Free diagnosis"}</span></li>'
        for s in D.SERVICES
    )

    crumb_html, crumb_ld = breadcrumb([
        ("Home", "/"), (suburb['region'], f"/{REGION_SLUG[suburb['region']]}/"), (suburb['name'], None),
    ])

    shops_ld = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {
                "@type": "ListItem", "position": i + 1,
                "item": {
                    "@type": "LocalBusiness", "name": sh['name'],
                    "address": sh['address'], "telephone": sh['phone'],
                    "url": sh['url'],
                },
            }
            for i, (d, sh) in enumerate(ranked)
        ],
    }

    title = f"Phone Repair in {suburb['name']} — Compare Local Repairers | Phone Repair Near Me"
    desc = f"Find phone screen, battery and charging repair near {suburb['name']} NSW {suburb['postcode']}. Nearest listed store: {nearest_shop['name']}, {nearest_dist:.1f} km away."

    main_html = f"""
<div class="wrap narrow">{crumb_html}</div>
<section class="hero-suburb wrap narrow">
  <p class="eyebrow">{esc(suburb['region'])} &middot; NSW {esc(suburb['postcode'])}</p>
  <h1>Phone repair in {esc(suburb['name'])}.</h1>
  <p class="lede">{len(D.SHOPS)} repair stores ranked by distance from {esc(suburb['name'])}. Check who's open, then call or get directions.</p>
</section>
<section class="wrap narrow suburb-shops">
  <div class="shop-list">{cards}</div>
  <aside class="map-aside">
    <div class="image-slot">Map of repairers near {esc(suburb['name'])}</div>
  </aside>
</section>
<section class="band-light">
  <div class="wrap narrow two-col">
    <div>
      <h2>Common repairs in {esc(suburb['name'])}.</h2>
      <p>{suburb_intro(suburb)}</p>
    </div>
    <ul class="price-list">{services_li}</ul>
  </div>
</section>
<section class="wrap narrow">
  <h2>Nearby suburbs</h2>
  <div class="chip-row">{nearby_html}</div>
  <p><a href="/{REGION_SLUG[suburb['region']]}/">See all of {esc(suburb['region'])} &rsaquo;</a></p>
</section>
"""
    write(f"{suburb['slug']}/index.html", page(title, desc, path, main_html, [crumb_ld, shops_ld]))


def build_region_page(region):
    slug = REGION_SLUG[region]
    path = f"/{slug}/"
    register(path)
    suburbs = sorted([s for s in D.SUBURBS if s['region'] == region], key=lambda s: s['name'])
    items = "".join(f'<li><a href="/{s["slug"]}/">{esc(s["name"])} <span class="muted">{esc(s["postcode"])}</span></a></li>' for s in suburbs)

    crumb_html, crumb_ld = breadcrumb([("Home", "/"), (region, None)])
    title = f"Phone Repair in {region} — All Suburbs | Phone Repair Near Me"
    desc = f"Compare phone repair shops across every suburb in {region}, Sydney. {len(suburbs)} suburbs covered, ranked by distance to the nearest listed store."

    main_html = f"""
<div class="wrap narrow">{crumb_html}</div>
<section class="hero-suburb wrap narrow">
  <p class="eyebrow">Greater Sydney</p>
  <h1>Phone repair across {esc(region)}.</h1>
  <p class="lede">{len(suburbs)} suburbs. Pick yours to see the nearest listed repairer, pricing and opening hours.</p>
</section>
<section class="wrap narrow">
  <ul class="suburb-grid">{items}</ul>
  <p><a href="/#suburbs">&larr; All regions</a></p>
</section>
"""
    write(f"{slug}/index.html", page(title, desc, path, main_html, [crumb_ld]))


def build_service_page(svc):
    path = f"/{svc['slug']}/"
    register(path)
    region_links = "".join(f'<a href="/{REGION_SLUG[r]}/">{esc(r)}</a>' for r in D.REGIONS)
    crumb_html, crumb_ld = breadcrumb([("Home", "/"), (svc['name'], None)])
    price_label = f"From ${svc['price']}" if svc['price'] else "Free diagnosis"
    title = f"{svc['name']} — Sydney Wide | Phone Repair Near Me"
    desc = f"{svc['desc']} {price_label}. Compare listed repairers across Greater Sydney by suburb."
    service_ld = {
        "@context": "https://schema.org", "@type": "Service",
        "serviceType": svc['name'], "areaServed": "Greater Sydney, NSW",
        "provider": {"@type": "Organization", "name": D.SITE_NAME},
    }
    main_html = f"""
<div class="wrap narrow">{crumb_html}</div>
<section class="hero-suburb wrap narrow">
  <p class="eyebrow">{esc(svc['tag'])}</p>
  <h1>{esc(svc['name'])}.</h1>
  <p class="lede">{esc(svc['desc'])} {price_label}.</p>
</section>
<section class="wrap narrow">
  <h2>Available across Greater Sydney</h2>
  <p>Find a {esc(svc['name'].lower())} repairer near you by suburb or browse by region:</p>
  <div class="link-grid">{region_links}</div>
  <p><a href="/#suburbs">Browse all suburbs &rsaquo;</a></p>
</section>
"""
    write(f"{svc['slug']}/index.html", page(title, desc, path, main_html, [crumb_ld, service_ld]))


def build_home():
    path = "/"
    register(path)
    service_cards = ""
    for s in D.SERVICES:
        price_label = f"From ${s['price']}" if s['price'] else "Free diagnosis"
        service_cards += f"""<a class="service-card" data-reveal="1" href="/{s['slug']}/">
  <span class="eyebrow">{esc(s['tag'])}</span>
  <h2>{esc(s['name'])}</h2>
  <p>{esc(s['desc'])}</p>
  <span class="price">{price_label}</span>
</a>"""
    region_cards = "".join(
        f'<a class="region-card" data-reveal="1" href="/{REGION_SLUG[r]}/"><h3>{esc(r)}</h3><span class="muted">{len([s for s in D.SUBURBS if s["region"] == r])} suburbs</span></a>'
        for r in D.REGIONS
    )
    faq_html = "".join(f"""<details class="faq">
  <summary>{esc(f['q'])}</summary>
  <p>{esc(f['a'])}</p>
</details>""" for f in D.FAQS)
    brand_html = "".join(f"<span>{esc(b)}</span>" for b in D.BRANDS)

    website_ld = {"@context": "https://schema.org", "@type": "WebSite", "name": D.SITE_NAME, "url": D.DOMAIN}
    faq_ld = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": f['q'], "acceptedAnswer": {"@type": "Answer", "text": f['a']}}
            for f in D.FAQS
        ],
    }

    title = "Phone Repair Near Me — Sydney | Screen, Battery & More"
    desc = "Find trusted phone repair near you in every Sydney suburb. Compare local repairers for iPhone, Samsung and Google Pixel screen, battery and charging port repairs."

    main_html = f"""
<section class="hero wrap">
  <p class="eyebrow">Every Sydney suburb. One search.</p>
  <h1>Phone repair.<br>Near you. Today.</h1>
  <p class="lede">Compare trusted local repairers for cracked screens, tired batteries and everything in between.</p>
  <form class="search-form" id="search" role="search">
    <input type="search" id="suburb-search-input" placeholder="Enter your suburb or postcode" aria-label="Suburb or postcode" autocomplete="off">
    <button type="submit">Search</button>
    <div id="suburb-search-results" class="search-results" hidden></div>
  </form>
  <p class="quick-links"><a href="#repairs">Browse repairs &rsaquo;</a> <a href="#suburbs">All suburbs &rsaquo;</a></p>
  <div class="hero-image"><div class="image-slot">Hero image &mdash; phone being repaired, shot from above</div></div>
</section>

<section id="repairs" class="band-light">
  <div class="wrap">
    <h2 data-reveal="1">Whatever broke,<br><span class="muted">someone nearby fixes it.</span></h2>
    <div class="service-grid">{service_cards}</div>
  </div>
</section>

<section class="band-dark">
  <div class="wrap">
    <h2 data-reveal="1">Three steps.<br><span class="muted">Zero guesswork.</span></h2>
    <div class="steps-grid">
      <div data-reveal="1"><div class="step-n">01</div><h3>Enter your suburb</h3><p>We show every listed repairer close to you, sorted by distance.</p></div>
      <div data-reveal="1"><div class="step-n">02</div><h3>Compare &amp; choose</h3><p>See who's open now, what they fix and what it costs.</p></div>
      <div data-reveal="1"><div class="step-n">03</div><h3>Walk in or call</h3><p>Most repairs are done the same day &mdash; often while you wait.</p></div>
    </div>
  </div>
</section>

<section class="wrap brands"><p class="eyebrow center" data-reveal="1">Repairs for every major brand.</p><div class="brand-row" data-reveal="1">{brand_html}</div></section>

<section id="suburbs" class="band-light">
  <div class="wrap">
    <h2 data-reveal="1">Find repair in your suburb.</h2>
    <p class="lede" data-reveal="1">{len(D.SUBURBS)} suburbs across {len(D.REGIONS)} regions of Greater Sydney.</p>
    <div class="region-grid">{region_cards}</div>
  </div>
</section>

<section class="wrap faqs">
  <h2>Questions, answered.</h2>
  {faq_html}
</section>
"""
    write("index.html", page(title, desc, path, main_html, [website_ld, faq_ld]))


def build_404():
    main_html = """
<section class="wrap narrow prose" style="text-align:center;padding:80px 22px">
  <h1>Page not found</h1>
  <p>That page doesn't exist. Try the <a href="/#suburbs">suburb directory</a> or go back <a href="/">home</a>.</p>
</section>
"""
    write("404.html", page("Page not found — Phone Repair Near Me", "Page not found.", "/404.html", main_html))


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

def build_assets():
    write("assets/style.css", STYLE_CSS)
    write("assets/main.js", MAIN_JS)
    write("assets/favicon.svg", FAVICON_SVG)
    suburb_index = [{"n": s['name'], "s": s['slug'], "r": s['region'], "p": s['postcode']} for s in D.SUBURBS]
    write("assets/suburbs.json", json.dumps(suburb_index, ensure_ascii=False))


STYLE_CSS = """
:root{--ink:#1d1d1f;--sub:#6e6e73;--muted:#86868b;--line:#d2d2d7;--bg-light:#f5f5f7;--accent:#0071e3;--accent2:#0066cc;--warn:#bf4800}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:#fff;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;letter-spacing:-0.01em;line-height:1.4}
a{color:var(--accent2);text-decoration:none}
a:hover{text-decoration:underline}
.muted{color:var(--muted)}
.wrap{max-width:1024px;margin:0 auto;padding:0 22px}
.wrap.narrow{max-width:860px}
h1,h2,h3{letter-spacing:-0.03em;line-height:1.1;margin:0}
.site-header{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.9);backdrop-filter:saturate(180%) blur(20px);border-bottom:1px solid rgba(0,0,0,.08)}
.nav-wrap{max-width:1024px;margin:0 auto;height:52px;padding:0 22px;display:flex;align-items:center;justify-content:space-between;gap:20px}
.brand{display:flex;align-items:center;gap:8px;font-weight:600;font-size:15px;color:var(--ink)}
.brand-mark{width:22px;height:22px;border-radius:7px;background:var(--ink);color:#fff;display:grid;place-items:center;font-size:12px;font-weight:700}
.nav-links{display:flex;gap:22px;font-size:14px}
.nav-links a{color:var(--ink);opacity:.85}
.nav-links a:hover{opacity:1}
.nav-right{display:flex;align-items:center;gap:14px}
.btn-pill{border-radius:980px;padding:6px 14px;font-size:12px;font-weight:500}
.nav-toggle{display:none;border:0;background:none;font-size:20px;cursor:pointer}
@media(max-width:680px){.nav-links{display:none;position:absolute;top:52px;left:0;right:0;background:#fff;flex-direction:column;padding:16px 22px;border-bottom:1px solid var(--line)}.nav-links.open{display:flex}.nav-toggle{display:block}}
.hero{text-align:center;padding:72px 22px 0;overflow:hidden}
.hero-image{max-width:1100px;margin:clamp(40px,6vw,72px) auto 0;aspect-ratio:16/8;min-height:260px;border-radius:28px 28px 0 0;overflow:hidden}
.image-slot{width:100%;height:100%;display:grid;place-items:center;background:linear-gradient(180deg,#f5f5f7,#e8e8ed);color:var(--muted);font-size:14px;text-align:center;padding:16px}
.hero h1{font-size:clamp(40px,8vw,88px)}
.eyebrow{color:var(--warn);font-weight:600;margin:0 0 8px}
.eyebrow.center{text-align:center}
.lede{color:var(--sub);font-size:19px;max-width:620px;margin:16px auto 0}
.search-form{position:relative;max-width:560px;margin:32px auto 0;display:flex;gap:8px;background:var(--bg-light);border-radius:980px;padding:6px 6px 6px 20px}
.search-form input{flex:1;min-width:0;border:0;background:transparent;font:inherit;font-size:17px;padding:10px 0;outline:none}
.search-form button{border:0;background:var(--accent);color:#fff;font:inherit;font-weight:500;padding:11px 20px;border-radius:980px;cursor:pointer}
.search-results{position:absolute;left:0;right:0;top:calc(100% + 8px);background:#fff;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.14);padding:6px;text-align:left;z-index:5}
.search-results a{display:flex;justify-content:space-between;padding:10px 14px;border-radius:10px;color:var(--ink)}
.search-results a:hover{background:var(--bg-light);text-decoration:none}
.quick-links{margin-top:18px;font-size:16px}
.quick-links a{margin:0 12px}
.band-light{background:var(--bg-light);padding:64px 0}
.band-dark{background:#000;color:#f5f5f7;padding:64px 0}
.band-dark .muted{color:#a1a1a6}
.service-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:18px;margin-top:36px}
.service-card{background:#fff;border-radius:22px;padding:28px 26px;min-height:220px;display:flex;flex-direction:column;color:var(--ink);transition:transform .5s cubic-bezier(.2,.8,.2,1),box-shadow .5s}
.service-card:hover{text-decoration:none;transform:scale(1.015);box-shadow:0 20px 50px rgba(0,0,0,.08)}
.service-card h2{font-size:24px;margin-top:6px}
.service-card p{color:var(--sub);flex:1}
.service-card .price{margin-top:auto;font-size:14px}
.steps-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:36px;margin-top:40px}
.step-n{font-size:48px;font-weight:700;color:#2997ff}
.brands{text-align:center;padding:48px 22px}
.brand-row{display:flex;justify-content:center;flex-wrap:wrap;gap:28px;margin-top:20px;color:var(--muted);font-size:19px;font-weight:500}
.region-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,220px),1fr));gap:16px;margin-top:36px}
.region-card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px 20px;color:var(--ink)}
.region-card:hover{text-decoration:none;border-color:var(--ink)}
.faqs{padding:64px 22px}
.faq{border-top:1px solid var(--line);padding:18px 0}
.faq summary{cursor:pointer;font-weight:600;font-size:17px}
.faq p{color:var(--sub);margin:12px 0 0}
.breadcrumb{font-size:12px;color:var(--sub);padding:16px 0 0;display:flex;gap:6px;flex-wrap:wrap}
.breadcrumb a{color:var(--sub)}
.breadcrumb .sep{color:var(--line)}
.hero-suburb{padding:36px 22px 28px}
.hero-suburb h1{font-size:clamp(34px,6vw,64px)}
.suburb-shops{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:24px;align-items:start;padding-bottom:clamp(64px,9vw,100px)}
@media(max-width:733px){.suburb-shops{grid-template-columns:minmax(0,1fr)}.map-aside{display:none}}
.shop-list{display:flex;flex-direction:column;gap:14px}
.map-aside{position:sticky;top:72px;border-radius:24px;overflow:hidden;aspect-ratio:3/4}
.shop-card{background:var(--bg-light);border-radius:20px;padding:22px}
.shop-head{display:flex;gap:16px}
.shop-rank{width:40px;height:40px;flex-shrink:0;border-radius:50%;background:#fff;display:grid;place-items:center;font-weight:700}
.shop-main h2{font-size:20px;display:inline}
.badge-nearest{font-size:12px;font-weight:600;color:var(--accent2);background:#e8f1fc;padding:3px 9px;border-radius:980px;margin-left:8px}
.shop-dist{font-weight:500;margin:6px 0 0}
.shop-addr{color:var(--sub);font-size:14px;margin:4px 0 0}
.shop-note{color:var(--muted);font-size:13px;margin:2px 0 0}
.shop-actions{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:16px;flex-wrap:wrap}
.shop-status{font-size:13px;color:var(--sub);margin:0}
.shop-buttons{display:flex;gap:10px;flex-wrap:wrap}
.btn-primary{background:var(--accent);color:#fff;font-size:14px;font-weight:500;padding:9px 18px;border-radius:980px}
.btn-primary:hover{text-decoration:none;background:#0077ed}
.btn-dark{background:var(--ink);color:#fff;font-size:14px;font-weight:500;padding:9px 18px;border-radius:980px}
.btn-dark:hover{text-decoration:none;background:#000}
.btn-outline{border:1px solid var(--accent);color:var(--accent);font-size:14px;font-weight:500;padding:8px 17px;border-radius:980px}
.btn-outline:hover{text-decoration:none}
.two-col{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:40px;padding:56px 0}
.price-list{list-style:none;margin:0;padding:0}
.price-list li{display:flex;justify-content:space-between;padding:14px 0;border-bottom:1px solid var(--line)}
.chip-row{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}
.chip{border:1px solid var(--line);border-radius:980px;padding:9px 16px;font-size:14px;color:var(--ink)}
.chip:hover{text-decoration:none;border-color:var(--ink)}
.suburb-grid,.link-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,200px),1fr));gap:10px;list-style:none;margin:28px 0;padding:0}
.link-grid{display:flex;flex-wrap:wrap;gap:10px 18px}
.suburb-grid a,.link-grid a{color:var(--ink)}
.region-block{padding:28px 0;border-bottom:1px solid var(--line)}
.region-block h2{font-size:20px}
.region-block .link-grid{margin-top:14px}
.prose p{color:var(--sub);font-size:17px;line-height:1.6}
.prose h1{font-size:clamp(32px,5vw,48px);margin-bottom:20px}
.site-footer{background:var(--bg-light);border-top:1px solid var(--line);padding:40px 22px 28px;font-size:12px;color:var(--sub)}
.footer-cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:28px;padding-bottom:28px;border-bottom:1px solid var(--line)}
.footer-cols h4{margin:0 0 10px;font-size:12px;color:var(--ink)}
.footer-cols ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.footer-cols a{color:#424245}
.footer-bottom{display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;padding-top:18px}
"""

MAIN_JS = """
(function(){
  var toggle = document.querySelector('.nav-toggle');
  var links = document.getElementById('nav-links');
  if (toggle && links) toggle.addEventListener('click', function(){
    var open = links.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  function fmtH(h){ return (h > 12 ? h - 12 : h) + (h >= 12 ? 'pm' : 'am'); }
  function sydneyNow(){ return new Date(new Date().toLocaleString('en-US', { timeZone: 'Australia/Sydney' })); }
  document.querySelectorAll('.js-status').forEach(function(el){
    var hoursAttr = el.getAttribute('data-hours');
    var hours = hoursAttr ? JSON.parse(hoursAttr) : null;
    var staticText = el.textContent;
    if (!hours) {
      var opens = el.getAttribute('data-opens');
      if (opens && new Date() < new Date(opens)) { el.textContent = 'Coming soon \\u00b7 ' + staticText; return; }
      el.textContent = 'Open now'; el.style.color = '#1d8a3a'; return;
    }
    var now = sydneyNow(), d = now.getDay(), t = now.getHours() + now.getMinutes() / 60;
    var slot = hours[d], open = t >= slot[0] && t < slot[1];
    if (open) { el.textContent = 'Open now \\u00b7 until ' + fmtH(slot[1]) + ' \\u00b7 ' + staticText; el.style.color = '#1d8a3a'; }
    else {
      var label = t < slot[0] ? ('Closed \\u00b7 opens ' + fmtH(slot[0]) + ' today') : ('Closed \\u00b7 opens ' + fmtH(hours[(d + 1) % 7][0]) + ' tomorrow');
      el.textContent = label + ' \\u00b7 ' + staticText;
    }
  });

  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if (entry.isIntersecting) {
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'none';
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    document.querySelectorAll('[data-reveal]').forEach(function(el){
      var r = el.getBoundingClientRect();
      if (r.top < window.innerHeight) return;
      el.style.opacity = '0';
      el.style.transform = 'translateY(28px)';
      el.style.transition = 'opacity .9s cubic-bezier(.2,.8,.2,1), transform .9s cubic-bezier(.2,.8,.2,1)';
      io.observe(el);
    });
  }

  var input = document.getElementById('suburb-search-input');
  var results = document.getElementById('suburb-search-results');
  var form = document.getElementById('search');
  if (!input || !results || !form) return;
  var DATA = null;
  fetch('/assets/suburbs.json').then(function(r){ return r.json(); }).then(function(j){ DATA = j; });
  var current = [];
  input.addEventListener('input', function(){
    var q = input.value.trim().toLowerCase();
    results.hidden = true;
    current = [];
    if (!q || !DATA) return;
    var scored = DATA.map(function(s){
      var n = s.n.toLowerCase();
      var score = s.p.indexOf(q) === 0 ? 0 : n.indexOf(q) === 0 ? 1 : n.indexOf(' ' + q) !== -1 ? 2 : n.indexOf(q) !== -1 ? 3 : 9;
      return { s: s, score: score };
    }).filter(function(x){ return x.score < 9; }).sort(function(a, b){ return a.score - b.score || a.s.n.localeCompare(b.s.n); }).slice(0, 6);
    current = scored.map(function(x){ return x.s; });
    if (!current.length) return;
    results.innerHTML = current.map(function(s){ return '<a href="/' + s.s + '/">' + s.n + '<span class="muted">' + s.r + '</span></a>'; }).join('');
    results.hidden = false;
  });
  form.addEventListener('submit', function(e){
    e.preventDefault();
    if (current.length) window.location.href = '/' + current[0].s + '/';
  });
  document.addEventListener('click', function(e){ if (!form.contains(e.target)) results.hidden = true; });
})();
"""

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="#1d1d1f"/><text x="32" y="44" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="34" font-weight="700" fill="#fff">P</text></svg>"""


def build_robots():
    write("robots.txt", f"""User-agent: *
Allow: /
Disallow: /tools/
Disallow: /legacy-artifact/

Sitemap: {D.DOMAIN}/sitemap.xml
""")


def build_sitemap():
    urls = "".join(f"  <url><loc>{D.DOMAIN}{p}</loc><lastmod>{TODAY}</lastmod></url>\n" for p in ALL_URLS)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')


def build_llms_txt():
    region_links = "\n".join(f"- [{r}]({D.DOMAIN}/{REGION_SLUG[r]}/)" for r in D.REGIONS)
    service_links = "\n".join(f"- [{s['name']}]({D.DOMAIN}/{s['slug']}/)" for s in D.SERVICES)
    write("llms.txt", f"""# {D.SITE_NAME}

> Independent directory of phone repair shops across Greater Sydney, NSW. Compare screen, battery, charging port, back glass, camera and water-damage repair options by suburb, with store distance, hours and contact details.

Phone Repair Near Me helps people in any Sydney suburb find the closest listed phone repair store, see indicative pricing and get directions or a phone number. The directory is independent of any phone manufacturer. Every suburb and region has its own page at the site root, e.g. {D.DOMAIN}/bondi-beach/ — there is no /sydney/ or /services/ path prefix.

## Regions ({len(D.SUBURBS)} suburbs across {len(D.REGIONS)} regions — each region page lists every suburb in it)
{region_links}

## Repair services
{service_links}

## Other pages
- [Home]({D.DOMAIN}/): overview and suburb search
- [About]({D.DOMAIN}/about/)
- [List your shop]({D.DOMAIN}/list-your-shop/): for repair businesses that want to be listed
- [Full sitemap]({D.DOMAIN}/sitemap.xml): every suburb, region and service URL

## Notes
- Each suburb page ranks the currently listed stores by straight-line distance from that suburb and shows live-computed opening hours.
- Store listings (name, address, phone, hours) are maintained directly by the site operator; only three physical stores are listed as of {TODAY}, so distances on far suburb pages can be large — this is disclosed on the page itself.
- Suburb/region page copy is template-generated from a shared dataset; store details and pricing are not.
""")


def main():
    clean_output()
    build_assets()
    build_home()
    for suburb in D.SUBURBS:
        build_suburb_page(suburb)
    for region in D.REGIONS:
        build_region_page(region)
    for svc in D.SERVICES:
        build_service_page(svc)
    build_404()
    build_robots()
    build_sitemap()
    build_llms_txt()
    write("CNAME", "phonerepairnearme.com.au\n")
    write(".nojekyll", "")
    print(f"Built {len(ALL_URLS)} pages.")


if __name__ == "__main__":
    main()
