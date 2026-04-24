"""Background job runner for bridge export and ingestion operations."""

from __future__ import annotations

import logging
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from apps.design.models import OperationJob
from services.hypar_bridge import (
    build_hypar_bridge_summary,
    write_hypar_bridge_csv,
    write_hypar_requirements_csv,
)
from services.knowledge_ingestion import ingest_documents_to_json
from services.pipeline import run_design_pipeline

logger = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="archi3d_jobs")
G2P_PREPROCESS_SCRIPTS = {
    1: "1.tf_train.py",
    2: "2.data_train_converted.py",
    3: "3.rNum_train.py",
    4: "4.data_train_eNum.py",
    5: "5.data_test_converted.py",
    6: "6.cluster.py",
}


def submit_operation_job(job: OperationJob) -> None:
    """Dispatch an operation job in background (or sync mode in tests)."""
    archi3d_settings = getattr(settings, "ARCHI3D", {})
    sync_mode = bool(archi3d_settings.get("JOB_SYNC_EXECUTION", False))
    if sync_mode:
        _run_operation_job(job.id)
        return
    _EXECUTOR.submit(_run_operation_job, job.id)


def _run_operation_job(job_pk: int) -> None:
    job = OperationJob.objects.get(pk=job_pk)
    job.status = "running"
    job.started_at = timezone.now()
    job.failure_reason = ""
    job.save(update_fields=["status", "started_at", "failure_reason", "updated_at"])

    if job.job_type == "hypar_bridge_export":
        _process_hypar_bridge_job(job_pk)
        return
    if job.job_type == "knowledge_ingestion":
        _process_ingestion_job(job_pk)
        return
    if job.job_type == "graph2plan_pipeline":
        _process_graph2plan_job(job_pk)
        return

    _mark_failed(job_pk, f"Unsupported job type: {job.job_type}")


def _process_hypar_bridge_job(job_pk: int) -> None:
    job = OperationJob.objects.get(pk=job_pk)
    payload = dict(job.request_payload or {})
    max_retries = int(job.max_retries)
    timeout_seconds = int(job.timeout_seconds)
    outputs_dir = Path(getattr(settings, "ARCHI3D", {}).get("OUTPUTS_DIR", settings.BASE_DIR / "outputs"))

    last_error = ""
    for attempt in range(max_retries + 1):
        attempt_start = time.perf_counter()
        try:
            pipeline_input = dict(payload)
            explicit = payload.get("_explicit_fields")
            if not isinstance(explicit, list):
                explicit = list(payload.keys())
            pipeline_input["_explicit_fields"] = explicit
            pipeline_result = run_design_pipeline(pipeline_input)
            duration = time.perf_counter() - attempt_start
            if duration > timeout_seconds:
                raise TimeoutError(f"Pipeline exceeded timeout of {timeout_seconds}s")

            session = _create_design_session_from_result(data=payload, pipeline_result=pipeline_result)
            job.session = session

            if pipeline_result.get("requires_clarification"):
                job.status = "clarification_required"
                job.result_payload = {
                    "requires_clarification": True,
                    "missing_fields": pipeline_result["parsed_input"].get("_parser_meta", {}).get(
                        "missing_fields", []
                    ),
                    "clarification_questions": pipeline_result["parsed_input"].get("_parser_meta", {}).get(
                        "clarification_questions", []
                    ),
                    "design_brief": pipeline_result.get("design_brief", {}),
                    "hypar_submission": pipeline_result.get("hypar_submission", {}),
                }
                job.finished_at = timezone.now()
                job.save(
                    update_fields=[
                        "session",
                        "status",
                        "result_payload",
                        "finished_at",
                        "updated_at",
                    ]
                )
                return

            layout_zones = pipeline_result.get("layout_zones", [])
            if not layout_zones:
                job.status = "failed"
                job.failure_reason = "No layout zones were generated; export artifact not created."
                job.finished_at = timezone.now()
                job.save(update_fields=["session", "status", "failure_reason", "finished_at", "updated_at"])
                return

            session_seed = uuid4().hex[:10]
            artifact_path = write_hypar_bridge_csv(
                layout_zones=layout_zones,
                outputs_dir=outputs_dir,
                session_seed=session_seed,
                region_id=pipeline_result.get("region", "default"),
                building_type=pipeline_result.get("building_type", "residential"),
                parsed_input=pipeline_result.get("parsed_input", {}) or {},
            )
            requirements_artifact_path = write_hypar_requirements_csv(
                parsed_input=pipeline_result.get("parsed_input", {}) or {},
                layout_zones=layout_zones,
                outputs_dir=outputs_dir,
                session_seed=session_seed,
                region_id=pipeline_result.get("region", "default"),
                building_type=pipeline_result.get("building_type", "residential"),
            )
            bridge_summary = build_hypar_bridge_summary(
                layout_zones=layout_zones,
                artifact_path=artifact_path,
                requirements_artifact_path=requirements_artifact_path,
                region_id=pipeline_result.get("region", "default"),
                building_type=pipeline_result.get("building_type", "residential"),
            )

            job.status = "succeeded"
            job.artifact_path = artifact_path
            job.result_payload = {
                "session_id": session.id,
                "status": "ready_for_upload",
                "design_brief": pipeline_result.get("design_brief", {}),
                "hypar_submission": pipeline_result.get("hypar_submission", {}),
                "hypar_bridge": bridge_summary,
                "hypar_json_path": pipeline_result.get("hypar_json_path", ""),
                "hypar_elements_reference_path": pipeline_result.get(
                    "hypar_elements_reference_path", ""
                ),
            }
            job.finished_at = timezone.now()
            job.save(
                update_fields=[
                    "session",
                    "status",
                    "artifact_path",
                    "result_payload",
                    "finished_at",
                    "updated_at",
                ]
            )
            return
        except TimeoutError as exc:
            last_error = str(exc)
            logger.warning("Hypar bridge job timed out", extra={"job_id": str(job.job_id), "attempt": attempt + 1})
            if attempt < max_retries:
                _mark_retry(job_pk, attempt + 1, f"Retrying after timeout: {exc}")
                continue
            _mark_timed_out(job_pk, last_error)
            return
        except Exception as exc:  # pragma: no cover - covered through API tests
            last_error = str(exc)
            logger.exception("Hypar bridge job failed", extra={"job_id": str(job.job_id), "attempt": attempt + 1})
            if attempt < max_retries:
                _mark_retry(job_pk, attempt + 1, f"Retrying after failure: {exc}")
                continue
            _mark_failed(job_pk, last_error)
            return

    _mark_failed(job_pk, last_error or "Unknown bridge processing failure.")


def _process_ingestion_job(job_pk: int) -> None:
    job = OperationJob.objects.get(pk=job_pk)
    payload = dict(job.request_payload or {})
    archi3d_settings = getattr(settings, "ARCHI3D", {})
    source_dir = Path(payload.get("source_dir") or archi3d_settings.get("KNOWLEDGE_SOURCE_DIR", settings.BASE_DIR / "knowledge" / "source_docs"))
    output_file = Path(payload.get("output_file") or archi3d_settings.get("KNOWLEDGE_OUTPUT_FILE", settings.BASE_DIR / "knowledge" / "raw" / "ingested_documents.json"))
    max_pdf_pages = int(payload.get("max_pdf_pages", archi3d_settings.get("INGESTION_MAX_PDF_PAGES", 300)))
    max_pdf_chars = int(payload.get("max_pdf_chars", archi3d_settings.get("INGESTION_MAX_PDF_CHARS", 1500000)))

    try:
        result = ingest_documents_to_json(
            input_dir=source_dir,
            output_file=output_file,
            chunk_chars=int(payload.get("chunk_chars", 1200)),
            overlap_chars=int(payload.get("overlap_chars", 200)),
            max_section_chars=int(payload.get("max_section_chars", 300000)),
            max_pdf_pages=max_pdf_pages,
            max_pdf_chars=max_pdf_chars,
        )
        job.status = "succeeded"
        job.artifact_path = str(result.output_path)
        job.result_payload = {
            "input_files": result.input_files,
            "ingested_docs": result.ingested_docs,
            "total_chunks": result.total_chunks,
            "skipped_files": result.skipped_files,
            "output_path": str(result.output_path),
        }
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "artifact_path", "result_payload", "finished_at", "updated_at"])
    except Exception as exc:
        logger.exception("Knowledge ingestion job failed", extra={"job_id": str(job.job_id)})
        _mark_failed(job_pk, str(exc))


def _resolve_graph2plan_root(payload: Dict[str, Any]) -> Path:
    archi3d_settings = getattr(settings, "ARCHI3D", {})
    requested_root = str(payload.get("graph2plan_root", "") or "").strip()
    if requested_root:
        return Path(requested_root).resolve()
    configured_root = archi3d_settings.get("GRAPH2PLAN_ROOT", settings.BASE_DIR / "Graph2plan-master")
    return Path(configured_root).resolve()


def _parse_preprocess_steps(raw_steps: str) -> list[int]:
    parts = [part.strip() for part in str(raw_steps or "").split(",") if part.strip()]
    if not parts:
        return sorted(G2P_PREPROCESS_SCRIPTS.keys())
    steps = [int(part) for part in parts]
    unknown = [step for step in steps if step not in G2P_PREPROCESS_SCRIPTS]
    if unknown:
        raise ValueError(f"Unsupported Graph2Plan preprocess steps: {unknown}")
    return steps


def _build_graph2plan_plan(payload: Dict[str, Any]) -> list[dict]:
    root = _resolve_graph2plan_root(payload)
    data_prep_dir = root / "DataPreparation"
    network_dir = root / "Network"
    python_exec = str(payload.get("python_executable", "") or "").strip() or sys.executable

    required_paths = [root, data_prep_dir, network_dir, network_dir / "train.py"]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Graph2Plan path is invalid or incomplete. Missing: {', '.join(missing)}")

    plan: list[dict] = []
    if bool(payload.get("preprocess", True)):
        for step in _parse_preprocess_steps(str(payload.get("preprocess_steps", "1,2,3,4,5,6"))):
            plan.append(
                {
                    "label": f"preprocess:{step}",
                    "cwd": data_prep_dir,
                    "cmd": [python_exec, G2P_PREPROCESS_SCRIPTS[step]],
                }
            )
    if bool(payload.get("split", False)):
        plan.append(
            {
                "label": "split",
                "cwd": network_dir,
                "cmd": [python_exec, "split.py"],
            }
        )
    if bool(payload.get("train", True)):
        train_cmd = [python_exec, "train.py"]
        train_args = str(payload.get("train_args", "") or "").strip()
        if train_args:
            train_cmd.extend(shlex.split(train_args))
        plan.append(
            {
                "label": "train",
                "cwd": network_dir,
                "cmd": train_cmd,
            }
        )
    if not plan:
        raise ValueError("No Graph2Plan steps to run. Enable preprocess, split, or train.")
    return plan


def _update_job_progress(
    job_pk: int,
    *,
    progress_pct: int,
    stage: str,
    current_step: str,
    completed_steps: list[str],
    recent_output: list[str],
) -> None:
    payload = {
        "progress_pct": int(max(0, min(progress_pct, 100))),
        "stage": stage,
        "current_step": current_step,
        "completed_steps": completed_steps,
        "recent_output": recent_output[-20:],
    }
    OperationJob.objects.filter(pk=job_pk).update(result_payload=payload, updated_at=timezone.now())


def _process_graph2plan_job(job_pk: int) -> None:
    job = OperationJob.objects.get(pk=job_pk)
    payload = dict(job.request_payload or {})
    timeout_seconds = int(job.timeout_seconds or 21600)
    start_ts = time.time()
    try:
        plan = _build_graph2plan_plan(payload)
        total_steps = len(plan)
        completed_steps: list[str] = []
        recent_output: list[str] = []

        for idx, step in enumerate(plan, start=1):
            elapsed = time.time() - start_ts
            if elapsed > timeout_seconds:
                _mark_timed_out(job_pk, f"Graph2Plan timed out after {int(elapsed)}s.")
                return

            current_progress = int(((idx - 1) / total_steps) * 100)
            _update_job_progress(
                job_pk,
                progress_pct=current_progress,
                stage="running",
                current_step=step["label"],
                completed_steps=completed_steps,
                recent_output=recent_output,
            )

            cmd = step["cmd"]
            cwd = Path(step["cwd"])
            logger.info("Running Graph2Plan step", extra={"job_id": str(job.job_id), "step": step["label"], "cmd": cmd})
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(cwd),
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except Exception as exc:
                _mark_failed(job_pk, f"Graph2Plan step '{step['label']}' failed to launch: {exc}")
                return

            stdout_tail = [line for line in (proc.stdout or "").splitlines() if line.strip()][-8:]
            stderr_tail = [line for line in (proc.stderr or "").splitlines() if line.strip()][-8:]
            recent_output.extend(stdout_tail + stderr_tail)
            if proc.returncode != 0:
                _update_job_progress(
                    job_pk,
                    progress_pct=current_progress,
                    stage="failed",
                    current_step=step["label"],
                    completed_steps=completed_steps,
                    recent_output=recent_output,
                )
                _mark_failed(
                    job_pk,
                    f"Graph2Plan step '{step['label']}' failed with exit code {proc.returncode}.",
                )
                return

            completed_steps.append(step["label"])
            progressed = int((idx / total_steps) * 100)
            _update_job_progress(
                job_pk,
                progress_pct=progressed,
                stage="running",
                current_step="",
                completed_steps=completed_steps,
                recent_output=recent_output,
            )

        OperationJob.objects.filter(pk=job_pk).update(
            status="succeeded",
            result_payload={
                "progress_pct": 100,
                "stage": "completed",
                "current_step": "",
                "completed_steps": completed_steps,
                "recent_output": recent_output[-20:],
                "graph2plan_root": str(_resolve_graph2plan_root(payload)),
                "summary": "Graph2Plan preprocessing/training pipeline finished successfully.",
            },
            finished_at=timezone.now(),
            updated_at=timezone.now(),
        )
    except TimeoutError as exc:
        _mark_timed_out(job_pk, str(exc))
    except Exception as exc:
        logger.exception("Graph2Plan job failed", extra={"job_id": str(job.job_id)})
        _mark_failed(job_pk, str(exc))


def _mark_retry(job_pk: int, retry_count: int, reason: str) -> None:
    OperationJob.objects.filter(pk=job_pk).update(
        status="retrying",
        retry_count=retry_count,
        failure_reason=reason,
        updated_at=timezone.now(),
    )


def _mark_failed(job_pk: int, reason: str) -> None:
    OperationJob.objects.filter(pk=job_pk).update(
        status="failed",
        failure_reason=reason,
        finished_at=timezone.now(),
        updated_at=timezone.now(),
    )


def _mark_timed_out(job_pk: int, reason: str) -> None:
    OperationJob.objects.filter(pk=job_pk).update(
        status="timed_out",
        failure_reason=reason,
        finished_at=timezone.now(),
        updated_at=timezone.now(),
    )


def _create_design_session_from_result(data: Dict[str, Any], pipeline_result: Dict[str, Any]):
    from apps.design.models import DesignSession

    parsed_input = pipeline_result.get("parsed_input", {}) or {}
    return DesignSession.objects.create(
        raw_text=data.get("raw_text", ""),
        parsed_input=parsed_input,
        region=pipeline_result.get("region", "default"),
        building_type=pipeline_result.get("building_type", "residential"),
        plot_width_m=float(parsed_input.get("plot_width_m", 0.0)),
        plot_depth_m=float(parsed_input.get("plot_depth_m", 0.0)),
        num_floors=int(parsed_input.get("num_floors", 2)),
        num_units=int(parsed_input.get("num_units", 1)),
        plot_facing_direction=parsed_input.get("plot_facing_direction", "north"),
        compliance_report=pipeline_result.get("compliance_report", {}),
        applied_bylaws=pipeline_result.get("applied_bylaws", {}),
        vastu_report=pipeline_result.get("vastu_report", {}),
        retrieved_knowledge=pipeline_result.get("retrieved_knowledge", []),
        layout_zones=pipeline_result.get("layout_zones", []),
        explanation=pipeline_result.get("explanation", ""),
        glb_file_path=pipeline_result.get("glb_file_path", ""),
        hypar_json_path=pipeline_result.get("hypar_json_path", ""),
        status=pipeline_result.get("status", "failed"),
        error_message=pipeline_result.get("error_message", ""),
    )
