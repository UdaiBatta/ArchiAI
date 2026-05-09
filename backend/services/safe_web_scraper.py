"""Safety-first web scraping utilities for dataset collection.

This module intentionally enforces domain allowlists, robots checks, and
license filtering before saving pages.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

LICENSE_PATTERNS = {
    "cc0": re.compile(r"\bcc0\b|creative\s*commons\s*zero", re.IGNORECASE),
    "cc-by": re.compile(r"\bcc\s*by\b|creative\s*commons\s*attribution", re.IGNORECASE),
    "cc-by-sa": re.compile(r"\bcc\s*by\s*-?\s*sa\b|sharealike", re.IGNORECASE),
    "public-domain": re.compile(r"public\s*domain", re.IGNORECASE),
    "mit": re.compile(r"\bmit\s*license\b", re.IGNORECASE),
    "apache-2.0": re.compile(r"apache\s*2\.0", re.IGNORECASE),
}

TEXT_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "article", "section"}
TITLE_TAGS = {"title", "h1"}


@dataclass
class SourceConfig:
    name: str
    start_urls: List[str]
    allowed_domains: List[str]
    max_pages: int = 100
    allowed_licenses: List[str] | None = None
    deny_path_keywords: List[str] | None = None


class _SimpleHTMLExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._title_parts: List[str] = []
        self._text_parts: List[str] = []
        self._capture_title = False
        self._capture_text = False
        self.links: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in TITLE_TAGS:
            self._capture_title = True
        if tag in TEXT_TAGS:
            self._capture_text = True
        if tag == "a":
            attr_map = {k.lower(): v for k, v in attrs}
            href = attr_map.get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in TITLE_TAGS:
            self._capture_title = False
        if tag in TEXT_TAGS:
            self._capture_text = False

    def handle_data(self, data: str) -> None:
        value = re.sub(r"\s+", " ", data).strip()
        if not value:
            return
        if self._capture_title:
            self._title_parts.append(value)
        if self._capture_text:
            self._text_parts.append(value)

    @property
    def title(self) -> str:
        title = " ".join(self._title_parts).strip()
        return title[:240]

    @property
    def text(self) -> str:
        text = " ".join(self._text_parts).strip()
        return text


def _normalize_url(base_url: str, maybe_relative: str) -> str:
    return urljoin(base_url, maybe_relative.strip())


def _domain_allowed(url: str, allowed_domains: Iterable[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    for domain in allowed_domains:
        d = domain.strip().lower()
        if host == d or host.endswith("." + d):
            return True
    return False


def _path_denied(url: str, deny_keywords: Iterable[str] | None) -> bool:
    if not deny_keywords:
        return False
    path = urlparse(url).path.lower()
    return any(keyword.lower() in path for keyword in deny_keywords)


def _license_from_text(text: str) -> str | None:
    for key, pattern in LICENSE_PATTERNS.items():
        if pattern.search(text):
            return key
    return None


def _is_license_allowed(license_key: str | None, allowed_licenses: Iterable[str] | None) -> bool:
    if not allowed_licenses:
        return True
    if not license_key:
        return False
    normalized = {item.strip().lower() for item in allowed_licenses}
    return license_key.lower() in normalized


def _robots_can_fetch(url: str, user_agent: str = "Archi3DDataBot") -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        return False


def _extract_page_data(url: str, html: str) -> Dict[str, object]:
    parser = _SimpleHTMLExtractor()
    parser.feed(html)

    title = parser.title or url
    text = parser.text
    normalized_links = []
    for href in parser.links:
        full = _normalize_url(url, href)
        if full.startswith("http://") or full.startswith("https://"):
            normalized_links.append(full)

    license_key = _license_from_text(" ".join([title, text]))

    return {
        "url": url,
        "title": title,
        "text": text,
        "links": sorted(set(normalized_links)),
        "license": license_key,
    }


def _slug_from_url(url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    host = (urlparse(url).hostname or "page").replace(".", "-")
    return f"{host}-{digest}"


def crawl_source(
    source: SourceConfig,
    output_dir: Path,
    *,
    timeout_seconds: int = 15,
    user_agent: str = "Archi3DDataBot",
) -> Dict[str, object]:
    queue: List[str] = list(source.start_urls)
    visited: set[str] = set()
    saved_pages: List[dict] = []
    skipped_pages: List[dict] = []

    output_dir = Path(output_dir)
    raw_pages_dir = output_dir / source.name / "raw_pages"
    raw_pages_dir.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": user_agent}

    with httpx.Client(timeout=timeout_seconds, headers=headers, follow_redirects=True) as client:
        while queue and len(visited) < source.max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            if not _domain_allowed(url, source.allowed_domains):
                skipped_pages.append({"url": url, "reason": "domain_not_allowed"})
                continue

            if _path_denied(url, source.deny_path_keywords):
                skipped_pages.append({"url": url, "reason": "path_denied"})
                continue

            if not _robots_can_fetch(url, user_agent=user_agent):
                skipped_pages.append({"url": url, "reason": "robots_disallowed"})
                continue

            try:
                response = client.get(url)
            except Exception as exc:
                skipped_pages.append({"url": url, "reason": f"request_error:{exc}"})
                continue

            if response.status_code >= 400:
                skipped_pages.append({"url": url, "reason": f"http_{response.status_code}"})
                continue

            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                skipped_pages.append({"url": url, "reason": "non_html"})
                continue

            page_data = _extract_page_data(url, response.text)
            if not _is_license_allowed(page_data.get("license"), source.allowed_licenses):
                skipped_pages.append({"url": url, "reason": "license_not_allowed"})
                continue

            slug = _slug_from_url(url)
            page_path = raw_pages_dir / f"{slug}.json"
            page_path.write_text(json.dumps(page_data, indent=2), encoding="utf-8")
            saved_pages.append(page_data)

            for link in page_data.get("links", []):
                if not isinstance(link, str):
                    continue
                if link in visited:
                    continue
                if not _domain_allowed(link, source.allowed_domains):
                    continue
                if _path_denied(link, source.deny_path_keywords):
                    continue
                queue.append(link)

    manifest = {
        "source": source.name,
        "visited_count": len(visited),
        "saved_count": len(saved_pages),
        "skipped_count": len(skipped_pages),
        "saved_pages": [{"url": page["url"], "license": page.get("license")} for page in saved_pages],
        "skipped_pages": skipped_pages,
    }
    (output_dir / source.name / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    return manifest


def build_chunk_payload_from_pages(
    pages: List[dict],
    *,
    source_name: str,
    region_id: str = "all",
    building_type: str = "all",
    priority: float = 1.0,
) -> Dict[str, object]:
    chunks: List[dict] = []

    for idx, page in enumerate(pages):
        text = str(page.get("text", "")).strip()
        if not text:
            continue

        title = str(page.get("title", "")).strip() or f"Page {idx + 1}"
        url = str(page.get("url", "")).strip()
        license_key = str(page.get("license", "")).strip().lower()

        base_tags = ["scraped", "web", "architecture", source_name.lower()]
        if license_key:
            base_tags.append(f"license:{license_key}")

        entities = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", f"{title} {text[:350]}".lower())
        dedup_entities: List[str] = []
        for entity in entities:
            if entity not in dedup_entities:
                dedup_entities.append(entity)

        section_path = [source_name, title[:120]]
        section_id = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-") or f"section-{idx+1}"

        chunks.append(
            {
                "id": f"scraped_{source_name}_{idx}",
                "title": title,
                "text": text,
                "source": url or f"scraped:{source_name}",
                "region_id": region_id,
                "building_type": building_type,
                "tags": sorted(set(base_tags + dedup_entities[:8])),
                "doc_id": f"scraped_{source_name}",
                "chapter_id": "web_pages",
                "section_id": section_id,
                "section_path": section_path,
                "page_no": None,
                "clause_id": section_id,
                "entities": dedup_entities[:20],
                "priority": priority,
            }
        )

    return {
        "doc_id": f"scraped_{source_name}",
        "source": f"scraped:{source_name}",
        "region_id": region_id,
        "building_type": building_type,
        "priority": priority,
        "chunks": chunks,
    }


def load_source_configs(config_path: Path) -> List[SourceConfig]:
    payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []

    configs: List[SourceConfig] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name", "")).strip()
        start_urls = [str(url).strip() for url in item.get("start_urls", []) if str(url).strip()]
        allowed_domains = [
            str(domain).strip().lower()
            for domain in item.get("allowed_domains", [])
            if str(domain).strip()
        ]
        if not name or not start_urls or not allowed_domains:
            continue

        configs.append(
            SourceConfig(
                name=name,
                start_urls=start_urls,
                allowed_domains=allowed_domains,
                max_pages=int(item.get("max_pages", 100)),
                allowed_licenses=[
                    str(entry).strip().lower()
                    for entry in item.get("allowed_licenses", [])
                    if str(entry).strip()
                ]
                or None,
                deny_path_keywords=[
                    str(entry).strip().lower()
                    for entry in item.get("deny_path_keywords", [])
                    if str(entry).strip()
                ]
                or None,
            )
        )

    return configs
