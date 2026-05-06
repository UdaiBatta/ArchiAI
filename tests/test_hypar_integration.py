"""Integration tests for Hypar API submission flow.

These tests mock the ``httpx.Client`` used by ``services.hypar_client``
to verify the pipeline handles success, server-error, and timeout
scenarios without crashing and correctly surfaces the outcome in
the structured ExplanationSchema.
"""

import pytest
from unittest.mock import patch, MagicMock

import httpx

from services.pipeline import run_design_pipeline


# ── Common input fixture ─────────────────────────────────────────────

_FULL_INPUT = {
    "raw_text": "Design a 2-floor residential house on a 30x40 plot with parking and vastu",
    "region": "india_mumbai",
    "building_type": "residential",
    "plot_width_m": 30,
    "plot_depth_m": 40,
    "num_floors": 2,
    "num_units": 1,
    "plot_facing_direction": "east",
    "preferences": {"parking": True},
    "use_vastu": True,
}

def _make_settings(settings, tmp_path):
    """Apply ARCHI3D overrides that enable Hypar submission."""
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
        "HYPAR_API_URL": "https://mock-hypar.example.com/api/submit",
        "HYPAR_API_TOKEN": "test-token-abc123",
    }


# ── Test 1: Successful submission (201 Created) ──────────────────────

@pytest.mark.unit
@patch("services.pipeline.validate_layout_geometry")
def test_hypar_submission_success(mock_validate, settings, tmp_path):
    """When Hypar returns 201, the pipeline records submitted=True
    and the explanation schema contains the success status."""
    mock_validate.return_value = {"valid": True, "checks": []}
    _make_settings(settings, tmp_path)

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.text = '{"id": "hypar_run_42"}'
    mock_response.json.return_value = {"id": "hypar_run_42"}

    with patch("services.hypar_client.httpx.Client") as MockClient:
        mock_ctx = MagicMock()
        mock_ctx.post.return_value = mock_response
        MockClient.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)

        result = run_design_pipeline(dict(_FULL_INPUT))

    # Pipeline must not crash.
    assert result["status"] in {"completed", "layout_generated"}

    # Hypar JSON file should have been written locally.
    if result["hypar_json_path"]:
        assert result["hypar_json_path"].endswith(".json")

    # Explanation must reflect successful submission.
    explanation = result["explanation"]
    assert isinstance(explanation, dict)
    assert explanation["hypar_submission_status"]["submitted"] is True
    assert "submitted successfully" in explanation["raw_explanation"].lower()

    # The pipeline metadata also carries it.
    hypar_meta = result["parsed_input"].get("_hypar_submission", {})
    assert hypar_meta.get("submitted") is True


# ── Test 2: Server error (500) ────────────────────────────────────────

@pytest.mark.unit
@patch("services.pipeline.validate_layout_geometry")
def test_hypar_submission_server_error(mock_validate, settings, tmp_path):
    """When Hypar returns 500, the pipeline must NOT crash.
    It should record submitted=False with the failure reason."""
    mock_validate.return_value = {"valid": True, "checks": []}
    _make_settings(settings, tmp_path)

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("services.hypar_client.httpx.Client") as MockClient:
        mock_ctx = MagicMock()
        mock_ctx.post.return_value = mock_response
        MockClient.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)

        result = run_design_pipeline(dict(_FULL_INPUT))

    # Pipeline must still complete without raising.
    assert result["status"] in {"completed", "layout_generated"}

    # Local JSON artifact should still exist.
    if result["hypar_json_path"]:
        assert result["hypar_json_path"].endswith(".json")

    # Explanation must reflect the failure.
    explanation = result["explanation"]
    assert isinstance(explanation, dict)
    assert explanation["hypar_submission_status"]["submitted"] is False
    assert explanation["hypar_submission_status"]["reason"] == "request_failed"
    assert "skipped/failed" in explanation["raw_explanation"].lower()

    hypar_meta = result["parsed_input"].get("_hypar_submission", {})
    assert hypar_meta.get("submitted") is False
    assert hypar_meta.get("status_code") == 500


# ── Test 3: Network timeout ──────────────────────────────────────────

@pytest.mark.unit
@patch("services.pipeline.validate_layout_geometry")
def test_hypar_submission_timeout(mock_validate, settings, tmp_path):
    """When the Hypar API call times out, the pipeline must gracefully
    degrade: return the locally written JSON and mark submission as
    failed with reason 'exception'."""
    mock_validate.return_value = {"valid": True, "checks": []}
    _make_settings(settings, tmp_path)

    with patch("services.hypar_client.httpx.Client") as MockClient:
        mock_ctx = MagicMock()
        mock_ctx.post.side_effect = httpx.TimeoutException("Connection timed out")
        MockClient.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        MockClient.return_value.__exit__ = MagicMock(return_value=False)

        result = run_design_pipeline(dict(_FULL_INPUT))

    # Pipeline must still complete.
    assert result["status"] in {"completed", "layout_generated"}

    # Local artifact should be present regardless of API failure.
    if result["hypar_json_path"]:
        assert result["hypar_json_path"].endswith(".json")
        assert (tmp_path / result["hypar_json_path"]).exists()

    # Explanation must reflect the timeout gracefully.
    explanation = result["explanation"]
    assert isinstance(explanation, dict)
    assert explanation["hypar_submission_status"]["submitted"] is False
    assert "timed out" in explanation["hypar_submission_status"]["detail"].lower()
    assert "skipped/failed" in explanation["raw_explanation"].lower()


# ── Test 4: Submission skipped when API not configured ────────────────

@pytest.mark.unit
@patch("services.pipeline.validate_layout_geometry")
def test_hypar_submission_skipped_when_not_configured(mock_validate, settings, tmp_path):
    """When HYPAR_API_URL is empty, submission should be skipped cleanly
    and the explanation records reason='not_configured'."""
    mock_validate.return_value = {"valid": True, "checks": []}
    settings.ARCHI3D = {
        **settings.ARCHI3D,
        "OUTPUTS_DIR": tmp_path,
        "HYPAR_API_URL": "",
        "HYPAR_API_TOKEN": "",
    }

    result = run_design_pipeline(dict(_FULL_INPUT))

    assert result["status"] in {"completed", "layout_generated"}

    explanation = result["explanation"]
    assert isinstance(explanation, dict)
    assert explanation["hypar_submission_status"]["submitted"] is False
    assert explanation["hypar_submission_status"]["reason"] == "not_configured"
