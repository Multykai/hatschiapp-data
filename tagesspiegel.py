import json
from urllib.parse import urljoin

import requests
import spacy
from bs4 import BeautifulSoup

# name -> (homepage, optional CSS selector for the first article link)
# Without a selector the first <article> with a linked heading is used.
websites = {
    "Tagesspiegel": ("https://www.tagesspiegel.de/", 'article[data-bi-hook="teaser"] a[href$=".html"]'),
    "Bild": ("https://www.bild.de/", None),
    "Die Zeit": ("https://www.zeit.de/index", None),
    "taz": ("https://taz.de/", None),
    "Die Welt": ("https://www.welt.de/", None),
    "Der Spiegel": ("https://www.spiegel.de/", None),
    "Handelsblatt": ("https://www.handelsblatt.com/", "a:has(app-teaser-headline)"),
    "Süddeutsche Zeitung": ("https://www.sueddeutsche.de/", None),
    "NZZ": ("https://www.nzz.ch/", None),
    "Tagesschau": ("https://www.tagesschau.de/", "a.teaser__link"),
    "FAZ": ("https://www.faz.net/aktuell/", None),
    "Focus": ("https://www.focus.de/", None),
    "Neues Deutschland": ("https://www.nd-aktuell.de/", "article .Title a"),
    "Junge Freiheit": ("https://jungefreiheit.de/", None),
    "junge Welt": ("https://www.jungewelt.de/", "h2 a"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}
nlp = spacy.load("de_core_news_sm")


def get_soup(url):
    res = requests.get(url, headers=HEADERS, timeout=20)
    res.raise_for_status()
    return BeautifulSoup(res.content, "html.parser")


def find_first_link(soup, selector):
    if selector:
        a = soup.select_one(selector)
        if a and a.get("href"):
            return a["href"]
    for art in soup.find_all("article"):
        h = art.find(["h1", "h2", "h3", "h4"])
        if not h:
            continue
        a = h.find_parent("a") or h.find("a") or art.find("a")
        if a and a.get("href"):
            return a["href"]
    return None


def meta(soup, *names):
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def json_ld_author(soup):
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            for node in item.get("@graph", [item]) if isinstance(item, dict) else []:
                author = node.get("author")
                if isinstance(author, list):
                    author = author[0] if author else None
                if isinstance(author, dict):
                    author = author.get("name")
                if isinstance(author, str) and author.strip():
                    return author.strip()
    return None


def get_author(page):
    # some sites put a profile URL into the author meta tag
    candidates = [meta(page, "author", "article:author"), json_ld_author(page)]
    return next((a for a in candidates if a and not a.startswith("http")), None)


def analyze(title):
    return [{"text": t.text, "pos": t.pos_, "tag": t.tag_} for t in nlp(title)]


def first_article(name, home, selector=None):
    soup = get_soup(home)
    href = find_first_link(soup, selector)
    if not href:
        raise ValueError("no article link found")
    link = urljoin(home, href)

    page = get_soup(link)
    h1 = page.find("h1")
    title = meta(page, "og:title", "twitter:title") or (h1.get_text(" ", strip=True) if h1 else None)
    image = meta(page, "og:image", "twitter:image")

    return {
        "source": name,
        "title": title,
        "teaser": meta(page, "og:description", "description"),
        "link": link,
        "image": urljoin(link, image) if image else None,
        "author": get_author(page),
        "spacy": analyze(title) if title else [],
    }


if __name__ == "__main__":
    results = []
    for name, (home, selector) in websites.items():
        try:
            results.append(first_article(name, home, selector))
        except Exception as e:
            print(f"!! {name}: {e}")
            results.append({"source": name, "error": str(e)})

    with open("tagesspiegel.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"saved {len(results)} entries to tagesspiegel.json")
