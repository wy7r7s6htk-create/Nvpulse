"""Fetch several Nvidia news feeds and rebuild index.html from template.html.

Standard library only, nothing to install. If one source fails, the others
still show. If every source fails, the old index.html is left untouched.
"""
import html
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# SEC asks every script to identify itself. Put your own email here.
USER_AGENT = "NVPulse/1.0 bruno.mg.horta@gmail.com"
MAX_ITEMS = 8
ATOM = "{http://www.w3.org/2005/Atom}"

SOURCES = [
    ("Nvidia Newsroom", "Official press releases",
     "https://nvidianews.nvidia.com/releases.xml"),
    ("SEC filings", "Official filings (8-K, 10-Q, 10-K, insider forms)",
     "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001045810&type=&dateb=&owner=include&count=20&output=atom"),
    ("Market news", "Headlines from many outlets via Google News",
     "https://news.google.com/rss/search?q=nvidia+stock+OR+nvda&hl=en-US&gl=US&ceid=US:en"),
    ("Chips and hardware", "Tom's Hardware coverage",
     "https://www.tomshardware.com/uk/feeds/tag/nvidia"),
]


def parse_date(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        d = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        root = ET.fromstring(resp.read())
    items = []
    for item in root.iter("item"):  # RSS
        items.append((item.findtext("title"), item.findtext("link"),
                      item.findtext("pubDate")))
    for entry in root.iter(ATOM + "entry"):  # Atom (SEC)
        link = entry.find(ATOM + "link")
        items.append((entry.findtext(ATOM + "title"),
                      link.get("href") if link is not None else "",
                      entry.findtext(ATOM + "updated")))
    out = []
    for title, link, date in items:
        title, link = (title or "").strip(), (link or "").strip()
        if title and link.startswith("https://"):
            out.append((title, link, parse_date(date)))
    out.sort(key=lambda x: x[2] or datetime.min.replace(tzinfo=timezone.utc),
             reverse=True)
    return out[:MAX_ITEMS]


def main():
    sections, newest = [], None
    for name, blurb, url in SOURCES:
        try:
            items = fetch(url)
        except Exception as exc:  # keep going if one source is down
            print("Skipped", name, "-", exc)
            continue
        if not items:
            print("Skipped", name, "- no items")
            continue
        rows = []
        for title, link, d in items:
            when = d.strftime("%d %b %Y").lstrip("0") if d else ""
            if d and (newest is None or d > newest):
                newest = d
            rows.append('<li><a href="{}">{}</a><small>{}</small></li>'.format(
                html.escape(link, quote=True), html.escape(title), when))
        sections.append(
            '<h3>{}</h3><p class="blurb">{}</p><ul class="news sans">{}</ul>'.format(
                html.escape(name), html.escape(blurb), "\n".join(rows)))
        print("OK", name, len(items))

    if not sections:
        sys.exit("Every source failed; leaving the page unchanged.")

    with open("template.html", encoding="utf-8") as f:
        page = f.read()
    page = page.replace("{{SECTIONS}}", "\n".join(sections))
    page = page.replace(
        "{{UPDATED}}", newest.strftime("%d %b %Y").lstrip("0") if newest else "n/a")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)


if __name__ == "__main__":
    main()
