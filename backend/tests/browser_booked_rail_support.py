"""Loopback-only V4 booked-rail composition for F-004C browser verification."""

from __future__ import annotations

import asyncio
import copy
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID

from fastapi import FastAPI

from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.repositories import (
    PlanningJobRepository,
    PlanningJobResultV4,
)
from intelligent_travel_assistant.bootstrap import (
    ProviderActivationState,
    ProviderAdapters,
    ProviderStartupReport,
    build_planning_persistence,
)
from intelligent_travel_assistant.contracts import (
    Money,
    PlanningStatus,
    TripPlanRequestV4,
    TripPlanResponseV4,
)
from tests.browser_multicity_support import (
    _expand_to_three_cities,
    _remap_source_ids,
    _required_path,
    _with_configured_dates,
    settings,
)
from tests.contracts.test_booked_rail_trip_planning_contracts import (
    request_payload as contract_request_payload,
)
from tests.contracts.test_booked_rail_trip_planning_contracts import response_payload

_CITY_COUNTS = frozenset({2, 3})
_VALIDATION_PATH = (
    PlanningStatus.NORMALIZING,
    PlanningStatus.COLLECTING,
    PlanningStatus.PLANNING,
    PlanningStatus.ENRICHING_ROUTES,
    PlanningStatus.VALIDATING,
)


def _configured_city_count() -> int:
    raw = os.environ.get("ITA_MULTICITY_CITY_COUNT", "2")
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError("synthetic_browser_city_count_invalid") from None
    if value not in _CITY_COUNTS:
        raise RuntimeError("synthetic_browser_city_count_invalid")
    return value


def request_payload(city_count: int) -> dict[str, object]:
    return _with_configured_dates(copy.deepcopy(contract_request_payload(city_count=city_count)))


def _terminal_result(
    city_count: int,
    *,
    attempt: int,
    total_budget: Money,
) -> PlanningJobResultV4:
    payload = copy.deepcopy(response_payload(unknown_fare=True))
    cast(dict[str, object], payload["request_summary"])["budget"] = total_budget.model_dump(
        mode="json"
    )
    cast(dict[str, object], cast(dict[str, object], payload["plan"])["budget_summary"])[
        "budget"
    ] = total_budget.model_dump(mode="json")
    if city_count == 3:
        _expand_to_three_cities(payload, unknown_fare=True)
        plan = cast(dict[str, object], payload["plan"])
        segments = cast(list[dict[str, object]], plan["intercity_segments"])
        segments[1]["service_number"] = "D2281"
    payload = _with_configured_dates(payload)
    payload["retryable"] = True
    payload["errors"] = [
        {
            "code": "provider_timeout",
            "message": "市内路线服务暂时超时；已购铁路段仍保持用户提供、未核验。",
            "field": None,
            "provider": "amap",
            "retryable": True,
        }
    ]
    response = TripPlanResponseV4.model_validate(_remap_source_ids(payload, attempt))
    return PlanningJobResultV4(
        response.status,
        response.resolved_destinations,
        response.plan,
        response.violations,
        response.warnings,
        response.uncertainties,
        response.sources,
        response.errors,
        response.retryable,
    )


class _BrowserSyntheticExecutor:
    """Publish bounded V4 fixtures without any Provider or model call."""

    def __init__(self, repository: PlanningJobRepository, *, city_count: int) -> None:
        self._repository = repository
        self._city_count = city_count

    async def execute(self, job_id: UUID) -> None:
        job = await self._repository.get(job_id)
        if not isinstance(job.request, TripPlanRequestV4):
            raise RuntimeError("synthetic_request_version_invalid")
        result = _terminal_result(
            self._city_count,
            attempt=job.attempt,
            total_budget=job.request.total_budget,
        )
        try:
            start = _VALIDATION_PATH.index(job.status) + 1
        except ValueError:
            if job.status is not PlanningStatus.DRAFT:
                raise RuntimeError("synthetic_job_state_invalid") from None
            start = 0
        for target in _VALIDATION_PATH[start:]:
            job = await self._repository.advance(
                job_id,
                target,
                expected_version=job.version,
            )
            await asyncio.sleep(0.05)
        await self._repository.record_result(
            job_id,
            result,
            expected_version=job.version,
        )


def disabled_providers() -> ProviderAdapters:
    disabled = ProviderActivationState.DISABLED
    return ProviderAdapters(
        report=ProviderStartupReport(deepseek=disabled, amap=disabled, qweather=disabled)
    )


def create_browser_app() -> FastAPI:
    """Use explicit synthetic V4 data, disabled providers, and one new temporary DB."""

    path = _required_path()
    city_count = _configured_city_count()
    persistence = build_planning_persistence(settings(path))
    executor = _BrowserSyntheticExecutor(persistence.repository, city_count=city_count)
    application = create_app(
        settings=settings(path),
        planning_job_repository=persistence.repository,
        planning_job_executor=executor,
        provider_adapters=disabled_providers(),
    )

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        await persistence.start()
        try:
            yield
        finally:
            persistence.close()

    application.router.lifespan_context = lifespan
    return application
