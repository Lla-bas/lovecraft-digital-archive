#!/usr/bin/env python3
"""
Build a Lovecraft corpus from hplovecraft.com.

Run once: python corpus.py

Produces:
    cache/<category>/<slug>.aspx.txt   downloaded bodies
    data/manifest.json                 titles + source URLs
    data/lovecraft.jsonl               final corpus
"""

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------- Constants ----------

BASE = "https://hplovecraft.com"
CATEGORIES = ("fiction", "poetry", "essays", "letters")

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
DATA_DIR = BASE_DIR / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"
CORPUS_PATH = DATA_DIR / "lovecraft.jsonl"

USER_AGENT = "lovecraft-corpus/1.0"
TIMEOUT = 30
DELAY = 1.0         # seconds between requests
MIN_CHARS = 75     # drop shorter fragments

SLUG_RE = re.compile(r"^[a-z0-9-]+\.aspx$")
SKIP_SLUGS = {"chrono.aspx", "index.aspx", "publish.aspx", "contents.aspx"}


# ---------- Extraction ----------

def extract_text(html_bytes: bytes) -> str | None:
    """
    Pull the body from a text page.

    Prose: <p> paragraphs joined by blank lines; <br> becomes newline.
    Poetry (no <p>): line breaks preserved via separator="\\n".
    Returns None if no body div is found.
    """

    soup = BeautifulSoup(html_bytes, "html.parser")
    blocks: list[str] = []
    for div in soup.find_all("div", {"align": "justify"}):
        paras = div.find_all("p")
        if paras:
            for p in paras:
                for br in p.find_all("br"):
                    br.replace_with("\n")
                t = p.get_text().strip()
                if t:
                    blocks.append(t)
        else:
            t = div.get_text(separator="\n").strip()
            if t:
                blocks.append(t)
    return "\n\n".join(blocks) if blocks else None


def normalize(text: str) -> str:
    """CRLF -> LF, strip trailing spaces, collapse >2 blank lines."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------- IDs ----------

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "untitled"


def assign_ids(titles: dict[str, str]) -> dict[str, str]:
    """
    Map cache keys ("fiction/a.aspx") to public ids ("fiction/the-alchemist").

    Collisions get -2, -3, ... suffixes in deterministic key order.
    Empty titles fall back to the source basename.
    """

    counts: dict[str, int] = {}
    mapping: dict[str, str] = {}
    for key in sorted(titles):
        cat, slug = key.split("/", 1)
        base = slugify(titles.get(key, ""))
        if base == "untitled":
            base = slugify(Path(slug).stem) or "untitled"
        base_id = f"{cat}/{base}"
        counts[base_id] = counts.get(base_id, 0) + 1
        n = counts[base_id]
        mapping[key] = base_id if n == 1 else f"{base_id}-{n}"
    return mapping


# ---------- Scrape ----------

def fetch(session: requests.Session, url: str) -> bytes:
    """Single GET; raises on failure. Callers catch and skip."""

    r = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content


def discover_entries(session: requests.Session) -> dict[str, str]:
    """
    Walk the four index pages and return { key -> title }.

    Links that don't look like text slugs (nav, anchors) are ignored.
    A failing category is logged and skipped; the others still run.
    """

    entries: dict[str, str] = {}
    for cat in CATEGORIES:
        index_url = f"{BASE}/writings/{cat}/"
        print(f"Index: {index_url}")
        try:
            html = fetch(session, index_url)
        except Exception as e:
            print(f"  SKIP {cat}: {e}")
            continue

        soup = BeautifulSoup(html, "html.parser")
        found = 0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not SLUG_RE.match(href) or href in SKIP_SLUGS:
                continue
            key = f"{cat}/{href}"
            title = a.get_text(" ", strip=True)
            if not entries.get(key):
                entries[key] = title
                found += 1
        print(f"  {found} links")
    return entries


def scrape_texts(session: requests.Session, entries: dict[str, str]) -> None:
    """
    Download each entry into cache/<key>.txt.

    Existing files are skipped. Per-document errors are
    logged and skipped; the run continues.
    """

    total = len(entries)
    for i, key in enumerate(sorted(entries), 1):
        out = CACHE_DIR / (key + ".txt")
        if out.exists():
            print(f"[{i:>3}/{total}] cached {key}")
            continue

        url = f"{BASE}/writings/texts/{key}"
        print(f"[{i:>3}/{total}] fetch  {url}")
        try:
            html = fetch(session, url)
            text = extract_text(html)
            if not text:
                print("    WARN no div[align=justify]")
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(normalize(text) + "\n", encoding="utf-8")
            print(f"    saved {len(text):,} chars")
        except Exception as e:
            print(f"    ERROR {e}")
        time.sleep(DELAY)

# ---------- Build ----------

def build_corpus(entries: dict[str, str]) -> list[dict]:
    """
    Read cache/ and write data/lovecraft.jsonl.

    IDs are assigned across the full `entries` set first, so records
    filtered out by MIN_CHARS don't shift the ids of survivors.
    """
    
    id_map = assign_ids(entries)
    records: list[dict] = []
    skipped = 0

    for key, title in sorted(entries.items()):
        path = CACHE_DIR / (key + ".txt")
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if len(text) < MIN_CHARS:
            skipped += 1
            continue
        records.append({
            "id": id_map[key],
            "category": key.split("/", 1)[0],
            "title": title,
            "source": f"{BASE}/writings/texts/{key}",
            "chars": len(text),
            "text": text,
        })

    records.sort(key=lambda r: r["id"])
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with CORPUS_PATH.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nExport")
    print(f"  documents written : {len(records)}")
    print(f"  skipped short     : {skipped}  (min_chars={MIN_CHARS})")
    print(f"  JSONL             : {CORPUS_PATH}  ({CORPUS_PATH.stat().st_size:,} bytes)")
    return records


def print_stats(records: list[dict]) -> None:
    if not records:
        print("\nCorpus is empty.")
        return
    by_cat = Counter(r["category"] for r in records)
    total_chars = sum(r["chars"] for r in records)
    print("\nCorpus summary:")
    for cat in sorted(by_cat):
        n = by_cat[cat]
        chars = sum(r["chars"] for r in records if r["category"] == cat)
        print(f"  {cat:8s} {n:>4} docs  {chars:>12,} chars")
    print(f"  {'TOTAL':8s} {len(records):>4} docs  {total_chars:>12,} chars")


# ---------- Main ----------

def main() -> None:
    session = requests.Session()
    entries = discover_entries(session)
    if not entries:
        sys.exit("No entries discovered due to changed site structure or network error.")
    scrape_texts(session, entries)
    print_stats(build_corpus(entries))


if __name__ == "__main__":
    main()