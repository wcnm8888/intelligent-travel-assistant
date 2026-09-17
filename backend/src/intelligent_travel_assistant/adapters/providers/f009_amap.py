"""F-009 projection over the existing allowlisted Amap Web Service transport."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Final, TypeGuard
from uuid import uuid5

from intelligent_travel_assistant.adapters.providers.amap import (
    AMAP_POI_NAMESPACE,
    AmapAdapter,
)
from intelligent_travel_assistant.application.f009 import (
    F009CityFact,
    F009MapPinFact,
    F009PoiQuery,
    F009ProviderFailure,
    F009ProviderFailureKind,
    F009ProviderOutcome,
    F009RouteFact,
    F009RouteQuery,
)
from intelligent_travel_assistant.application.ports import CityResolutionRequest
from intelligent_travel_assistant.contracts.f009 import (
    Gcj02Point,
    PoiConfirmationStatus,
    PoiOption,
    PoiPurpose,
    PoiScopeKind,
)
from intelligent_travel_assistant.domain import ProviderError, ProviderErrorCategory

_CATEGORY_TYPES: Final = {
    "hotel": "100000",
    "scenic_area": "110000",
    "historic_site": "110200",
    "museum": "140100",
    "culture": "140000",
    "leisure": "080000",
    "shopping": "060000",
    "food": "050000",
}
_CATEGORY_PREFIXES: Final = {
    "hotel": ("10",),
    "scenic_area": ("11",),
    "historic_site": ("1102",),
    "museum": ("1401",),
    "culture": ("14",),
    "leisure": ("08",),
    "shopping": ("06",),
    "food": ("05",),
}
_DEFAULT_VISIT_CATEGORIES: Final = (
    "scenic_area",
    "museum",
    "culture",
    "leisure",
    "shopping",
    "food",
)


class F009AmapProvider:
    """Return only validated, provider-neutral F-009 facts."""

    __slots__ = ("_adapter",)

    def __init__(self, adapter: AmapAdapter) -> None:
        self._adapter = adapter

    async def resolve_city(self, city: str) -> F009ProviderOutcome[F009CityFact]:
        result = await self._adapter.resolve_city(CityResolutionRequest(city))
        if result.data is None:
            return _failure(result.error)
        center = None
        if result.data.center is not None:
            center = Gcj02Point(
                longitude=float(result.data.center.longitude),
                latitude=float(result.data.center.latitude),
            )
        return F009ProviderOutcome(
            F009CityFact(
                city_name=result.data.city_name,
                city_adcode=result.data.adcode,
                citycode=result.data.citycode,
                center=center,
            )
        )

    async def search_pois(self, query: F009PoiQuery) -> F009ProviderOutcome[tuple[PoiOption, ...]]:
        categories = query.category_codes or (
            ("hotel",) if query.purpose is PoiPurpose.ACCOMMODATION else _DEFAULT_VISIT_CATEGORIES
        )
        if any(category not in _CATEGORY_TYPES for category in categories):
            return _schema_failure()
        expected_prefixes = tuple(
            prefix for category in categories for prefix in _CATEGORY_PREFIXES[category]
        )
        region = query.district_adcode or query.city_adcode
        params = {
            "keywords": query.keywords,
            "types": "|".join(_CATEGORY_TYPES[category] for category in categories),
            "region": region,
            "city_limit": "true",
            "page_size": str(query.page_size),
            "page_num": str(query.page),
            "output": "json",
        }
        path = "/v5/place/text"
        if query.center is not None and query.radius_m is not None:
            path = "/v5/place/around"
            params["location"] = _coordinate(query.center)
            params["radius"] = str(query.radius_m)
        value = await self._adapter._get_json(path, params)  # noqa: SLF001
        if isinstance(value, ProviderError):
            return _failure(value)
        pois = value.get("pois")
        if not isinstance(pois, list):
            return _schema_failure()
        if not pois:
            return _empty_failure()

        items: list[PoiOption] = []
        provider_ids: set[str] = set()
        for raw in pois:
            item = _parse_poi(
                raw,
                query=query,
                expected_prefixes=expected_prefixes,
            )
            if item is None or item.provider_place_id in provider_ids:
                continue
            provider_ids.add(item.provider_place_id)
            items.append(item)
        if not items:
            return _schema_failure()
        return F009ProviderOutcome(tuple(items))

    async def reverse_geocode(self, coordinate: Gcj02Point) -> F009ProviderOutcome[F009MapPinFact]:
        value = await self._adapter._get_json(  # noqa: SLF001
            "/v3/geocode/regeo",
            {
                "location": _coordinate(coordinate),
                "extensions": "base",
                "output": "json",
            },
        )
        if isinstance(value, ProviderError):
            return _failure(value)
        regeocode = value.get("regeocode")
        if not isinstance(regeocode, dict):
            return _schema_failure()
        address = regeocode.get("formatted_address")
        component = regeocode.get("addressComponent")
        if not isinstance(address, str) or not address.strip() or not isinstance(component, dict):
            return _schema_failure()
        adcode = component.get("adcode")
        citycode = component.get("citycode")
        if not _adcode(adcode) or not isinstance(citycode, str):
            return _schema_failure()
        city_adcode = _city_adcode(adcode)
        return F009ProviderOutcome(F009MapPinFact(address.strip(), city_adcode, adcode, coordinate))

    async def calculate_route(self, query: F009RouteQuery) -> F009ProviderOutcome[F009RouteFact]:
        params = {
            "origin": _coordinate(query.origin),
            "destination": _coordinate(query.destination),
            "show_fields": "cost,polyline",
            "output": "json",
        }
        if query.mode.value == "walking":
            path = "/v5/direction/walking"
            params.update({"alternative_route": "1", "isindoor": "0"})
            collection = "paths"
        else:
            path = "/v5/direction/transit/integrated"
            params.update(
                {
                    "city1": query.origin_citycode,
                    "city2": query.destination_citycode,
                    "strategy": "0",
                    "AlternativeRoute": "1",
                    "nightflag": "0",
                }
            )
            collection = "transits"
        value = await self._adapter._get_json(path, params)  # noqa: SLF001
        if isinstance(value, ProviderError):
            return _failure(value)
        route = value.get("route")
        count = value.get("count")
        if count == "0":
            return _empty_failure()
        if not isinstance(route, dict):
            return _schema_failure()
        options = route.get(collection)
        if not isinstance(options, list) or not options or not isinstance(options[0], dict):
            return _schema_failure()
        option = options[0]
        distance = _positive_int(option.get("distance"))
        cost = option.get("cost")
        duration_seconds = _positive_int(cost.get("duration")) if isinstance(cost, dict) else None
        points = _collect_polyline(option)
        if distance is None or duration_seconds is None or len(points) < 2:
            return _schema_failure()
        return F009ProviderOutcome(
            F009RouteFact(
                distance_meters=distance,
                duration_minutes=(duration_seconds + 59) // 60,
                points=points,
            )
        )


def _parse_poi(
    raw: object,
    *,
    query: F009PoiQuery,
    expected_prefixes: tuple[str, ...],
) -> PoiOption | None:
    if not isinstance(raw, dict):
        return None
    provider_id = raw.get("id")
    name = raw.get("name")
    typecode = raw.get("typecode")
    district_adcode = raw.get("adcode")
    location = _point(raw.get("location"))
    if (
        not isinstance(provider_id, str)
        or not provider_id.strip()
        or not isinstance(name, str)
        or not name.strip()
        or not isinstance(typecode, str)
        or len(typecode) != 6
        or not typecode.isdigit()
        or not _adcode(district_adcode)
        or not _contains(query.city_adcode, district_adcode)
        or query.district_adcode is not None
        and district_adcode != query.district_adcode
        or not typecode.startswith(expected_prefixes)
        or location is None
    ):
        return None
    category_code = next(
        (
            category
            for category, prefixes in _CATEGORY_PREFIXES.items()
            if typecode.startswith(prefixes)
            and category in (query.category_codes or _CATEGORY_TYPES)
        ),
        None,
    )
    if category_code is None:
        return None
    purpose = PoiPurpose.ACCOMMODATION if typecode.startswith("10") else PoiPurpose.VISIT
    if purpose is not query.purpose:
        return None
    address = raw.get("address")
    normalized_address = address.strip() if isinstance(address, str) and address.strip() else None
    semantic_area = typecode == "110000"
    return PoiOption(
        location_id=uuid5(AMAP_POI_NAMESPACE, provider_id),
        provider_place_id=provider_id,
        name=name.strip(),
        address=normalized_address,
        city_adcode=query.city_adcode,
        district_adcode=district_adcode,
        category_code=category_code,
        category_label=_category_label(category_code),
        coordinate_gcj02=location,
        purpose=purpose,
        scope_kind=PoiScopeKind.COMPLEX if semantic_area else PoiScopeKind.POINT,
        confirmation_status=(
            PoiConfirmationStatus.REPRESENTATIVE_REQUIRED
            if semantic_area
            else PoiConfirmationStatus.VERIFIED
        ),
    )


def _collect_polyline(value: object) -> tuple[Gcj02Point, ...]:
    found: list[Gcj02Point] = []

    def visit(node: object) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if key == "polyline" and isinstance(child, str):
                    for raw_point in _polyline_points(child):
                        point = _point(raw_point)
                        if point is not None and (not found or point != found[-1]):
                            found.append(point)
                elif key not in {"instruction", "road_name", "action", "assistant_action"}:
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return tuple(found)


def _polyline_points(value: str) -> tuple[str, ...]:
    semicolon_points = tuple(part for part in value.split(";") if part)
    if len(semicolon_points) > 1:
        return semicolon_points
    values = value.split(",")
    if len(values) > 2 and len(values) % 2 == 0:
        return tuple(",".join(values[index : index + 2]) for index in range(0, len(values), 2))
    return semicolon_points


def _point(value: object) -> Gcj02Point | None:
    if not isinstance(value, str):
        return None
    parts = value.split(",")
    if len(parts) != 2:
        return None
    try:
        return Gcj02Point(longitude=float(Decimal(parts[0])), latitude=float(Decimal(parts[1])))
    except (InvalidOperation, ValueError):
        return None


def _coordinate(point: Gcj02Point) -> str:
    return f"{point.longitude:.6f},{point.latitude:.6f}"


def _positive_int(value: object) -> int | None:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        return None
    parsed = int(value)
    return parsed if 0 < parsed <= 10_000_000 else None


def _adcode(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and len(value) == 6 and value.isdigit()


def _city_adcode(district_adcode: str) -> str:
    if district_adcode[:2] in {"11", "12", "31", "50"}:
        return f"{district_adcode[:2]}0000"
    return f"{district_adcode[:4]}00"


def _contains(city_adcode: str, district_adcode: str) -> bool:
    if city_adcode.endswith("0000"):
        return city_adcode[:2] == district_adcode[:2]
    return city_adcode[:4] == district_adcode[:4]


def _category_label(category: str) -> str:
    return {
        "hotel": "住宿服务",
        "scenic_area": "风景名胜",
        "historic_site": "历史遗址",
        "museum": "博物馆",
        "culture": "科教文化",
        "leisure": "体育休闲",
        "shopping": "购物服务",
        "food": "餐饮服务",
    }[category]


def _failure[T](error: ProviderError | None) -> F009ProviderOutcome[T]:
    category = error.category if error is not None else ProviderErrorCategory.UNKNOWN
    kind = {
        ProviderErrorCategory.AUTH: F009ProviderFailureKind.AUTH,
        ProviderErrorCategory.RATE_LIMITED: F009ProviderFailureKind.RATE_LIMITED,
        ProviderErrorCategory.TIMEOUT: F009ProviderFailureKind.TIMEOUT,
        ProviderErrorCategory.SERVER: F009ProviderFailureKind.SERVER,
        ProviderErrorCategory.SCHEMA: F009ProviderFailureKind.SCHEMA,
        ProviderErrorCategory.EMPTY_RESULT: F009ProviderFailureKind.EMPTY_RESULT,
        ProviderErrorCategory.UNKNOWN: F009ProviderFailureKind.UNKNOWN,
    }[category]
    return F009ProviderOutcome(
        None,
        F009ProviderFailure(
            kind,
            retryable=kind
            in {
                F009ProviderFailureKind.RATE_LIMITED,
                F009ProviderFailureKind.TIMEOUT,
                F009ProviderFailureKind.SERVER,
            },
        ),
    )


def _schema_failure[T]() -> F009ProviderOutcome[T]:
    return F009ProviderOutcome(None, F009ProviderFailure(F009ProviderFailureKind.SCHEMA))


def _empty_failure[T]() -> F009ProviderOutcome[T]:
    return F009ProviderOutcome(None, F009ProviderFailure(F009ProviderFailureKind.EMPTY_RESULT))
