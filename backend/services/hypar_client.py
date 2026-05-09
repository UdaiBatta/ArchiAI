"""Optional Hypar submission client for concept payloads.

Submission is skipped automatically when API URL/token are not configured.
"""

from __future__ import annotations

from typing import Dict

import httpx


def submit_hypar_payload(
    payload: Dict[str, object],
    api_url: str,
    api_token: str,
) -> Dict[str, object]:
    if not api_url or not api_token:
        return {
            "submitted": False,
            "reason": "not_configured",
        }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code >= 400:
            return {
                "submitted": False,
                "reason": "request_failed",
                "status_code": response.status_code,
                "detail": response.text[:500],
            }

        response_data = {}
        try:
            response_data = response.json()
        except Exception:
            response_data = {"raw": response.text[:500]}

        return {
            "submitted": True,
            "status_code": response.status_code,
            "response": response_data,
        }
    except Exception as exc:
        return {
            "submitted": False,
            "reason": "exception",
            "detail": str(exc),
        }
