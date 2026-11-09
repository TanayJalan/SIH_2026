"""Response-time budget checks for the seeded dashboards.

The acceptance target is under 500 ms per dashboard on the demo dataset. The
assertions use the fastest of three warm calls so a single cold connection or
CI scheduling hiccup does not fail the build; a real regression (missing
index, Python-side aggregation) still exceeds the budget consistently.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.support import TestData, auth_headers

BUDGET_SECONDS = 0.5


def _fastest_seconds(call: Callable[[], object], runs: int = 3) -> float:
    call()  # warm the connection and any statement cache
    timings: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        call()
        timings.append(time.perf_counter() - started)
    return min(timings)


def _assert_budget(label: str, seconds: float) -> None:
    assert seconds < BUDGET_SECONDS, f"{label} took {seconds * 1000:.0f} ms (budget 500 ms)"


def test_seeded_dashboards_answer_within_budget(
    api_client: TestClient, test_data: TestData
) -> None:
    super_headers = auth_headers(api_client, test_data.users["super"], test_data.password)
    regulation_headers = auth_headers(
        api_client, test_data.users["regulation"], test_data.password
    )
    institution_headers = auth_headers(
        api_client, test_data.users["institution_admin_west"], test_data.password
    )

    checks = (
        (
            "regional dashboard",
            lambda: api_client.get("/reports/regional", headers=super_headers),
        ),
        (
            "regulation bureau dashboard",
            lambda: api_client.get("/reports/regulation-bureau", headers=regulation_headers),
        ),
        (
            "institution dashboard",
            lambda: api_client.get("/reports/institution", headers=institution_headers),
        ),
        (
            "application list page",
            lambda: api_client.get(
                "/applications?page=1&page_size=20", headers=super_headers
            ),
        ),
        (
            "alert inbox page",
            lambda: api_client.get("/alerts?page=1&page_size=20", headers=super_headers),
        ),
    )

    for label, call in checks:
        _assert_budget(label, _fastest_seconds(call))
