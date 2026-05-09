"""CLI for ingesting multiple local documents into knowledge/raw JSON chunks."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

from services.knowledge_ingestion import ingest_documents_from_paths, ingest_documents_to_json

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf"}


def _discover_input_files(input_dir: Path) -> List[Path]:
    return [
        path
        for path in sorted(input_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def _iter_batches(items: List[Path], batch_size: int) -> Iterable[List[Path]]:
    for idx in range(0, len(items), batch_size):
        yield items[idx : idx + batch_size]


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
    parser.add_argument(
        "--max-section-chars",
        type=int,
        default=300000,
        help="Hard cap per section/page text before chunking to prevent memory spikes.",
    )
    parser.add_argument(
        "--max-pdf-pages",
        type=int,
        default=300,
        help="Max pages parsed per PDF to avoid runaway ingestion.",
    )
    parser.add_argument(
        "--max-pdf-chars",
        type=int,
        default=1500000,
        help="Max extracted text chars per PDF before truncation.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="Process files in batches (for example 2). When >0, writes one output JSON per batch.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_file = Path(args.output_file)

    if args.batch_size <= 0:
        result = ingest_documents_to_json(
            input_dir=input_dir,
            output_file=output_file,
            default_region_id=args.default_region,
            default_building_type=args.default_building_type,
            default_priority=args.default_priority,
            chunk_chars=args.chunk_chars,
            overlap_chars=args.overlap_chars,
            max_section_chars=args.max_section_chars,
            max_pdf_pages=args.max_pdf_pages,
            max_pdf_chars=args.max_pdf_chars,
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
        return

    files = _discover_input_files(input_dir)
    if not files:
        print("Knowledge ingestion completed")
        print("- Input files detected: 0")
        print("- No supported files found for batched processing")
        return

    stem = output_file.stem
    suffix = output_file.suffix or ".json"
    output_dir = output_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    total_files = len(files)
    total_ingested = 0
    total_chunks = 0
    all_skipped: List[str] = []

    for batch_index, batch_paths in enumerate(_iter_batches(files, args.batch_size), start=1):
        batch_output = output_dir / f"{stem}_batch{batch_index:03d}{suffix}"
        result = ingest_documents_from_paths(
            paths=batch_paths,
            output_file=batch_output,
            default_region_id=args.default_region,
            default_building_type=args.default_building_type,
            default_priority=args.default_priority,
            chunk_chars=args.chunk_chars,
            overlap_chars=args.overlap_chars,
            max_section_chars=args.max_section_chars,
            max_pdf_pages=args.max_pdf_pages,
            max_pdf_chars=args.max_pdf_chars,
        )

        total_ingested += result.ingested_docs
        total_chunks += result.total_chunks
        all_skipped.extend(result.skipped_files)

        print(
            f"Batch {batch_index:03d}: files={len(batch_paths)} "
            f"ingested={result.ingested_docs} chunks={result.total_chunks} output={batch_output}"
        )

    print("Knowledge ingestion completed")
    print(f"- Input files detected: {total_files}")
    print(f"- Documents ingested:   {total_ingested}")
    print(f"- Chunks generated:     {total_chunks}")
    print(f"- Output directory:     {output_dir}")
    if all_skipped:
        print(f"- Skipped files:        {len(all_skipped)}")
        for item in all_skipped[:20]:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
