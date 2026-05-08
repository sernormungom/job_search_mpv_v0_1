#!/usr/bin/env python3
"""
Optional Playwright adapter for Verama/Ework-style job portals.

This module is intentionally separate from the core source adapter so the normal
copied-job and public-URL flow does not require Playwright. It uses a persistent
Chromium profile, which lets the user log in once in the opened browser window
without storing credentials in this repository.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse


JOB_DETAIL_PATH_RE = re.compile(r"^/app/job-requests/\d+/?$")

JOB_LINK_HINTS = (
    "assignment",
    "assignments",
    "job",
    "jobs",
    "job-request",
    "job-requests",
    "opportunity",
    "opportunities",
    "uppdrag",
    "consultant",
    "request",
    "requests",
)

COOKIE_BUTTON_NAMES = (
    "accept",
    "accept all",
    "allow all",
    "i agree",
    "ok",
    "got it",
    "godkann",
    "acceptera",
)

FOOTER_MARKERS = [
    "Kontakt Ework Group AB",
    "Inköpsprocessen hanteras av Ework Group AB",
    "This request is managed by Ework Group",
    "Få betalt snabbt och enkelt!",
    "PayExpress:",
    "Terms of use",
    "Senast visade",
    "Hitta uppdrag",
]


def clean_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\ufeff", "")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _ascii_fold(value: str) -> str:
    table = str.maketrans({
        "å": "a",
        "ä": "a",
        "ö": "o",
        "Å": "a",
        "Ä": "a",
        "Ö": "o",
    })
    return value.translate(table).lower()


def import_playwright() -> Any:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Playwright is not installed. Install optional browser support with:\n"
            "  python -m pip install playwright\n"
            "  python -m playwright install chromium"
        ) from exc
    return sync_playwright


def resolve_path(path_value: str, root: Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = root / path
    return path


def truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def same_domain(url: str, allowed_domains: Iterable[str]) -> bool:
    domains = [str(domain).lower().strip() for domain in allowed_domains if domain]
    if not domains:
        return True
    hostname = (urlparse(url).hostname or "").lower()
    return any(hostname == domain or hostname.endswith("." + domain) for domain in domains)


def text_contains_location(text: str, location: Optional[str]) -> bool:
    if not location:
        return True
    hay = _ascii_fold(text)
    needle = _ascii_fold(location)
    if needle in hay:
        return True
    # Common Gothenburg/Goteborg/Goteborg variants.
    if needle in {"gothenburg", "goteborg"}:
        return "gothenburg" in hay or "goteborg" in hay
    return False


def is_job_detail_url(url: str) -> bool:
    parsed = urlparse(url)
    return bool(JOB_DETAIL_PATH_RE.match(parsed.path))


def _trim_footer(lines: List[str]) -> List[str]:
    cut_idx = len(lines)
    for i, line in enumerate(lines):
        if any(marker.lower() in line.lower() for marker in FOOTER_MARKERS):
            cut_idx = i
            break
    return lines[:cut_idx]


def _looks_like_location(value: str) -> bool:
    low = value.lower()
    if not value:
        return False
    if "terms of use" in low:
        return False
    if len(value) > 80:
        return False
    if "(se)" in low:
        return True
    return bool(re.search(r"(gothenburg|göteborg|stockholm|malmö|sweden)", low))


def dismiss_cookie_banners(page: Any) -> None:
    for name in COOKIE_BUTTON_NAMES:
        try:
            button = page.get_by_role("button", name=re.compile(rf"^{re.escape(name)}$", re.I))
            if button.count():
                button.first.click(timeout=1200)
                return
        except Exception:
            continue


def wait_for_app_ready(page: Any, timeout_ms: int) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 10000))
    except Exception:
        pass


def auto_scroll(page: Any) -> None:
    page.evaluate(
        """
        async () => {
          const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
          let lastHeight = 0;
          for (let i = 0; i < 8; i += 1) {
            window.scrollTo(0, document.body.scrollHeight);
            await delay(350);
            const height = document.body.scrollHeight;
            if (height === lastHeight) break;
            lastHeight = height;
          }
          window.scrollTo(0, 0);
        }
        """
    )


def try_fill_location_filter(page: Any, location: str) -> bool:
    patterns = [re.compile(r"location|city|place|ort|plats|stad", re.I)]
    locators = []
    for pattern in patterns:
        locators.extend(
            [
                lambda pattern=pattern: page.get_by_label(pattern),
                lambda pattern=pattern: page.get_by_placeholder(pattern),
                lambda pattern=pattern: page.get_by_role("textbox", name=pattern),
                lambda pattern=pattern: page.get_by_role("combobox", name=pattern),
            ]
        )

    css_selectors = [
        "input[name*='location' i]",
        "input[placeholder*='location' i]",
        "input[aria-label*='location' i]",
        "input[name*='city' i]",
        "input[placeholder*='city' i]",
        "input[aria-label*='city' i]",
        "input[name*='ort' i]",
        "input[placeholder*='ort' i]",
        "input[aria-label*='ort' i]",
        "input[name*='plats' i]",
        "input[placeholder*='plats' i]",
        "input[aria-label*='plats' i]",
    ]

    for make_locator in locators:
        try:
            locator = make_locator()
            if locator.count():
                target = locator.first
                target.click(timeout=1500)
                target.fill(location, timeout=1500)
                target.press("Enter", timeout=1500)
                page.wait_for_timeout(1200)
                return True
        except Exception:
            continue

    for selector in css_selectors:
        try:
            locator = page.locator(selector)
            if locator.count():
                target = locator.first
                target.click(timeout=1500)
                target.fill(location, timeout=1500)
                target.press("Enter", timeout=1500)
                page.wait_for_timeout(1200)
                return True
        except Exception:
            continue
    return False


def collect_candidate_links(
    page: Any,
    start_url: str,
    location: Optional[str],
    allowed_domains: List[str],
    max_jobs: int,
) -> List[Dict[str, str]]:
    rows = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('a[href]')).map(anchor => {
          const container = anchor.closest(
            'article, li, tr, [role="row"], [role="listitem"], [data-testid], .card, .job, .assignment'
          ) || anchor;
          return {
            href: anchor.href,
            linkText: anchor.innerText || anchor.textContent || '',
            containerText: container.innerText || container.textContent || '',
            ariaLabel: anchor.getAttribute('aria-label') || '',
            title: anchor.getAttribute('title') || ''
          };
        })
        """
    )

    seen: set[str] = set()
    candidates: List[Dict[str, str]] = []
    for row in rows:
        href = str(row.get("href") or "").strip()
        if not href or href.startswith("javascript:") or href in seen:
            continue
        absolute = urljoin(start_url, href)
        if not same_domain(absolute, allowed_domains):
            continue
        if not is_job_detail_url(absolute):
            continue
        text = clean_text(
            " ".join(str(row.get(key) or "") for key in ["linkText", "containerText", "ariaLabel", "title"])
        )
        hint_text = f"{absolute} {text}".lower()
        if not any(hint in hint_text for hint in JOB_LINK_HINTS):
            continue
        if location and text and not text_contains_location(text, location):
            # Location is often only visible on detail pages, so keep some candidates.
            if len(candidates) >= max_jobs:
                continue
        seen.add(absolute)
        candidates.append({"url": absolute, "summary": text[:500]})
        if len(candidates) >= max_jobs:
            break
    return candidates


def extract_page_title(page: Any) -> Optional[str]:
    for selector in ["h1", "[data-testid*='title' i]", "[class*='title' i]"]:
        try:
            locator = page.locator(selector)
            if locator.count():
                title = clean_text(locator.first.inner_text(timeout=1500))
                if title:
                    return title
        except Exception:
            continue
    try:
        title = clean_text(page.title())
        return title or None
    except Exception:
        return None


def extract_visible_text(page: Any) -> str:
    for selector in ["main", "article", "[role='main']", "body"]:
        try:
            locator = page.locator(selector)
            if locator.count():
                text = clean_text(locator.first.inner_text(timeout=2500))
                if len(text) >= 200:
                    return text
        except Exception:
            continue
    return clean_text(page.locator("body").inner_text(timeout=2500))


def extract_job_fields(raw_text: str) -> Dict[str, str]:
    lines = [line.strip() for line in clean_text(raw_text).splitlines() if line.strip()]
    lines = _trim_footer(lines)
    fields = {"company": "", "role": "", "seniority": "", "location": "", "deadline": ""}
    for i, line in enumerate(lines):
        if re.match(r"^publicerad den .* av$", line, flags=re.I):
            if i + 1 < len(lines):
                fields["company"] = lines[i + 1]
        if line.lower() == "roll" and i + 1 < len(lines):
            fields["role"] = lines[i + 1]
        if line.lower() == "senioritetsnivå" and i + 1 < len(lines):
            fields["seniority"] = lines[i + 1]
        if line.lower() == "plats" and i + 1 < len(lines) and _looks_like_location(lines[i + 1]) and not fields["location"]:
            fields["location"] = lines[i + 1]
        if line.lower() == "ansökningstiden löper ut" and i + 1 < len(lines):
            fields["deadline"] = lines[i + 1]
    return fields


def clean_job_text(raw_text: str, title: str = "") -> str:
    lines = [line.strip() for line in clean_text(raw_text).splitlines() if line.strip()]
    if not lines:
        return ""
    lines = _trim_footer(lines)

    nav_prefixes = (
        "Hem",
        "Uppdragsannonser",
        "Visa",
        "Ework+",
        "Tidsrapporter",
        "Help center",
        "Tillbaka till uppdrag",
        "Spara uppdrag",
        "Dela",
    )
    noisy_exact = {
        "Du kan inte ansöka själv. Be din Manager att ansöka.",
        "Plats",
        "Visa profil",
    }
    filtered: List[str] = []
    for line in lines:
        if line in noisy_exact:
            continue
        if line.startswith(nav_prefixes):
            continue
        if re.match(r"^för \d+ .* sedan$", line, flags=re.I):
            continue
        filtered.append(line)

    # Start near the title when present.
    if title:
        try:
            title_idx = next(i for i, line in enumerate(filtered) if _ascii_fold(title) == _ascii_fold(line))
            filtered = filtered[title_idx:]
        except StopIteration:
            pass

    return clean_text("\n".join(filtered))


def collect_job_detail(context: Any, url: str, source: Dict[str, Any], timeout_ms: int) -> Dict[str, Any]:
    page = context.new_page()
    try:
        if not is_job_detail_url(url):
            raise RuntimeError("Skipped non-detail page URL.")
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        wait_for_app_ready(page, timeout_ms)
        dismiss_cookie_banners(page)
        auto_scroll(page)
        title = extract_page_title(page)
        raw_text = extract_visible_text(page)
        fields = extract_job_fields(raw_text)
        text = clean_job_text(raw_text, title=title or "")
        return {
            "source_id": source.get("id", "verama_browser"),
            "source_type": source.get("type", "verama_playwright"),
            "source_url": page.url,
            "title_hint": title,
            "company_hint": fields.get("company") or source.get("company_hint"),
            "role_hint": fields.get("role", ""),
            "seniority_hint": fields.get("seniority", ""),
            "location_hint": fields.get("location", ""),
            "deadline_hint": fields.get("deadline", ""),
            "text": text,
            "origin": page.url,
        }
    finally:
        page.close()


def collect_verama_jobs(source: Dict[str, Any], package_root: Path) -> List[Dict[str, Any]]:
    sync_playwright = import_playwright()
    start_url = source.get("start_url") or source.get("url")
    if not start_url:
        raise RuntimeError("verama_playwright source requires url or start_url")

    location = source.get("location")
    max_jobs = int(source.get("max_jobs", 25) or 25)
    timeout_ms = int(source.get("timeout_ms", 30000) or 30000)
    headed = truthy(source.get("headed"), default=False)
    headless = False if headed else truthy(source.get("headless"), default=False)
    login_if_needed = truthy(source.get("login_if_needed"), default=True)
    wait_for_manual_filter = truthy(source.get("wait_for_manual_filter"), default=login_if_needed)
    strict_location = truthy(source.get("strict_location"), default=True)
    strict_detail_pages = truthy(source.get("strict_detail_pages"), default=True)
    profile_dir = resolve_path(
        str(source.get("user_data_dir") or "browser_profiles/verama"),
        package_root,
    )
    profile_dir.mkdir(parents=True, exist_ok=True)
    allowed_domains = [str(x) for x in source.get("allowed_domains", []) or []]

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=headless,
            viewport={"width": 1440, "height": 1000},
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(str(start_url), wait_until="domcontentloaded", timeout=timeout_ms)
            wait_for_app_ready(page, timeout_ms)
            dismiss_cookie_banners(page)

            if location:
                try_fill_location_filter(page, str(location))

            if wait_for_manual_filter and not headless:
                print(
                    "\nVerama/Ework browser is open. Log in if needed, apply or confirm the "
                    f"{location or 'desired'} location filter, then press Enter here to collect jobs.",
                    file=sys.stderr,
                )
                input()
                wait_for_app_ready(page, timeout_ms)

            auto_scroll(page)
            candidates = collect_candidate_links(page, page.url, location, allowed_domains, max_jobs)
            if not candidates:
                current_text = clean_job_text(extract_visible_text(page))
                if is_job_detail_url(page.url) and len(current_text) >= 200 and text_contains_location(current_text, location):
                    candidates = [{"url": page.url, "summary": current_text[:500]}]

            jobs: List[Dict[str, Any]] = []
            seen_urls: set[str] = set()
            for candidate in candidates:
                url = candidate["url"]
                if url in seen_urls:
                    continue
                if strict_detail_pages and not is_job_detail_url(url):
                    continue
                seen_urls.add(url)
                try:
                    item = collect_job_detail(context, url, source, timeout_ms)
                    text = item.get("text", "") or ""
                    if len(text) < 200:
                        item["error"] = "Extracted page text is too short; page may not be a job detail."
                    elif strict_location and location and not text_contains_location(
                        " ".join(
                            [
                                text,
                                str(item.get("location_hint") or ""),
                                str(item.get("title_hint") or ""),
                            ]
                        ),
                        str(location),
                    ):
                        item["error"] = f"Skipped because extracted text did not contain location {location!r}."
                    jobs.append(item)
                except Exception as exc:
                    jobs.append(
                        {
                            "source_id": source.get("id", "verama_browser"),
                            "source_type": source.get("type", "verama_playwright"),
                            "source_url": url,
                            "title_hint": "",
                            "company_hint": source.get("company_hint"),
                            "text": "",
                            "origin": url,
                            "error": str(exc),
                        }
                    )
            return jobs
        finally:
            context.close()


def stable_job_id(text: str, source_url: Optional[str] = None) -> str:
    key = "url:" + source_url.strip().lower().rstrip("/") if source_url else "content:" + clean_text(text).lower()[:5000]
    return "job_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def write_collected_jobs(out_dir: Path, jobs: List[Dict[str, Any]], location: str = "") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "job_manifest.csv"
    collected_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    fields = [
        "job_id",
        "status",
        "source_id",
        "source_type",
        "source_url",
        "title_guess",
        "origin",
        "output_file",
        "duplicate_of",
        "collected_at",
        "error",
    ]
    rows: List[Dict[str, str]] = []
    seen: Dict[str, str] = {}
    for job in jobs:
        text = clean_text(str(job.get("text") or ""))
        source_url = str(job.get("source_url") or "")
        title = str(job.get("title_hint") or "Untitled Verama job")
        location_hint = str(job.get("location_hint") or location or "")
        deadline_hint = str(job.get("deadline_hint") or "")
        role_hint = str(job.get("role_hint") or "")
        seniority_hint = str(job.get("seniority_hint") or "")
        job_id = stable_job_id(text, source_url or None)
        if job.get("error"):
            rows.append({
                "job_id": job_id,
                "status": "fetch_error",
                "source_id": str(job.get("source_id") or "verama_browser"),
                "source_type": str(job.get("source_type") or "verama_playwright"),
                "source_url": source_url,
                "title_guess": title,
                "origin": str(job.get("origin") or source_url),
                "output_file": "",
                "duplicate_of": "",
                "collected_at": collected_at,
                "error": str(job.get("error") or ""),
            })
            continue
        if job_id in seen:
            rows.append({
                "job_id": job_id,
                "status": "duplicate",
                "source_id": str(job.get("source_id") or "verama_browser"),
                "source_type": str(job.get("source_type") or "verama_playwright"),
                "source_url": source_url,
                "title_guess": title,
                "origin": str(job.get("origin") or source_url),
                "output_file": "",
                "duplicate_of": seen[job_id],
                "collected_at": collected_at,
                "error": "",
            })
            continue
        output_name = f"{job_id}.txt"
        output_path = out_dir / output_name
        body = "\n".join([
            f"Source URL: {source_url}",
            f"Title: {title}",
            f"Company/Client: {job.get('company_hint') or ''}",
            f"Location: {location_hint}",
            f"Role: {role_hint}",
            f"Seniority: {seniority_hint}",
            f"Application Deadline: {deadline_hint}",
            f"Collected From: {job.get('source_id') or 'verama_browser'}",
            f"Collected At: {collected_at}",
            "",
            "Full job description",
            "",
            text,
            "",
        ])
        output_path.write_text(body, encoding="utf-8")
        seen[job_id] = output_name
        rows.append({
            "job_id": job_id,
            "status": "collected",
            "source_id": str(job.get("source_id") or "verama_browser"),
            "source_type": str(job.get("source_type") or "verama_playwright"),
            "source_url": source_url,
            "title_guess": title,
            "origin": str(job.get("origin") or source_url),
            "output_file": output_name,
            "duplicate_of": "",
            "collected_at": collected_at,
            "error": "",
        })
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Verama/Ework jobs with Playwright")
    parser.add_argument("--start-url", "--url", dest="start_url", required=True, help="Verama/Ework app URL to open")
    parser.add_argument("--location", default="Gothenburg", help="Location filter to apply/check")
    parser.add_argument("--max-jobs", type=int, default=25, help="Maximum job detail pages to collect")
    parser.add_argument("--user-data-dir", default="browser_profiles/verama", help="Persistent browser profile")
    parser.add_argument("--out-dir", default="sources/collected_jobs", help="Directory where collected .txt files are written")
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window")
    parser.add_argument("--headless", action="store_true", help="Run without a visible browser")
    parser.add_argument("--login-if-needed", action="store_true", help="Pause for manual login/filtering in headed mode")
    parser.add_argument("--no-manual-filter", action="store_true", help="Do not pause for manual login/filtering")
    parser.add_argument("--dry-run", action="store_true", help="Collect and print results without writing job text files")
    parser.add_argument("--package-root", default=".", help="Package root")
    parser.add_argument("--json", action="store_true", help="Print collected items as JSON")
    args = parser.parse_args()

    wait_for_manual_filter = True
    if args.no_manual_filter:
        wait_for_manual_filter = False
    elif args.login_if_needed:
        wait_for_manual_filter = True

    source = {
        "id": "verama_browser",
        "type": "verama_playwright",
        "start_url": args.start_url,
        "location": args.location,
        "max_jobs": args.max_jobs,
        "user_data_dir": args.user_data_dir,
        "headed": args.headed,
        "headless": bool(args.headless and not args.headed),
        "login_if_needed": not args.no_manual_filter,
        "wait_for_manual_filter": wait_for_manual_filter,
        "strict_location": True,
    }
    package_root = Path(args.package_root).resolve()
    jobs = collect_verama_jobs(source, package_root)
    if args.json:
        print(json.dumps(jobs, ensure_ascii=False, indent=2))
    else:
        ok = sum(1 for job in jobs if not job.get("error"))
        errors = len(jobs) - ok
        print(f"Collected {ok} Verama/Ework jobs, {errors} skipped/errors")
        for job in jobs:
            status = "ERROR" if job.get("error") else "OK"
            print(f"[{status}] {job.get('title_hint') or 'Untitled'} - {job.get('source_url')}")
            if job.get("error"):
                print(f"       {job.get('error')}")
    if not args.dry_run:
        out_dir = Path(args.out_dir)
        if not out_dir.is_absolute():
            out_dir = package_root / out_dir
        manifest = write_collected_jobs(out_dir, jobs, args.location)
        print(f"Wrote collected job files to {out_dir}")
        print(f"Manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
