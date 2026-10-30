#!/usr/bin/env python3
"""
Theyyam Calendar - static page + SEO asset generator
------------------------------------------------------
Your site currently shows every kavu on one page (index.html) via JavaScript
reading data.csv. Google can struggle to index individual kavu/theyyam
content that way, and there is no single URL to rank for a specific search
like "Parassinikadavu theyyam dates".

This script builds one real, crawlable HTML page per kavu (English content
first, since that is your site's differentiator, Malayalam content below),
plus:

  kavu_pages/<slug>.html   - one static page per kavu, ready to upload
  sitemap.xml              - submit this in Google Search Console
  robots.txt               - starter file
  kavu_links.html          - a plain <ul><li><a>...</a> block of links to
                             every generated page. Paste this into index.html
                             as real, static HTML (not JS-injected) somewhere
                             on the page - e.g. as a footer "Browse all
                             Kaavus" list. Actual <a href> links written
                             directly in the HTML are what let Google's
                             crawler discover and follow through to every
                             kavu page; a JS-only list is far less reliable.

USAGE:
    python3 generate_static_pages.py data.csv https://theyyamcalendar.in

Your actual data.csv headers (already matched below - edit only if your
sheet's column names change):
kavu_id, kavu_name, googlemap_link, kavu_name_e, place, place_e, district,
district_e, start_date, end_date, theyyam_list, theyyam_list_e, kollavarsham,
kollavarsham_e, contact_no, description, description_e, image_url_en,
status, scroll_box, scroll_box_e, neeliyar_kottam, parassini_madappura,
image_url, kativanur_veeran, kandanar_kelan, muchilot_bhagavathy,
perumkaliyattam, thalappoli, theyyam_kettu, thulu_theyyam,
mookambika_gulikan, panchuruli, kozhikode_district_theyyam,
theekuttichathan, Dupli_id_No

(thirumuttam / thirumuttam_e exist in the sheet but aren't used here.)
"""

import base64
import csv
import json
import os
import re
import sys
from datetime import date
from html import escape as h
from urllib.parse import quote
from io import StringIO
from xml.sax.saxutils import escape as x

# Your data.csv has at least one very long cell (likely a long description,
# scroll_box text, or an embedded long URL) that exceeds Python's default
# 131072-byte CSV field limit. Raise it so csv.DictReader doesn't error out.
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)

OUTPUT_DIR = "kavu_pages"

# NOTE: there is intentionally NO fallback image any more. When a kavu has no
# notice image, the page carries no og:image / twitter:image at all, so
# WhatsApp/Facebook/Telegram/X show a plain text card (name + place + dates)
# instead of the site logo.

# Rows whose `status` value (case-insensitive) is in this set are skipped.
# Adjust this list once you know what values your `status` column actually uses.
SKIP_STATUS_VALUES = {"draft", "inactive", "hide", "no"}

# Category/tag columns from your sheet - each is treated as a checkbox
# (see is_truthy below). Whichever ones are set for a row get listed as
# tags on that kavu's page - this also helps that page turn up for
# category-specific searches (e.g. "Kativanur Veeran theyyam kavu list").
# Edit the display labels on the right if you'd like different wording.
TAG_COLUMNS = {
    "kativanur_veeran": "Kativanur Veeran",
    "kandanar_kelan": "Kandanar Kelan",
    "muchilot_bhagavathy": "Muchilot Bhagavathy",
    "perumkaliyattam": "Perumkaliyattam",
    "thalappoli": "Thalappoli",
    "theyyam_kettu": "Theyyam Kettu",
    "thulu_theyyam": "Thulu Theyyam",
    "mookambika_gulikan": "Mookambika Gulikan",
    "panchuruli": "Panchuruli",
    "kozhikode_district_theyyam": "Kozhikode District Theyyam",
    "theekuttichathan": "Theekuttichathan",
    "neeliyar_kottam": "Neeliyar Kottam",
    "parassini_madappura": "Parassini Madappura",
}

# Your sheet marks a tag column as set by putting the literal text "yes"
# in it (blank otherwise) - only that value counts as true.
TRUE_VALUE = "yes"


def is_truthy(value):
    return (value or "").strip().lower() == TRUE_VALUE


def to_direct_image_url(url, base_url=""):
    """Turns whatever is in the sheet's image column into an absolute, directly
    loadable image URL (needed for og:image - WhatsApp/Facebook ignore
    relative paths and HTML pages):
      - Google Drive share link  -> drive thumbnail URL (as the site does)
      - github.com/.../blob/...  -> raw.githubusercontent.com/... (the blob
                                    link is an HTML page, not an image)
      - relative path (notices/x.jpg) -> https://<site>/notices/x.jpg
    Anything else is left as-is."""
    if not url:
        return ""
    url = str(url).strip()
    if not url:
        return ""
    g = re.match(r"https?://github\.com/([^/]+)/([^/]+)/(?:blob|raw)/([^?#]+)", url)
    if g:
        return f"https://raw.githubusercontent.com/{g.group(1)}/{g.group(2)}/{g.group(3)}"
    if base_url and not re.match(r"https?://", url) and not re.search(r"/d/|[?&]id=", url):
        return base_url.rstrip("/") + "/" + quote(re.sub(r"^(\./|/)+", "", url), safe="/%")
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m:
        return f"https://drive.google.com/thumbnail?id={m.group(1)}&sz=w1000"
    return url


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "kavu"


def decode_csv_payload(text):
    """Mirrors the site's client-side decodeCsvPayload(): your data.csv is
    stored base64-encoded (index.html base64-decodes it before parsing).
    A plain csv.DictReader on the raw file therefore sees the whole payload
    as a single unmatched header and reads zero real rows - which is why no
    kavu_pages/ got generated. Decode it the same way the site does; if it
    doesn't look like base64-encoded CSV, fall back to using it as-is."""
    text = (text or "").strip()
    if not text:
        return text
    try:
        decoded = base64.b64decode(text, validate=False).decode("utf-8")
        if "kavu_name" in decoded:
            return decoded
    except Exception:
        pass
    return text


def read_rows(csv_path):
    with open(csv_path, encoding="utf-8-sig") as f:
        raw = f.read()
    content = decode_csv_payload(raw)
    return list(csv.DictReader(StringIO(content)))


def is_primary_row(row):
    """Dupli_id_No is just a manual duplicate-check column the user keeps
    in the sheet for their own reference - it doesn't mean anything about
    whether this row should get a page, so it's not used here."""
    status = (row.get("status") or "").strip().lower()
    if status in SKIP_STATUS_VALUES:
        return False
    return True


def parse_latlon(googlemap_link):
    """Best-effort extraction of lat,lon from a Google Maps URL."""
    if not googlemap_link:
        return None, None
    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", googlemap_link)
    if not m:
        m = re.search(r"q=(-?\d+\.\d+),(-?\d+\.\d+)", googlemap_link)
    if m:
        return m.group(1), m.group(2)
    return None, None


def build_slug_map(rows):
    used = set()
    slugs = {}
    for row in rows:
        kavu_id = (row.get("kavu_id") or "").strip()
        base = row.get("kavu_name_e") or row.get("kavu_name") or kavu_id
        slug = slugify(base)
        if slug in used:
            slug = f"{slug}-{kavu_id}"
        used.add(slug)
        slugs[kavu_id] = slug
    return slugs


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{meta_description}">
<link rel="canonical" href="{page_url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Theyyam Calendar">
<meta property="og:locale" content="{og_locale}">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_description}">
{og_image_tags}<meta property="og:url" content="{page_url}">
<meta name="twitter:card" content="{twitter_card}">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{og_description}">
{twitter_image_tag}<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+Malayalam:wght@400;700&display=swap">
<script type="application/ld+json">
{json_ld}
</script>
<style>
body{{font-family:'Noto Sans Malayalam',Arial,sans-serif;margin:0;padding:0;background-color:#f4e9dc;color:#333;font-size:.95em}}
.container{{max-width:800px;margin:20px auto;padding:16px;background-color:#fffaf6;border-radius:14px;box-shadow:0 4px 20px rgba(0,0,0,.2)}}
.page-header{{background-color:#8f1414;margin:-16px -16px 18px -16px;padding:16px;border-radius:14px 14px 0 0;text-align:center}}
.page-header h1{{color:#fff;margin:0;font-size:1.4em}}
.back-link{{display:inline-block;margin-top:8px;color:gold;text-decoration:none;font-weight:700;font-size:.85em}}
.content-box{{background:#fff;border:2px solid #c62828;border-radius:10px;padding:18px;line-height:1.7}}
.content-box h2{{color:#c62828;margin-top:22px}}
.meta-line{{color:#555;font-size:.9em;margin:4px 0}}
img.kavu-photo{{max-width:100%;border-radius:8px;margin:10px 0}}
.tags{{margin:10px 0}}
.tags .tag{{display:inline-block;background:#fceceb;color:#7a1414;border-radius:12px;padding:3px 10px;font-size:.82em;margin:2px 4px 2px 0}}
</style>
</head>
<body>
<div class="container">
  <div class="page-header">
    <h1>{h1_name}</h1>
    <a class="back-link" href="../index.html">&larr; Back to Theyyam Calendar</a>
  </div>
  <div class="content-box">
    <h2>English</h2>
    <p class="meta-line"><strong>Place:</strong> {place_e}, {district_e}</p>
    <p class="meta-line"><strong>Dates:</strong> {start_date} {end_date_str}</p>
    <p class="meta-line"><strong>Theyyams:</strong> {theyyam_list_e}</p>
    {kollavarsham_e_line}
    {contact_line}
    {image_en_html}
    <p>{description_e}</p>
    {scroll_box_e_html}
    {tags_html}
    {map_link_html}

    <h2>മലയാളം</h2>
    <p class="meta-line"><strong>സ്ഥലം:</strong> {place}, {district}</p>
    <p class="meta-line"><strong>തെയ്യങ്ങൾ:</strong> {theyyam_list}</p>
    {kollavarsham_line}
    {image_ml_html}
    <p>{description}</p>
    {scroll_box_html}
    {hindi_section}
  </div>
</div>
</body>
</html>
"""


def fmt_date(value):
    """'2027-01-30' -> '30 Jan 2027'. Anything unparseable is returned as-is."""
    v = (value or "").strip()
    try:
        d = date.fromisoformat(v[:10])
        return f"{d.day} {d.strftime('%b %Y')}"
    except ValueError:
        return v


def line(label, value):
    return f"<p class=\"meta-line\"><strong>{h(label)}</strong> {h(value)}</p>" if value else ""


MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "ml": ["ജനുവരി", "ഫെബ്രുവരി", "മാർച്ച്", "ഏപ്രിൽ", "മേയ്", "ജൂൺ", "ജൂലൈ", "ഓഗസ്റ്റ്", "സെപ്റ്റംബർ", "ഒക്ടോബർ", "നവംബർ", "ഡിസംബർ"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
}


def _parse_day(value):
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return None


def fmt_range(lang, start, end):
    """Share-card date text, written fully in the page's own language:
    en '2 to 3 Nov 2026', ml '2 മുതൽ 3 നവംബർ 2026 വരെ', hi '2 से 3 नवंबर 2026'."""
    s_d, e_d = _parse_day(start), _parse_day(end)
    if not s_d:
        return (start or "").strip()
    m = MONTHS[lang]
    if not e_d or e_d == s_d:
        return f"{s_d.day} {m[s_d.month - 1]} {s_d.year}"
    if s_d.year == e_d.year and s_d.month == e_d.month:
        a = f"{s_d.day}"
    elif s_d.year == e_d.year:
        a = f"{s_d.day} {m[s_d.month - 1]}"
    else:
        a = f"{s_d.day} {m[s_d.month - 1]} {s_d.year}"
    b = f"{e_d.day} {m[e_d.month - 1]} {e_d.year}"
    if lang == "ml":
        return f"{a} മുതൽ {b} വരെ"
    if lang == "hi":
        return f"{a} से {b}"
    return f"{a} to {b}"


def pick_image(row, lang, base_url):
    """Notice image for this language's page - same order the website uses.
    Returns "" when the kavu has no notice image at all (-> text-only card)."""
    en = row.get("image_url_en") or ""
    ml = row.get("image_url") or ""
    hi = row.get("image_url_hi") or ""
    order = {"ml": [ml, en], "en": [en, ml], "hi": [hi, en, ml]}[lang]
    for cand in order:
        url = to_direct_image_url(cand, base_url)
        if url:
            return url
    return ""


PAGE_SUFFIX = {"en": "", "ml": "-ml", "hi": "-hi"}
OG_LOCALE = {"en": "en_IN", "ml": "ml_IN", "hi": "hi_IN"}


def build_page(row, slug, base_url, lang="en"):
    name_e = row.get("kavu_name_e") or row.get("kavu_name") or "Theyyam Kavu"
    name_ml = row.get("kavu_name") or name_e
    name_h = row.get("kavu_name_h") or name_e
    place_e = row.get("place_e") or ""
    place_ml = row.get("place") or ""
    place_h = row.get("place_h") or place_e
    district_e = row.get("district_e") or ""
    district_ml = row.get("district") or ""
    district_h = row.get("district_h") or district_e
    start_date = row.get("start_date") or ""
    end_date_val = row.get("end_date") or ""
    theyyam_list_e = row.get("theyyam_list_e") or ""
    theyyam_list_ml = row.get("theyyam_list") or ""
    theyyam_list_h = row.get("theyyam_list_h") or theyyam_list_e
    description_e = row.get("description_e") or ""
    description_ml = row.get("description") or ""
    description_h = row.get("description_h") or ""
    image_en = row.get("image_url_en") or ""
    image_ml = row.get("image_url") or ""
    image_hi = row.get("image_url_hi") or ""
    contact_no = row.get("contact_no") or ""
    kollavarsham_e = row.get("kollavarsham_e") or ""
    kollavarsham_ml = row.get("kollavarsham") or ""
    kollavarsham_h = row.get("kollavarsham_h") or ""
    scroll_box_e = row.get("scroll_box_e") or ""
    scroll_box_ml = row.get("scroll_box") or ""
    maplink = row.get("googlemap_link") or ""

    active_tags = [label for col, label in TAG_COLUMNS.items() if is_truthy(row.get(col))]

    page_url = f"{base_url.rstrip('/')}/kavu_pages/{slug}{PAGE_SUFFIX[lang]}.html"

    dash_end = f" - {end_date_val}" if end_date_val else ""
    if lang == "ml":
        nm, pl, di, ty = name_ml, place_ml, district_ml, theyyam_list_ml
        title = f"{name_ml} - {theyyam_list_ml or name_ml} | Theyyam Calendar"
        meta_desc = f"{theyyam_list_ml or name_ml}, {place_ml}, {district_ml}. {start_date}{dash_end}"
    elif lang == "hi":
        nm, pl, di, ty = name_h, place_h, district_h, theyyam_list_h
        title = f"{name_h} - {theyyam_list_h or name_h} | Theyyam Calendar"
        meta_desc = f"{theyyam_list_h or name_h}, {place_h}, {district_h}. {start_date}{dash_end}"
    else:
        nm, pl, di, ty = name_e, place_e, district_e, theyyam_list_e
        title = f"{name_e} Kaliyattam & Theyyam Dates | Theyyam Calendar"
        meta_desc = f"{theyyam_list_e or name_e} at {place_e}, {district_e}. Dates: {start_date}{' to ' + end_date_val if end_date_val else ''}."

    # Share card (WhatsApp / Facebook / Telegram / X): title = kavu name only,
    # description = dates + place, both in the page's own language.
    og_title = nm
    place_line = ", ".join(q for q in [pl, di] if q)
    og_description = " \u00b7 ".join(p for p in [fmt_range(lang, start_date, end_date_val), place_line] if p)

    og_image = pick_image(row, lang, base_url)
    if og_image:
        og_image_tags = f'<meta property="og:image" content="{h(og_image)}">\n'
        twitter_image_tag = f'<meta name="twitter:image" content="{h(og_image)}">\n'
        twitter_card = "summary_large_image"
    else:
        og_image_tags = ""
        twitter_image_tag = ""
        twitter_card = "summary"

    lat, lon = parse_latlon(maplink)
    place_obj = {
        "@type": "Place",
        "name": place_e or name_e,
        "address": {
            "@type": "PostalAddress",
            "addressLocality": district_e or district_ml,
            "addressRegion": "Kerala",
            "addressCountry": "IN",
        },
    }
    if lat and lon:
        place_obj["geo"] = {"@type": "GeoCoordinates", "latitude": float(lat), "longitude": float(lon)}

    json_ld = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": f"{theyyam_list_e or name_e} - Kaliyattam",
        "startDate": start_date,
        "endDate": end_date_val or start_date,
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "eventStatus": "https://schema.org/EventScheduled",
        "location": place_obj,
        "description": description_e or description_ml,
        "url": page_url,
    }
    if og_image:
        json_ld["image"] = og_image
    if active_tags:
        json_ld["keywords"] = ", ".join(active_tags)

    hindi_section = ""
    if any(row.get(k) for k in ("kavu_name_h", "place_h", "theyyam_list_h", "description_h")):
        img_hi_html = ""
        if image_hi and image_hi not in (image_en, image_ml):
            img_hi_html = f'<img class="kavu-photo" src="{h(to_direct_image_url(image_hi, base_url))}" alt="{h(name_h)}">'
        hindi_section = (
            "<h2>हिन्दी</h2>\n"
            f'    <p class="meta-line"><strong>स्थान:</strong> {h(place_h)}, {h(district_h)}</p>\n'
            f'    <p class="meta-line"><strong>तेय्यम:</strong> {h(theyyam_list_h)}</p>\n'
            f"    {line('कोल्लवर्षम:', kollavarsham_h)}\n"
            f"    {img_hi_html}\n"
            f"    <p>{h(description_h)}</p>"
        )

    html = PAGE_TEMPLATE.format(
        lang=lang,
        og_locale=OG_LOCALE[lang],
        og_title=h(og_title),
        og_description=h(og_description),
        og_image_tags=og_image_tags,
        twitter_card=twitter_card,
        twitter_image_tag=twitter_image_tag,
        title=h(title),
        meta_description=h(meta_desc),
        page_url=h(page_url),
        json_ld=json.dumps(json_ld, ensure_ascii=False, indent=2),
        h1_name=h(nm),
        place_e=h(place_e),
        district_e=h(district_e),
        start_date=h(start_date),
        end_date_str=(f"&ndash; {h(end_date_val)}" if end_date_val else ""),
        theyyam_list_e=h(theyyam_list_e),
        kollavarsham_e_line=line("Kollavarsham year:", kollavarsham_e),
        contact_line=line("Contact:", contact_no),
        image_en_html=(f'<img class="kavu-photo" src="{h(to_direct_image_url(image_en, base_url))}" alt="{h(name_e)}">' if image_en else ""),
        description_e=h(description_e),
        scroll_box_e_html=(f"<p><em>{h(scroll_box_e)}</em></p>" if scroll_box_e else ""),
        tags_html=(
            '<div class="tags">' + "".join(f'<span class="tag">{h(t)}</span>' for t in active_tags) + "</div>"
            if active_tags else ""
        ),
        map_link_html=(f'<p><a href="{h(maplink)}" target="_blank" rel="noopener">View on Google Maps</a></p>' if maplink else ""),
        place=h(place_ml),
        district=h(district_ml),
        theyyam_list=h(theyyam_list_ml),
        kollavarsham_line=line("കൊല്ലവർഷം:", kollavarsham_ml),
        image_ml_html=(f'<img class="kavu-photo" src="{h(to_direct_image_url(image_ml, base_url))}" alt="{h(name_ml)}">' if image_ml and image_ml != image_en else ""),
        description=h(description_ml),
        scroll_box_html=(f"<p><em>{h(scroll_box_ml)}</em></p>" if scroll_box_ml else ""),
        hindi_section=hindi_section,
    )
    return html, name_e, place_e, district_e


def build_sitemap(entries, base_url):
    base_url = base_url.rstrip("/")
    today = date.today().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <url><loc>{x(base_url)}/</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.9</priority></url>",
    ]
    for slug, _, _, _ in entries:
        loc = f"{base_url}/kavu_pages/{slug}.html"
        lines.append(
            f"  <url><loc>{x(loc)}</loc><lastmod>{today}</lastmod>"
            f"<changefreq>monthly</changefreq><priority>0.6</priority></url>"
        )
    lines.append("</urlset>")
    return "\n".join(lines)


def build_links_block(entries, base_url):
    base_url = base_url.rstrip("/")
    items = []
    for slug, name_e, place_e, district_e in sorted(entries, key=lambda e: e[3] or ""):
        label = f"{name_e} – {place_e}, {district_e}" if place_e else name_e
        items.append(f'  <li><a href="kavu_pages/{h(slug)}.html">{h(label)}</a></li>')
    return '<ul id="all-kavus">\n' + "\n".join(items) + "\n</ul>"


LINKS_START_MARKER = "<!-- KAVU_LINKS_START -->"
LINKS_END_MARKER = "<!-- KAVU_LINKS_END -->"


def inject_links_into_index(index_path, links_html):
    """If index.html contains the two marker comments, replace everything
    between them with the current links list - so a CI job can keep
    index.html's crawlable link list in sync automatically, every run.
    Add the two marker comments (on their own lines) into index.html once,
    by hand, wherever you want the list to appear; after that this
    function keeps the content between them up to date on every run.
    If the markers aren't found, index.html is left untouched."""
    if not os.path.exists(index_path):
        return False
    with open(index_path, encoding="utf-8") as f:
        content = f.read()
    if LINKS_START_MARKER not in content or LINKS_END_MARKER not in content:
        return False
    pattern = re.compile(
        re.escape(LINKS_START_MARKER) + r".*?" + re.escape(LINKS_END_MARKER),
        re.DOTALL,
    )
    new_block = f"{LINKS_START_MARKER}\n{links_html}\n{LINKS_END_MARKER}"
    content = pattern.sub(new_block, content, count=1)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def build_robots_txt(base_url):
    base_url = base_url.rstrip("/")
    return f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n"


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 generate_static_pages.py <path-to-data.csv> <site-base-url>")
        sys.exit(1)

    csv_path, base_url = sys.argv[1], sys.argv[2]
    rows = read_rows(csv_path)
    rows = [r for r in rows if is_primary_row(r)]
    slug_map = build_slug_map(rows)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    entries = []
    for row in rows:
        kavu_id = (row.get("kavu_id") or "").strip()
        slug = slug_map.get(kavu_id, slugify(kavu_id or "kavu"))

        for lang in ("en", "ml", "hi"):
            page_html, name_e, place_e, district_e = build_page(row, slug, base_url, lang=lang)
            with open(os.path.join(OUTPUT_DIR, f"{slug}{PAGE_SUFFIX[lang]}.html"), "w", encoding="utf-8") as f:
                f.write(page_html)

        entries.append((slug, name_e, place_e, district_e))

    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(build_sitemap(entries, base_url))

    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write(build_robots_txt(base_url))

    # kavu_id -> slug map, read by index.html so the "Share" button links
    # straight to that kavu's static page (which carries the correct
    # og:image) instead of the old ?date=&row= link, which always showed
    # the site logo in WhatsApp/social previews.
    with open("kavu_slugs.json", "w", encoding="utf-8") as f:
        json.dump(slug_map, f, ensure_ascii=False)

    # No public link list is written or injected into index.html on purpose -
    # the sitemap.xml above is what gets these pages indexed by Google;
    # index.html stays as it is, so there's no one-click browsable list of
    # every kavu on the site itself.

    print(f"Generated {len(entries)} kavus x 3 language variants = {len(entries) * 3} pages in ./{OUTPUT_DIR}/")
    print("Also wrote: sitemap.xml, robots.txt, kavu_slugs.json")
    print("\nNext steps:")
    print(f"1. Upload the whole '{OUTPUT_DIR}' folder, sitemap.xml and robots.txt to your site.")
    print("2. Submit sitemap.xml in Google Search Console -> Sitemaps.")


if __name__ == "__main__":
    main()
