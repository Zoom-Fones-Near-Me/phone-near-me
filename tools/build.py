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
                   'tools', 'legacy-artifact', 'sitemap', 'robots', 'llms', '404',
                   'repairs', 'suburbs'}
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


LEAFLET_CSS = '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">\n'
LEAFLET_JS = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>\n'

NAV_LINKS = [
    ("Repairs", "/repairs/"),
    ("Suburbs", "/suburbs/"),
    ("iPhone", "/repairs/"),
    ("Samsung", "/repairs/"),
]


def head(title, description, canonical_path, extra_jsonld=None, extra_head="", geo=None):
    canonical = D.DOMAIN + canonical_path
    jsonld = ""
    if extra_jsonld:
        for block in extra_jsonld:
            jsonld += f'<script type="application/ld+json">{json.dumps(block, ensure_ascii=False)}</script>\n'
    geo_tags = ""
    if geo:
        lat, lng, placename = geo
        geo_tags = (f'<meta name="geo.region" content="AU-NSW">\n'
                    f'<meta name="geo.placename" content="{esc(placename)}">\n'
                    f'<meta name="geo.position" content="{lat};{lng}">\n'
                    f'<meta name="ICBM" content="{lat}, {lng}">\n')
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
{geo_tags}<link rel="stylesheet" href="/assets/style.css">
{extra_head}{jsonld}</head>
<body>
"""


def header_html():
    links = "".join(f'<a href="{href}">{esc(label)}</a>' for label, href in NAV_LINKS)
    return f"""<header class="site-header">
  <nav class="nav-wrap" aria-label="Primary">
    <a href="/" class="brand"><span class="brand-mark">P</span><span class="brand-text">phonerepair<span class="muted">nearme</span></span></a>
    <div class="nav-links" id="nav-links">{links}</div>
    <div class="nav-right">
      <a class="btn-primary btn-pill" href="/suburbs/">Find a repairer</a>
      <button class="nav-toggle" aria-controls="nav-links" aria-expanded="false" aria-label="Menu">&#9776;</button>
    </div>
  </nav>
</header>
"""


def footer_html():
    cols = [
        ("Repairs", [(s['name'], f"/{s['slug']}/") for s in D.SERVICES]),
        ("Brands", [(b, "/repairs/") for b in D.BRANDS]),
        ("Regions", [(r, f"/{REGION_SLUG[r]}/") for r in D.REGIONS[:6]]),
        ("Company", [("About", "/about/"), ("List your shop", "/list-your-shop/"), ("Contact", "/contact/"), ("Privacy", "/privacy/")]),
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


def page(title, description, canonical_path, main_html, extra_jsonld=None, extra_head="", extra_foot="", geo=None):
    return (head(title, description, canonical_path, extra_jsonld, extra_head, geo) + header_html()
            + f'<main>{main_html}</main>' + footer_html() + extra_foot
            + '<script src="/assets/main.js"></script>\n</body>\n</html>\n')


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


def suburb_faqs(suburb, ranked):
    name, postcode = suburb['name'], suburb['postcode']
    nearest_dist, nearest_shop = ranked[0]
    items = [{
        'q': f"Is there phone repair near me in {name}?",
        'a': f"Yes — phone repair near me in {name} NSW {postcode} is available at {nearest_shop['name']}, about {nearest_dist:.1f} km away. Compare every listed repairer above, ranked by distance from {name}.",
    }]
    for s in D.SERVICES:
        price_label = f"from ${s['price']}" if s['price'] else "with a free diagnosis"
        svc_phrase = s['slug'].replace('-', ' ')
        items.append({
            'q': f"Where can I get {svc_phrase} in {name}?",
            'a': f"{s['name']} near {name} is available {price_label} from the repairers listed above. {s['desc']}",
        })
    return items


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

    faqs = suburb_faqs(suburb, ranked)
    faq_html = "".join(f"""<details class="faq">
  <summary>{esc(f['q'])}</summary>
  <p>{esc(f['a'])}</p>
</details>""" for f in faqs)
    faq_ld = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": f['q'], "acceptedAnswer": {"@type": "Answer", "text": f['a']}}
            for f in faqs
        ],
    }

    DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
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
                    "geo": {"@type": "GeoCoordinates", "latitude": sh['ll'][0], "longitude": sh['ll'][1]},
                    "priceRange": "$$",
                    "sameAs": [sh['maps']],
                    **({"openingHoursSpecification": [
                        {"@type": "OpeningHoursSpecification", "dayOfWeek": DAY_NAMES[d],
                         "opens": f"{h[0]:02d}:00", "closes": f"{h[1]:02d}:00"}
                        for d, h in enumerate(sh['hours'])
                    ]} if sh['hours'] else {}),
                },
            }
            for i, (d, sh) in enumerate(ranked)
        ],
    }

    title = f"Phone Repair in {suburb['name']} — Compare Local Repairers | Phone Repair Near Me"
    desc = f"Find phone screen, battery and charging repair near {suburb['name']} NSW {suburb['postcode']}. Nearest listed store: {nearest_shop['name']}, {nearest_dist:.1f} km away."

    map_suburb = esc(json.dumps({"name": suburb['name'], "ll": list(suburb_coord(suburb))}, ensure_ascii=False))
    map_shops = esc(json.dumps([{"name": sh['name'], "ll": sh['ll'], "maps": sh['maps']} for d, sh in ranked], ensure_ascii=False))

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
    <div id="leaflet-map" class="leaflet-map" data-suburb='{map_suburb}' data-shops='{map_shops}'></div>
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
<section class="wrap narrow faqs">
  <h2>Phone repair in {esc(suburb['name'])}, answered.</h2>
  {faq_html}
</section>
"""
    here_ll = suburb_coord(suburb)
    write(f"{suburb['slug']}/index.html", page(title, desc, path, main_html, [crumb_ld, shops_ld, faq_ld],
          extra_head=LEAFLET_CSS, extra_foot=LEAFLET_JS,
          geo=(here_ll[0], here_ll[1], f"{suburb['name']}, NSW")))


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
  <p><a href="/suburbs/">&larr; All regions</a></p>
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
  <p><a href="/suburbs/">Browse all suburbs &rsaquo;</a></p>
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
  <p class="quick-links"><a href="/repairs/">Browse repairs &rsaquo;</a> <a href="/suburbs/">All suburbs &rsaquo;</a></p>
  <div class="hero-image"><img src="/assets/hero-repair.svg" width="1600" height="800" alt="Top-down view of a phone being repaired, with the back open showing the battery and logic board, a screwdriver, tweezers and a tray of screws nearby" loading="eager"></div>
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


def build_repairs_index():
    path = "/repairs/"
    register(path)
    crumb_html, crumb_ld = breadcrumb([("Home", "/"), ("Repairs", None)])
    title = "Phone Repair Services — Screen, Battery & More | Phone Repair Near Me"
    desc = "Browse every phone repair service covered by listed Sydney repairers: screen, battery, charging port, back glass, camera and water damage."
    service_cards = ""
    for s in D.SERVICES:
        price_label = f"From ${s['price']}" if s['price'] else "Free diagnosis"
        service_cards += f"""<a class="service-card" href="/{s['slug']}/">
  <span class="eyebrow">{esc(s['tag'])}</span>
  <h2>{esc(s['name'])}</h2>
  <p>{esc(s['desc'])}</p>
  <span class="price">{price_label}</span>
</a>"""
    main_html = f"""
<div class="wrap narrow">{crumb_html}</div>
<section class="hero-suburb wrap narrow">
  <p class="eyebrow">Every repair, one directory</p>
  <h1>Phone repairs.</h1>
  <p class="lede">Whatever broke, someone nearby fixes it. Pick a repair to see listed Sydney repairers and indicative pricing.</p>
</section>
<section class="wrap narrow">
  <div class="service-grid">{service_cards}</div>
</section>
"""
    write("repairs/index.html", page(title, desc, path, main_html, [crumb_ld]))


def build_suburbs_index():
    path = "/suburbs/"
    register(path)
    crumb_html, crumb_ld = breadcrumb([("Home", "/"), ("Suburbs", None)])
    title = "Find Phone Repair by Suburb — Greater Sydney | Phone Repair Near Me"
    desc = f"Search phone repair by suburb or browse all {len(D.REGIONS)} regions of Greater Sydney, covering {len(D.SUBURBS)} suburbs."
    region_cards = "".join(
        f'<a class="region-card" href="/{REGION_SLUG[r]}/"><h3>{esc(r)}</h3><span class="muted">{len([s for s in D.SUBURBS if s["region"] == r])} suburbs</span></a>'
        for r in D.REGIONS
    )
    main_html = f"""
<div class="wrap narrow">{crumb_html}</div>
<section class="hero-suburb wrap narrow">
  <p class="eyebrow">Greater Sydney</p>
  <h1>Find repair in your suburb.</h1>
  <p class="lede">{len(D.SUBURBS)} suburbs across {len(D.REGIONS)} regions. Search yours, or browse by region below.</p>
  <form class="search-form" id="search" role="search">
    <input type="search" id="suburb-search-input" placeholder="Enter your suburb or postcode" aria-label="Suburb or postcode" autocomplete="off">
    <button type="submit">Search</button>
    <div id="suburb-search-results" class="search-results" hidden></div>
  </form>
</section>
<section class="wrap narrow">
  <div class="region-grid">{region_cards}</div>
</section>
"""
    write("suburbs/index.html", page(title, desc, path, main_html, [crumb_ld]))


def build_contact():
    path = "/contact/"
    register(path)
    crumb_html, crumb_ld = breadcrumb([("Home", "/"), ("Contact", None)])
    title = "Contact — Phone Repair Near Me"
    desc = "How to get in touch with Phone Repair Near Me, or with a listed repair store directly."
    main_html = f"""
<div class="wrap narrow">{crumb_html}</div>
<section class="hero-suburb wrap narrow">
  <p class="eyebrow">Get in touch</p>
  <h1>Contact.</h1>
  <p class="lede">For a repair, the fastest way is to contact the store directly &mdash; every listing has a call or directions button.</p>
</section>
<section class="wrap narrow prose">
  <p>Want to get your shop listed? Use the <a href="/list-your-shop/">list your shop</a> form and we'll be in touch.</p>
  <p>For anything else about this directory, reach the listed store nearest you &mdash; each listing includes a phone number or store page.</p>
</section>
"""
    write("contact/index.html", page(title, desc, path, main_html, [crumb_ld]))


def build_list_your_shop():
    path = "/list-your-shop/"
    register(path)
    crumb_html, crumb_ld = breadcrumb([("Home", "/"), ("List your shop", None)])
    title = "List Your Repair Shop — Get Found by Local Customers | Phone Repair Near Me"
    desc = "List your phone repair shop on Phone Repair Near Me and get found by customers searching by suburb across Greater Sydney. Free to list, no obligation."

    main_html = f"""
<div class="wrap narrow">{crumb_html}</div>
<section class="hero-suburb wrap narrow">
  <p class="eyebrow">For repair businesses</p>
  <h1>List your shop.</h1>
  <p class="lede">Get found by customers searching for phone repair in your suburb. Tell us about your shop below &mdash; it's free to be listed.</p>
  <div class="hero-image"><img src="/assets/list-your-shop-hero.svg" width="1200" height="600" alt="Illustration of a phone repair storefront with a signup checklist, representing a shop being added to the directory" loading="lazy"></div>
</section>
<section class="band-light">
  <div class="wrap narrow">
    <h2>Why list with us.</h2>
    <div class="benefit-grid">
      <div class="benefit-card" data-reveal="1"><h3>Free to list</h3><p>No cost and no obligation to add your shop to the directory.</p></div>
      <div class="benefit-card" data-reveal="1"><h3>Ranked by distance</h3><p>Customers see your shop sorted by how close it is to them, suburb by suburb.</p></div>
      <div class="benefit-card" data-reveal="1"><h3>Simple to update</h3><p>Send us new hours, services or details any time and we'll update your listing.</p></div>
    </div>
  </div>
</section>
<section class="wrap narrow">
  <h2>Tell us about your shop</h2>
  <form class="form-card" id="list-shop-form">
    <div class="form-grid">
      <label class="field"><span>Business name</span><input type="text" name="business-name" required></label>
      <label class="field"><span>Your name</span><input type="text" name="contact-name" required></label>
      <label class="field"><span>Email</span><input type="email" name="email" required></label>
      <label class="field"><span>Phone number</span><input type="tel" name="phone" required></label>
      <label class="field full"><span>Suburb</span><input type="text" name="suburb" required></label>
    </div>
    <div class="form-actions"><button type="submit" class="btn-primary">Submit listing request</button></div>
  </form>
  <div class="form-success" id="list-shop-success" hidden>
    <h2>Thanks &mdash; we've got your details.</h2>
    <p class="lede">We'll review your shop and get back to you within 2 business days.</p>
    <button type="button" class="btn-outline" id="list-shop-again">Submit another shop</button>
  </div>
</section>
"""
    write("list-your-shop/index.html", page(title, desc, path, main_html, [crumb_ld]))


def build_about():
    path = "/about/"
    register(path)
    crumb_html, crumb_ld = breadcrumb([("Home", "/"), ("About", None)])
    title = "About — Phone Repair Near Me"
    desc = "Phone Repair Near Me is an independent directory built to make finding phone repair services near you easier, suburb by suburb across Greater Sydney."
    main_html = f"""
<div class="wrap narrow">{crumb_html}</div>
<section class="hero-suburb wrap narrow">
  <p class="eyebrow">About us</p>
  <h1>About Phone Repair Near Me.</h1>
  <p class="lede">An independent directory built to make finding phone repair services near you easier.</p>
</section>
<section class="wrap narrow prose">
  <p>Phone Repair Near Me exists for one reason: to make finding a phone repair service nearby easier. We cover every suburb and region across Greater Sydney, ranking listed repairers by distance so you can see who's closest, what they fix and whether they're open right now.</p>
  <p>We're independent &mdash; not affiliated with Apple, Samsung, Google or any other phone manufacturer. Listings are maintained directly with the businesses shown.</p>
  <p>Run a repair shop? <a href="/list-your-shop/">List your shop</a> to get found by customers searching in your suburb.</p>
</section>
"""
    write("about/index.html", page(title, desc, path, main_html, [crumb_ld]))


def build_privacy():
    path = "/privacy/"
    register(path)
    crumb_html, crumb_ld = breadcrumb([("Home", "/"), ("Privacy", None)])
    title = "Privacy Policy — Phone Repair Near Me"
    desc = "How Phone Repair Near Me collects and uses information, including details submitted through the list your shop form."
    main_html = f"""
<div class="wrap narrow">{crumb_html}</div>
<section class="hero-suburb wrap narrow">
  <p class="eyebrow">Legal</p>
  <h1>Privacy policy.</h1>
  <p class="lede">This directory is built to make finding phone repair services easier &mdash; here's how we handle the limited information we collect along the way.</p>
</section>
<section class="wrap narrow prose">
  <h2>What we collect</h2>
  <p>Browsing the directory itself doesn't require an account or any personal details. If you submit the "list your shop" form, we collect what you enter &mdash; business name, contact name, email, phone number and suburb &mdash; so we can review and add your listing.</p>
  <h2>How we use it</h2>
  <p>Information submitted through the listing form is used only to review, add and maintain your shop's listing on this directory. We don't sell or share it with third parties for marketing.</p>
  <h2>Contact</h2>
  <p>If you have questions about this policy or want a listing removed, get in touch using the details on this site.</p>
</section>
"""
    write("privacy/index.html", page(title, desc, path, main_html, [crumb_ld]))


def build_404():
    main_html = """
<section class="wrap narrow prose" style="text-align:center;padding:80px 22px">
  <h1>Page not found</h1>
  <p>That page doesn't exist. Try the <a href="/suburbs/">suburb directory</a> or go back <a href="/">home</a>.</p>
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
    write("assets/hero-repair.svg", HERO_SVG)
    write("assets/list-your-shop-hero.svg", LIST_SHOP_HERO_SVG)
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
.nav-wrap{max-width:1024px;margin:0 auto;height:52px;padding:0 16px;display:flex;align-items:center;justify-content:space-between;gap:12px}
.brand{display:flex;align-items:center;gap:8px;font-weight:600;font-size:15px;color:var(--ink);min-width:0;flex-shrink:1}
.brand-mark{width:22px;height:22px;flex-shrink:0;border-radius:7px;background:var(--ink);color:#fff;display:grid;place-items:center;font-size:12px;font-weight:700}
.brand-text{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nav-links{display:flex;gap:22px;font-size:14px}
.nav-links a{color:var(--ink);opacity:.85}
.nav-links a:hover{opacity:1}
.nav-right{display:flex;align-items:center;gap:10px;flex-shrink:0}
.btn-pill{border-radius:980px;padding:6px 14px;font-size:12px;font-weight:500;white-space:nowrap}
.nav-toggle{display:none;border:0;background:none;font-size:20px;cursor:pointer;flex-shrink:0}
@media(max-width:680px){.nav-links{display:none;position:absolute;top:52px;left:0;right:0;background:#fff;flex-direction:column;padding:16px 22px;border-bottom:1px solid var(--line)}.nav-links.open{display:flex}.nav-toggle{display:block}}
@media(max-width:360px){.btn-pill{padding:5px 9px;font-size:11px}.nav-wrap{gap:8px}}
.hero{text-align:center;padding:72px 22px 0;overflow:hidden}
.hero-image{width:100%;max-width:1100px;margin:clamp(40px,6vw,72px) auto 0;aspect-ratio:16/8;min-height:260px;border-radius:28px 28px 0 0;overflow:hidden}
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
.region-card{display:flex;flex-direction:column;gap:4px;min-width:0;background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px 20px;color:var(--ink)}
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
.map-aside{width:100%;position:sticky;top:72px;border-radius:24px;overflow:hidden;aspect-ratio:3/4;background:var(--bg-light)}
.leaflet-map{width:100%;height:100%}
.shop-card{background:var(--bg-light);border-radius:20px;padding:22px}
.shop-head{display:flex;gap:16px}
.shop-rank{width:40px;height:40px;flex-shrink:0;border-radius:50%;background:#fff;display:grid;place-items:center;font-weight:700}
.shop-main{flex:1;min-width:0}
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
.hero-image img{width:100%;height:100%;object-fit:cover;display:block}
.benefit-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:18px;margin-top:36px}
.benefit-card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:24px}
.benefit-card h3{font-size:17px;margin-bottom:8px}
.benefit-card p{color:var(--sub);font-size:14px;margin:0}
.form-card{background:var(--bg-light);border-radius:24px;padding:clamp(24px,4vw,40px);margin-top:24px}
.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:16px}
.field{display:flex;flex-direction:column;gap:6px;font-size:14px}
.field.full{grid-column:1/-1}
.field input,.field textarea{width:100%;font:inherit;padding:10px 14px;border:1px solid var(--line);border-radius:12px;background:#fff;color:var(--ink)}
.field textarea{resize:vertical;min-height:90px}
.checkbox-grid{display:flex;flex-wrap:wrap;gap:10px 12px}
.checkbox-grid label{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:400;background:#fff;border:1px solid var(--line);border-radius:980px;padding:8px 16px}
.form-actions{margin-top:24px;display:flex;justify-content:flex-end}
.form-actions button{border:0;cursor:pointer}
.form-success{text-align:center;padding:40px 20px}
.form-success button{border:0;cursor:pointer}
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

  var mapEl = document.getElementById('leaflet-map');
  if (mapEl && window.L) {
    try {
      var suburbPt = JSON.parse(mapEl.getAttribute('data-suburb'));
      var shopPts = JSON.parse(mapEl.getAttribute('data-shops'));
      var map = L.map(mapEl, { scrollWheelZoom: false }).setView(suburbPt.ll, 12);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      }).addTo(map);
      var bounds = [suburbPt.ll];
      L.marker(suburbPt.ll).addTo(map).bindPopup(suburbPt.name).openPopup();
      shopPts.forEach(function(s){
        bounds.push(s.ll);
        L.marker(s.ll).addTo(map).bindPopup('<strong>' + s.name + '</strong><br><a href="' + s.maps + '" target="_blank" rel="noopener">Directions</a>');
      });
      map.fitBounds(bounds, { padding: [28, 28] });
    } catch (e) {}
  }

  var shopForm = document.getElementById('list-shop-form');
  if (shopForm) {
    var shopSuccess = document.getElementById('list-shop-success');
    shopForm.addEventListener('submit', function(e){
      e.preventDefault();
      shopForm.hidden = true;
      if (shopSuccess) shopSuccess.hidden = false;
    });
    var shopAgain = document.getElementById('list-shop-again');
    if (shopAgain) shopAgain.addEventListener('click', function(){
      shopForm.reset();
      shopForm.hidden = false;
      if (shopSuccess) shopSuccess.hidden = true;
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

HERO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 800" role="img" aria-label="Top-down illustration of a phone being repaired, with the back open showing the battery and logic board, a screwdriver, tweezers and a tray of screws nearby">
<defs>
<linearGradient id="bg2" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#f5f5f7"/>
<stop offset="1" stop-color="#ffffff"/>
</linearGradient>
<linearGradient id="glass" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#2997ff"/>
<stop offset="1" stop-color="#0071e3"/>
</linearGradient>
</defs>
<rect width="1600" height="800" fill="url(#bg2)"/>
<rect x="940" y="120" width="300" height="600" rx="42" fill="url(#glass)" transform="rotate(8 1090 420)"/>
<rect x="960" y="150" width="60" height="540" rx="30" fill="#ffffff" opacity="0.18" transform="rotate(8 1090 420)"/>
<path d="M1150 260l40 60-30 90" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round" opacity="0.5" transform="rotate(8 1090 420)"/>
<rect x="560" y="120" width="340" height="600" rx="46" fill="#e5e5ea" stroke="#d2d2d7" stroke-width="3"/>
<rect x="700" y="150" width="60" height="10" rx="5" fill="#c7c7cc"/>
<circle cx="800" cy="155" r="7" fill="#c7c7cc"/>
<rect x="590" y="190" width="280" height="230" rx="22" fill="#eaf2fc" stroke="#0071e3" stroke-width="3"/>
<rect x="710" y="178" width="40" height="16" rx="6" fill="#eaf2fc" stroke="#0071e3" stroke-width="3"/>
<rect x="612" y="212" width="236" height="186" rx="12" fill="#ffffff"/>
<rect x="628" y="228" width="140" height="154" rx="8" fill="#0071e3"/>
<rect x="590" y="440" width="280" height="250" rx="18" fill="#ffffff" stroke="#1d1d1f" stroke-width="2"/>
<rect x="614" y="464" width="60" height="44" rx="6" fill="#1d1d1f"/>
<rect x="690" y="464" width="100" height="44" rx="6" fill="#1d1d1f"/>
<rect x="614" y="522" width="156" height="30" rx="6" fill="#1d1d1f"/>
<path d="M614 570h236M614 594h180M614 618h236M614 642h150" stroke="#d2d2d7" stroke-width="4" stroke-linecap="round"/>
<circle cx="820" cy="470" r="10" fill="#0071e3"/>
<g transform="rotate(-35 430 260)">
<rect x="380" y="150" width="28" height="220" rx="14" fill="#1d1d1f"/>
<rect x="372" y="140" width="44" height="40" rx="10" fill="#1d1d1f"/>
<rect x="388" y="364" width="12" height="18" fill="#8e8e93"/>
</g>
<g transform="rotate(20 1220 640)">
<path d="M1190 560l20 150-14 40" fill="none" stroke="#1d1d1f" stroke-width="10" stroke-linecap="round"/>
<path d="M1230 560l-20 150 14 40" fill="none" stroke="#1d1d1f" stroke-width="10" stroke-linecap="round"/>
</g>
<rect x="200" y="540" width="220" height="130" rx="20" fill="#ffffff" stroke="#d2d2d7" stroke-width="3"/>
<circle cx="250" cy="580" r="10" fill="#86868b"/>
<circle cx="290" cy="605" r="10" fill="#86868b"/>
<circle cx="330" cy="580" r="10" fill="#86868b"/>
<circle cx="370" cy="610" r="10" fill="#86868b"/>
<circle cx="250" cy="625" r="10" fill="#86868b"/>
<circle cx="1420" cy="190" r="60" fill="#0071e3"/>
<path d="M1394 192l18 18 36-40" fill="none" stroke="#ffffff" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="180" cy="200" r="7" fill="#d2d2d7"/>
<circle cx="1480" cy="520" r="7" fill="#d2d2d7"/>
<circle cx="900" cy="80" r="6" fill="#d2d2d7"/>
</svg>"""

LIST_SHOP_HERO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600" role="img" aria-label="Illustration of a phone repair storefront with a signup checklist">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#f5f5f7"/>
<stop offset="1" stop-color="#ffffff"/>
</linearGradient>
<pattern id="awning" width="30" height="30" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
<rect width="15" height="30" fill="#1d1d1f"/>
<rect x="15" width="15" height="30" fill="#0071e3"/>
</pattern>
</defs>
<rect width="1200" height="600" fill="url(#bg)"/>
<ellipse cx="520" cy="538" rx="360" ry="20" fill="#e5e5ea"/>
<rect x="120" y="522" width="960" height="4" rx="2" fill="#d2d2d7"/>
<rect x="250" y="230" width="460" height="290" rx="20" fill="#ffffff" stroke="#d2d2d7" stroke-width="2"/>
<rect x="236" y="186" width="488" height="52" rx="10" fill="url(#awning)"/>
<rect x="236" y="230" width="488" height="14" fill="#1d1d1f"/>
<rect x="430" y="140" width="150" height="56" rx="28" fill="#1d1d1f"/>
<circle cx="505" cy="168" r="16" fill="#0071e3"/>
<path d="M497 168l5 6 11-13" fill="none" stroke="#ffffff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
<rect x="286" y="268" width="150" height="180" rx="14" fill="#e8f1fc" stroke="#0071e3" stroke-width="2"/>
<rect x="331" y="298" width="60" height="118" rx="10" fill="#1d1d1f"/>
<rect x="337" y="306" width="48" height="84" rx="3" fill="#eef4fb"/>
<circle cx="361" cy="402" r="4" fill="#eef4fb"/>
<path d="M322 352l40-26 10 14-40 26z" fill="#0071e3" stroke="#ffffff" stroke-width="3" stroke-linejoin="round"/>
<circle cx="322" cy="352" r="7" fill="#0071e3" stroke="#ffffff" stroke-width="3"/>
<rect x="462" y="310" width="100" height="166" rx="8" fill="#1d1d1f"/>
<rect x="470" y="318" width="84" height="40" rx="4" fill="#2c2c2e"/>
<circle cx="545" cy="393" r="5" fill="#ffffff"/>
<rect x="594" y="268" width="130" height="180" rx="14" fill="#fdf2e9" stroke="#bf4800" stroke-width="2"/>
<rect x="616" y="292" width="86" height="118" rx="8" fill="#ffffff" stroke="#1d1d1f" stroke-width="2"/>
<rect x="638" y="282" width="42" height="18" rx="4" fill="#bf4800"/>
<rect x="628" y="316" width="66" height="8" rx="4" fill="#d2d2d7"/>
<rect x="628" y="336" width="66" height="8" rx="4" fill="#d2d2d7"/>
<rect x="628" y="356" width="40" height="8" rx="4" fill="#d2d2d7"/>
<circle cx="686" cy="396" r="18" fill="#0071e3"/>
<path d="M678 396l6 6 13-14" fill="none" stroke="#ffffff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="960" cy="200" r="54" fill="#0071e3"/>
<path d="M938 202l16 16 32-36" fill="none" stroke="#ffffff" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="200" cy="150" r="6" fill="#d2d2d7"/>
<circle cx="860" cy="430" r="6" fill="#d2d2d7"/>
<circle cx="1000" cy="340" r="5" fill="#d2d2d7"/>
<circle cx="170" cy="400" r="5" fill="#d2d2d7"/>
</svg>"""


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
    build_repairs_index()
    build_suburbs_index()
    build_contact()
    build_list_your_shop()
    build_about()
    build_privacy()
    build_404()
    build_robots()
    build_sitemap()
    build_llms_txt()
    write("CNAME", "phonerepairnearme.com.au\n")
    write(".nojekyll", "")
    print(f"Built {len(ALL_URLS)} pages.")


if __name__ == "__main__":
    main()
