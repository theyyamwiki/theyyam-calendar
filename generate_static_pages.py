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

import csv
import json
import os
import re
import sys
from datetime import date
from html import escape as h
from xml.sax.saxutils import escape as x

# Your data.csv has at least one very long cell (likely a long description,
# scroll_box text, or an embedded long URL) that exceeds Python's default
# 131072-byte CSV field limit. Raise it so csv.DictReader doesn't error out.
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)

OUTPUT_DIR = "kavu_pages"

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


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "kavu"


def read_rows(csv_path):
    with open(csv_path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


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
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{meta_description}">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+Malayalam:wght@400;700&display=swap">
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
    <h1>{name_e}</h1>
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
  </div>
</div>
</body>
</html>
"""


def line(label, value):
    return f"<p class=\"meta-line\"><strong>{h(label)}</strong> {h(value)}</p>" if value else ""


def build_page(row, slug, base_url):
    name_e = row.get("kavu_name_e") or row.get("kavu_name") or "Theyyam Kavu"
    name_ml = row.get("kavu_name") or name_e
    place_e = row.get("place_e") or ""
    place_ml = row.get("place") or ""
    district_e = row.get("district_e") or ""
    district_ml = row.get("district") or ""
    start_date = row.get("start_date") or ""
    end_date_val = row.get("end_date") or ""
    theyyam_list_e = row.get("theyyam_list_e") or ""
    theyyam_list_ml = row.get("theyyam_list") or ""
    description_e = row.get("description_e") or ""
    description_ml = row.get("description") or ""
    image_en = row.get("image_url_en") or ""
    image_ml = row.get("image_url") or ""
    contact_no = row.get("contact_no") or ""
    kollavarsham_e = row.get("kollavarsham_e") or ""
    kollavarsham_ml = row.get("kollavarsham") or ""
    scroll_box_e = row.get("scroll_box_e") or ""
    scroll_box_ml = row.get("scroll_box") or ""
    maplink = row.get("googlemap_link") or ""

    active_tags = [label for col, label in TAG_COLUMNS.items() if is_truthy(row.get(col))]

    title = f"{name_e} Kaliyattam & Theyyam Dates | Theyyam Calendar"
    meta_desc = f"{theyyam_list_e or name_e} at {place_e}, {district_e}. Dates: {start_date}{' to ' + end_date_val if end_date_val else ''}."

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
        "url": f"{base_url}/kavu_pages/{slug}.html",
    }
    if image_en or image_ml:
        json_ld["image"] = image_en or image_ml
    if active_tags:
        json_ld["keywords"] = ", ".join(active_tags)

    html = PAGE_TEMPLATE.format(
        title=h(title),
        meta_description=h(meta_desc),
        json_ld=json.dumps(json_ld, ensure_ascii=False, indent=2),
        name_e=h(name_e),
        place_e=h(place_e),
        district_e=h(district_e),
        start_date=h(start_date),
        end_date_str=(f"&ndash; {h(end_date_val)}" if end_date_val else ""),
        theyyam_list_e=h(theyyam_list_e),
        kollavarsham_e_line=line("Kollavarsham year:", kollavarsham_e),
        contact_line=line("Contact:", contact_no),
        image_en_html=(f'<img class="kavu-photo" src="{h(image_en)}" alt="{h(name_e)}">' if image_en else ""),
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
        image_ml_html=(f'<img class="kavu-photo" src="{h(image_ml)}" alt="{h(name_ml)}">' if image_ml and image_ml != image_en else ""),
        description=h(description_ml),
        scroll_box_html=(f"<p><em>{h(scroll_box_ml)}</em></p>" if scroll_box_ml else ""),
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
        html, name_e, place_e, district_e = build_page(row, slug, base_url)
        with open(os.path.join(OUTPUT_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
            f.write(html)
        entries.append((slug, name_e, place_e, district_e))

    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(build_sitemap(entries, base_url))

    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write(build_robots_txt(base_url))

    with open("kavu_links.html", "w", encoding="utf-8") as f:
        f.write(build_links_block(entries, base_url))

    injected = inject_links_into_index("index.html", build_links_block(entries, base_url))

    print(f"Generated {len(entries)} pages in ./{OUTPUT_DIR}/")
    print("Also wrote: sitemap.xml, robots.txt, kavu_links.html")
    if injected:
        print("index.html: link list auto-updated between KAVU_LINKS markers.")
    else:
        print(
            "index.html: markers not found, so it was NOT modified. Add these two\n"
            "lines to index.html once, wherever you want the link list to show:\n"
            f"  {LINKS_START_MARKER}\n  {LINKS_END_MARKER}\n"
            "After that, this script fills in the content between them automatically."
        )
    print("\nNext steps:")
    print(f"1. Upload the whole '{OUTPUT_DIR}' folder, sitemap.xml and robots.txt to your site.")
    print("2. Submit sitemap.xml in Google Search Console -> Sitemaps.")


if __name__ == "__main__":
    main()
