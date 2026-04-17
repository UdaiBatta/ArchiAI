"""CLI for safety-first web scraping and chunk payload generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.safe_web_scraper import (
    build_chunk_payload_from_pages,
    crawl_source,
    load_source_configs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape approved web sources and export vectorless-RAG chunk JSON."
    )
    parser.add_argument(
        "--config",
        default="knowledge/source_configs/sources.sample.json",
        help="Path to source config JSON list.",
    )
    parser.add_argument(
        "--crawl-output-dir",
        default="outputs/scraped",
        help="Directory where raw pages and manifests are stored.",
    )
    parser.add_argument(
        "--payload-output",
        default="knowledge/raw/scraped_sources.json",
        help="Output JSON for combined scraped chunks.",
    )
    parser.add_argument(
        "--region-id",
        default="all",
        help="Region metadata for generated chunks.",
    )
    parser.add_argument(
        "--building-type",
        default="all",
        help="Building-type metadata for generated chunks.",
    )
    parser.add_argument(
        "--priority",
        type=float,
        default=0.9,
        help="Priority score for scraped chunks.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=15,
        help="HTTP request timeout for each page.",
    )
    parser.add_argument(
        "--user-agent",
        default="Archi3DDataBot",
        help="User-Agent used during crawling.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=None,
        help="Optional source name filter. Repeat to include multiple sources.",
    )
    return parser


def _load_pages(raw_pages_dir: Path) -> list[dict]:
    pages: list[dict] = []
    if not raw_pages_dir.exists():
        return pages

    for page_file in sorted(raw_pages_dir.glob("*.json")):
        try:
            page = json.loads(page_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(page, dict):
            pages.append(page)
    return pages


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config_path = Path(args.config)
    crawl_output_dir = Path(args.crawl_output_dir)
    payload_output = Path(args.payload_output)

    configs = load_source_configs(config_path)
    if args.source:
        wanted = {item.strip().lower() for item in args.source if item.strip()}
        configs = [cfg for cfg in configs if cfg.name.lower() in wanted]

    if not configs:
        raise SystemExit("No valid source configs found. Check --config and --source filters.")

    combined_chunks: list[dict] = []
    manifests: list[dict] = []

    for cfg in configs:
        manifest = crawl_source(
            cfg,
            crawl_output_dir,
            timeout_seconds=args.timeout_seconds,
            user_agent=args.user_agent,
        )
        manifests.append(manifest)

        pages = _load_pages(crawl_output_dir / cfg.name / "raw_pages")
        payload = build_chunk_payload_from_pages(
            pages,
            source_name=cfg.name,
            region_id=args.region_id,
            building_type=args.building_type,
            priority=args.priority,
        )
        combined_chunks.extend(payload.get("chunks", []))

    final_payload = {
        "doc_id": "scraped_sources_bundle",
        "source": "generated:safe_web_scraper",
        "region_id": args.region_id,
        "building_type": args.building_type,
        "priority": args.priority,
        "chunks": combined_chunks,
        "crawl_manifests": manifests,
    }

    payload_output.parent.mkdir(parents=True, exist_ok=True)
    payload_output.write_text(json.dumps(final_payload, indent=2), encoding="utf-8")

    print("Scraping pipeline completed")
    print(f"- Sources crawled: {len(configs)}")
    print(f"- Chunks generated: {len(combined_chunks)}")
    print(f"- Payload output: {payload_output}")

    for manifest in manifests:
        print(
            f"  * {manifest.get('source')}: "
            f"saved={manifest.get('saved_count')} "
            f"skipped={manifest.get('skipped_count')}"
        )


if __name__ == "__main__":
    main()
