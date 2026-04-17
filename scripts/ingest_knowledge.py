"""CLI for ingesting multiple local documents into knowledge/raw JSON chunks."""

from __future__ import annotations

import argparse
from pathlib import Path

from services.knowledge_ingestion import ingest_documents_to_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest local documents into vectorless-RAG chunk JSON format."
    )
    parser.add_argument(
        "--input-dir",
        default="knowledge/source_docs",
        help="Directory containing .md/.txt/.pdf docs and optional .meta.json sidecars.",
    )
    parser.add_argument(
        "--output-file",
        default="knowledge/raw/ingested_documents.json",
        help="Output JSON file path in chunk payload format.",
    )
    parser.add_argument("--default-region", default="all", help="Default region_id when sidecar is missing.")
    parser.add_argument(
        "--default-building-type",
        default="all",
        help="Default building_type when sidecar is missing.",
    )
    parser.add_argument("--default-priority", type=float, default=1.0, help="Default chunk priority.")
    parser.add_argument("--chunk-chars", type=int, default=1200, help="Max chars per chunk.")
    parser.add_argument("--overlap-chars", type=int, default=200, help="Chunk overlap size.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    result = ingest_documents_to_json(
        input_dir=Path(args.input_dir),
        output_file=Path(args.output_file),
        default_region_id=args.default_region,
        default_building_type=args.default_building_type,
        default_priority=args.default_priority,
        chunk_chars=args.chunk_chars,
        overlap_chars=args.overlap_chars,
    )

    print("Knowledge ingestion completed")
    print(f"- Input files detected: {result.input_files}")
    print(f"- Documents ingested:   {result.ingested_docs}")
    print(f"- Chunks generated:     {result.total_chunks}")
    print(f"- Output file:          {result.output_path}")
    if result.skipped_files:
        print(f"- Skipped files:        {len(result.skipped_files)}")
        for item in result.skipped_files[:20]:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
