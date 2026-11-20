#!/usr/bin/env python3
"""
Build a Lovecraft corpus from hplovecraft.com, Wikisource, and LetterCraft.

Run: python corpus.py

Produces:
    cache/<origin>/<category>/<slug>.txt   downloaded bodies
    data/lovecraft.jsonl                   final corpus
"""

import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote

import requests
from bs4 import BeautifulSoup

# ---------- Constants ----------

HPL_BASE = "https://hplovecraft.com"
WS_API = "https://en.wikisource.org/w/api.php"
WS_BASE = "https://en.wikisource.org/wiki/"
WS_AUTHOR_PAGE = "Author:Howard Phillips Lovecraft"
LC_API = "https://api.github.com/repos/punchmonster/Lovecraft-Letters/contents"

CATEGORIES = ("fiction", "poetry", "essays", "letters")
WS_SECTIONS = {"Poetry": "poetry", "Essays": "essays", "Letters": "letters"}

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
DATA_DIR = BASE_DIR / "data"
CORPUS_PATH = DATA_DIR / "lovecraft.jsonl"

USER_AGENT = "lovecraft-corpus/1.0 (https://github.com/Lla-bas/lovecraft-corpus)"
TIMEOUT = 30
DELAY = 1.0         # seconds between requests
MIN_CHARS = 75      # drop shorter fragments

LINK_RE = re.compile(r"^([a-z]+)/([a-z0-9_-]+\.aspx)$")
LC_FILE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})-(.+)$")
SKIP_SLUGS = {"chrono.aspx", "index.aspx", "publish.aspx", "contents.aspx"}
WS_STRIP_SELECTORS = (
    ".ws-noexport", ".noprint", ".headerContainer", ".footertemplate",
    ".mw-editsection", ".toc", "sup.reference", "style", "script",
)
LC_TYPOS = {
    "Aflred": "Alfred",
    "Rimmel": "Rimel",
    "Block": "Bloch",
    "Harlow": "Barlow",
}


@dataclass
class Entry:
    key: str            # unique internal key, e.g. "hplovecraft/fiction/cc.aspx"
    origin: str         # "hplovecraft" | "wikisource" | "lettercraft"
    category: str       # "fiction" | "poetry" | "essays" | "letters"
    title: str
    source: str         # canonical URL
    cache_path: Path
    ws_page: str | None = None
    raw_url: str | None = None


# ---------- Extraction ----------

def extract_hplovecraft(html_bytes: bytes) -> str | None:
    """Pull the body from an hplovecraft.com text page."""

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


def extract_wikisource(html_str: str) -> str | None:
    """Pull the body from a Wikisource API parsed HTML fragment."""

    soup = BeautifulSoup(html_str, "html.parser")
    for sel in WS_STRIP_SELECTORS:
        for el in soup.select(sel):
            el.decompose()

    root = soup.select_one(".prp-pages-output") or soup.select_one(".mw-parser-output") or soup
    for br in root.find_all("br"):
        br.replace_with("\n")

    blocks: list[str] = []
    for el in root.find_all(["p", "div"], recursive=True):
        if el.name == "div" and "poem" not in (el.get("class") or []):
            continue
        if el.name == "p" and el.find_parent("div", class_="poem"):
            continue
        t = el.get_text().strip()
        if t:
            blocks.append(t)
    return "\n\n".join(blocks) if blocks else None


def extract_lettercraft(md_bytes: bytes) -> str | None:
    """Strip Markdown formatting from a LetterCraft .md transcript."""

    text = md_bytes.decode("utf-8", errors="replace")
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)          # images
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)      # links
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)                # headings
    text = re.sub(r"(?m)^>\s?", "", text)                     # blockquotes
    text = re.sub(r"(?m)^[-*_]{3,}\s*$", "", text)            # horizontal rules
    text = re.sub(r"(\*\*|__|\*|_)(.*?)\1", r"\2", text)      # bold/italic
    text = re.sub(r"<[^>]+>", "", text)                       # inline HTML
    text = text.strip()
    return text or None


def normalize(text: str) -> str:
    """CRLF -> LF, strip trailing spaces, collapse >2 blank lines."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------- IDs & Deduplication ----------

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "untitled"


def norm_title(title: str) -> str:
    """Normalized title for cross-source deduplication."""

    s = slugify(title)
    return re.sub(r"^(the|a|an)-", "", s)


def assign_ids(entries: list[Entry]) -> dict[str, str]:
    """Map internal entry keys to deterministic public ids ('fiction/the-alchemist')."""

    counts: dict[str, int] = {}
    mapping: dict[str, str] = {}
    for e in sorted(entries, key=lambda x: x.key):
        base = slugify(e.title)
        if base == "untitled":
            base = slugify(e.cache_path.stem) or "untitled"
        base_id = f"{e.category}/{base}"
        counts[base_id] = counts.get(base_id, 0) + 1
        n = counts[base_id]
        mapping[e.key] = base_id if n == 1 else f"{base_id}-{n}"
    return mapping


def shingles(text: str, k: int = 5) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < k:
        return {tuple(words)}
    return {tuple(words[i:i + k]) for i in range(len(words) - k + 1)}


def source_priority(source_url: str) -> int:
    if "hplovecraft.com" in source_url:
        return 0
    if "wikisource.org" in source_url:
        return 1
    return 2


def deduplicate(records: list[dict], threshold: float = 0.6) -> list[dict]:
    """Drop near-duplicate texts, prioritizing hplovecraft.com > wikisource > lettercraft."""

    ordered = sorted(records, key=lambda r: (source_priority(r["source"]), r["id"]))
    kept: list[dict] = []
    kept_shingles: list[set[tuple[str, ...]]] = []

    for r in ordered:
        s = shingles(r["text"])
        dup_of = None
        for prev, prev_s in zip(kept, kept_shingles):
            union = len(s | prev_s)
            if union and (len(s & prev_s) / union) >= threshold:
                dup_of = prev["id"]
                break
        if dup_of:
            print(f"  DUP  {r['id']}  ≈  {dup_of}")
        else:
            kept.append(r)
            kept_shingles.append(s)

    return kept


# ---------- Discovery ----------

def fetch(session: requests.Session, url: str, params: dict | None = None) -> bytes:
    r = session.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content

def discover_hplovecraft(session: requests.Session) -> list[Entry]:
    """Walk /writings/texts/ on hplovecraft.com."""

    index_url = f"{HPL_BASE}/writings/texts/"
    print(f"Index: {index_url}")
    html = fetch(session, index_url)
    soup = BeautifulSoup(html, "html.parser")

    entries: list[Entry] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].removeprefix("/writings/texts/")
        m = LINK_RE.match(href)
        if not m or m.group(1) not in CATEGORIES or m.group(2) in SKIP_SLUGS:
            continue
        if href in seen:
            continue
        seen.add(href)
        cat, slug = m.group(1), m.group(2)
        entries.append(Entry(
            key=f"hplovecraft/{href}",
            origin="hplovecraft",
            category=cat,
            title=a.get_text(" ", strip=True),
            source=f"{HPL_BASE}/writings/texts/{href}",
            cache_path=CACHE_DIR / "hplovecraft" / cat / f"{slug}.txt",
        ))

    print(f"  {len(entries)} links")
    return entries


def discover_wikisource(session: requests.Session) -> list[Entry]:
    """Walk Poetry, Essays, and Letters sections of the Wikisource author page."""

    print(f"Index: {WS_BASE}{WS_AUTHOR_PAGE.replace(' ', '_')}")
    raw = fetch(session, WS_API, params={
        "action": "parse",
        "page": WS_AUTHOR_PAGE,
        "prop": "text",
        "format": "json",
        "redirects": 1,
    })
    html = json.loads(raw)["parse"]["text"]["*"]
    soup = BeautifulSoup(html, "html.parser")

    entries: list[Entry] = []
    seen_pages: set[str] = set()

    for heading_id, cat in WS_SECTIONS.items():
        if cat not in CATEGORIES:
            continue
        h = soup.find(id=heading_id)
        if not h:
            print(f"  WARN section '{heading_id}' not found")
            continue

        node = h.parent if h.parent and "mw-heading" in (h.parent.get("class") or []) else h
        for sib in node.find_next_siblings():
            if sib.name in ("h2", "h3") or "mw-heading" in (sib.get("class") or []):
                break
            for li in sib.find_all("li"):
                a = li.find("a", href=True)
                if not a or "new" in (a.get("class") or []):
                    continue
                href = a["href"]
                if not href.startswith("/wiki/") or ":" in href.removeprefix("/wiki/"):
                    continue
                page = unquote(href.removeprefix("/wiki/").split("#", 1)[0])
                if page in seen_pages:
                    continue
                seen_pages.add(page)
                title = a.get_text(" ", strip=True)
                slug = slugify(title)
                entries.append(Entry(
                    key=f"wikisource/{cat}/{slug}",
                    origin="wikisource",
                    category=cat,
                    title=title,
                    source=f"{WS_BASE}{quote(page, safe='()/_-')}",
                    cache_path=CACHE_DIR / "wikisource" / cat / f"{slug}.txt",
                    ws_page=page,
                ))

    print(f"  {len(entries)} links")
    return entries


def discover_lettercraft(session: requests.Session) -> list[Entry]:
    """List letter transcripts from punchmonster/Lovecraft-Letters."""

    if "letters" not in CATEGORIES:
        return []

    print(f"Index: {LC_API}")
    items = json.loads(fetch(session, LC_API))
    entries: list[Entry] = []

    for item in items:
        name = item.get("name", "")
        if item.get("type") != "file" or not name.endswith(".md") or name.lower() == "readme.md":
            continue
        stem = Path(name).stem
        m = LC_FILE_RE.match(stem)
        if m:
            year, month, day, recipient = m.groups()
            words = [LC_TYPOS.get(w, w) for w in recipient.split("-")]
            date_str = f"{year}-{month}" if day == "99" else f"{year}-{month}-{day}"
            title = f"Letter to {' '.join(words)} ({date_str})"
        else:
            title = stem.replace("-", " ")

        entries.append(Entry(
            key=f"lettercraft/letters/{stem}",
            origin="lettercraft",
            category="letters",
            title=title,
            source=item["html_url"],
            cache_path=CACHE_DIR / "lettercraft" / "letters" / f"{stem}.txt",
            raw_url=item["download_url"],
        ))

    print(f"  {len(entries)} links")
    return entries


def merge_entries(*sources: list[Entry]) -> list[Entry]:
    """Merge entry lists in priority order, skipping duplicate (category, norm_title)."""

    seen: set[tuple[str, str]] = set()
    merged: list[Entry] = []
    skipped = 0
    for src in sources:
        for e in src:
            sig = (e.category, norm_title(e.title))
            if sig not in seen:
                seen.add(sig)
                merged.append(e)
            else:
                skipped += 1
    print(f"Merged: {len(merged)} unique entries ({skipped} title duplicates skipped)")
    return merged


# ---------- Scrape ----------

def scrape_entries(session: requests.Session, entries: list[Entry]) -> None:
    """Download each entry into its cache path."""

    total = len(entries)
    for i, e in enumerate(sorted(entries, key=lambda x: x.key), 1):
        if e.cache_path.exists():
            print(f"[{i:>3}/{total}] cached {e.key}")
            continue

        print(f"[{i:>3}/{total}] fetch  {e.source}")
        try:
            if e.origin == "hplovecraft":
                text = extract_hplovecraft(fetch(session, e.source))
            elif e.origin == "wikisource":
                raw = fetch(session, WS_API, params={
                    "action": "parse",
                    "page": e.ws_page,
                    "prop": "text",
                    "format": "json",
                    "redirects": 1,
                })
                html_str = json.loads(raw)["parse"]["text"]["*"]
                text = extract_wikisource(html_str)
            else:
                text = extract_lettercraft(fetch(session, e.raw_url))

            if not text:
                print("    WARN no text extracted")
                continue
            e.cache_path.parent.mkdir(parents=True, exist_ok=True)
            e.cache_path.write_text(normalize(text) + "\n", encoding="utf-8")
            print(f"    saved {len(text):,} chars")
        except Exception as exc:
            print(f"    ERROR {exc}")
        time.sleep(DELAY)


# ---------- Build ----------

def build_corpus(entries: list[Entry]) -> list[dict]:
    """Read cache/ and write data/lovecraft.jsonl."""

    id_map = assign_ids(entries)
    records: list[dict] = []
    skipped = 0

    for e in sorted(entries, key=lambda x: x.key):
        if not e.cache_path.exists():
            continue
        text = e.cache_path.read_text(encoding="utf-8").strip()
        if e.category in ("fiction", "essays"):
            text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
            text = re.sub(r" {2,}", " ", text)
        if len(text) < MIN_CHARS:
            skipped += 1
            continue
        records.append({
            "id": id_map[e.key],
            "category": e.category,
            "title": e.title,
            "source": e.source,
            "chars": len(text),
            "text": text,
        })

    records = deduplicate(records)
    records.sort(key=lambda r: r["id"])
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with CORPUS_PATH.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("\nExport")
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
    hpl = discover_hplovecraft(session)
    ws = discover_wikisource(session)
    lc = discover_lettercraft(session)
    entries = merge_entries(hpl, ws, lc)
    if not entries:
        sys.exit("No entries discovered due to changed site structure or network error.")
    scrape_entries(session, entries)
    print_stats(build_corpus(entries))


if __name__ == "__main__":
    main()