"""Loopback-only V3 SQLite composition for F-004B1 browser verification."""

from __future__ import annotations

import asyncio
import copy
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from ipaddress import IPv4Address
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI

from intelligent_travel_assistant.adapters.fakes import SyntheticPlanningJobExecutor
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.repositories import (
    PlanningJobRepository,
    PlanningJobResultV3,
)
from intelligent_travel_assistant.bootstrap import (
    ProviderActivationState,
    ProviderAdapters,
    ProviderStartupReport,
    build_planning_persistence,
)
from intelligent_travel_assistant.contracts import TripPlanResponseV3
from intelligent_travel_assistant.settings import Settings
from tests.contracts.test_multicity_trip_planning_contracts import (
    request_payload as contract_request_payload,
)
from tests.contracts.test_multicity_trip_planning_contracts import response_payload

_SCENARIOS = frozenset({"ready", "partial", "conflict", "needs_input", "failed"})
_CITY_COUNTS = frozenset({2, 3})
_FROZEN_START_DATE = date(2026, 8, 21)
_SOURCE_C = "d1000000-0000-4000-8000-000000000002"
_HOTEL_C = "c1000000-0000-4000-8000-000000000001"
_STATION_C = "c2000000-0000-4000-8000-000000000001"
_ACTIVITY_C = "c3000000-0000-4000-8000-000000000001"
_ITEM_C = "c4000000-0000-4000-8000-000000000001"
_SEGMENT_C = "e1000000-0000-4000-8000-000000000002"
_COST_C = "e2000000-0000-4000-8000-000000000002"
_SOURCE_IDS_BY_ATTEMPT = {
    1: (
        "d1000000-0000-4000-8000-000000000001",
        "d1000000-0000-4000-8000-000000000002",
    ),
    2: (
        "d1000000-0000-4000-8000-000000000003",
        "d1000000-0000-4000-8000-000000000004",
    ),
    3: (
        "d1000000-0000-4000-8000-000000000005",
        "d1000000-0000-4000-8000-000000000006",
    ),
}
_PLAN_IDS_BY_ATTEMPT = {
    1: "f1000000-0000-4000-8000-000000000001",
    2: "f1000000-0000-4000-8000-000000000002",
    3: "f1000000-0000-4000-8000-000000000003",
}


def _required_path() -> Path:
    raw = os.environ.get("ITA_BROWSER_SQLITE_PATH")
    if raw is None:
        raise RuntimeError("synthetic_browser_sqlite_path_required")
    path = Path(raw)
    if not path.is_absolute():
        raise RuntimeError("synthetic_browser_sqlite_path_invalid")
    resolved = path.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if (
        resolved == temporary_root
        or not resolved.is_relative_to(temporary_root)
        or resolved.exists()
    ):
        raise RuntimeError("synthetic_browser_sqlite_path_unsafe")
    return resolved


def _configured_city_count() -> int:
    raw = os.environ.get("ITA_MULTICITY_CITY_COUNT", "2")
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError("synthetic_browser_city_count_invalid") from None
    if value not in _CITY_COUNTS:
        raise RuntimeError("synthetic_browser_city_count_invalid")
    return value


def _configured_start_date() -> date | None:
    raw = os.environ.get("ITA_BROWSER_START_DATE")
    if raw is None:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise RuntimeError("synthetic_browser_start_date_invalid") from None


def _shift_frozen_dates(value: object, start: date) -> object:
    if isinstance(value, str) and len(value) >= 10:
        try:
            current = date.fromisoformat(value[:10])
        except ValueError:
            return value
        offset = (current - _FROZEN_START_DATE).days
        if 0 <= offset <= 6:
            return f"{date.fromordinal(start.toordinal() + offset).isoformat()}{value[10:]}"
        return value
    if isinstance(value, list):
        return [_shift_frozen_dates(item, start) for item in value]
    if isinstance(value, dict):
        return {key: _shift_frozen_dates(item, start) for key, item in value.items()}
    return value


def _with_configured_dates(payload: dict[str, object]) -> dict[str, object]:
    start = _configured_start_date()
    if start is None:
        return payload
    return cast(dict[str, object], _shift_frozen_dates(payload, start))


def request_payload(city_count: int) -> dict[str, object]:
    return _with_configured_dates(copy.deepcopy(contract_request_payload(city_count)))


def _user_source(source_id: str) -> dict[str, object]:
    return {
        "source_id": source_id,
        "provider": "user",
        "source_type": "user_provided_intercity_segment",
        "provider_record_id": None,
        "fetched_at": "2026-08-20T12:00:00+08:00",
        "valid_until": None,
        "freshness": "unknown_validity",
        "reference_url": None,
        "attributions": ["用户提供"],
        "warnings": ["未核验班次、票价、余票或库存"],
    }


def _location(
    location_id: str,
    name: str,
    category: str,
    adcode: str,
) -> dict[str, object]:
    return {
        "location_id": location_id,
        "provider": "user",
        "provider_place_id": None,
        "name": name,
        "category": category,
        "address": None,
        "city_adcode": adcode,
        "coordinates": None,
        "source_ids": [_SOURCE_C],
    }


def _expand_to_three_cities(payload: dict[str, object], *, unknown_fare: bool) -> None:
    summary = cast(dict[str, object], payload["request_summary"])
    stays = cast(list[dict[str, object]], summary["city_stays"])
    stays.append({"city": "南京", "nights": 1})
    summary["end_date"] = "2026-08-24"

    destinations = cast(list[dict[str, object]], payload["resolved_destinations"])
    destinations.append(
        {"city_name": "南京市", "adcode": "320100", "center": None, "source_ids": [_SOURCE_C]}
    )

    plan = cast(dict[str, object], payload["plan"])
    plan["city_adcodes"] = ["330100", "310000", "320100"]
    plan["end_date"] = "2026-08-24"
    locations = cast(list[dict[str, object]], plan["locations"])
    locations.extend(
        (
            _location(_STATION_C, "南京站", "rail_station", "320100"),
            _location(_HOTEL_C, "南京住宿", "accommodation_anchor", "320100"),
            _location(_ACTIVITY_C, "玄武湖", "attraction", "320100"),
        )
    )
    fare: dict[str, object] = {
        "cost_id": _COST_C,
        "category": "intercity_transport",
        "confidence": "unknown" if unknown_fare else "user_provided",
        "amount": None if unknown_fare else {"amount": "120.00", "currency": "CNY"},
        "description": "用户提供城际费用",
        "source_ids": [_SOURCE_C],
    }
    segments = cast(list[dict[str, object]], plan["intercity_segments"])
    segments.append(
        {
            "segment_id": _SEGMENT_C,
            "from_city_index": 1,
            "to_city_index": 2,
            "mode": "rail",
            "departure_station_location_id": "b2000000-0000-4000-8000-000000000001",
            "arrival_station_location_id": _STATION_C,
            "departure_at": "2026-08-23T10:00:00+08:00",
            "arrival_at": "2026-08-23T12:00:00+08:00",
            "fare": fare,
            "source_ids": [_SOURCE_C],
        }
    )
    days = cast(list[dict[str, object]], plan["days"])
    days[2] = {
        "local_date": "2026-08-23",
        "departure_city_index": 1,
        "arrival_city_index": 2,
        "overnight_city_index": 2,
        "intercity_segment_id": _SEGMENT_C,
        "accommodation_location_id": _HOTEL_C,
        "activities": [],
        "routes": [],
        "weather": None,
    }
    days.append(
        {
            "local_date": "2026-08-24",
            "departure_city_index": 2,
            "arrival_city_index": 2,
            "overnight_city_index": 2,
            "intercity_segment_id": None,
            "accommodation_location_id": _HOTEL_C,
            "activities": [
                {
                    "item_id": _ITEM_C,
                    "location_id": _ACTIVITY_C,
                    "title": "玄武湖",
                    "start_time": "14:00:00",
                    "end_time": "15:00:00",
                    "cost_items": [],
                    "source_ids": [_SOURCE_C],
                }
            ],
            "routes": [],
            "weather": None,
        }
    )
    budget = cast(dict[str, object], plan["budget_summary"])
    cost_items = cast(list[dict[str, object]], budget["cost_items"])
    cost_items.append(fare)
    budget["known_total"] = {
        "amount": "0.00" if unknown_fare else "240.00",
        "currency": "CNY",
    }
    budget["unknown_count"] = 2 if unknown_fare else 0
    cast(list[dict[str, object]], payload["sources"]).append(_user_source(_SOURCE_C))


def _remap_source_ids(payload: dict[str, object], attempt: int) -> dict[str, object]:
    current = _SOURCE_IDS_BY_ATTEMPT[1]
    target = _SOURCE_IDS_BY_ATTEMPT[attempt]
    mapping = dict(zip(current, target, strict=True))
    mapping[_PLAN_IDS_BY_ATTEMPT[1]] = _PLAN_IDS_BY_ATTEMPT[attempt]

    def replace(value: object) -> object:
        if isinstance(value, str):
            return mapping.get(value, value)
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    return cast(dict[str, object], replace(payload))


def _terminal_result(scenario: str, city_count: int, *, attempt: int = 1) -> PlanningJobResultV3:
    if scenario not in _SCENARIOS:
        raise RuntimeError("synthetic_browser_scenario_invalid")
    unknown_fare = scenario == "partial"
    payload = copy.deepcopy(response_payload(unknown_fare=unknown_fare))
    if city_count == 3:
        _expand_to_three_cities(payload, unknown_fare=unknown_fare)
    payload = _with_configured_dates(payload)
    if scenario == "partial":
        payload["retryable"] = True
        payload["errors"] = [
            {
                "code": "provider_timeout",
                "message": "市内路线服务暂时超时。",
                "field": None,
                "provider": "amap",
                "retryable": True,
            }
        ]
    elif scenario == "conflict":
        payload["status"] = "conflict"
        payload["violations"] = [
            {
                "code": "intercity_buffer_conflict",
                "severity": "error",
                "message": "城际缓冲与活动窗口冲突。",
                "affected_refs": ["e1000000-0000-4000-8000-000000000001"],
            }
        ]
    elif scenario in {"needs_input", "failed"}:
        payload.update(
            status=scenario,
            resolved_destinations=[],
            plan=None,
            warnings=[],
            uncertainties=[],
            sources=[],
            errors=[
                {
                    "code": "input_invalid" if scenario == "needs_input" else "internal_error",
                    "message": "需要补充城市输入。" if scenario == "needs_input" else "规划失败。",
                    "field": "city_stays" if scenario == "needs_input" else None,
                    "provider": None,
                    "retryable": False,
                }
            ],
        )
    response = TripPlanResponseV3.model_validate(_remap_source_ids(payload, attempt))
    return PlanningJobResultV3(
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
    """Give each retry attempt fresh source identities without changing schema-v2 semantics."""

    def __init__(
        self,
        repository: PlanningJobRepository,
        *,
        scenario: str,
        city_count: int,
    ) -> None:
        self._repository = repository
        self._scenario = scenario
        self._city_count = city_count

    async def execute(self, job_id: UUID) -> None:
        job = await self._repository.get(job_id)
        executor = SyntheticPlanningJobExecutor(
            self._repository,
            _terminal_result(self._scenario, self._city_count, attempt=job.attempt),
            wait_between_states=lambda: asyncio.sleep(0.05),
        )
        await executor.execute(job_id)


def settings(path: Path) -> Settings:
    return Settings.model_validate(
        {
            "app_env": "test",
            "api_host": IPv4Address("127.0.0.1"),
            "api_port": 8000,
            "sqlite_database_path": path.resolve(),
        }
    )


def configure_browser_environment(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
    *,
    city_count: int,
    scenario: str,
) -> None:
    monkeypatch.setenv("ITA_BROWSER_SQLITE_PATH", str(path.resolve()))
    monkeypatch.setenv("ITA_MULTICITY_CITY_COUNT", str(city_count))
    monkeypatch.setenv("ITA_MULTICITY_SCENARIO", scenario)


def create_browser_app() -> FastAPI:
    """Use explicit synthetic V3 data, disabled providers, and one new temporary DB."""

    path = _required_path()
    city_count = _configured_city_count()
    scenario = os.environ.get("ITA_MULTICITY_SCENARIO", "ready")
    persistence = build_planning_persistence(settings(path))
    executor = _BrowserSyntheticExecutor(
        persistence.repository,
        scenario=scenario,
        city_count=city_count,
    )
    disabled = ProviderActivationState.DISABLED
    providers = ProviderAdapters(
        report=ProviderStartupReport(deepseek=disabled, amap=disabled, qweather=disabled)
    )
    application = create_app(
        settings=settings(path),
        planning_job_repository=persistence.repository,
        planning_job_executor=executor,
        provider_adapters=providers,
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
