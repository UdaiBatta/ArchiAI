# Archi3D AI Planning System - Step-by-Step Roadmap

This roadmap tracks the implementation of an explainable, bylaw-aware conceptual design system using Ollama, vectorless retrieval, deterministic compliance, and Hypar-compatible geometry output.

## Current Status

Implemented in this iteration:
- Input parser with optional Ollama extraction and deterministic fallback heuristics
- Vectorless RAG retrieval using BM25, metadata boosts, and bylaw context chunks
- Deterministic compliance engine integration (existing)
- Heuristic layout generator constrained by coverage and adjusted floors
- Geometry conversion to Hypar-compatible JSON payload
- Optional Vastu preference evaluation with explicit priority ordering
- Explanation builder combining bylaw checks, knowledge references, and trade-offs
- API integration through a single orchestrated planning pipeline
- Clarification-aware API contract with missing-field questions
- Strict clarification gate that defers generation when critical fields are missing
- Layout quality scoring with adjacency and circulation metrics
- Deterministic geometry validation checks before export
- Optional Hypar API submission hook (config driven)
- Multi-document knowledge ingestion pipeline (markdown/txt/pdf with metadata sidecars)
- Safety-first web scraping pipeline (domain allowlist, robots checks, license filtering)

## Step 1 - Input Understanding

Files:
- services/input_parser.py
- apps/design/serializers.py

What it does:
- Parses structured request fields directly
- Uses raw text heuristics for plot size, floors, rooms, preferences, region, and Vastu
- Attempts Ollama parsing when available, with deterministic fallback when unavailable

## Step 2 - Vectorless Knowledge Retrieval

Files:
- services/vectorless_rag.py
- knowledge/raw/architectural_principles.md

What it does:
- Loads chunked knowledge from markdown/json files
- Uses BM25 lexical scoring and metadata boosts
- Adds explicit bylaw context chunks to retrieval results

## Step 3 - Bylaw Compliance (Deterministic)

Files:
- services/rule_engine.py
- services/bylaw_loader.py

What it does:
- Applies setbacks, FAR, floors, height, coverage, and parking checks
- Produces transparent pass/fail checks with notes
- Keeps legal compliance outside LLM logic

## Step 4 - Zoning and Layout

Files:
- services/layout_generator.py

What it does:
- Generates floor-wise conceptual rectangular zones
- Enforces coverage-limited footprint
- Handles basic room program expansion and parking preference

## Step 5 - Geometry and Hypar Payload

Files:
- services/geometry_builder.py

What it does:
- Converts zones into level-aware geometric payload
- Writes JSON artifact suitable for Hypar integration workflow

## Step 6 - Vastu Preference Layer

Files:
- services/vastu_rules.py

What it does:
- Runs only if requested
- Scores orientation preference checks per room type
- Preserves legal/safety/feasibility priorities over Vastu

## Step 7 - Explanation Layer

Files:
- services/explanation_builder.py

What it does:
- Generates user-facing explanation report
- Summarizes applied bylaws, knowledge references, Vastu outcomes, and trade-offs

## Step 8 - Pipeline Orchestration

Files:
- services/pipeline.py
- apps/design/views.py

What it does:
- Orchestrates parsing -> retrieval -> compliance -> layout -> geometry -> explanation
- Persists all outputs into DesignSession for auditability

## Next Implementation Steps

1. Add region and building-type scoped knowledge metadata files for higher retrieval precision
2. Expand layout feasibility checks with corridor width, stair core continuity, and service shaft constraints
3. Add explainability schema versioning as a structured API object (not just text)
4. Add direct Hypar API integration test harness with mocked endpoint
5. Expand ingestion/scraper quality gates (duplicate detection, source trust scoring, and stricter citation normalization)
