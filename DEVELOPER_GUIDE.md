# Archi3D — Developer Guide
## Phase 1: Foundation

---

## Table of Contents
1. [Quick Start](#1-quick-start)
2. [Project Structure Explained](#2-project-structure-explained)
3. [How the Pipeline Works](#3-how-the-pipeline-works)
4. [API Reference](#4-api-reference)
5. [Module Deep-Dives](#5-module-deep-dives)
6. [Bylaw Database Guide](#6-bylaw-database-guide)
7. [Running Tests](#7-running-tests)
8. [Django Admin](#8-django-admin)
9. [Common Issues & Debugging](#9-common-issues--debugging)
10. [What's Coming Next (Phase 2)](#10-whats-coming-next-phase-2)

---

## 1. Quick Start

### Prerequisites
- Python 3.10+
- uv

### Setup (Windows PowerShell)
```powershell
# Navigate to the backend directory
cd "D:\My projects\Archi3D\backend"

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies from uv.lock
uv sync

# If `uv` is not recognized in your shell, use:
# python -m uv sync

# Set up environment variables
copy .env.example .env
# (Edit .env to set SECRET_KEY if needed — a dev key works for local)

# Create the database tables
python manage.py migrate

# Start the development server
python manage.py runserver
```

The API is now running at: **http://localhost:8000**

### Dependency Workflow (uv)
```powershell
# After changing dependencies in pyproject.toml
uv lock
uv sync

# Fallback in shells where `uv` alias is unavailable:
# python -m uv lock
# python -m uv sync

# Optional: export a pip-compatible file for external tooling
uv export --format requirements-txt --output-file requirements.txt

# Fallback:
# python -m uv export --format requirements-txt --output-file requirements.txt
```

### Knowledge Ingestion and Scraping (Pre-Dataset Foundation)

Create local document source folder (optional but recommended):
```powershell
Set-Location "D:\My projects\Archi3D\backend"
New-Item -ItemType Directory -Path "knowledge\source_docs" -Force
```

Ingest local markdown/txt/pdf documents into retriever-ready JSON:
```powershell
Set-Location "D:\My projects\Archi3D\backend"
"C:/Program Files/Python314/python.exe" -m uv run python scripts/ingest_knowledge.py --input-dir knowledge/source_docs --output-file knowledge/raw/ingested_documents.json
```

Safety-first web scraping using allowlist + robots + license filters:
```powershell
Set-Location "D:\My projects\Archi3D\backend"
"C:/Program Files/Python314/python.exe" -m uv run python scripts/scrape_knowledge_sources.py --config knowledge/source_configs/sources.sample.json --payload-output knowledge/raw/scraped_sources.json
```

Notes:
- Scraped pages are stored under outputs/scraped/<source_name>/raw_pages.
- Crawl summaries are stored as outputs/scraped/<source_name>/manifest.json.
- Generated JSON files in knowledge/raw are automatically picked up by services/vectorless_rag.py.

### Quick Test — Send a design request
Open a new terminal and run:
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/design/" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"plot_width_m": 30, "plot_depth_m": 40, "region": "india_mumbai", "num_floors": 3}'
```

Or use any REST client (Postman, Insomnia, VS Code Thunder Client) pointing at:
- **POST** `http://localhost:8000/api/v1/design/`
- **GET** `http://localhost:8000/api/v1/health/`

---

## 2. Project Structure Explained

```
backend/
│
├── manage.py                  ← Django CLI entry point (run commands here)
├── pyproject.toml             ← Canonical dependency definitions
├── uv.lock                    ← Fully resolved and pinned lockfile
├── requirements.txt           ← Exported pip-compatible dependencies
├── .env.example               ← Copy to .env and configure
├── pytest.ini                 ← Test runner config
│
├── archi3d/                   ← Django PROJECT package (config, not code)
│   ├── settings.py            ← All Django settings (reads .env)
│   ├── urls.py                ← Root URL routing table
│   ├── wsgi.py                ← Production WSGI entry point
│   └── asgi.py                ← Async/WebSocket entry point
│
├── apps/                      ← Django APPS (feature modules)
│   ├── design/                ← Main design pipeline app
│   │   ├── models.py          ← Database schema (DesignSession table)
│   │   ├── serializers.py     ← Input/output data validation
│   │   ├── views.py           ← HTTP request handlers
│   │   ├── urls.py            ← URL routes for /api/v1/design/
│   │   └── admin.py           ← Django Admin config for sessions
│   └── health/                ← Simple health check app
│       ├── views.py           ← GET /api/v1/health/
│       └── urls.py
│
├── services/                  ← PURE PYTHON business logic (no Django)
│   ├── bylaw_loader.py        ← Load bylaw JSON → BylawRuleset dataclass
│   └── rule_engine.py         ← Deterministic compliance calculations
│
├── bylaws/                    ← Bylaw data files (one JSON per region)
│   ├── india_mumbai.json      ← Mumbai DCPR 2034
│   ├── india_delhi.json       ← Delhi MPD 2041
│   ├── usa_nyc.json           ← NYC R2 Zone
│   └── default.json           ← Conservative fallback
│
├── knowledge/                 ← RAG knowledge base (Phase 2+)
│   ├── raw/                   ← Retriever-ready markdown/json knowledge chunks
│   ├── source_docs/           ← Local source docs for ingestion script (manual input)
│   └── source_configs/        ← Safe web source configs for scraper pipeline
│
├── outputs/                   ← Generated GLB + Hypar JSON (Phase 3+)
│
└── tests/                     ← Test files
    └── test_rule_engine.py    ← 20+ tests for rule engine
```

### Key Mental Model
```
HTTP Request
    ↓
apps/design/views.py    ← "Controller" — receives request, calls services
    ↓
services/               ← "Business Logic" — pure Python, no HTTP awareness
    ↓
bylaws/*.json           ← "Data" — static rule definitions
    ↓
apps/design/models.py   ← "Persistence" — saves results to SQLite
    ↓
HTTP Response
```

---

## 3. How the Pipeline Works

### Phase 1 Pipeline (What happens on `POST /api/v1/design/`)

```
POST /api/v1/design/ { plot_width_m: 30, plot_depth_m: 40, region: "india_mumbai", num_floors: 3 }
        │
        ▼
[1] DesignRequestSerializer.is_valid()
    → Validates types, ranges, required fields
    → Returns 400 if invalid
        │
        ▼
[2] detect_region("india_mumbai") → "india_mumbai"
    → Keyword matching against REGION_KEYWORDS dict
        │
        ▼
[3] load_bylaws("india_mumbai", "residential")
    → Opens backend/bylaws/india_mumbai.json
    → Returns BylawRuleset(setback_front=3.0, max_far=1.5, ...)
        │
        ▼
[4] run_full_compliance(plot_w=30, plot_d=40, floors=3, units=1, bylaws)
    → calculate_buildable_area()  → 27m × 34m = 918 sq.m
    → validate_floor_count(3)     → Mumbai max=4 → PASSES
    → validate_height(3)          → 3×3m=9m < 15m → PASSES
    → validate_far(918×3, 1200)   → FAR=2.295 > 1.5 → FAILS
    → validate_plot_coverage()    → 76.5% > 50% → FAILS
    → calculate_parking()         → 1 stall needed
    → Returns ComplianceReport(is_fully_compliant=False, adjusted_floors=1, ...)
        │
        ▼
[5] DesignSession.objects.create(...)
    → Saves everything to SQLite database
        │
        ▼
[6] DesignResponseSerializer(session)
    → Returns 201 Created with full JSON response
```

### Understanding the Compliance Report

Every check in the report has these fields:
| Field | Meaning |
|---|---|
| `check_name` | Which rule was checked |
| `passed` | `true` = design meets this rule |
| `actual_value` | What the design has |
| `limit_value` | What the bylaw allows |
| `unit` | The measurement unit |
| `message` | Plain English explanation |
| `severity` | `"error"` = blocking, `"warning"` = advisory |

---

## 4. API Reference

### POST /api/v1/design/ — Run Design Pipeline

**Request Body:**
```json
{
  "raw_text": "Design a 3-floor house on a 30×40 plot in Mumbai",
  "region": "india_mumbai",
  "building_type": "residential",
  "plot_width_m": 30.0,
  "plot_depth_m": 40.0,
  "num_floors": 3,
  "num_units": 1,
  "rooms": ["living_room", "kitchen", "bedroom", "bedroom", "bedroom"],
  "preferences": {"parking": true, "balcony": true},
  "plot_facing_direction": "north"
}
```
**Minimum required:** only `plot_width_m` and `plot_depth_m` are mandatory.

**Response (201):**
```json
{
  "session_id": 1,
  "status": "compliance_checked",
  "region": "india_mumbai",
  "compliance_report": {
    "region_name": "India — Mumbai (DCPR 2034)",
    "is_fully_compliant": false,
    "adjusted_floors": 1,
    "actual_far": 0.765,
    "total_built_area_sqm": 918.0,
    "required_parking_stalls": 1,
    "buildable_area": {
      "plot_area_sqm": 1200.0,
      "buildable_width_m": 27.0,
      "buildable_depth_m": 34.0,
      "buildable_area_sqm": 918.0
    },
    "checks": [
    python -m venv .venv
    .venv\Scripts\activate
        "passed": true,
        "status": "✅ PASS",
        ...
      },
      {
        "check_name": "FAR / FSI Limit",
        "passed": false,
        "status": "❌ FAIL",
        "actual_value": 2.295,
        "limit_value": 1.5,
        "message": "FAR of 2.30 exceeds maximum of 1.50..."
      }
    ]
  }
}
```

**Supported regions:** `india_mumbai`, `india_delhi`, `usa_nyc`, `default`

---

### GET /api/v1/design/list/ — List All Sessions
Returns compact list of all past sessions (most recent first).

### GET /api/v1/design/<id>/ — Get Session Detail
Returns full output for session with given ID.

### GET /api/v1/health/ — Health Check
Returns server status, available bylaw regions, and phase info.

---

## 5. Module Deep-Dives

### `services/bylaw_loader.py`

**Key Functions:**
```python
detect_region("Mumbai")                    # → "india_mumbai"
load_bylaws("india_mumbai")                # → BylawRuleset dataclass
list_available_regions()                   # → ["default", "india_delhi", ...]
```

**BylawRuleset fields:**
```python
bylaws.setback_front_m    # 3.0 m
bylaws.setback_rear_m     # 3.0 m
bylaws.setback_side_m     # 1.5 m
bylaws.max_far            # 1.5
bylaws.max_height_m       # 15.0 m
bylaws.max_floors         # 4
bylaws.max_plot_coverage_pct  # 50.0 %
bylaws.parking.min_stalls_per_unit  # 1.0
```

### `services/rule_engine.py`

**Key Functions:**
```python
calculate_buildable_area(30, 40, bylaws)   # → BuildableArea
validate_floor_count(3, bylaws)            # → (ComplianceCheck, adjusted_floors)
validate_height(3, bylaws)                 # → ComplianceCheck
validate_far(buildable, 3, bylaws)         # → (ComplianceCheck, total_area, far)
validate_plot_coverage(buildable, bylaws)  # → ComplianceCheck
calculate_parking_requirement(1, bylaws)   # → (stalls, ComplianceCheck)
run_full_compliance(30, 40, 3, 1, bylaws)  # → ComplianceReport  ← use this!
```

**Key formulas:**
```
buildable_width  = plot_width − (setback_side × 2)
buildable_depth  = plot_depth − setback_front − setback_rear
buildable_area   = buildable_width × buildable_depth
total_built_area = buildable_area × num_floors
actual_far       = total_built_area ÷ plot_area
actual_coverage  = buildable_area ÷ plot_area × 100
```

---

## 6. Bylaw Database Guide

### Structure of a Bylaw JSON File

```json
{
  "region_id": "india_mumbai",
  "region_name": "India — Mumbai (DCPR 2034)",
  "building_types": {
    "residential": {
      "setback_front_m": 3.0,
      "setback_rear_m": 3.0,
      "setback_side_m": 1.5,
      "max_far": 1.5,
      "max_height_m": 15.0,
      "max_floors": 4,
      "max_plot_coverage_pct": 50.0,
      "floor_height_m": 3.0,
      "parking": {
        "min_stalls_per_unit": 1.0,
        "stall_width_m": 2.5,
        "stall_depth_m": 5.0,
        "aisle_width_m": 3.5,
        "notes": "..."
      }
    }
  }
}
```

### Adding a New City (e.g., Pune)
1. Create `backend/bylaws/india_pune.json` (copy from india_mumbai.json)
2. Fill in Pune's actual PMRDA/PMC bylaw values
3. Add keywords to `bylaw_loader.py`:
   ```python
   "india_pune": ["pune", "pimpri", "chinchwad", "pcmc"],
   ```
4. No other code changes needed!

---

## 7. Running Tests

```powershell
# From the backend/ directory with .venv active:
pytest tests/ -v                           # All tests
pytest tests/test_rule_engine.py -v       # Just this file
pytest tests/ -v -k "mumbai"              # Tests with "mumbai" in name
pytest tests/ -v -m unit                  # Only @pytest.mark.unit tests
```

### Reading Test Output
```
PASSED tests/test_rule_engine.py::test_buildable_area_mumbai_standard ✅
FAILED tests/test_rule_engine.py::test_far_fails_too_many_floors      ❌
  AssertionError: assert False is True
  Where: far_check.passed = False, expected = True
```

When a test fails:
1. Read the assertion message — it tells you what was expected vs actual
2. Check the scenario description at the top of the test function
3. Add a `print()` call before the assertion to inspect values

---

## 8. Django Admin

Access at: **http://localhost:8000/admin/**

Create a superuser first:
```powershell
python manage.py createsuperuser
```

In the admin you can:
- Browse every design session ever processed
- See full compliance reports as JSON
- Filter by status, region, building type
- Search by region name
- View which bylaws were applied

---

## 9. Common Issues & Debugging

### "ModuleNotFoundError: No module named 'archi3d'"
**Cause:** You're not in the `backend/` directory.
**Fix:** `cd "D:\My projects\Archi3D\backend"` then try again.

### "django.db.utils.OperationalError: no such table"
**Cause:** Migrations haven't been run.
**Fix:** `python manage.py migrate`

### "KeyError: 'residential'" when loading bylaws
**Cause:** The bylaw JSON file is missing the `residential` building type.
**Fix:** Check the JSON file structure matches the schema in section 6.

### Test fails on a FAR check
**Explanation:** For Mumbai on a 30×40 plot, even 2 floors gives:
- buildable_area = 918 sq.m
- total_built = 918 × 2 = 1836 sq.m
- FAR = 1836 / 1200 = **1.53 > 1.5 limit** → FAILS
This is CORRECT behaviour. The rule engine is telling you 2 floors violates Mumbai's FAR.
To pass FAR: use 1 floor (FAR = 0.765) or use a larger plot.

### "Connection refused" when starting server
**Fix:** Make sure port 8000 is free:
```powershell
netstat -an | findstr :8000
# If occupied, use a different port:
python manage.py runserver 8001
```

---

## 10. What's Coming Next (Phase 2)

Phase 2 will add:
1. **Ollama NLP Parser** (`services/nlp_parser.py`)
   - Takes `raw_text` input
   - Calls local Ollama `llama3.2` model
   - Extracts structured design parameters
   - So you can type: "3 bedroom house in Mumbai on 30×40 plot"

2. **BM25 Vectorless RAG** (`services/rag_retriever.py`)
   - Keyword-based retrieval from `knowledge/knowledge_base.json`
   - Returns relevant architectural principles for the query
   - No GPU, no embeddings needed

3. **Vastu Shastra Engine** (`services/vastu_engine.py`)
   - Checks room placement for Vastu compliance
   - Advisory output (doesn't block compliance)
   - Based on plot facing direction

To activate Phase 2: just say "start Phase 2" and development continues from here.
