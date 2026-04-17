"""Knowledge ingestion utilities for vectorless RAG.

This module ingests multiple document types into chunked JSON payloads
compatible with services/vectorless_rag.py.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class IngestionResult:
    input_files: int
    ingested_docs: int
    output_path: Path
    total_chunks: int
    skipped_files: List[str]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "section"


def _load_sidecar_metadata(doc_path: Path) -> Dict[str, object]:
    sidecar_path = doc_path.with_suffix(doc_path.suffix + ".meta.json")
    if not sidecar_path.exists():
        return {}

    try:
        return json.loads(sidecar_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_markdown_sections(content: str, fallback_title: str) -> List[dict]:
    lines = content.splitlines()
    stack: List[str] = []
    sections: List[dict] = []

    current_title = fallback_title
    current_path = [fallback_title]
    buffer: List[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if not text:
            return
        sections.append(
            {
                "title": current_title,
                "section_path": list(current_path),
                "text": text,
            }
        )

    for line in lines:
        match = HEADING_RE.match(line.strip())
        if match:
            flush()
            buffer.clear()

            level = len(match.group(1))
            heading = match.group(2).strip()
            if level <= len(stack):
                stack = stack[: level - 1]
            stack.append(heading)

            current_title = heading
            current_path = list(stack)
            continue

        buffer.append(line)

    flush()

    if not sections and content.strip():
        sections.append(
            {
                "title": fallback_title,
                "section_path": [fallback_title],
                "text": content.strip(),
            }
        )

    return sections


def _parse_plaintext_sections(content: str, fallback_title: str) -> List[dict]:
    text = content.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    sections = []
    for idx, paragraph in enumerate(paragraphs):
        sections.append(
            {
                "title": f"{fallback_title} Part {idx + 1}",
                "section_path": [fallback_title, f"part_{idx + 1}"],
                "text": paragraph,
            }
        )
    return sections


def _parse_pdf_sections(path: Path, fallback_title: str) -> List[dict]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return []

    try:
        reader = PdfReader(str(path))
    except Exception:
        return []

    sections: List[dict] = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        sections.append(
            {
                "title": f"{fallback_title} Page {page_index}",
                "section_path": [fallback_title, f"page_{page_index}"],
                "text": text,
                "page_no": page_index,
            }
        )

    return sections


def _load_document_sections(path: Path) -> List[dict]:
    suffix = path.suffix.lower()
    fallback_title = path.stem.replace("_", " ").replace("-", " ").title()

    if suffix in {".md", ".markdown"}:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return _parse_markdown_sections(content, fallback_title)

    if suffix in {".txt"}:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return _parse_plaintext_sections(content, fallback_title)

    if suffix in {".pdf"}:
        return _parse_pdf_sections(path, fallback_title)

    return []


def _chunk_text(text: str, chunk_chars: int = 1200, overlap_chars: int = 200) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    if len(text) <= chunk_chars:
        return [text]

    chunks: List[str] = []
    cursor = 0
    while cursor < len(text):
        end = min(len(text), cursor + chunk_chars)
        segment = text[cursor:end]

        if end < len(text):
            split_points = [m.start() for m in re.finditer(r"[.!?] ", segment)]
            if split_points:
                end = cursor + split_points[-1] + 1
                segment = text[cursor:end]

        chunks.append(segment.strip())
        if end >= len(text):
            break

        cursor = max(0, end - overlap_chars)

    return [chunk for chunk in chunks if chunk]


def _chunk_entities(title: str, section_path: List[str], text: str) -> List[str]:
    seed = " ".join([title] + section_path + SENTENCE_SPLIT_RE.split(text[:400]))
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", seed.lower())
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "are",
        "was",
        "were",
        "have",
        "has",
    }
    unique = []
    for token in tokens:
        if token in stop:
            continue
        if token not in unique:
            unique.append(token)
    return unique[:20]


def ingest_documents_to_json(
    input_dir: Path,
    output_file: Path,
    *,
    default_region_id: str = "all",
    default_building_type: str = "all",
    default_priority: float = 1.0,
    chunk_chars: int = 1200,
    overlap_chars: int = 200,
) -> IngestionResult:
    input_dir = Path(input_dir)
    output_file = Path(output_file)

    docs: List[dict] = []
    skipped: List[str] = []
    total_chunks = 0

    candidates = [
        path
        for path in sorted(input_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in {".md", ".markdown", ".txt", ".pdf"}
    ]

    for doc_path in candidates:
        metadata = _load_sidecar_metadata(doc_path)
        sections = _load_document_sections(doc_path)
        if not sections:
            skipped.append(str(doc_path.relative_to(input_dir)))
            continue

        doc_id = str(metadata.get("doc_id", doc_path.stem)).strip() or doc_path.stem
        source = str(metadata.get("source", doc_path.name)).strip() or doc_path.name
        region_id = str(metadata.get("region_id", default_region_id)).strip().lower() or "all"
        building_type = (
            str(metadata.get("building_type", default_building_type)).strip().lower() or "all"
        )
        chapter_id = str(metadata.get("chapter_id", "")).strip()
        clause_prefix = str(metadata.get("clause_prefix", "")).strip()
        tags = [str(tag).strip().lower() for tag in metadata.get("tags", []) if str(tag).strip()]
        priority = float(metadata.get("priority", default_priority))

        chunks: List[dict] = []
        chunk_counter = 0

        for section_idx, section in enumerate(sections):
            title = str(section.get("title", f"Section {section_idx + 1}")).strip()
            section_path = section.get("section_path", [title])
            if not isinstance(section_path, list):
                section_path = [title]
            section_path = [str(entry).strip() for entry in section_path if str(entry).strip()] or [title]

            section_text = str(section.get("text", "")).strip()
            page_no = section.get("page_no")
            if page_no is not None:
                try:
                    page_no = int(page_no)
                except (TypeError, ValueError):
                    page_no = None

            text_chunks = _chunk_text(section_text, chunk_chars=chunk_chars, overlap_chars=overlap_chars)
            for part_idx, chunk_text in enumerate(text_chunks):
                section_slug = _slugify("::".join(section_path))
                chunk_id = f"{doc_id}_{chunk_counter}"
                chunk_counter += 1

                chapter = chapter_id or _slugify(section_path[0])
                clause_id = f"{clause_prefix}{section_slug}" if clause_prefix else section_slug
                entities = _chunk_entities(title, section_path, chunk_text)

                chunks.append(
                    {
                        "id": chunk_id,
                        "title": title,
                        "text": chunk_text,
                        "source": source,
                        "region_id": region_id,
                        "building_type": building_type,
                        "tags": sorted(set(tags + entities[:8])),
                        "doc_id": doc_id,
                        "chapter_id": chapter,
                        "section_id": section_slug,
                        "section_path": section_path,
                        "page_no": page_no,
                        "clause_id": clause_id,
                        "entities": entities,
                        "priority": priority,
                        "part_index": part_idx,
                    }
                )

        docs.append(
            {
                "doc_id": doc_id,
                "source": source,
                "region_id": region_id,
                "building_type": building_type,
                "priority": priority,
                "chunks": chunks,
            }
        )
        total_chunks += len(chunks)

    flat_chunks: List[dict] = []
    for doc in docs:
        flat_chunks.extend(doc["chunks"])

    payload = {
        "doc_id": "knowledge_ingestion_bundle",
        "source": "generated:knowledge_ingestion",
        "region_id": "all",
        "building_type": "all",
        "priority": 1.0,
        "chunks": flat_chunks,
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return IngestionResult(
        input_files=len(candidates),
        ingested_docs=len(docs),
        output_path=output_file,
        total_chunks=total_chunks,
        skipped_files=skipped,
    )


def ingest_documents_from_paths(
    paths: Iterable[Path],
    output_file: Path,
    **kwargs,
) -> IngestionResult:
    temp_root = Path(output_file).parent / ".ingestion_temp"
    if temp_root.exists():
        for old in temp_root.rglob("*"):
            if old.is_file():
                old.unlink()
    temp_root.mkdir(parents=True, exist_ok=True)

    for source_path in paths:
        source_path = Path(source_path)
        if source_path.is_file():
            target = temp_root / source_path.name
            target.write_bytes(source_path.read_bytes())
            sidecar = source_path.with_suffix(source_path.suffix + ".meta.json")
            if sidecar.exists():
                (temp_root / sidecar.name).write_bytes(sidecar.read_bytes())

    return ingest_documents_to_json(temp_root, output_file, **kwargs)
