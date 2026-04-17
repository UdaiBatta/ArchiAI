"""Vectorless retrieval utilities for architectural planning knowledge.

This module intentionally avoids embeddings and uses metadata, structure,
and BM25-style lexical matching for grounded retrieval.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List

from rank_bm25 import BM25Okapi

from services.bylaw_loader import BylawRuleset

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]{1,}")
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "section"


@dataclass
class KnowledgeChunk:
    chunk_id: str
    title: str
    text: str
    source: str
    region_id: str = "all"
    building_type: str = "all"
    tags: List[str] = field(default_factory=list)
    doc_id: str = ""
    chapter_id: str = ""
    section_id: str = ""
    section_path: List[str] = field(default_factory=list)
    page_no: int | None = None
    clause_id: str = ""
    entities: List[str] = field(default_factory=list)
    priority: float = 1.0

    def to_dict(self, score: float) -> dict:
        return {
            "id": self.chunk_id,
            "title": self.title,
            "text": self.text,
            "source": self.source,
            "region_id": self.region_id,
            "building_type": self.building_type,
            "tags": self.tags,
            "doc_id": self.doc_id,
            "chapter_id": self.chapter_id,
            "section_id": self.section_id,
            "section_path": self.section_path,
            "page_no": self.page_no,
            "clause_id": self.clause_id,
            "entities": self.entities,
            "priority": self.priority,
            "score": round(float(score), 4),
        }


def _tokenize(text: str) -> List[str]:
    return [token.lower() for token in WORD_RE.findall(text)]


def _default_chunks() -> List[KnowledgeChunk]:
    return [
        KnowledgeChunk(
            chunk_id="k_default_living_01",
            title="Living room near entry",
            text=(
                "Place the living room close to the primary entry for intuitive visitor access. "
                "Keep clear circulation from living to staircase and kitchen."
            ),
            source="built_in:residential_heuristics",
            tags=["residential", "circulation", "living_room"],
            doc_id="residential_heuristics",
            chapter_id="zoning",
            section_id="living-near-entry",
            section_path=["Residential Planning Heuristics", "Entry and Public Zone"],
            entities=["living_room", "entry", "circulation"],
            priority=1.3,
        ),
        KnowledgeChunk(
            chunk_id="k_default_kitchen_01",
            title="Kitchen adjacency",
            text=(
                "Kitchen should stay adjacent to dining or living for efficient movement. "
                "Ensure one exterior wall for ventilation and daylight where possible."
            ),
            source="built_in:residential_heuristics",
            tags=["residential", "kitchen", "ventilation"],
            doc_id="residential_heuristics",
            chapter_id="functional_adjacency",
            section_id="kitchen-adjacency",
            section_path=["Residential Planning Heuristics", "Kitchen and Service Logic"],
            entities=["kitchen", "dining", "ventilation"],
            priority=1.3,
        ),
        KnowledgeChunk(
            chunk_id="k_default_stair_01",
            title="Stair placement",
            text=(
                "Staircases should be centrally reachable and not block primary circulation. "
                "Provide direct vertical connectivity from the entrance zone."
            ),
            source="built_in:residential_heuristics",
            tags=["circulation", "staircase"],
            doc_id="residential_heuristics",
            chapter_id="vertical_core",
            section_id="stair-placement",
            section_path=["Residential Planning Heuristics", "Stair and Vertical Core"],
            entities=["staircase", "circulation"],
            priority=1.25,
        ),
        KnowledgeChunk(
            chunk_id="k_default_bed_01",
            title="Bedroom privacy",
            text=(
                "Locate bedrooms away from noisy entry edges. "
                "Stack wet areas vertically to simplify plumbing and service shafts."
            ),
            source="built_in:residential_heuristics",
            tags=["bedroom", "privacy", "services"],
            doc_id="residential_heuristics",
            chapter_id="private_zone",
            section_id="bedroom-privacy",
            section_path=["Residential Planning Heuristics", "Bedroom Privacy"],
            entities=["bedroom", "bathroom", "services"],
            priority=1.2,
        ),
        KnowledgeChunk(
            chunk_id="k_default_vastu_01",
            title="Vastu as preference",
            text=(
                "Apply Vastu recommendations after legal constraints. "
                "When conflicts occur, keep bylaws and safety as higher priority."
            ),
            source="built_in:vastu_guidance",
            tags=["vastu", "tradeoff"],
            doc_id="vastu_guidance",
            chapter_id="conflict_resolution",
            section_id="vastu-preference",
            section_path=["Vastu Preference Guidance"],
            entities=["vastu", "tradeoff", "bylaw"],
            priority=1.15,
        ),
    ]


def _parse_markdown_chunks(path: Path) -> List[KnowledgeChunk]:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    chunks: List[KnowledgeChunk] = []
    section_stack: List[str] = []
    current_title = path.stem.replace("_", " ").title()
    current_section_path = [current_title]
    buffer: List[str] = []
    chunk_index = 0

    def flush_buffer() -> None:
        nonlocal chunk_index
        text = "\n".join(buffer).strip()
        if not text:
            return

        chapter_id = _slugify(current_section_path[0]) if current_section_path else _slugify(path.stem)
        section_id = _slugify("::".join(current_section_path))
        tags = [token for token in _tokenize(" ".join(current_section_path)) if len(token) > 2][:8]

        chunks.append(
            KnowledgeChunk(
                chunk_id=f"{path.stem}_{chunk_index}",
                title=current_title,
                text=text,
                source=str(path.name),
                doc_id=path.stem,
                chapter_id=chapter_id,
                section_id=section_id,
                section_path=list(current_section_path),
                tags=sorted(set(tags)),
                entities=sorted(set(tags)),
            )
        )
        chunk_index += 1

    for line in lines:
        heading_match = HEADING_RE.match(line.strip())
        if heading_match:
            flush_buffer()
            buffer.clear()

            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            if level <= len(section_stack):
                section_stack = section_stack[: level - 1]
            section_stack.append(heading_text)

            current_title = heading_text
            current_section_path = list(section_stack)
            continue

        buffer.append(line)

    flush_buffer()

    if not chunks:
        fallback_text = content.strip()
        if fallback_text:
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{path.stem}_0",
                    title=current_title,
                    text=fallback_text,
                    source=str(path.name),
                    doc_id=path.stem,
                    chapter_id=_slugify(path.stem),
                    section_id=_slugify(path.stem),
                    section_path=[current_title],
                    tags=[token for token in _tokenize(path.stem) if len(token) > 2],
                )
            )

    return chunks


def _parse_json_chunks(path: Path) -> List[KnowledgeChunk]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks: List[KnowledgeChunk] = []

    root_doc_id = path.stem
    root_source = path.name
    root_region = "all"
    root_building_type = "all"
    root_chapter_id = ""
    root_priority = 1.0

    if isinstance(payload, dict):
        root_doc_id = str(payload.get("doc_id", root_doc_id)).strip() or path.stem
        root_source = str(payload.get("source", root_source)).strip() or path.name
        root_region = str(payload.get("region_id", "all")).strip().lower() or "all"
        root_building_type = str(payload.get("building_type", "all")).strip().lower() or "all"
        root_chapter_id = str(payload.get("chapter_id", "")).strip()
        try:
            root_priority = float(payload.get("priority", 1.0))
        except (TypeError, ValueError):
            root_priority = 1.0
        payload = payload.get("chunks", [])

    if not isinstance(payload, list):
        return chunks

    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            continue

        text = str(item.get("text", "")).strip()
        if not text:
            continue

        raw_section_path = item.get("section_path", [])
        if isinstance(raw_section_path, str):
            section_path = [raw_section_path.strip()] if raw_section_path.strip() else []
        elif isinstance(raw_section_path, list):
            section_path = [str(entry).strip() for entry in raw_section_path if str(entry).strip()]
        else:
            section_path = []

        page_raw = item.get("page_no")
        page_no = None
        if page_raw is not None:
            try:
                page_no = int(page_raw)
            except (TypeError, ValueError):
                page_no = None

        entities = [
            str(entity).strip().lower()
            for entity in item.get("entities", [])
            if str(entity).strip()
        ]

        tags = [str(tag).strip().lower() for tag in item.get("tags", []) if str(tag).strip()]
        entities = sorted(set(entities + tags))

        try:
            priority = float(item.get("priority", root_priority))
        except (TypeError, ValueError):
            priority = root_priority

        chapter_id = str(item.get("chapter_id", root_chapter_id)).strip()
        if not chapter_id:
            chapter_id = _slugify(section_path[0]) if section_path else _slugify(path.stem)

        section_id = str(item.get("section_id", "")).strip()
        if not section_id:
            joined = "::".join(section_path) if section_path else str(item.get("title", path.stem))
            section_id = _slugify(joined)

        chunks.append(
            KnowledgeChunk(
                chunk_id=str(item.get("id", f"{path.stem}_{idx}")),
                title=str(item.get("title", path.stem)).strip(),
                text=text,
                source=str(item.get("source", root_source)).strip() or root_source,
                region_id=str(item.get("region_id", root_region)).strip().lower() or "all",
                building_type=str(item.get("building_type", root_building_type)).strip().lower() or "all",
                tags=tags,
                doc_id=str(item.get("doc_id", root_doc_id)).strip() or root_doc_id,
                chapter_id=chapter_id,
                section_id=section_id,
                section_path=section_path,
                page_no=page_no,
                clause_id=str(item.get("clause_id", "")).strip(),
                entities=entities,
                priority=priority,
            )
        )

    return chunks


def load_knowledge_chunks(knowledge_raw_dir: Path) -> List[KnowledgeChunk]:
    chunks: List[KnowledgeChunk] = []

    if knowledge_raw_dir.exists():
        for path in sorted(knowledge_raw_dir.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() in {".md", ".txt"}:
                chunks.extend(_parse_markdown_chunks(path))
            elif path.suffix.lower() == ".json":
                chunks.extend(_parse_json_chunks(path))

    if not chunks:
        chunks.extend(_default_chunks())

    return chunks


def build_bylaw_context_chunks(bylaws: BylawRuleset) -> List[KnowledgeChunk]:
    doc_id = f"bylaw_{bylaws.region_id}"
    chapter = f"{bylaws.building_type}_rules"
    return [
        KnowledgeChunk(
            chunk_id=f"bylaw_{bylaws.region_id}_setbacks",
            title="Setback constraints",
            text=(
                f"Front setback {bylaws.setback_front_m}m, rear setback {bylaws.setback_rear_m}m, "
                f"side setback {bylaws.setback_side_m}m each side."
            ),
            source=f"bylaws:{bylaws.region_id}",
            region_id=bylaws.region_id,
            building_type=bylaws.building_type,
            tags=["bylaw", "setback"],
            doc_id=doc_id,
            chapter_id=chapter,
            section_id="setbacks",
            section_path=["Bylaw Clauses", "Setback constraints"],
            clause_id="setback",
            entities=["setback", "front", "rear", "side"],
            priority=1.6,
        ),
        KnowledgeChunk(
            chunk_id=f"bylaw_{bylaws.region_id}_far",
            title="FAR and floors",
            text=(
                f"Maximum FAR {bylaws.max_far}, maximum floors {bylaws.max_floors}, "
                f"maximum height {bylaws.max_height_m}m."
            ),
            source=f"bylaws:{bylaws.region_id}",
            region_id=bylaws.region_id,
            building_type=bylaws.building_type,
            tags=["bylaw", "far", "height"],
            doc_id=doc_id,
            chapter_id=chapter,
            section_id="far-height",
            section_path=["Bylaw Clauses", "FAR and floors"],
            clause_id="far",
            entities=["far", "fsi", "height", "floors"],
            priority=1.8,
        ),
        KnowledgeChunk(
            chunk_id=f"bylaw_{bylaws.region_id}_coverage",
            title="Coverage and parking",
            text=(
                f"Maximum plot coverage {bylaws.max_plot_coverage_pct} percent. "
                f"Parking minimum {bylaws.parking.min_stalls_per_unit} per unit."
            ),
            source=f"bylaws:{bylaws.region_id}",
            region_id=bylaws.region_id,
            building_type=bylaws.building_type,
            tags=["bylaw", "coverage", "parking"],
            doc_id=doc_id,
            chapter_id=chapter,
            section_id="coverage-parking",
            section_path=["Bylaw Clauses", "Coverage and parking"],
            clause_id="coverage",
            entities=["coverage", "parking", "ecs"],
            priority=1.7,
        ),
    ]


def _chunk_matches_scope(chunk: KnowledgeChunk, region_id: str, building_type: str) -> bool:
    region_match = chunk.region_id in {"all", region_id}
    building_match = chunk.building_type in {"all", building_type}
    return region_match and building_match


class VectorlessKnowledgeRetriever:
    """Keyword and metadata based retriever with BM25 scoring."""

    def __init__(self, knowledge_raw_dir: Path):
        self.knowledge_raw_dir = knowledge_raw_dir
        self._chunks = load_knowledge_chunks(knowledge_raw_dir)
        self._region_index: Dict[str, List[int]] = {}
        self._building_type_index: Dict[str, List[int]] = {}
        self._build_metadata_index()

    def _build_metadata_index(self) -> None:
        region_index: Dict[str, List[int]] = {}
        building_index: Dict[str, List[int]] = {}

        for idx, chunk in enumerate(self._chunks):
            region_index.setdefault(chunk.region_id, []).append(idx)
            building_index.setdefault(chunk.building_type, []).append(idx)

        self._region_index = region_index
        self._building_type_index = building_index

    def _scoped_base_chunks(self, region_id: str, building_type: str) -> List[KnowledgeChunk]:
        region_candidate_ids = set(self._region_index.get("all", [])) | set(
            self._region_index.get(region_id, [])
        )
        building_candidate_ids = set(self._building_type_index.get("all", [])) | set(
            self._building_type_index.get(building_type, [])
        )

        scoped_ids = sorted(region_candidate_ids & building_candidate_ids)
        if not scoped_ids:
            return list(self._chunks)

        return [self._chunks[idx] for idx in scoped_ids]

    def _combined_chunk_terms(self, chunk: KnowledgeChunk) -> set[str]:
        terms = set(chunk.tags)
        terms.update(chunk.entities)
        terms.update(_tokenize(" ".join(chunk.section_path)))
        if chunk.clause_id:
            terms.update(_tokenize(chunk.clause_id))
        if chunk.doc_id:
            terms.update(_tokenize(chunk.doc_id))
        return terms

    def retrieve(
        self,
        query: str,
        region_id: str,
        building_type: str,
        top_k: int = 5,
        extra_chunks: Iterable[KnowledgeChunk] | None = None,
    ) -> List[dict]:
        region_id = str(region_id or "all").strip().lower()
        building_type = str(building_type or "all").strip().lower()

        chunks = self._scoped_base_chunks(region_id=region_id, building_type=building_type)
        if extra_chunks:
            chunks.extend(
                chunk
                for chunk in extra_chunks
                if _chunk_matches_scope(chunk, region_id=region_id, building_type=building_type)
            )

        if not chunks:
            return []

        corpus = [_tokenize(f"{chunk.title} {chunk.text} {' '.join(chunk.tags)}") for chunk in chunks]
        query_tokens = _tokenize(query)

        if not query_tokens:
            query_tokens = _tokenize(f"{region_id} {building_type} residence layout")

        query_token_set = set(query_tokens)

        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query_tokens)

        ranked = []
        for chunk, score in zip(chunks, scores):
            boosted = float(score)

            if chunk.region_id in {"all", region_id}:
                boosted += 1.0
            if chunk.building_type in {"all", building_type}:
                boosted += 0.7
            if region_id in chunk.text.lower() or building_type in chunk.text.lower():
                boosted += 0.5

            metadata_terms = self._combined_chunk_terms(chunk)
            metadata_overlap = len(query_token_set & metadata_terms)
            boosted += metadata_overlap * 0.35

            if chunk.priority > 0:
                boosted += min(chunk.priority, 3.0) * 0.2

            if chunk.page_no is not None:
                boosted += 0.05

            ranked.append((boosted, chunk))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [chunk.to_dict(score) for score, chunk in ranked[: max(1, top_k)]]
