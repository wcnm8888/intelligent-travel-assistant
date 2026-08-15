"""Offline contracts for Amap v5 walking and transit route planning."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import httpx2
import pytest

from intelligent_travel_assistant.adapters.providers.amap import AmapAdapter, AmapAdapterConfig
from intelligent_travel_assistant.application.ports import RouteCalculationRequest
from intelligent_travel_assistant.domain import (
    Coordinates,
    CoordinateSystem,
    Provider,
    ProviderErrorCategory,
    ProviderResultStatus,
    RouteMode,
)

ORIGIN_ID = UUID("90000000-0000-4000-8000-000000000030")
DESTINATION_ID = UUID("90000000-0000-4000-8000-000000000031")
FIXED_NOW = datetime(2026, 8, 14, 8, 0, tzinfo=UTC)
FIXED_SOURCE_ID = UUID("70000000-0000-4000-8000-000000000030")
TEST_AUTH_VALUE = "test-only-amap-route-value"
ORIGIN = Coordinates(
    Decimal("120.155070"),
    Decimal("30.274085"),
    CoordinateSystem.PROVIDER_NATIVE,
)
DESTINATION = Coordinates(
    Decimal("120.147350"),
    Decimal("30.252030"),
    CoordinateSystem.PROVIDER_NATIVE,
)


def _request(mode: RouteMode = RouteMode.WALKING) -> RouteCalculationRequest:
    return RouteCalculationRequest(
        origin_location_id=ORIGIN_ID,
        destination_location_id=DESTINATION_ID,
        origin=ORIGIN,
        destination=DESTINATION,
        origin_citycode="0571",
        destination_citycode="0571",
        mode=mode,
    )


def _walking_response(
    *,
    distance: object = "2468",
    duration: object = "901",
    origin: object = "120.155070,30.274085",
    destination: object = "120.147350,30.252030",
) -> dict[str, object]:
    return {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "count": "1",
        "route": {
            "origin": origin,
            "destination": destination,
            "paths": [
                {
                    "distance": distance,
                    "cost": {"duration": duration, "taxi": "0"},
                    "steps": [],
                }
            ],
        },
    }


def _transit_response(
    *,
    distance: object = "8032",
    duration: object = "1800",
    origin: object = "120.155070,30.274085",
    destination: object = "120.147350,30.252030",
) -> dict[str, object]:
    return {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "count": "1",
        "route": {
            "origin": origin,
            "destination": destination,
            "transits": [
                {
                    "distance": distance,
                    "nightflag": "0",
                    "cost": {"duration": duration, "transit_fee": "4"},
                    "segments": [],
                }
            ],
        },
    }


def _walking_response_with_two_paths() -> dict[str, object]:
    response = _walking_response()
    route = cast(dict[str, object], response["route"])
    first_path = cast(list[dict[str, object]], route["paths"])[0]
    route["paths"] = [first_path, dict(first_path)]
    return response


def _adapter(transport: httpx2.MockTransport) -> AmapAdapter:
    return AmapAdapter(
        AmapAdapterConfig(web_service_key=TEST_AUTH_VALUE),
        transport=transport,
        clock=lambda: FIXED_NOW,
        source_id_factory=lambda: FIXED_SOURCE_ID,
    )


@pytest.mark.anyio
async def test_walking_route_uses_v5_cost_fields_and_converts_seconds_upward() -> None:
    observed: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        observed.append(request)
        return httpx2.Response(200, json=_walking_response())

    result = await _adapter(httpx2.MockTransport(handler)).calculate_routes(_request())

    assert result.status is ProviderResultStatus.OK
    assert result.provider is Provider.AMAP
    assert result.data is not None
    assert result.data.origin_location_id == ORIGIN_ID
    assert result.data.destination_location_id == DESTINATION_ID
    assert result.data.mode is RouteMode.WALKING
    assert result.data.distance_meters == 2468
    assert result.data.duration_minutes == 16
    assert result.data.source_ids == (FIXED_SOURCE_ID,)
    assert result.fetched_at == FIXED_NOW
    assert result.valid_until is None
    assert result.warnings == ("高德路线结果没有固定有效期。",)
    assert result.error is None
    assert result.source_records[0].source_type == "amap_route_walking"

    assert len(observed) == 1
    request = observed[0]
    assert request.method == "GET"
    assert request.url.path == "/v5/direction/walking"
    assert dict(request.url.params) == {
        "key": TEST_AUTH_VALUE,
        "origin": "120.155070,30.274085",
        "destination": "120.147350,30.252030",
        "alternative_route": "1",
        "show_fields": "cost",
        "isindoor": "0",
        "output": "json",
    }


@pytest.mark.anyio
async def test_transit_route_supplies_both_citycodes_and_uses_recommended_strategy() -> None:
    observed: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        observed.append(request)
        return httpx2.Response(200, json=_transit_response())

    result = await _adapter(httpx2.MockTransport(handler)).calculate_routes(
        _request(RouteMode.PUBLIC_TRANSIT)
    )

    assert result.status is ProviderResultStatus.OK
    assert result.data is not None
    assert result.data.mode is RouteMode.PUBLIC_TRANSIT
    assert result.data.distance_meters == 8032
    assert result.data.duration_minutes == 30
    assert result.data.source_ids == (FIXED_SOURCE_ID,)
    assert result.source_records[0].source_type == "amap_route_public_transit"

    assert len(observed) == 1
    request = observed[0]
    assert request.url.path == "/v5/direction/transit/integrated"
    assert dict(request.url.params) == {
        "key": TEST_AUTH_VALUE,
        "origin": "120.155070,30.274085",
        "destination": "120.147350,30.252030",
        "city1": "0571",
        "city2": "0571",
        "strategy": "0",
        "AlternativeRoute": "1",
        "nightflag": "0",
        "show_fields": "cost",
        "output": "json",
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("seconds", "minutes"),
    [("1", 1), ("59", 1), ("60", 1), ("61", 2), ("120", 2)],
)
async def test_route_duration_rounds_up_without_using_float(
    seconds: str,
    minutes: int,
) -> None:
    result = await _adapter(
        httpx2.MockTransport(
            lambda request: httpx2.Response(200, json=_walking_response(duration=seconds))
        )
    ).calculate_routes(_request())

    assert result.status is ProviderResultStatus.OK
    assert result.data is not None
    assert result.data.duration_minutes == minutes


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        {**_walking_response(), "count": "0", "route": {"paths": []}},
        {**_walking_response(), "count": "2"},
        {**_walking_response(), "route": {"paths": []}},
        _walking_response_with_two_paths(),
        _walking_response(distance="-1"),
        _walking_response(distance="1.5"),
        _walking_response(distance="2147483648"),
        _walking_response(distance="9" * 5_000),
        _walking_response(duration="0"),
        _walking_response(duration="60.5"),
        _walking_response(duration="86401"),
        _walking_response(duration="9" * 5_000),
        {**_walking_response(), "count": "9" * 5_000},
        _walking_response(origin="120.000000,30.000000"),
        _walking_response(destination="120.000000,30.000000"),
    ],
)
async def test_empty_or_malformed_walking_routes_are_not_admitted(
    response: dict[str, object],
) -> None:
    result = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, json=response))
    ).calculate_routes(_request())

    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    if response["count"] == "0":
        assert result.error.category is ProviderErrorCategory.EMPTY_RESULT
    else:
        assert result.error.category is ProviderErrorCategory.SCHEMA


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        {**_transit_response(), "count": "0", "route": {"transits": []}},
        {**_transit_response(), "route": {"transits": []}},
        _transit_response(distance=[]),
        _transit_response(duration=[]),
        _transit_response(origin="not-a-coordinate"),
    ],
)
async def test_empty_or_malformed_transit_routes_are_not_admitted(
    response: dict[str, object],
) -> None:
    result = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, json=response))
    ).calculate_routes(_request(RouteMode.PUBLIC_TRANSIT))

    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    if response["count"] == "0":
        assert result.error.category is ProviderErrorCategory.EMPTY_RESULT
    else:
        assert result.error.category is ProviderErrorCategory.SCHEMA


@pytest.mark.anyio
@pytest.mark.parametrize("infocode", ["20800", "20801", "20802", "20803"])
async def test_no_route_infocodes_map_to_empty_result(infocode: str) -> None:
    result = await _adapter(
        httpx2.MockTransport(
            lambda request: httpx2.Response(
                200,
                json={"status": "0", "info": "raw route detail", "infocode": infocode},
            )
        )
    ).calculate_routes(_request())

    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.EMPTY_RESULT
    assert "raw route detail" not in repr(result)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "port_request",
    [
        replace(_request(), destination_location_id=ORIGIN_ID),
        replace(
            _request(),
            origin=Coordinates(Decimal("120"), Decimal("30"), CoordinateSystem.WGS84),
        ),
        replace(
            _request(),
            destination=Coordinates(Decimal("120"), Decimal("30"), CoordinateSystem.UNKNOWN),
        ),
        replace(_request(), origin_citycode=""),
        replace(_request(), destination_citycode="12345"),
        replace(
            _request(),
            origin=Coordinates(
                Decimal("120.1234567"),
                Decimal("30.123456"),
                CoordinateSystem.PROVIDER_NATIVE,
            ),
        ),
        replace(_request(), mode=cast(RouteMode, "driving")),
    ],
)
async def test_invalid_route_requests_fail_before_transport(
    port_request: RouteCalculationRequest,
) -> None:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(200, json=_walking_response())

    result = await _adapter(httpx2.MockTransport(handler)).calculate_routes(port_request)

    assert calls == 0
    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.SCHEMA


@pytest.mark.anyio
async def test_route_http_and_transport_failures_use_existing_safe_mapping() -> None:
    calls = 0

    def http_failure(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(503, content=b"key=sensitive-route-body")

    first = await _adapter(httpx2.MockTransport(http_failure)).calculate_routes(_request())

    def timeout(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        raise httpx2.ReadTimeout("key=sensitive", request=request)

    second = await _adapter(httpx2.MockTransport(timeout)).calculate_routes(_request())

    assert calls == 2
    assert first.error is not None
    assert first.error.category is ProviderErrorCategory.SERVER
    assert second.error is not None
    assert second.error.category is ProviderErrorCategory.TIMEOUT
    assert "sensitive" not in repr((first, second))
