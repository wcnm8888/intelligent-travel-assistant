from __future__ import annotations

from uuid import UUID, uuid5

import httpx2
import pytest

from intelligent_travel_assistant.adapters.providers.amap import (
    AMAP_POI_NAMESPACE,
    AmapAdapter,
    AmapAdapterConfig,
)
from intelligent_travel_assistant.adapters.providers.f009_amap import F009AmapProvider
from intelligent_travel_assistant.application.f009 import (
    F009PoiQuery,
    F009ProviderFailureKind,
    F009RouteQuery,
)
from intelligent_travel_assistant.contracts.f009 import (
    Gcj02Point,
    PoiConfirmationStatus,
    PoiPurpose,
    PoiScopeKind,
)
from intelligent_travel_assistant.contracts.trip_planning import TransportMode

KEY = "test-only-f009-amap-value"
ORIGIN_ID = UUID("40000000-0000-4000-8000-000000000001")
DESTINATION_ID = UUID("40000000-0000-4000-8000-000000000002")


def provider(handler: object) -> F009AmapProvider:
    transport = httpx2.MockTransport(handler)  # type: ignore[arg-type]
    return F009AmapProvider(
        AmapAdapter(AmapAdapterConfig(web_service_key=KEY), transport=transport)
    )


@pytest.mark.anyio
async def test_f009_poi_search_uses_strict_city_category_and_paging() -> None:
    observed: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        observed.append(request)
        return httpx2.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "count": "2",
                "pois": [
                    {
                        "id": "WEST-LAKE",
                        "name": "西湖风景名胜区",
                        "location": "120.148674,30.242879",
                        "type": "风景名胜",
                        "typecode": "110000",
                        "adcode": "330106",
                        "address": "龙井路1号",
                    },
                    {
                        "id": "OUTSIDE",
                        "name": "异城同名景点",
                        "location": "121.48,31.23",
                        "type": "风景名胜",
                        "typecode": "110000",
                        "adcode": "310101",
                        "address": "外地",
                    },
                ],
            },
        )

    outcome = await provider(handler).search_pois(
        F009PoiQuery(
            city_adcode="330100",
            purpose=PoiPurpose.VISIT,
            keywords="西湖",
            district_adcode="330106",
            center=None,
            radius_m=None,
            category_codes=("scenic_area",),
            page=2,
            page_size=20,
        )
    )

    assert outcome.data is not None
    assert len(outcome.data) == 1
    item = outcome.data[0]
    assert item.location_id == uuid5(AMAP_POI_NAMESPACE, "WEST-LAKE")
    assert item.provider_place_id == "WEST-LAKE"
    assert item.city_adcode == "330100"
    assert item.district_adcode == "330106"
    assert item.scope_kind is PoiScopeKind.COMPLEX
    assert item.confirmation_status is PoiConfirmationStatus.REPRESENTATIVE_REQUIRED
    assert dict(observed[0].url.params) == {
        "key": KEY,
        "keywords": "西湖",
        "types": "110000",
        "region": "330106",
        "city_limit": "true",
        "page_size": "20",
        "page_num": "2",
        "output": "json",
    }


@pytest.mark.anyio
async def test_f009_map_pin_reverse_geocode_returns_verified_district() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v3/geocode/regeo"
        return httpx2.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "regeocode": {
                    "formatted_address": "浙江省杭州市上城区湖滨",
                    "addressComponent": {"adcode": "330102", "citycode": "0571"},
                },
            },
        )

    outcome = await provider(handler).reverse_geocode(Gcj02Point(longitude=120.16, latitude=30.25))
    assert outcome.data is not None
    assert outcome.data.city_adcode == "330100"
    assert outcome.data.district_adcode == "330102"


@pytest.mark.anyio
async def test_f009_route_requests_geometry_and_preserves_ordered_points() -> None:
    observed: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        observed.append(request)
        return httpx2.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "count": "1",
                "route": {
                    "origin": "120.160000,30.250000",
                    "destination": "120.170000,30.260000",
                    "paths": [
                        {
                            "distance": "1800",
                            "cost": {"duration": "901"},
                            "steps": [
                                {"polyline": "120.160000,30.250000;120.165000,30.255000"},
                                {"polyline": "120.165000,30.255000;120.170000,30.260000"},
                            ],
                        }
                    ],
                },
            },
        )

    outcome = await provider(handler).calculate_route(
        F009RouteQuery(
            origin_location_id=ORIGIN_ID,
            destination_location_id=DESTINATION_ID,
            origin_provider_place_id="ORIGIN",
            destination_provider_place_id="DESTINATION",
            origin=Gcj02Point(longitude=120.16, latitude=30.25),
            destination=Gcj02Point(longitude=120.17, latitude=30.26),
            origin_citycode="0571",
            destination_citycode="0571",
            mode=TransportMode.WALKING,
        )
    )

    assert outcome.data is not None
    assert outcome.data.distance_meters == 1800
    assert outcome.data.duration_minutes == 16
    assert len(outcome.data.points) == 3
    assert dict(observed[0].url.params)["show_fields"] == "cost,polyline"


@pytest.mark.anyio
async def test_f009_explicit_zero_route_is_not_provider_unavailable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "count": "0",
                "route": {"paths": []},
            },
        )

    outcome = await provider(handler).calculate_route(
        F009RouteQuery(
            origin_location_id=ORIGIN_ID,
            destination_location_id=DESTINATION_ID,
            origin_provider_place_id=None,
            destination_provider_place_id=None,
            origin=Gcj02Point(longitude=120.16, latitude=30.25),
            destination=Gcj02Point(longitude=120.17, latitude=30.26),
            origin_citycode="0571",
            destination_citycode="0571",
            mode=TransportMode.WALKING,
        )
    )
    assert outcome.data is None
    assert outcome.failure is not None
    assert outcome.failure.kind is F009ProviderFailureKind.EMPTY_RESULT
