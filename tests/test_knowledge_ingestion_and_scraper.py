from __future__ import annotations

import json

from services.knowledge_ingestion import ingest_documents_from_paths, ingest_documents_to_json
from services.safe_web_scraper import (
    SourceConfig,
    build_chunk_payload_from_pages,
    crawl_source,
    load_source_configs,
)


def test_ingest_documents_to_json_with_sidecar(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    doc_path = docs_dir / "delhi_rules.md"
    doc_path.write_text(
        """
# Setbacks
Front setback should be 3m for this zone.

## Ventilation
Every habitable room should have natural ventilation.
""".strip(),
        encoding="utf-8",
    )

    sidecar_path = docs_dir / "delhi_rules.md.meta.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "doc_id": "delhi_rules_v1",
                "source": "delhi_rules_handbook",
                "region_id": "india_delhi",
                "building_type": "residential",
                "tags": ["bylaw", "setback"],
                "chapter_id": "chapter_setbacks",
                "clause_prefix": "dr-",
                "priority": 1.25,
            }
        ),
        encoding="utf-8",
    )

    output_file = tmp_path / "ingested.json"
    result = ingest_documents_to_json(docs_dir, output_file)

    assert result.input_files == 1
    assert result.ingested_docs == 1
    assert result.total_chunks >= 1
    assert output_file.exists()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["doc_id"] == "knowledge_ingestion_bundle"
    assert payload["chunks"]

    first = payload["chunks"][0]
    assert first["doc_id"] == "delhi_rules_v1"
    assert first["source"] == "delhi_rules_handbook"
    assert first["region_id"] == "india_delhi"
    assert first["building_type"] == "residential"
    assert first["chapter_id"] == "chapter_setbacks"
    assert first["section_path"]
    assert "bylaw" in first["tags"]


def test_ingest_documents_from_paths(tmp_path):
    source_doc = tmp_path / "source_doc.txt"
    source_doc.write_text(
        "Room placement should prioritize daylight and natural airflow.",
        encoding="utf-8",
    )

    output_file = tmp_path / "from_paths.json"
    result = ingest_documents_from_paths([source_doc], output_file, default_region_id="all")

    assert result.input_files == 1
    assert result.ingested_docs == 1
    assert result.total_chunks >= 1

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["chunks"]


def test_load_source_configs_filters_invalid(tmp_path):
    config_path = tmp_path / "sources.json"
    config_path.write_text(
        json.dumps(
            [
                {
                    "name": "valid_source",
                    "start_urls": ["https://example.org/start"],
                    "allowed_domains": ["example.org"],
                    "max_pages": 5,
                    "allowed_licenses": ["cc-by"],
                },
                {
                    "name": "invalid_missing_domains",
                    "start_urls": ["https://invalid.local"],
                },
                "bad_entry",
            ]
        ),
        encoding="utf-8",
    )

    configs = load_source_configs(config_path)
    assert len(configs) == 1
    assert configs[0].name == "valid_source"
    assert configs[0].allowed_domains == ["example.org"]


def test_build_chunk_payload_from_pages_adds_metadata():
    pages = [
        {
            "url": "https://example.org/a",
            "title": "Courtyard Planning",
            "text": "Creative Commons Attribution guidance for courtyard ventilation.",
            "license": "cc-by",
        }
    ]

    payload = build_chunk_payload_from_pages(
        pages,
        source_name="example_source",
        region_id="india_mumbai",
        building_type="residential",
        priority=0.85,
    )

    assert payload["doc_id"] == "scraped_example_source"
    assert len(payload["chunks"]) == 1

    chunk = payload["chunks"][0]
    assert chunk["region_id"] == "india_mumbai"
    assert chunk["building_type"] == "residential"
    assert chunk["priority"] == 0.85
    assert "license:cc-by" in chunk["tags"]


class _FakeResponse:
    def __init__(self, *, text: str, status_code: int = 200, content_type: str = "text/html"):
        self.text = text
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}


class _FakeClient:
    def __init__(self, pages: dict[str, _FakeResponse], **_kwargs):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str):
        return self.pages.get(
            url,
            _FakeResponse(text="<html><title>Missing</title><p>cc-by</p></html>", status_code=404),
        )


def test_crawl_source_respects_allowlist_and_generates_manifest(monkeypatch, tmp_path):
    start_url = "https://allowed.example.com/start"
    next_url = "https://allowed.example.com/next"

    start_html = (
        "<html><title>Start Page</title><body>"
        "<p>Creative Commons Attribution licensed architecture notes.</p>"
        f"<a href=\"{next_url}\">next</a>"
        "<a href=\"https://blocked.example.com/x\">blocked</a>"
        "</body></html>"
    )
    next_html = (
        "<html><title>Next Page</title><body>"
        "<p>Creative Commons Attribution more details.</p>"
        "</body></html>"
    )

    pages = {
        start_url: _FakeResponse(text=start_html),
        next_url: _FakeResponse(text=next_html),
    }

    monkeypatch.setattr("services.safe_web_scraper._robots_can_fetch", lambda *_args, **_kwargs: True)
    monkeypatch.setattr("services.safe_web_scraper.httpx.Client", lambda **kwargs: _FakeClient(pages, **kwargs))

    source = SourceConfig(
        name="demo_source",
        start_urls=[start_url],
        allowed_domains=["allowed.example.com"],
        max_pages=10,
        allowed_licenses=["cc-by"],
        deny_path_keywords=["private"],
    )

    manifest = crawl_source(source, tmp_path)

    assert manifest["source"] == "demo_source"
    assert manifest["saved_count"] == 2
    assert manifest["visited_count"] == 2

    raw_pages_dir = tmp_path / "demo_source" / "raw_pages"
    assert raw_pages_dir.exists()
    assert len(list(raw_pages_dir.glob("*.json"))) == 2

    saved_urls = [item["url"] for item in manifest["saved_pages"]]
    assert start_url in saved_urls
    assert next_url in saved_urls
