#!/usr/bin/env python3
"""
Source adapter layer for Job Search Automation MVP.

This script collects job descriptions from configured sources and writes a clean,
deduplicated folder of .txt files that can be passed to run_job_batch.py.

Supported source types in v0.1:
  - local_folder: copy .txt files from a folder, preserving Source URL headers
  - url_list: fetch simple public HTML/text URLs without login or JavaScript
  - verama_playwright / browser_verama: optional Playwright adapter for Verama/Ework-style portals

The browser_verama adapter is isolated in verama_playwright_adapter.py so normal
source collection does not require Playwright.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .paths import PROJECT_ROOT, resolve_config_path, resolve_project_root

try:
    import yaml  # type: ignore
except ModuleNotFoundError:
    yaml = None


THIS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = PROJECT_ROOT


class SimpleHTMLTextExtractor(HTMLParser):
    """Small dependency-free HTML-to-text extractor."""

    BLOCK_TAGS = {"p", "div", "section", "article", "li", "br", "h1", "h2", "h3", "h4", "tr"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.skip_depth = 0
        self.title: Optional[str] = None
        self._in_title = False
        self._title_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth > 0:
            self.skip_depth -= 1
        if tag == "title":
            self._in_title = False
            title = " ".join(self._title_parts).strip()
            if title:
                self.title = clean_text(title)
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
        self.parts.append(text + " ")

    def get_text(self) -> str:
        return clean_text("".join(self.parts))


def load_config(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Cannot read {path} without PyYAML because it is not JSON-compatible. "
            "Install with: python -m pip install pyyaml"
        ) from exc


def clean_text(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fold_text(text: str) -> str:
    """ASCII-friendly lowercase fold for robust text matching."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_only.lower().strip()


def read_source_url_from_text(text: str) -> Optional[str]:
    for line in text.splitlines()[:20]:
        m = re.match(r"^\s*Source URL\s*:\s*(https?://\S+)\s*$", line, flags=re.I)
        if m:
            return m.group(1)
    return None


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    remove_prefixes = ("utm_",)
    remove_exact = {"fbclid", "gclid", "mc_cid", "mc_eid"}
    clean_query = [(k, v) for k, v in query if not k.startswith(remove_prefixes) and k not in remove_exact]
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), urllib.parse.urlencode(clean_query), "")
    )


def stable_job_id(text: str, source_url: Optional[str] = None) -> str:
    if source_url:
        key = "url:" + normalize_url(source_url)
    else:
        body = re.sub(r"\s+", " ", text.lower()).strip()
        key = "content:" + body[:5000]
    return "job_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def extract_title_guess(text: str, title_hint: Optional[str] = None) -> str:
    if title_hint:
        return title_hint
    for line in text.splitlines():
        line = line.strip(" \t#-*:")
        if 6 <= len(line) <= 120 and not line.lower().startswith("source url"):
            return line
    return "Unspecified role"


def fetch_url(url: str, timeout: float = 20.0) -> Tuple[str, Optional[str]]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 JobSearchAutomationPrototype/0.1",
            "Accept": "text/html,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        content_type = resp.headers.get("content-type", "")
    charset = "utf-8"
    m = re.search(r"charset=([^;]+)", content_type, flags=re.I)
    if m:
        charset = m.group(1).strip()
    decoded = raw.decode(charset, errors="replace")
    if "html" in content_type.lower() or "<html" in decoded[:1000].lower():
        parser = SimpleHTMLTextExtractor()
        parser.feed(decoded)
        return parser.get_text(), parser.title
    return clean_text(decoded), None


def iter_local_folder(source: Dict[str, Any], root: Path) -> Iterable[Dict[str, Any]]:
    folder = Path(str(source.get("path", "")))
    if not folder.is_absolute():
        folder = root / folder
    file_glob = source.get("file_glob", "*.txt")
    if not folder.exists():
        print(f"[WARN] Local folder does not exist for source {source.get('id')}: {folder}", file=sys.stderr)
        return
    for path in sorted(folder.glob(file_glob)):
        if not path.is_file():
            continue
        text = clean_text(path.read_text(encoding="utf-8", errors="replace"))
        yield {
            "source_id": source.get("id", "local_folder"),
            "source_type": "local_folder",
            "source_url": read_source_url_from_text(text),
            "title_hint": None,
            "company_hint": None,
            "text": text,
            "origin": str(path),
        }


def iter_url_list(source: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for item in source.get("urls", []) or []:
        if isinstance(item, str):
            url = item
            title_hint = None
            company_hint = None
        else:
            url = item.get("url")
            title_hint = item.get("title_hint")
            company_hint = item.get("company_hint")
        if not url:
            continue
        try:
            text, page_title = fetch_url(url)
            if len(text) < 200:
                raise RuntimeError("Fetched page text is too short; page may require JavaScript or login.")
            if title_hint or page_title:
                text = f"{title_hint or page_title}\n\n{text}"
            yield {
                "source_id": source.get("id", "url_list"),
                "source_type": "url_list",
                "source_url": url,
                "title_hint": title_hint or page_title,
                "company_hint": company_hint,
                "text": text,
                "origin": url,
            }
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            yield {
                "source_id": source.get("id", "url_list"),
                "source_type": "url_list",
                "source_url": url,
                "title_hint": title_hint,
                "company_hint": company_hint,
                "text": "",
                "origin": url,
                "error": str(exc),
            }


def iter_saab_public(source: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Collect Saab job detail pages by expanding the public listing page."""
    base_url = str(source.get("base_url") or "https://www.saab.com").rstrip("/")
    listing_url = source.get("url") or source.get("listing_url") or f"{base_url}/career/job-opportunities"
    location_filter = fold_text(str(source.get("location") or ""))
    max_jobs = int(source.get("max_jobs") or 0)

    try:
        req = urllib.request.Request(
            str(listing_url),
            headers={
                "User-Agent": "Mozilla/5.0 JobSearchAutomationPrototype/0.1",
                "Accept": "text/html,text/plain;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            listing_html = resp.read().decode("utf-8", errors="replace")
        listing_html = html.unescape(listing_html)
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        yield {
            "source_id": source.get("id", "saab_public"),
            "source_type": "saab_public",
            "source_url": str(listing_url),
            "title_hint": "Saab job opportunities",
            "company_hint": "Saab",
            "text": "",
            "origin": str(listing_url),
            "error": f"Cannot fetch Saab listing page: {exc}",
        }
        return

    item_pattern = re.compile(r'<div class="item">(.*?)</div>\s*</div>\s*<div class="item-listing__job-end-date">', re.I | re.S)
    link_pattern = re.compile(r'href="(/career/job-opportunities/[^"]+)"', re.I)
    loc_pattern = re.compile(r'<div class="location">\s*([^<]+)\s*</div>', re.I)
    title_pattern = re.compile(r'>([^<>]+)<span class="icon">', re.I)

    seen_links: set[str] = set()
    items: List[Tuple[str, Optional[str], str]] = []

    for block in item_pattern.findall(listing_html):
        link_m = link_pattern.search(block)
        if not link_m:
            continue
        rel = link_m.group(1).strip()
        full_url = urllib.parse.urljoin(base_url + "/", rel.lstrip("/"))

        location_m = loc_pattern.search(block)
        item_location = (location_m.group(1).strip() if location_m else "")
        if location_filter and location_filter not in fold_text(item_location):
            continue

        if full_url in seen_links:
            continue
        seen_links.add(full_url)

        title_m = title_pattern.search(block)
        title_hint = clean_text(title_m.group(1)) if title_m else None
        items.append((full_url, title_hint, item_location))

    if max_jobs > 0:
        items = items[:max_jobs]

    for job_url, title_hint, item_location in items:
        try:
            text, page_title = fetch_url(job_url)
            if len(text) < 200:
                raise RuntimeError("Fetched Saab job page text is too short.")
            yield {
                "source_id": source.get("id", "saab_public"),
                "source_type": "saab_public",
                "source_url": job_url,
                "title_hint": title_hint or page_title,
                "company_hint": source.get("company_hint") or "Saab",
                "text": text,
                "origin": f"{listing_url} -> {job_url} ({item_location})",
            }
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            yield {
                "source_id": source.get("id", "saab_public"),
                "source_type": "saab_public",
                "source_url": job_url,
                "title_hint": title_hint,
                "company_hint": source.get("company_hint") or "Saab",
                "text": "",
                "origin": job_url,
                "error": str(exc),
            }


def iter_browser_verama(source: Dict[str, Any], root: Path) -> Iterable[Dict[str, Any]]:
    try:
        from .verama_playwright_adapter import collect_verama_jobs
    except Exception as exc:
        yield {
            "source_id": source.get("id", "verama_browser"),
            "source_type": source.get("type", "verama_playwright"),
            "source_url": source.get("start_url") or source.get("url") or "",
            "title_hint": "",
            "company_hint": "",
            "text": "",
            "origin": source.get("start_url") or source.get("url") or "",
            "error": str(exc),
        }
        return

    try:
        yield from collect_verama_jobs(source, root)
    except Exception as exc:
        yield {
            "source_id": source.get("id", "verama_browser"),
            "source_type": source.get("type", "verama_playwright"),
            "source_url": source.get("start_url") or source.get("url") or "",
            "title_hint": "",
            "company_hint": "",
            "text": "",
            "origin": source.get("start_url") or source.get("url") or "",
            "error": str(exc),
        }


def collect_jobs(config: Dict[str, Any], package_root: Path, out_dir: Path) -> List[Dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    collected_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    rows: List[Dict[str, Any]] = []
    seen: Dict[str, str] = {}

    for source in config.get("sources", []) or []:
        if not source.get("enabled", False):
            continue
        source_type = source.get("type")
        if source_type == "local_folder":
            iterator = iter_local_folder(source, package_root)
        elif source_type == "url_list":
            iterator = iter_url_list(source)
        elif source_type == "saab_public":
            iterator = iter_saab_public(source)
        elif source_type in {"browser_verama", "verama_playwright"}:
            iterator = iter_browser_verama(source, package_root)
        else:
            print(f"[WARN] Unsupported source type {source_type!r} for {source.get('id')}", file=sys.stderr)
            continue

        for item in iterator:
            error = item.get("error", "")
            text = item.get("text", "") or ""
            source_url = item.get("source_url")
            if error:
                rows.append({
                    "job_id": "",
                    "status": "fetch_error",
                    "source_id": item.get("source_id", ""),
                    "source_type": item.get("source_type", ""),
                    "source_url": source_url or "",
                    "title_guess": item.get("title_hint") or "",
                    "origin": item.get("origin", ""),
                    "output_file": "",
                    "duplicate_of": "",
                    "collected_at": collected_at,
                    "error": error,
                })
                continue
            job_id = stable_job_id(text, source_url)
            title_guess = extract_title_guess(text, item.get("title_hint"))
            if job_id in seen:
                rows.append({
                    "job_id": job_id,
                    "status": "duplicate",
                    "source_id": item.get("source_id", ""),
                    "source_type": item.get("source_type", ""),
                    "source_url": source_url or "",
                    "title_guess": title_guess,
                    "origin": item.get("origin", ""),
                    "output_file": "",
                    "duplicate_of": seen[job_id],
                    "collected_at": collected_at,
                    "error": "",
                })
                continue
            output_name = f"{job_id}.txt"
            output_path = out_dir / output_name
            header_lines = []
            if source_url:
                header_lines.append(f"Source URL: {source_url}")
            header_lines.append(f"Collected From: {item.get('source_id', '')}")
            header_lines.append(f"Collected At: {collected_at}")
            header_lines.append("")
            output_path.write_text("\n".join(header_lines) + clean_text(text) + "\n", encoding="utf-8")
            seen[job_id] = output_name
            rows.append({
                "job_id": job_id,
                "status": "collected",
                "source_id": item.get("source_id", ""),
                "source_type": item.get("source_type", ""),
                "source_url": source_url or "",
                "title_guess": title_guess,
                "origin": item.get("origin", ""),
                "output_file": output_name,
                "duplicate_of": "",
                "collected_at": collected_at,
                "error": "",
            })
    return rows


def write_manifest(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "job_id", "status", "source_id", "source_type", "source_url", "title_guess", "origin",
        "output_file", "duplicate_of", "collected_at", "error",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect and deduplicate jobs from configured sources")
    parser.add_argument("--sources", default="job_sources.yaml", help="Path to job_sources.yaml")
    parser.add_argument("--package-root", default=".", help="Package root, usually .")
    parser.add_argument("--out-dir", default=None, help="Collected jobs output folder")
    parser.add_argument("--manifest", default=None, help="Manifest CSV path")
    args = parser.parse_args()

    package_root = resolve_project_root(args.package_root)
    sources_path = resolve_config_path(args.sources, package_root)
    config = load_config(sources_path)

    dedupe = config.get("deduplication", {}) or {}
    out_dir = Path(args.out_dir or dedupe.get("output_dir") or "outputs/collected_jobs")
    manifest = Path(args.manifest or dedupe.get("manifest_file") or "outputs/collected_jobs/job_manifest.csv")
    if not out_dir.is_absolute():
        out_dir = package_root / out_dir
    if not manifest.is_absolute():
        manifest = package_root / manifest

    rows = collect_jobs(config, package_root, out_dir)
    write_manifest(manifest, rows)
    collected = sum(1 for r in rows if r.get("status") == "collected")
    dupes = sum(1 for r in rows if r.get("status") == "duplicate")
    errors = sum(1 for r in rows if r.get("status") == "fetch_error")
    print(f"Collected {collected} jobs, {dupes} duplicates, {errors} fetch errors")
    print(f"Output folder: {out_dir}")
    print(f"Manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
