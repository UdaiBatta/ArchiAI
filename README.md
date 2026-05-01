# Archi3D Backend

Backend-first Django + DRF service for deterministic bylaw-compliant architectural planning, explainable layout generation, and Hypar bridge exports.

## Run locally (Windows, fastest path)

1. Open **PowerShell** and go to this folder (quotes matter if the path has spaces):

   ```powershell
   cd "D:\My projects\Archi3D\backend"
   ```

2. Install dependencies (uses the locked `uv.lock`):

   ```powershell
   uv sync
   ```

3. Apply the database migrations:

   ```powershell
   uv run python manage.py migrate
   ```

4. Start the dev server (bind explicitly so the URL is predictable):

   ```powershell
   uv run python manage.py runserver 127.0.0.1:8000
   ```

5. In your browser open:

   - **http://127.0.0.1:8000/** — simple page where you can type requirements and click **Run design pipeline** (this calls `POST /api/v1/design/`).
   - **http://127.0.0.1:8000/api/v1/health/** — JSON status check (database, bylaws, Ollama, RAG).

If the root URL used to show **404**, that was expected before: there was no home page. Now `/` serves the local test page.

**Common issues**

- **`python` is not recognized**: use `uv run python ...` from this folder after `uv sync`, or activate `.venv` and run `python manage.py ...`.
- **Wrong folder**: run commands from the directory that contains `manage.py` (the `backend` folder), not a parent folder.
- **Port in use**: try `uv run python manage.py runserver 127.0.0.1:8001` and open that port instead.
- **PowerShell and `&&`**: older PowerShell does not support `&&`; run commands **one per line**, or use `;` between commands.

**Test the API without the browser (PowerShell)**

```powershell
$body = @{
  raw_text = "Design a 2-floor residential house in Mumbai on a 30x40m plot with parking."
  region = "india_mumbai"
  building_type = "residential"
  plot_width_m = 30
  plot_depth_m = 40
  num_floors = 2
  num_units = 1
  plot_facing_direction = "north"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/design/" -Method Post -ContentType "application/json; charset=utf-8" -Body $body
```

There is still **no file-upload UI** for PDFs in this repo; knowledge files are ingested via scripts or the ingestion job API. The design pipeline accepts **JSON** (and natural language in `raw_text`).

### Hypar: Elements API vs spreadsheet vs this backend

- **[Hypar Elements API (namespace Elements)](https://hypar-io.github.io/Elements/api/Elements.html)** documents the **Elements** model library (e.g. `Space`, `Wall`, `Floor`, `Model`) used in Hypar’s geometry stack. It is **not** the same as logging into hypar.io and using **Upload spreadsheet**; it is the reference for **types and concepts** when you build importers, plugins, or Hypar Functions in .NET/C#.
- **Spreadsheet / CSV**: our bridge still produces a **CSV** for the product’s manual upload flow; that remains the simplest path without a product API token.
- **JSON outputs from Archi3D**:
  - `hypar_<seed>.json` — internal concept schema `archi3d-hypar-concept/v1`.
  - `hypar_elements_ref_<seed>.json` — **Elements-oriented hints** (same `outputs/` folder when layout export runs): maps each zone to a documented `Space`-style record and points at the Elements docs URL above. Use it as a bridge for a custom Elements-based tool; it is **not** a full serialized Elements `Model`.

The API response includes **`hypar_elements_reference_path`** (filename) when that file is written.

## Setup

- Install deps with lockfile:
  - `uv sync`
- Apply migrations:
  - `uv run python manage.py migrate`
- Run server:
  - `uv run python manage.py runserver 127.0.0.1:8000`
- Run tests:
  - `uv run pytest -q`

## Core API Workflow

- Generate direct design session:
  - `POST /api/v1/design/`
- Auto-create project in Hypar (direct submit):
  - `POST /api/v1/design/hypar/auto-create/`
- Trigger synchronous Hypar bridge export (legacy):
  - `POST /api/v1/design/hypar/bridge/`
- Trigger background Hypar bridge export job:
  - `POST /api/v1/design/hypar/bridge/jobs/`
- Trigger background ingestion job:
  - `POST /api/v1/design/ingestion/jobs/`
- Check single job:
  - `GET /api/v1/design/jobs/<job_id>/`
- List recent jobs:
  - `GET /api/v1/design/jobs/?limit=20`

## API-First: Requirements-Only + Optional Hypar Auto-Submit

You can call `POST /api/v1/design/` from your own frontend/backend with only `raw_text`.
If `raw_text` includes plot dimensions (for example, `30x40`), the parser uses them directly and does not force a separate `plot_width_m` / `plot_depth_m` entry.

Optional request placeholders for direct Hypar automation:

- `hypar_api_url`
- `hypar_api_token`
- `hypar_project_name`

Example request body:

```json
{
  "raw_text": "Design a 2-floor residential house in Mumbai on a 30x40 metre plot with parking.",
  "hypar_api_url": "https://your-hypar-endpoint",
  "hypar_api_token": "<your-token>",
  "hypar_project_name": "Archi3D Demo Project"
}
```

Response includes `hypar_submission` to indicate direct submission outcome.
Credentials are consumed at runtime and removed from persisted `parsed_input`.

For direct submit behavior, prefer:

- `POST /api/v1/design/hypar/auto-create/`

This endpoint returns:

- `status=created_in_hypar` when project creation succeeds
- `status=hypar_submission_failed` when credentials/endpoint are missing or submission fails

## Production-Safe Defaults Added

- Bridge and ingestion operations have persistent `OperationJob` tracking.
- Bridge jobs capture status lifecycle (`queued`, `running`, `retrying`, `clarification_required`, `succeeded`, `failed`, `timed_out`).
- Bridge jobs support configurable retries and timeout tracking.
- Ingestion now enforces strict PDF limits:
  - max pages per PDF
  - max extracted characters per PDF
- Clarification gate remains enforced before heavy generation.

## Example: Background Bridge Job

Request:

```json
{
  "raw_text": "Design a 2-floor residential house in Mumbai",
  "region": "india_mumbai",
  "building_type": "residential",
  "plot_width_m": 30,
  "plot_depth_m": 40,
  "num_floors": 2,
  "num_units": 1,
  "plot_facing_direction": "north",
  "max_retries": 2,
  "timeout_seconds": 120
}
```

Polling:

- `GET /api/v1/design/jobs/<job_id>/`
- Inspect `status`, `failure_reason`, `result_payload`, `artifact_path`.

## Ingestion Operational Notes

- Default source dir: `knowledge/source_docs`
- Default output file: `knowledge/raw/ingested_documents.json`
- Override limits from ingestion job payload:
  - `max_pdf_pages`
  - `max_pdf_chars`
  - `max_section_chars`

## Web Scraping Prototype (Design Knowledge)

Use the safety-first scraper to collect architecture pages into retriever-ready chunks.

- Prototype source config:
  - `knowledge/source_configs/sources.prototype.json`
- Run scraper:
  - `uv run python scripts/scrape_knowledge_sources.py --config knowledge/source_configs/sources.prototype.json --crawl-output-dir outputs/scraped --payload-output knowledge/raw/scraped_sources.json --region-id all --building-type all --priority 0.85 --timeout-seconds 12`
- What it writes:
  - raw crawled pages + manifests under `outputs/scraped/<source>/`
  - chunk payload at `knowledge/raw/scraped_sources.json`

Notes:
- Scraper enforces domain allowlist and robots checks.
- For prototype speed, this config does not enforce license filtering; tighten this before production.

---

## Roadmap — What's Pending

The following items are the next planned implementation steps, in priority order. Dataset model training is intentionally deferred until all pre-dataset backend tasks are done.

### Pre-Dataset Backend Tasks

1. **Region and building-type scoped knowledge metadata expansion**
   - Add per-region and per-building-type metadata files so the vectorless retriever returns more targeted bylaw and design knowledge.

2. **Layout feasibility checks**
   - Corridor width constraints
   - Stair core continuity checks across floors
   - Service shaft continuity checks

3. **Structured explainability object (versioned JSON)**
   - Replace free-text explanation with a versioned, machine-readable JSON schema in the API response so frontends can render it properly.

4. **Hypar API integration test harness**
   - Add mocked endpoint tests that exercise the full Hypar submission flow without a live Hypar account, to keep CI reliable.

5. **Ingestion and scraper quality gates**
   - Duplicate detection across ingested documents
   - Source trust scoring
   - Stricter citation normalisation before knowledge chunks are indexed

### Deferred (Post-Dataset)

- LLM fine-tuning / model training on collected architectural dataset
- Larger bylaw corpus ingestion for more regions

---

## Platform / Website Plans

**Hypar.io API availability** — Hypar currently requires per-account API tokens and its API is not freely accessible to all users. We have two parallel tracks:

- **Track A — Hypar bridge (current):** When a Hypar API token is available, the bridge submits designs directly to Hypar via `POST /api/v1/design/hypar/auto-create/` or the background job endpoint. The CSV upload flow remains the simplest path without an API token.

- **Track B — ArchiAI standalone platform:** If Hypar's API remains gated or unavailable for general use, we plan to build a **dedicated ArchiAI web platform** that hosts the full design-generation workflow directly. This would include:
  - A browser-based UI for entering project requirements
  - Real-time design generation and bylaw compliance feedback
  - Built-in 3D/2D layout visualisation (no Hypar dependency)
  - PDF report export and shareable project links
  - User accounts, project history, and collaboration features

Track B development will begin once the pre-dataset backend tasks above are complete and Hypar API access is evaluated. Both tracks share the same Django + DRF backend; only the frontend and submission layer differ.

---

## How We Plan to Build and Improve the Design Intelligence

### 1 — Hypar Elements API for Geometry and Structures

We intend to use the [Hypar Elements API](https://hypar-io.github.io/Elements/api/Elements.html) as the primary geometry layer for defining architectural structures. Elements provides a rich type system (`Space`, `Wall`, `Floor`, `Column`, `Beam`, `Roof`, etc.) that lets us express every room, structural member, and building component in a well-typed, version-controlled model rather than ad-hoc JSON blobs.

Planned use:
- Map each zone produced by the layout generator to a typed `Space` record with dimensions, level, and adjacency metadata.
- Express walls, slabs, and structural grids as first-class Elements objects so they can be visualised, validated, and exported consistently.
- Produce a serialized Elements `Model` (not just the hints file currently written) that can be loaded into any Elements-compatible viewer or downstream tool.
- Use Elements as the single source of truth for geometry whether we submit to Hypar or render inside the ArchiAI platform (Track B above).

### 2 — Architecture Books and Curated Knowledge as the Training Corpus

Good design outputs depend on good design knowledge. We plan to build a structured knowledge pipeline that feeds the retriever and (eventually) model fine-tuning:

**Architecture reference books and standards**
- Ingest digitised architecture handbooks (e.g. Neufert, Time-Saver Standards, NBC/BIS codes) as chunked PDF documents via the existing `knowledge_ingestion.py` pipeline.
- Each chunk is tagged with region, building type, topic (circulation, accessibility, structural, MEP, fire safety, etc.) so the vectorless retriever can return precisely scoped results.
- Bylaw PDFs for additional Indian and international regions will be added incrementally as structured bylaw YAML files consumed by `bylaw_loader.py`.

**Web scraper for live architectural knowledge**
- The existing `safe_web_scraper.py` prototype (domain allowlist + robots.txt checks) will be extended to crawl trusted architecture knowledge sources (planning portals, open-access journals, municipal bylaw sites).
- Each scraped page is chunked, deduplicated, and trust-scored before it enters `knowledge/raw/`.
- License filtering will be tightened before any production crawl so only permissively licensed content is retained.
- The combined scraped + ingested corpus forms the retrieval index that drives bylaw-aware, knowledge-grounded design explanations.

### 3 — Manual Review and Iterative Design Improvement

Automated generation is the starting point, not the final answer. We plan structured human-in-the-loop workflows:

- **Manual knowledge curation:** Architects and domain experts can review, annotate, and override knowledge chunks in `knowledge/raw/` to correct errors or add nuance that scrapers miss.
- **Design review layer:** Generated layouts and geometry outputs will be reviewable through the platform UI. Reviewers can flag zones, adjust dimensions, or override bylaw interpretations, and those decisions are stored as corrections that inform future generation.
- **Feedback loop into retrieval:** Approved corrections are tagged and re-indexed so the retriever surfaces them in similar future requests, making the system progressively more accurate without requiring a full model retrain.
- **Continuous bylaw updates:** As municipal codes change, bylaw YAML files can be updated manually and the compliance engine picks up the changes on the next server start — no model retraining needed for legal rule changes.