"""Amap Web Service adapter for city, POI and single-leg route facts."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Final
from uuid import UUID, uuid4, uuid5

import httpx2

from intelligent_travel_assistant.application.ports import (
    CityResolution,
    CityResolutionRequest,
    PoiCandidate,
    PoiSearchRequest,
    PoiSearchResult,
    RouteCalculationRequest,
)
from intelligent_travel_assistant.domain import (
    MAX_ROUTE_DISTANCE_METERS,
    MAX_ROUTE_DURATION_MINUTES,
    Coordinates,
    CoordinateSystem,
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderResult,
    ProviderResultStatus,
    RouteLeg,
    RouteMode,
    SourceRecord,
)

AMAP_BASE_URL: Final = "https://restapi.amap.com"
AMAP_TIMEOUT_SECONDS: Final = 6.0
AMAP_POI_NAMESPACE: Final = UUID("d5089142-cbe7-4c87-a9af-b717a9f47636")
MAX_RESPONSE_BYTES: Final = 1_000_000
MAX_INTEGER_DIGITS: Final = 18

_ADCODE: Final = re.compile(r"^\d{6}$")
_CITYCODE: Final = re.compile(r"^\d{3,4}$")
_TYPECODE: Final = re.compile(r"^\d{6}$")
_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f]")
_DIRECT_MUNICIPALITIES: Final = frozenset({"北京市", "上海市", "天津市", "重庆市"})
_CATEGORY_TYPECODES: Final = {
    "scenic_area": "110000",
    "museum": "140100",
}
_CATEGORY_PREFIXES: Final = {
    "scenic_area": "11",
    "museum": "1401",
}

_AUTH_INFOCODES: Final = frozenset(
    {
        "10001",
        "10002",
        "10005",
        "10006",
        "10007",
        "10008",
        "10009",
        "10012",
        "10013",
        "10026",
        "10041",
        "20011",
        "40000",
        "40002",
        "40003",
    }
)
_RATE_LIMIT_INFOCODES: Final = frozenset(
    {
        "10003",
        "10004",
        "10010",
        "10014",
        "10015",
        "10019",
        "10020",
        "10021",
        "10029",
        "10044",
        "10045",
    }
)
_SERVER_INFOCODES: Final = frozenset({"10016", "10017"})
_SCHEMA_INFOCODES: Final = frozenset({"20000", "20001", "20002", "20012"})
_EMPTY_INFOCODES: Final = frozenset({"20800", "20801", "20802", "20803"})


@dataclass(frozen=True, slots=True)
class AmapAdapterConfig:
    """Explicit task-local configuration; environment loading belongs to Step 32."""

    web_service_key: str = field(repr=False)
    base_url: str = AMAP_BASE_URL
    timeout_seconds: float = AMAP_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if (
            not isinstance(self.web_service_key, str)
            or not self.web_service_key
            or self.web_service_key != self.web_service_key.strip()
            or "\n" in self.web_service_key
            or "\r" in self.web_service_key
            or len(self.web_service_key) > 4_096
        ):
            raise ValueError("amap_web_service_key_invalid")
        if self.base_url != AMAP_BASE_URL:
            raise ValueError("amap_base_url_unapproved")
        if self.timeout_seconds != AMAP_TIMEOUT_SECONDS:
            raise ValueError("amap_timeout_unapproved")


class AmapAdapter:
    """Amap city, POI and single-leg walking/transit implementation."""

    __slots__ = ("_clock", "_config", "_source_id_factory", "_transport")

    def __init__(
        self,
        config: AmapAdapterConfig,
        *,
        transport: httpx2.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        source_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._config = config
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._source_id_factory = source_id_factory

    async def resolve_city(
        self,
        request: CityResolutionRequest,
    ) -> ProviderResult[CityResolution]:
        if not _valid_city_request(request):
            return _unavailable(ProviderErrorCategory.SCHEMA)

        value = await self._get_json(
            "/v3/geocode/geo",
            {
                "address": request.city_text,
                "city": request.city_text,
                "output": "JSON",
            },
        )
        if isinstance(value, ProviderErrorCategory):
            return _unavailable(value)
        parsed = _parse_city(value)
        if isinstance(parsed, ProviderErrorCategory):
            return _unavailable(parsed)
        return self._available(
            parsed,
            source_type="amap_geocode",
            warnings=("高德地理编码没有固定有效期。",),
        )

    async def search_pois(
        self,
        request: PoiSearchRequest,
    ) -> ProviderResult[PoiSearchResult]:
        if not _valid_poi_request(request):
            return _unavailable(ProviderErrorCategory.SCHEMA)

        params = {
            "region": request.city_adcode,
            "city_limit": "true",
            "page_size": str(request.limit),
            "page_num": "1",
            "output": "json",
        }
        if request.keywords:
            params["keywords"] = "|".join(request.keywords)
        if request.categories:
            params["types"] = "|".join(
                _CATEGORY_TYPECODES[category] for category in request.categories
            )

        value = await self._get_json("/v5/place/text", params)
        if isinstance(value, ProviderErrorCategory):
            return _unavailable(value)
        parsed = _parse_pois(value, request=request)
        if isinstance(parsed, ProviderErrorCategory):
            return _unavailable(parsed)
        result, ignored_invalid = parsed
        warnings = ["高德 POI 数据没有固定有效期。"]
        status = ProviderResultStatus.OK
        error = None
        if ignored_invalid:
            status = ProviderResultStatus.PARTIAL
            error = ProviderError(ProviderErrorCategory.SCHEMA)
            warnings.append("高德 POI 响应包含已忽略的无效或异城记录。")
        return self._available(
            result,
            source_type="amap_poi_search",
            warnings=tuple(warnings),
            status=status,
            error=error,
        )

    async def calculate_routes(
        self,
        request: RouteCalculationRequest,
    ) -> ProviderResult[RouteLeg]:
        params = _route_params(request)
        if params is None:
            return _unavailable(ProviderErrorCategory.SCHEMA)

        if request.mode is RouteMode.WALKING:
            path = "/v5/direction/walking"
            params.update(
                {
                    "alternative_route": "1",
                    "show_fields": "cost",
                    "isindoor": "0",
                    "output": "json",
                }
            )
            source_type = "amap_route_walking"
        else:
            path = "/v5/direction/transit/integrated"
            params.update(
                {
                    "city1": request.origin_citycode,
                    "city2": request.destination_citycode,
                    "strategy": "0",
                    "AlternativeRoute": "1",
                    "nightflag": "0",
                    "show_fields": "cost",
                    "output": "json",
                }
            )
            source_type = "amap_route_public_transit"

        value = await self._get_json(path, params)
        if isinstance(value, ProviderErrorCategory):
            return _unavailable(value)
        parsed = _parse_route(value, request=request)
        if isinstance(parsed, ProviderErrorCategory):
            return _unavailable(parsed)
        distance_meters, duration_minutes = parsed

        fetched_at = self._clock()
        source_id = self._source_id_factory()
        source = SourceRecord(
            source_id=source_id,
            provider=Provider.AMAP,
            source_type=source_type,
            fetched_at=fetched_at,
            valid_until=None,
        )
        route = RouteLeg(
            request.origin_location_id,
            request.destination_location_id,
            request.mode,
            distance_meters,
            duration_minutes,
            (source_id,),
        )
        return ProviderResult(
            ProviderResultStatus.OK,
            Provider.AMAP,
            route,
            fetched_at,
            None,
            ("高德路线结果没有固定有效期。",),
            None,
            (source,),
        )

    async def _get_json(
        self,
        path: str,
        params: dict[str, str],
    ) -> dict[str, object] | ProviderErrorCategory:
        query = {"key": self._config.web_service_key, **params}
        try:
            async with httpx2.AsyncClient(
                base_url=self._config.base_url,
                headers={"Accept": "application/json"},
                timeout=self._config.timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                transport=self._transport,
            ) as client:
                response = await client.get(path, params=query)
        except httpx2.TimeoutException:
            return ProviderErrorCategory.TIMEOUT
        except httpx2.RequestError:
            return ProviderErrorCategory.UNKNOWN

        http_error = _http_error_category(response.status_code)
        if http_error is not None:
            return http_error
        if len(response.content) > MAX_RESPONSE_BYTES:
            return ProviderErrorCategory.SCHEMA
        try:
            value = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return ProviderErrorCategory.SCHEMA
        if not isinstance(value, dict):
            return ProviderErrorCategory.SCHEMA

        business_error = _business_error_category(value)
        if business_error is not None:
            return business_error
        return value

    def _available[T](
        self,
        data: T,
        *,
        source_type: str,
        warnings: tuple[str, ...],
        status: ProviderResultStatus = ProviderResultStatus.OK,
        error: ProviderError | None = None,
    ) -> ProviderResult[T]:
        fetched_at = self._clock()
        source = SourceRecord(
            source_id=self._source_id_factory(),
            provider=Provider.AMAP,
            source_type=source_type,
            fetched_at=fetched_at,
            valid_until=None,
        )
        return ProviderResult(
            status,
            Provider.AMAP,
            data,
            fetched_at,
            None,
            warnings,
            error,
            (source,),
        )


def _valid_city_request(request: object) -> bool:
    if not isinstance(request, CityResolutionRequest):
        return False
    return _valid_text(request.city_text, max_length=40, allow_pipe=False)


def _valid_poi_request(request: object) -> bool:
    if not isinstance(request, PoiSearchRequest):
        return False
    if _ADCODE.fullmatch(request.city_adcode) is None:
        return False
    if (
        not isinstance(request.limit, int)
        or isinstance(request.limit, bool)
        or not 1 <= request.limit <= 25
    ):
        return False
    if not isinstance(request.keywords, tuple) or not isinstance(request.categories, tuple):
        return False
    if not request.keywords and not request.categories:
        return False
    if any(not _valid_text(value, max_length=80, allow_pipe=False) for value in request.keywords):
        return False
    if len("|".join(request.keywords)) > 80:
        return False
    if any(category not in _CATEGORY_TYPECODES for category in request.categories):
        return False
    return len(set(request.keywords)) == len(request.keywords) and len(
        set(request.categories)
    ) == len(request.categories)


def _valid_text(value: object, *, max_length: int, allow_pipe: bool) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= max_length
        and _CONTROL.search(value) is None
        and (allow_pipe or "|" not in value)
    )


def _route_params(request: object) -> dict[str, str] | None:
    if not isinstance(request, RouteCalculationRequest):
        return None
    if (
        not isinstance(request.origin_location_id, UUID)
        or not isinstance(request.destination_location_id, UUID)
        or request.origin_location_id == request.destination_location_id
        or not isinstance(request.origin, Coordinates)
        or not isinstance(request.destination, Coordinates)
        or request.origin.coordinate_system is not CoordinateSystem.PROVIDER_NATIVE
        or request.destination.coordinate_system is not CoordinateSystem.PROVIDER_NATIVE
        or not isinstance(request.origin_citycode, str)
        or _CITYCODE.fullmatch(request.origin_citycode) is None
        or not isinstance(request.destination_citycode, str)
        or _CITYCODE.fullmatch(request.destination_citycode) is None
        or request.mode not in {RouteMode.WALKING, RouteMode.PUBLIC_TRANSIT}
    ):
        return None
    origin = _coordinate_param(request.origin)
    destination = _coordinate_param(request.destination)
    if origin is None or destination is None:
        return None
    return {"origin": origin, "destination": destination}


def _coordinate_param(coordinates: Coordinates) -> str | None:
    values = (coordinates.longitude, coordinates.latitude)
    for value in values:
        exponent = value.as_tuple().exponent
        if not isinstance(exponent, int) or exponent < -6:
            return None
    return f"{format(coordinates.longitude, 'f')},{format(coordinates.latitude, 'f')}"


def _parse_city(value: dict[str, object]) -> CityResolution | ProviderErrorCategory:
    count = _count(value.get("count"))
    geocodes = value.get("geocodes")
    if count is None or not isinstance(geocodes, list) or count != len(geocodes):
        return ProviderErrorCategory.SCHEMA
    if count == 0:
        return ProviderErrorCategory.EMPTY_RESULT
    if count != 1 or not isinstance(geocodes[0], dict):
        return ProviderErrorCategory.SCHEMA

    item = geocodes[0]
    adcode = item.get("adcode")
    level = item.get("level")
    province = item.get("province")
    citycode = item.get("citycode")
    city_valid, city = _optional_text(item.get("city"))
    if (
        not isinstance(adcode, str)
        or _ADCODE.fullmatch(adcode) is None
        or not isinstance(level, str)
        or not isinstance(province, str)
        or not province.strip()
        or not isinstance(citycode, str)
        or _CITYCODE.fullmatch(citycode) is None
        or not city_valid
    ):
        return ProviderErrorCategory.SCHEMA

    if level == "市" and adcode.endswith("00") and city is not None:
        city_name = city
    elif (
        level == "省"
        and province in _DIRECT_MUNICIPALITIES
        and adcode.endswith("0000")
        and city is None
    ):
        city_name = province
    else:
        return ProviderErrorCategory.SCHEMA

    coordinates_valid, center = _optional_coordinates(item.get("location"))
    if not coordinates_valid:
        return ProviderErrorCategory.SCHEMA
    return CityResolution(city_name, adcode, citycode, center)


def _parse_pois(
    value: dict[str, object],
    *,
    request: PoiSearchRequest,
) -> tuple[PoiSearchResult, bool] | ProviderErrorCategory:
    count = _count(value.get("count"))
    pois = value.get("pois")
    if count is None or not isinstance(pois, list) or count != len(pois) or count > request.limit:
        return ProviderErrorCategory.SCHEMA
    if count == 0:
        return ProviderErrorCategory.EMPTY_RESULT

    candidates: list[PoiCandidate] = []
    provider_ids: set[str] = set()
    ignored_invalid = False
    for value_item in pois:
        parsed = _parse_poi(value_item, request=request)
        if parsed is None:
            ignored_invalid = True
            continue
        provider_id, candidate = parsed
        if provider_id in provider_ids:
            ignored_invalid = True
            continue
        provider_ids.add(provider_id)
        candidates.append(candidate)

    if not candidates:
        return ProviderErrorCategory.SCHEMA
    return PoiSearchResult(tuple(candidates)), ignored_invalid


def _parse_route(
    value: dict[str, object],
    *,
    request: RouteCalculationRequest,
) -> tuple[int, int] | ProviderErrorCategory:
    count = _count(value.get("count"))
    if count is None:
        return ProviderErrorCategory.SCHEMA
    if count == 0:
        return ProviderErrorCategory.EMPTY_RESULT
    route = value.get("route")
    if count != 1 or not isinstance(route, dict):
        return ProviderErrorCategory.SCHEMA

    origin_valid, origin = _optional_coordinates(route.get("origin"))
    destination_valid, destination = _optional_coordinates(route.get("destination"))
    if (
        not origin_valid
        or origin is None
        or not destination_valid
        or destination is None
        or origin != request.origin
        or destination != request.destination
    ):
        return ProviderErrorCategory.SCHEMA

    collection_name = "paths" if request.mode is RouteMode.WALKING else "transits"
    options = route.get(collection_name)
    if not isinstance(options, list) or len(options) != 1 or not isinstance(options[0], dict):
        return ProviderErrorCategory.SCHEMA
    option = options[0]
    distance = _nonnegative_integer(option.get("distance"))
    cost = option.get("cost")
    if distance is None or not isinstance(cost, dict):
        return ProviderErrorCategory.SCHEMA
    duration_seconds = _positive_integer(cost.get("duration"))
    if duration_seconds is None:
        return ProviderErrorCategory.SCHEMA
    duration_minutes = (duration_seconds + 59) // 60
    if distance > MAX_ROUTE_DISTANCE_METERS or duration_minutes > MAX_ROUTE_DURATION_MINUTES:
        return ProviderErrorCategory.SCHEMA
    return distance, duration_minutes


def _parse_poi(
    value: object,
    *,
    request: PoiSearchRequest,
) -> tuple[str, PoiCandidate] | None:
    if not isinstance(value, dict):
        return None
    provider_id = value.get("id")
    name = value.get("name")
    type_name = value.get("type")
    typecode = value.get("typecode")
    adcode = value.get("adcode")
    if (
        not isinstance(provider_id, str)
        or not _valid_text(provider_id, max_length=128, allow_pipe=False)
        or not isinstance(name, str)
        or not _valid_text(name, max_length=200, allow_pipe=True)
        or not _valid_text(type_name, max_length=200, allow_pipe=True)
        or not isinstance(typecode, str)
        or _TYPECODE.fullmatch(typecode) is None
        or not isinstance(adcode, str)
        or _ADCODE.fullmatch(adcode) is None
        or not _adcode_contains(request.city_adcode, adcode)
    ):
        return None

    category = next(
        (
            requested
            for requested in request.categories
            if typecode.startswith(_CATEGORY_PREFIXES[requested])
        ),
        None,
    )
    if request.categories and category is None:
        return None
    if category is None:
        category = "poi"

    address_valid, address = _optional_text(value.get("address"))
    coordinates_valid, coordinates = _optional_coordinates(value.get("location"))
    if not address_valid or not coordinates_valid:
        return None

    candidate = PoiCandidate(
        uuid5(AMAP_POI_NAMESPACE, provider_id),
        name,
        category,
        request.city_adcode,
        address,
        coordinates,
    )
    return provider_id, candidate


def _optional_text(value: object) -> tuple[bool, str | None]:
    if isinstance(value, str):
        if value and value == value.strip() and _CONTROL.search(value) is None:
            return True, value
        return False, None
    if value == []:
        return True, None
    return False, None


def _optional_coordinates(value: object) -> tuple[bool, Coordinates | None]:
    if value == []:
        return True, None
    if not isinstance(value, str) or value != value.strip():
        return False, None
    parts = value.split(",")
    if len(parts) != 2:
        return False, None
    try:
        coordinates = Coordinates(
            Decimal(parts[0]),
            Decimal(parts[1]),
            CoordinateSystem.PROVIDER_NATIVE,
        )
    except (InvalidOperation, ValueError):
        return False, None
    return True, coordinates


def _adcode_contains(city_adcode: str, poi_adcode: str) -> bool:
    if city_adcode.endswith("0000"):
        return poi_adcode[:2] == city_adcode[:2]
    if city_adcode.endswith("00"):
        return poi_adcode[:4] == city_adcode[:4]
    return poi_adcode == city_adcode


def _count(value: object) -> int | None:
    if (
        not isinstance(value, str)
        or len(value) > MAX_INTEGER_DIGITS
        or not value.isascii()
        or not value.isdigit()
    ):
        return None
    return int(value)


def _nonnegative_integer(value: object) -> int | None:
    if (
        not isinstance(value, str)
        or len(value) > MAX_INTEGER_DIGITS
        or not value.isascii()
        or not value.isdigit()
    ):
        return None
    return int(value)


def _positive_integer(value: object) -> int | None:
    parsed = _nonnegative_integer(value)
    return parsed if parsed is not None and parsed > 0 else None


def _business_error_category(value: dict[str, object]) -> ProviderErrorCategory | None:
    status = value.get("status")
    info = value.get("info")
    infocode = value.get("infocode")
    if not isinstance(info, str) or not isinstance(infocode, str):
        return ProviderErrorCategory.SCHEMA
    if status == "1":
        return None if infocode == "10000" else ProviderErrorCategory.SCHEMA
    if status != "0":
        return ProviderErrorCategory.SCHEMA
    if infocode in _AUTH_INFOCODES:
        return ProviderErrorCategory.AUTH
    if infocode in _RATE_LIMIT_INFOCODES:
        return ProviderErrorCategory.RATE_LIMITED
    if infocode in _SERVER_INFOCODES or infocode.startswith("3"):
        return ProviderErrorCategory.SERVER
    if infocode in _SCHEMA_INFOCODES:
        return ProviderErrorCategory.SCHEMA
    if infocode in _EMPTY_INFOCODES:
        return ProviderErrorCategory.EMPTY_RESULT
    return ProviderErrorCategory.UNKNOWN


def _http_error_category(status_code: int) -> ProviderErrorCategory | None:
    if status_code == 200:
        return None
    if status_code in {400, 422}:
        return ProviderErrorCategory.SCHEMA
    if status_code in {401, 402, 403}:
        return ProviderErrorCategory.AUTH
    if status_code == 429:
        return ProviderErrorCategory.RATE_LIMITED
    if 500 <= status_code <= 599:
        return ProviderErrorCategory.SERVER
    return ProviderErrorCategory.UNKNOWN


def _unavailable[T](category: ProviderErrorCategory) -> ProviderResult[T]:
    return ProviderResult(
        ProviderResultStatus.UNAVAILABLE,
        Provider.AMAP,
        None,
        None,
        None,
        (),
        ProviderError(category),
        (),
    )
