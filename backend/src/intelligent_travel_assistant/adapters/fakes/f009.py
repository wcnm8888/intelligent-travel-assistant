"""Deterministic Hangzhou F-009 facts for offline browser acceptance only."""

from __future__ import annotations

from uuid import UUID

from intelligent_travel_assistant.application.f009 import (
    F009CityFact,
    F009MapPinFact,
    F009Narrative,
    F009NarrativeDay,
    F009NarrativeRequest,
    F009PoiQuery,
    F009ProviderFailure,
    F009ProviderFailureKind,
    F009ProviderOutcome,
    F009RouteFact,
    F009RouteQuery,
    F014AdvisorDraft,
    F014AdvisorRequest,
)
from intelligent_travel_assistant.application.f009.solver import haversine_meters
from intelligent_travel_assistant.contracts.f009 import (
    Gcj02Point,
    PoiConfirmationStatus,
    PoiOption,
    PoiPurpose,
    PoiScopeKind,
)


def _id(value: int) -> UUID:
    return UUID(f"91000000-0000-4000-8000-{value:012d}")


SYNTHETIC_F009_POIS = (
    PoiOption(
        location_id=_id(1),
        provider_place_id="synthetic-lodging-longxiangqiao",
        name="龙翔桥住宿代表锚点（synthetic）",
        address="杭州市上城区湖滨",
        city_adcode="330100",
        district_adcode="330102",
        category_code="hotel",
        category_label="住宿服务",
        coordinate_gcj02=Gcj02Point(longitude=120.1647, latitude=30.2552),
        purpose=PoiPurpose.ACCOMMODATION,
        scope_kind=PoiScopeKind.POINT,
        confirmation_status=PoiConfirmationStatus.VERIFIED,
    ),
    PoiOption(
        location_id=_id(2),
        provider_place_id="synthetic-west-lake-area",
        name="西湖风景名胜区（synthetic）",
        address="杭州市西湖区",
        city_adcode="330100",
        district_adcode="330106",
        category_code="scenic_area",
        category_label="风景名胜",
        coordinate_gcj02=Gcj02Point(longitude=120.1487, latitude=30.2429),
        purpose=PoiPurpose.VISIT,
        scope_kind=PoiScopeKind.COMPLEX,
        confirmation_status=PoiConfirmationStatus.REPRESENTATIVE_REQUIRED,
    ),
    PoiOption(
        location_id=_id(3),
        provider_place_id="synthetic-west-lake-anchor",
        name="断桥残雪入口（synthetic）",
        address="杭州市西湖区北山街",
        city_adcode="330100",
        district_adcode="330106",
        category_code="scenic_area",
        category_label="风景名胜",
        coordinate_gcj02=Gcj02Point(longitude=120.1518, latitude=30.259),
        purpose=PoiPurpose.VISIT,
    ),
    PoiOption(
        location_id=_id(4),
        provider_place_id="synthetic-lingyin",
        name="灵隐寺（synthetic）",
        address="杭州市西湖区灵隐路",
        city_adcode="330100",
        district_adcode="330106",
        category_code="historic_site",
        category_label="历史遗址",
        coordinate_gcj02=Gcj02Point(longitude=120.1022, latitude=30.2408),
        purpose=PoiPurpose.VISIT,
    ),
    PoiOption(
        location_id=_id(5),
        provider_place_id="synthetic-feilai",
        name="飞来峰（synthetic）",
        address="杭州市西湖区灵隐路",
        city_adcode="330100",
        district_adcode="330106",
        category_code="scenic_area",
        category_label="风景名胜",
        coordinate_gcj02=Gcj02Point(longitude=120.105, latitude=30.2395),
        purpose=PoiPurpose.VISIT,
    ),
    PoiOption(
        location_id=_id(6),
        provider_place_id="synthetic-hefang",
        name="河坊街（synthetic）",
        address="杭州市上城区",
        city_adcode="330100",
        district_adcode="330102",
        category_code="shopping",
        category_label="购物服务",
        coordinate_gcj02=Gcj02Point(longitude=120.176, latitude=30.238),
        purpose=PoiPurpose.VISIT,
    ),
    PoiOption(
        location_id=_id(7),
        provider_place_id="synthetic-southern-song",
        name="南宋御街（synthetic）",
        address="杭州市上城区",
        city_adcode="330100",
        district_adcode="330102",
        category_code="shopping",
        category_label="购物服务",
        coordinate_gcj02=Gcj02Point(longitude=120.1715, latitude=30.2405),
        purpose=PoiPurpose.VISIT,
    ),
)


class SyntheticF009MapProvider:
    """Never performs I/O; synthetic values are visibly labelled."""

    async def resolve_city(self, city: str) -> F009ProviderOutcome[F009CityFact]:
        if city not in {"杭州", "杭州市"}:
            return F009ProviderOutcome(
                None,
                F009ProviderFailure(F009ProviderFailureKind.EMPTY_RESULT),
            )
        return F009ProviderOutcome(
            F009CityFact(
                "杭州市",
                "330100",
                "0571",
                Gcj02Point(longitude=120.1551, latitude=30.2741),
            )
        )

    async def search_pois(self, query: F009PoiQuery) -> F009ProviderOutcome[tuple[PoiOption, ...]]:
        if query.purpose is PoiPurpose.VISIT and "入口" in query.keywords:
            items = tuple(item for item in SYNTHETIC_F009_POIS if item.location_id == _id(3))
        else:
            items = tuple(
                item
                for item in SYNTHETIC_F009_POIS
                if item.purpose is query.purpose
                and (
                    query.keywords.lower() in item.name.lower()
                    or query.keywords in {"杭州景点", "景点", "自然景点", "湖滨 龙翔桥", "湖滨"}
                    or any(token in item.name for token in query.keywords.split())
                )
            )
        if not items:
            return F009ProviderOutcome(
                None,
                F009ProviderFailure(F009ProviderFailureKind.EMPTY_RESULT),
            )
        start = (query.page - 1) * query.page_size
        return F009ProviderOutcome(items[start : start + query.page_size])

    async def reverse_geocode(self, coordinate: Gcj02Point) -> F009ProviderOutcome[F009MapPinFact]:
        return F009ProviderOutcome(
            F009MapPinFact("湖滨地图锚点（synthetic）", "330100", "330102", coordinate)
        )

    async def calculate_route(self, query: F009RouteQuery) -> F009ProviderOutcome[F009RouteFact]:
        straight = haversine_meters(query.origin, query.destination)
        distance = max(100, round(straight * (1.12 if query.mode.value == "walking" else 1.3)))
        speed = 75 if query.mode.value == "walking" else 320
        duration = max(2, (distance + speed - 1) // speed)
        midpoint = Gcj02Point(
            longitude=(query.origin.longitude + query.destination.longitude) / 2,
            latitude=(query.origin.latitude + query.destination.latitude) / 2,
        )
        return F009ProviderOutcome(
            F009RouteFact(distance, duration, (query.origin, midpoint, query.destination))
        )


class SyntheticF009NarrativeProvider:
    async def generate(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        return self._outcome(request)

    async def repair(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        return self._outcome(request)

    @staticmethod
    def _outcome(request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        return F009ProviderOutcome(
            F009Narrative(
                days=tuple(
                    F009NarrativeDay(
                        local_date=local_date,
                        location_ids=tuple(item[0] for item in locations),
                        pace_note="按冻结顺序游览，并为现场排队预留弹性（synthetic）。",
                        stop_narratives=tuple(
                            "到达后先核对现场公告与开放状态（synthetic）。" for _ in locations
                        ),
                        rationale="该说明只解释确定性排程，不改变地点或路线（synthetic）。",
                    )
                    for local_date, locations in request.days
                ),
                global_notes=("营业时间未核验（synthetic/offline）。",),
            )
        )


class SyntheticF014AdvisorProvider:
    """Deterministic advisor double for the five offline traveler scenarios."""

    async def generate(self, request: F014AdvisorRequest) -> F009ProviderOutcome[F014AdvisorDraft]:
        return self._outcome(request)

    async def repair(self, request: F014AdvisorRequest) -> F009ProviderOutcome[F014AdvisorDraft]:
        return self._outcome(request)

    @staticmethod
    def _outcome(request: F014AdvisorRequest) -> F009ProviderOutcome[F014AdvisorDraft]:
        message = request.user_message
        preferences: list[tuple[str, str]] = []
        if "老人" in message or "亲子" in message or "少走" in message:
            preferences.extend((("walking_tolerance", "low"), ("crowd_tolerance", "low")))
        if "晚起" in message:
            preferences.append(("day_start", "10:00"))
        if "美食" in message:
            preferences.append(("food_preferences", "本地菜,少排队"))
        if "预算" in message:
            preferences.append(("budget_flexibility", "fixed"))
        recommend = (
            request.recommendation_requested
            or "推荐" in message
            or "第一次" in message
            or "不知道" in message
        )
        candidate_indices = tuple(item[0] for item in request.candidates[:2]) if recommend else ()
        return F009ProviderOutcome(
            F014AdvisorDraft(
                role="curation" if candidate_indices else "interview",
                question=(
                    "先看看这些已验证景点；其他偏好可以以后再补充。"
                    if request.recommendation_requested
                    else "这些建议需要你确认；还要补充作息、步行或拥挤偏好吗？"
                ),
                preference_values=tuple(preferences),
                candidate_indices=candidate_indices,
                candidate_reasons=tuple(
                    "来自已验证候选，适合首次到访时比较取舍。" for _ in candidate_indices
                ),
            )
        )
