# Archi3D Collaboration Handoff

Date: 2026-04-17
Timezone: +05:30
Project area: backend prototype (pre-dataset phase)
Collaboration mode: living document (single source of truth)

IMPORTANT:
- Every collaborator must update this same file only.
- Do not create another handoff file for daily progress.
- Add new updates at the top of the log so latest work is visible first.

---

## 1) Executive Summary

The backend is now a working Phase 2/3 prototype with:
- Natural language parsing (Ollama optional + deterministic fallback)
- Vectorless RAG retrieval
- Deterministic bylaw compliance checks
- Conceptual layout generation with adjacency and circulation scoring
- Geometry validation before export
- Hypar JSON export with optional API submission hook
- Clarification gate for missing critical inputs
- API tests for Vastu and multi-region scenarios

Dataset ingestion/scraping/training is intentionally deferred.

---

## 2) Timestamped Daily Log (Append-Only)

How to update this section:
1. Copy the template below.
2. Paste it at the top of this section (above older entries).
3. Fill all fields.
4. Keep timestamp format exactly: YYYY-MM-DD HH:MM:SS +/-TZ.

Entry template (copy/paste):

```text
- YYYY-MM-DD HH:MM:SS +05:30 | Name: <your-name> | Branch: <branch-name>
  - Task: <one-line summary>
  - Files changed: <file1>, <file2>, <file3>
  - Validation run: <command>
  - Validation result: <pass/fail + short output>
  - Risks/Notes: <optional>
```

- 2026-04-17 01:07:00 +05:30 | Name: GitHub-Copilot | Branch: working-tree
  - Task: Implemented both requested foundations: multi-document ingestion and safe web scraping pipeline
  - Files changed: services/knowledge_ingestion.py, services/safe_web_scraper.py, scripts/ingest_knowledge.py, scripts/scrape_knowledge_sources.py, knowledge/source_configs/sources.sample.json, tests/test_knowledge_ingestion_and_scraper.py, DEVELOPER_GUIDE.md, IMPLEMENTATION_ROADMAP.md
  - Validation run: Set-Location "D:\My projects\Archi3D\backend"; & "C:/Program Files/Python314/python.exe" -m uv run pytest -q
  - Validation result: pass, 44 passed, 3 warnings, 0 failures
  - Risks/Notes: pypdf remains optional; pdf ingestion safely skips if dependency is unavailable

- 2026-04-17 00:29:40 +05:30
  - Captured repository status snapshot.
  - Confirmed current working files include pipeline, layout, tests, and roadmap updates.

- 2026-04-17 00:29:47 +05:30
  - Ran full backend test suite.
  - Result: 37 passed, 3 warnings, 0 failures.

---

## 2.1) Current Collaboration Board (Editable)

Update rules:
- Move items across status columns instead of deleting history.
- If you complete a task, add a log entry in Section 2 first, then update this board.

### In Progress
- <owner-name> | <task-id> | <short-task-title> | Started: <timestamp>

### Ready / Next
- TASK-01 | Region and building-type scoped knowledge metadata expansion
- TASK-02 | Layout feasibility checks: corridor width + stair core + service shaft continuity
- TASK-03 | Structured explainability object (versioned JSON in API response)
- TASK-04 | Hypar API integration test harness with mocked endpoint

### Done
- GitHub-Copilot | TASK-05 | Multi-document knowledge ingestion foundation | Completed: 2026-04-17 01:07:00 +05:30
- GitHub-Copilot | TASK-06 | Safety-first web scraping foundation | Completed: 2026-04-17 01:07:00 +05:30
- <owner-name> | <task-id> | <short-task-title> | Completed: <timestamp>

---

## 3) Last Known Good State

- Python runtime used: 3.14.3
- Django: 5.1.15
- Test command:

```powershell
Set-Location "D:\My projects\Archi3D\backend"
"C:/Program Files/Python314/python.exe" -m uv run pytest -q
```

- Result: all tests passing (44/44).

---

## 4) What Has Been Completed

### A. Pipeline and Parsing
- Implemented full orchestrated planning flow in services/pipeline.py.
- Added clarification-aware parsing and missing-field question generation in services/input_parser.py.
- Added strict clarification gate: generation is deferred until critical fields are supplied.

### B. Compliance and Retrieval
- Deterministic bylaw checks remain in services/rule_engine.py.
- Vectorless retrieval implemented in services/vectorless_rag.py (BM25 + metadata boosts + bylaw context).

### C. Layout and Geometry
- Added layout quality improvements in services/layout_generator.py:
  - adjacency-aware slot assignment
  - circulation scoring
  - floor-level and overall quality metrics
- Added deterministic geometry validation in services/geometry_validator.py.
- Hypar payload generation remains in services/geometry_builder.py.
- Optional Hypar submission client added in services/hypar_client.py.

### D. Vastu and Explanations
- Optional Vastu preference layer is implemented in services/vastu_rules.py.
- Explanation output enhanced in services/explanation_builder.py with geometry/submission summary and schema marker.

### E. API and Tests
- POST /api/v1/design/ now includes clarification contract fields.
- Added API tests for:
  - Vastu-enabled requests
  - multi-region bylaw behavior
  - clarification behavior
- Added service tests for:
  - strict clarification gate
  - geometry validation
  - layout metrics

---

## 5) What Is Still Left (Pre-Dataset)

These should be completed before any data scraping/training work:

1. Region and building-type scoped knowledge metadata expansion
2. Layout feasibility checks:
   - corridor width constraints
   - stair core continuity checks
   - service shaft continuity checks
3. Structured explainability object (versioned JSON in API response, not only free-text explanation)
4. Hypar API integration test harness with mocked endpoint

Dataset model training remains deferred by plan.
Safe ingestion/scraping foundations are now implemented only for controlled source collection.

When any item is done:
- Move it to Section 4 with a short implementation note.
- Add a timestamped entry in Section 2.
- Move it from "Ready / Next" to "Done" in Section 2.1.

---

## 6) Collaboration Rules (Must Follow)

### Rule 1: Environment consistency
Always run project commands through uv-managed environment.

```powershell
Set-Location "D:\My projects\Archi3D\backend"
"C:/Program Files/Python314/python.exe" -m uv run python manage.py runserver
"C:/Program Files/Python314/python.exe" -m uv run pytest -q
```

Do not rely on plain python from random terminals if imports fail.

### Rule 2: Compliance boundary
- LLM can parse and explain.
- Legal compliance must stay deterministic in code (rule_engine).
- Never move legal checks into model-only reasoning.

### Rule 3: Clarification safety
If parser marks requires_clarification = true, do not force generation.
Fix missing fields first, then rerun.

### Rule 4: Testing gate
Before pushing code:
1. Run full test suite
2. Ensure zero failing tests
3. Record command and output summary in PR description

### Rule 5: Scope discipline
Do not start dataset scraping/training until pre-dataset backend checklist is complete.

### Rule 6: Small, auditable changes
- Keep PRs focused by feature (single responsibility)
- Update roadmap/handoff docs when behavior changes
- Include at least one test for each new rule or behavior

### Rule 7: Handoff discipline (mandatory)
- No silent changes: every code change must have a log line in Section 2.
- No undocumented test runs: include command and result in Section 2.
- No new handoff files: continue in this file only.

---

## 7) Branch and Handoff Workflow

1. Create branch from latest main:

```powershell
git checkout main
git pull
git checkout -b feat/<short-feature-name>
```

2. Implement one scoped item.
3. Run tests.
4. Update documentation (this file + roadmap if needed).
5. Open PR with:
   - what changed
   - why
   - test output
   - risks

---

## 8) Suggested Task Split For Friends

- Friend A: Knowledge metadata scoping and retrieval precision improvements
- Friend B: Layout feasibility checks (corridor + stair + service continuity)
- Friend C: Explainability schema object and serializer/API response integration
- Friend D: Hypar mocked integration tests and submission flow hardening

Each person must follow the rules in Section 6.

---

## 9) Quick API Smoke Commands

Run server:

```powershell
Set-Location "D:\My projects\Archi3D\backend"
"C:/Program Files/Python314/python.exe" -m uv run python manage.py runserver
```

Health check:

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health/" -Method GET
```

Design request (structured):

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/design/" -Method POST -ContentType "application/json" -Body '{"region":"india_mumbai","building_type":"residential","plot_width_m":30,"plot_depth_m":40,"num_floors":2,"num_units":1,"plot_facing_direction":"north","preferences":{"parking":true}}'
```

Design request (sparse, expected clarification):

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/design/" -Method POST -ContentType "application/json" -Body '{"raw_text":"Design a vastu house with parking"}'
```

---

## 10) Next Update Protocol

When anyone completes a task:
1. Add a timestamped line in Section 2.
2. Move completed items from Section 5 to Section 4.
3. Update Section 2.1 board status.
4. Keep this as the single source of collaboration truth.

Quick checklist before push:
- [ ] Section 2 log entry added
- [ ] Section 2.1 board updated
- [ ] Section 4/5 updated if scope changed
- [ ] Tests executed and result recorded
