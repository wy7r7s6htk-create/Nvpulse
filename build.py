"""Fetch Nvidia news from several sources and rebuild index.html.

Standard library only, nothing to install. If a source fails it is skipped
and the others still show. If every source fails, index.html is left alone.
"""
import html
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# The SEC asks every script to identify itself. Put your own email here.
USER_AGENT = "NVPulse/1.0 your-email@example.com"
MAX_ITEMS = 6
ATOM = "{http://www.w3.org/2005/Atom}"


def sec(form):
    return ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            "&CIK=0001045810&type=%s&dateb=&owner=include&count=20&output=atom" % form)


def gnews(query):
    return ("https://news.google.com/rss/search?q=%s&hl=en-US&gl=US&ceid=US:en"
            % urllib.parse.quote_plus(query))


# (title, description, [feed urls])  - several urls are merged into one list
SOURCES = [
    ("Nvidia Newsroom", "Official press releases from Nvidia",
     ["https://nvidianews.nvidia.com/releases.xml"]),
    ("Quarterly and annual reports", "Nvidia 10-Q and 10-K filings from the SEC",
     [sec("10-Q"), sec("10-K")]),
    ("Earnings releases and filings", "Nvidia 8-K filings from the SEC, which include earnings releases",
     [sec("8-K")]),
    ("Yahoo Finance", "NVDA headlines from Yahoo Finance",
     ["https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA&region=US&lang=en-US"]),
    ("MarketWatch", "Nvidia stories from MarketWatch",
     [gnews("nvidia site:marketwatch.com")]),
    ("Reuters, CNBC and Bloomberg", "Nvidia stories from three major newsrooms",
     [gnews("nvidia (site:reuters.com OR site:cnbc.com OR site:bloomberg.com)")]),
    ("Barron's, Motley Fool and Seeking Alpha", "Analysis and opinion on Nvidia",
     [gnews("nvidia (site:barrons.com OR site:fool.com OR site:seekingalpha.com)")]),
]

EPOCH = datetime.min.replace(tzinfo=timezone.utc)


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


def fetch_one(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        root = ET.fromstring(resp.read())
    raw = [(i.findtext("title"), i.findtext("link"), i.findtext("pubDate"))
           for i in root.iter("item")]                       # RSS
    for e in root.iter(ATOM + "entry"):                      # Atom (SEC)
        link = e.find(ATOM + "link")
        raw.append((e.findtext(ATOM + "title"),
                    link.get("href") if link is not None else "",
                    e.findtext(ATOM + "updated")))
    out = []
    for title, link, date in raw:
        title, link = (title or "").strip(), (link or "").strip()
        if title and link.startswith("https://"):
            out.append((title, link, parse_date(date)))
    return out


def fetch_source(urls):
    items, last_error = [], None
    for url in urls:
        try:
            items += fetch_one(url)
        except Exception as exc:
            last_error = exc
    if not items and last_error:
        raise last_error
    seen, unique = set(), []
    for it in sorted(items, key=lambda x: x[2] or EPOCH, reverse=True):
        if it[1] not in seen:
            seen.add(it[1])
            unique.append(it)
    return unique[:MAX_ITEMS]


def main():
    sections, newest = [], None
    for name, blurb, urls in SOURCES:
        try:
            items = fetch_source(urls)
        except Exception as exc:
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
            '<div class="src"><h3>{}</h3><p class="blurb">{}</p>'
            '<ul class="news">{}</ul></div>'.format(
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
