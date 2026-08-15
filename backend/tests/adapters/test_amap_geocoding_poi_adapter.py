"""Offline contracts for the Amap geocoding and POI 2.0 adapter."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

import httpx2
import pytest

from intelligent_travel_assistant.adapters.providers.amap import (
    AMAP_BASE_URL,
    AMAP_POI_NAMESPACE,
    AmapAdapter,
    AmapAdapterConfig,
)
from intelligent_travel_assistant.application.ports import (
    CityResolutionRequest,
    PoiSearchRequest,
)
from intelligent_travel_assistant.domain import (
    CoordinateSystem,
    Provider,
    ProviderErrorCategory,
    ProviderResultStatus,
)

ADAPTER_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "intelligent_travel_assistant"
    / "adapters"
    / "providers"
    / "amap.py"
)
FIXED_NOW = datetime(2026, 8, 14, 7, 0, tzinfo=UTC)
FIXED_SOURCE_ID = UUID("70000000-0000-4000-8000-000000000029")
TEST_AUTH_VALUE = "test-only-amap-web-service-value"


def _geocode(
    *,
    city: object = "杭州市",
    province: object = "浙江省",
    adcode: object = "330100",
    citycode: object = "0571",
    location: object = "120.155070,30.274085",
    level: object = "市",
) -> dict[str, object]:
    return {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "count": "1",
        "geocodes": [
            {
                "formatted_address": "浙江省杭州市",
                "country": "中国",
                "province": province,
                "city": city,
                "citycode": citycode,
                "district": [],
                "street": [],
                "number": [],
                "adcode": adcode,
                "location": location,
                "level": level,
            }
        ],
    }


def _poi(
    *,
    provider_id: object = "B0SYNTHETIC01",
    name: object = "西湖风景名胜区 synthetic",
    type_name: object = "风景名胜;风景名胜;风景名胜",
    typecode: object = "110000",
    adcode: object = "330106",
    location: object = "120.148674,30.242879",
    address: object = "龙井路1号",
) -> dict[str, object]:
    return {
        "id": provider_id,
        "name": name,
        "location": location,
        "type": type_name,
        "typecode": typecode,
        "pname": "浙江省",
        "cityname": "杭州市",
        "adname": "西湖区",
        "address": address,
        "pcode": "330000",
        "adcode": adcode,
        "citycode": "0571",
    }


def _poi_response(*pois: dict[str, object]) -> dict[str, object]:
    return {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "count": str(len(pois)),
        "pois": list(pois),
    }


def _ambiguous_geocode() -> dict[str, object]:
    response = _geocode()
    geocodes = response["geocodes"]
    assert isinstance(geocodes, list)
    response["count"] = "2"
    response["geocodes"] = [*geocodes, *geocodes]
    return response


def _adapter(transport: httpx2.MockTransport) -> AmapAdapter:
    return AmapAdapter(
        AmapAdapterConfig(web_service_key=TEST_AUTH_VALUE),
        transport=transport,
        clock=lambda: FIXED_NOW,
        source_id_factory=lambda: FIXED_SOURCE_ID,
    )


@pytest.mark.anyio
async def test_city_resolution_uses_frozen_geocoding_request_and_native_coordinates() -> None:
    observed: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        observed.append(request)
        return httpx2.Response(200, json=_geocode())

    result = await _adapter(httpx2.MockTransport(handler)).resolve_city(
        CityResolutionRequest("杭州市")
    )

    assert result.status is ProviderResultStatus.OK
    assert result.provider is Provider.AMAP
    assert result.data is not None
    assert result.data.city_name == "杭州市"
    assert result.data.adcode == "330100"
    assert result.data.citycode == "0571"
    assert result.data.center is not None
    assert result.data.center.longitude == Decimal("120.155070")
    assert result.data.center.latitude == Decimal("30.274085")
    assert result.data.center.coordinate_system is CoordinateSystem.PROVIDER_NATIVE
    assert result.fetched_at == FIXED_NOW
    assert result.valid_until is None
    assert result.warnings == ("高德地理编码没有固定有效期。",)
    assert result.error is None
    assert result.source_records[0].source_id == FIXED_SOURCE_ID
    assert result.source_records[0].source_type == "amap_geocode"

    assert len(observed) == 1
    request = observed[0]
    assert request.method == "GET"
    assert request.url.path == "/v3/geocode/geo"
    assert request.url.host == "restapi.amap.com"
    assert dict(request.url.params) == {
        "key": TEST_AUTH_VALUE,
        "address": "杭州市",
        "city": "杭州市",
        "output": "JSON",
    }
    assert request.headers["accept"] == "application/json"


@pytest.mark.anyio
async def test_direct_municipality_uses_province_when_provider_city_is_empty_array() -> None:
    response = _geocode(
        city=[],
        province="北京市",
        adcode="110000",
        citycode="010",
        location="116.407387,39.904179",
        level="省",
    )
    result = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, json=response))
    ).resolve_city(CityResolutionRequest("北京市"))

    assert result.status is ProviderResultStatus.OK
    assert result.data is not None
    assert result.data.city_name == "北京市"
    assert result.data.adcode == "110000"
    assert result.data.citycode == "010"


@pytest.mark.anyio
async def test_poi_search_uses_v5_city_limit_and_maps_project_categories() -> None:
    observed: list[httpx2.Request] = []
    response = _poi_response(
        _poi(),
        _poi(
            provider_id="B0SYNTHETIC02",
            name="浙江省博物馆 synthetic",
            type_name="科教文化服务;博物馆;博物馆",
            typecode="140100",
            adcode="330106",
            location="120.147350,30.252030",
            address=[],
        ),
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        observed.append(request)
        return httpx2.Response(200, json=response)

    result = await _adapter(httpx2.MockTransport(handler)).search_pois(
        PoiSearchRequest(
            "330100",
            ("西湖", "博物馆"),
            ("scenic_area", "museum"),
            3,
        )
    )

    assert result.status is ProviderResultStatus.OK
    assert result.provider is Provider.AMAP
    assert result.data is not None
    assert len(result.data.candidates) == 2
    scenic, museum = result.data.candidates
    assert scenic.location_id == uuid5(AMAP_POI_NAMESPACE, "B0SYNTHETIC01")
    assert scenic.name == "西湖风景名胜区 synthetic"
    assert scenic.category == "scenic_area"
    assert scenic.city_adcode == "330100"
    assert scenic.address == "龙井路1号"
    assert scenic.coordinates is not None
    assert scenic.coordinates.coordinate_system is CoordinateSystem.PROVIDER_NATIVE
    assert museum.location_id == uuid5(AMAP_POI_NAMESPACE, "B0SYNTHETIC02")
    assert museum.category == "museum"
    assert museum.address is None
    assert result.warnings == ("高德 POI 数据没有固定有效期。",)
    assert result.source_records[0].source_type == "amap_poi_search"

    assert len(observed) == 1
    request = observed[0]
    assert request.method == "GET"
    assert request.url.path == "/v5/place/text"
    assert dict(request.url.params) == {
        "key": TEST_AUTH_VALUE,
        "keywords": "西湖|博物馆",
        "types": "110000|140100",
        "region": "330100",
        "city_limit": "true",
        "page_size": "3",
        "page_num": "1",
        "output": "json",
    }


@pytest.mark.anyio
async def test_missing_poi_coordinates_are_preserved_instead_of_invented() -> None:
    result = await _adapter(
        httpx2.MockTransport(
            lambda request: httpx2.Response(200, json=_poi_response(_poi(location=[])))
        )
    ).search_pois(PoiSearchRequest("330100", ("西湖",), ("scenic_area",), 1))

    assert result.status is ProviderResultStatus.OK
    assert result.data is not None
    assert result.data.candidates[0].coordinates is None


@pytest.mark.anyio
async def test_malformed_or_out_of_city_pois_are_dropped_as_partial() -> None:
    response = _poi_response(
        _poi(),
        _poi(provider_id="OUTSIDE", adcode="310101"),
        _poi(provider_id="BAD", location="not-a-coordinate"),
    )
    result = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, json=response))
    ).search_pois(PoiSearchRequest("330100", ("西湖",), ("scenic_area",), 3))

    assert result.status is ProviderResultStatus.PARTIAL
    assert result.data is not None
    assert len(result.data.candidates) == 1
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.SCHEMA
    assert result.warnings == (
        "高德 POI 数据没有固定有效期。",
        "高德 POI 响应包含已忽略的无效或异城记录。",
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        _poi_response(),
        _poi_response(_poi(provider_id="OUTSIDE", adcode="310101")),
        _poi_response(_poi(provider_id="BAD", name=[])),
    ],
)
async def test_empty_or_wholly_invalid_poi_results_are_unavailable(
    response: dict[str, object],
) -> None:
    result = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, json=response))
    ).search_pois(PoiSearchRequest("330100", ("西湖",), ("scenic_area",), 3))

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
        _ambiguous_geocode(),
        _geocode(level="区县", adcode="330106"),
        _geocode(location="181,30"),
        _geocode(city=[], province="浙江省"),
    ],
)
async def test_ambiguous_or_invalid_city_results_are_rejected(
    response: dict[str, object],
) -> None:
    result = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, json=response))
    ).resolve_city(CityResolutionRequest("杭州市"))

    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.SCHEMA


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("infocode", "category"),
    [
        ("10001", ProviderErrorCategory.AUTH),
        ("10012", ProviderErrorCategory.AUTH),
        ("40000", ProviderErrorCategory.AUTH),
        ("10003", ProviderErrorCategory.RATE_LIMITED),
        ("10020", ProviderErrorCategory.RATE_LIMITED),
        ("10016", ProviderErrorCategory.SERVER),
        ("30001", ProviderErrorCategory.SERVER),
        ("20000", ProviderErrorCategory.SCHEMA),
        ("20012", ProviderErrorCategory.SCHEMA),
        ("29999", ProviderErrorCategory.UNKNOWN),
    ],
)
async def test_amap_infocodes_map_to_project_owned_errors(
    infocode: str,
    category: ProviderErrorCategory,
) -> None:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(
            200,
            json={
                "status": "0",
                "info": "sensitive upstream detail",
                "infocode": infocode,
            },
        )

    result = await _adapter(httpx2.MockTransport(handler)).resolve_city(
        CityResolutionRequest("杭州市")
    )

    assert calls == 1
    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.category is category
    assert "sensitive" not in repr(result)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status_code", "category"),
    [
        (400, ProviderErrorCategory.SCHEMA),
        (401, ProviderErrorCategory.AUTH),
        (403, ProviderErrorCategory.AUTH),
        (418, ProviderErrorCategory.UNKNOWN),
        (422, ProviderErrorCategory.SCHEMA),
        (429, ProviderErrorCategory.RATE_LIMITED),
        (500, ProviderErrorCategory.SERVER),
        (503, ProviderErrorCategory.SERVER),
    ],
)
async def test_http_statuses_are_safe_and_never_retried(
    status_code: int,
    category: ProviderErrorCategory,
) -> None:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(status_code, content=b"key=sensitive-provider-body")

    result = await _adapter(httpx2.MockTransport(handler)).resolve_city(
        CityResolutionRequest("杭州市")
    )

    assert calls == 1
    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.category is category
    assert "sensitive" not in repr(result)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("exception_type", "category"),
    [
        (httpx2.ReadTimeout, ProviderErrorCategory.TIMEOUT),
        (httpx2.ConnectError, ProviderErrorCategory.UNKNOWN),
    ],
)
async def test_transport_failures_are_safe_and_never_retried(
    exception_type: type[httpx2.RequestError],
    category: ProviderErrorCategory,
) -> None:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        raise exception_type("key=sensitive", request=request)

    result = await _adapter(httpx2.MockTransport(handler)).search_pois(
        PoiSearchRequest("330100", ("西湖",), ("scenic_area",), 3)
    )

    assert calls == 1
    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.category is category
    assert "sensitive" not in repr(result)


@pytest.mark.anyio
async def test_non_json_and_oversized_responses_are_rejected_without_raw_text() -> None:
    responses = iter(
        (
            httpx2.Response(200, content=b"private non-json upstream body"),
            httpx2.Response(200, content=b"x" * 1_000_001),
        )
    )
    adapter = _adapter(httpx2.MockTransport(lambda request: next(responses)))

    first = await adapter.resolve_city(CityResolutionRequest("杭州市"))
    second = await adapter.resolve_city(CityResolutionRequest("杭州市"))

    for result in (first, second):
        assert result.status is ProviderResultStatus.UNAVAILABLE
        assert result.error is not None
        assert result.error.category is ProviderErrorCategory.SCHEMA
        assert "private" not in repr(result)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "port_request",
    [
        CityResolutionRequest(""),
        CityResolutionRequest(" 杭州市"),
        PoiSearchRequest("33010", ("西湖",), ("scenic_area",), 3),
        PoiSearchRequest("330100", (), (), 3),
        PoiSearchRequest("330100", ("西湖",), ("unsupported",), 3),
        PoiSearchRequest("330100", ("x" * 81,), (), 3),
        PoiSearchRequest("330100", ("西湖",), ("scenic_area",), 26),
    ],
)
async def test_invalid_application_requests_fail_before_transport(port_request: object) -> None:
    calls = 0

    def handler(http_request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(200, json=_geocode())

    adapter = _adapter(httpx2.MockTransport(handler))
    if isinstance(port_request, CityResolutionRequest):
        city_result = await adapter.resolve_city(port_request)
        observed_result = (city_result.status, city_result.error)
    else:
        assert isinstance(port_request, PoiSearchRequest)
        poi_result = await adapter.search_pois(port_request)
        observed_result = (poi_result.status, poi_result.error)

    assert calls == 0
    assert observed_result[0] is ProviderResultStatus.UNAVAILABLE
    assert observed_result[1] is not None
    assert observed_result[1].category is ProviderErrorCategory.SCHEMA


def test_config_is_fixed_redacted_and_rejects_unapproved_values() -> None:
    config = AmapAdapterConfig(web_service_key=TEST_AUTH_VALUE)

    assert config.base_url == AMAP_BASE_URL
    assert config.timeout_seconds == 6.0
    assert TEST_AUTH_VALUE not in repr(config)

    for values in (
        {"web_service_key": ""},
        {"web_service_key": "bad\nvalue"},
        {
            "web_service_key": TEST_AUTH_VALUE,
            "base_url": "https://restapi.amap.com/v3",
        },
        {"web_service_key": TEST_AUTH_VALUE, "timeout_seconds": 7.0},
    ):
        with pytest.raises(ValueError):
            AmapAdapterConfig(**values)


def test_adapter_source_has_no_environment_sdk_logging_or_retry_sleep() -> None:
    tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"), filename=str(ADAPTER_PATH))
    forbidden_imports: list[str] = []
    forbidden_calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules = (node.module,)
        else:
            modules = ()
        forbidden_imports.extend(
            module
            for module in modules
            if module.split(".", 1)[0] in {"fastapi", "logging", "os", "requests", "time", "urllib"}
        )
        if isinstance(node, ast.Call):
            rendered = ast.unparse(node.func).casefold()
            if any(token in rendered for token in ("getenv", "environ", "sleep", "print")):
                forbidden_calls.append(rendered)

    assert forbidden_imports == []
    assert forbidden_calls == []
