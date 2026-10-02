"""Scrape the front pages, mirror every article image and write the site GitHub Pages serves.

    python build_site.py --base-url https://<user>.github.io/<repo> --out site

Writes <out>/tagesspiegel.json (same format the scraper makes, but "image" points at the
mirrored copy and the original URL moves to "image_source") and <out>/images/*.jpg.
"""
import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import requests
from PIL import Image

HERE = Path(__file__).parent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}
MAX_SIZE = 1400  # the game shows the image phone-wide; anything bigger only costs memory
MAX_BYTES = 15_000_000


def slug(text):
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def mirror_image(url, name, images_dir):
    """Download url, shrink it, save it as a JPEG and return the file name."""
    res = requests.get(url, headers=HEADERS, timeout=20)
    res.raise_for_status()
    if len(res.content) > MAX_BYTES:
        raise ValueError("image is too large")
    img = Image.open(io.BytesIO(res.content))
    img.thumbnail((MAX_SIZE, MAX_SIZE))
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, "JPEG", quality=85, optimize=True)
    data = buffer.getvalue()
    # the hash is in the name, so a new picture never hides behind a cached old one
    file = f"{slug(name)}-{hashlib.sha1(data).hexdigest()[:8]}.jpg"
    (images_dir / file).write_bytes(data)
    return file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True, help="where the site will be served")
    parser.add_argument("--out", default="site")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    out = Path(args.out)
    images_dir = out / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run([sys.executable, str(HERE / "tagesspiegel.py")], cwd=HERE, check=True)
    articles = json.loads((HERE / "tagesspiegel.json").read_text(encoding="utf-8"))

    # Don't replace yesterday's good data with a broken scrape.
    ok = [a for a in articles if "spacy" in a]
    if not any(a["source"] == "Tagesspiegel" for a in ok) or len(ok) < len(articles) / 2:
        sys.exit(f"Not publishing: only {len(ok)} of {len(articles)} articles were scraped "
                 "(or Tagesspiegel is missing).")

    for article in ok:
        source_url = article.get("image")
        article["image_source"] = source_url
        article["image"] = None
        if not source_url:
            continue
        try:
            file = mirror_image(source_url, article["source"], images_dir)
            article["image"] = f"{base_url}/images/{file}"
        except Exception as e:  # one broken picture must not stop the rest
            print(f"!! image {article['source']}: {e}")

    (out / "tagesspiegel.json").write_text(
        json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"published {len(ok)} articles, {len(list(images_dir.iterdir()))} images -> {out}/")


if __name__ == "__main__":
    main()
