# hatschiapp-data

Scrapes the front page of 15 German newspapers once a day and publishes the result with GitHub Pages
for the hatschiapp game.

- `tagesspiegel.py` – the scraper (headline, teaser, link, image, spaCy word types)
- `build_site.py` – runs the scraper, mirrors the article images (shrunk JPEGs) and writes `site/`
- `.github/workflows/news.yml` – runs it daily, on every push and on demand, then deploys `site/`

The game downloads `tagesspiegel.json`; its `image` fields point at the mirrored files under `images/`.
If a run scrapes too little (Tagesspiegel missing or fewer than half the sites), nothing is deployed and the
previous day's data stays up.
