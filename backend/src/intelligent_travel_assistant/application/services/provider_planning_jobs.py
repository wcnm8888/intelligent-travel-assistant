"""Execute a stored planning job through provider ports and publish a safe result."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import AnyHttpUrl

from intelligent_travel_assistant.application.planning import (
    CandidateResolutionDiagnosticCode,
    CandidateResolutionErrorCode,
    FinalValidationIssue,
    FinalValidationIssueCode,
    FinalValidationSeverity,
)
from intelligent_travel_assistant.application.ports import (
    PlanCandidate,
    PoiCandidate,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJobRepository,
    PlanningJobResult,
)
from intelligent_travel_assistant.application.services.offline_planning import (
    OfflinePlanningOrchestrator,
    OfflinePlanningOutcome,
    OfflinePlanningRequest,
)
from intelligent_travel_assistant.contracts import (
    ApiError,
    ApiErrorCode,
    BudgetAssessment,
    BudgetSummary,
    ConstraintViolation,
    Coordinates,
    CoordinateSystem,
    CostCategory,
    CostConfidence,
    CostItem,
    DataFreshness,
    ItineraryItem,
    LocationRef,
    Money,
    PlanDay,
    PlanningStatus,
    ProviderName,
    ResolvedDestination,
    RouteLeg,
    RouteMode,
    SourceRecord,
    TransportMode,
    TripPlan,
    TripPlanRequest,
    Uncertainty,
    ViolationSeverity,
    WeatherAlert,
    WeatherSnapshot,
)
from intelligent_travel_assistant.domain import (
    BudgetCostItem,
    DailyAvailability,
    DomainInvariantError,
    ProviderResult,
    TripRequestInput,
    evaluate_freshness,
)
from intelligent_travel_assistant.domain import (
    CostCategory as DomainCostCategory,
)
from intelligent_travel_assistant.domain import (
    CostConfidence as DomainCostConfidence,
)
from intelligent_travel_assistant.domain import (
    Money as DomainMoney,
)
from intelligent_travel_assistant.domain import (
    RouteMode as DomainRouteMode,
)

_EVALUATION_GRACE = timedelta(seconds=91)

_ISSUE_MESSAGES = {
    FinalValidationIssueCode.SCHEDULE_CONFLICT: "活动时间与可用时间窗口冲突。",
    FinalValidationIssueCode.ROUTE_INCOMPLETE: "部分路线缺失，交通时间尚未完整验证。",
    FinalValidationIssueCode.ROUTE_RESULT_INVALID: "部分路线结果未通过确定性引用校验。",
    FinalValidationIssueCode.ROUTE_CONFLICT: "路线时长与当天活动安排存在冲突。",
    FinalValidationIssueCode.WEATHER_INCOMPLETE: "双日天气数据不完整。",
    FinalValidationIssueCode.BUDGET_INDETERMINATE: "存在未知费用，完整预算无法判定。",
    FinalValidationIssueCode.BUDGET_EXCEEDED: "已知费用超过用户总预算。",
    FinalValidationIssueCode.SOURCE_REFERENCE_INVALID: "计划中的来源引用未通过校验。",
    FinalValidationIssueCode.SOURCE_STALE: "部分外部数据已超过有效期。",
    FinalValidationIssueCode.SOURCE_VALIDITY_UNKNOWN: "部分外部数据未提供固定有效期。",
    FinalValidationIssueCode.PROVIDER_DEGRADED: "部分外部服务只返回了不完整数据。",
    FinalValidationIssueCode.HARD_CONSTRAINT_UNVERIFIED: "硬约束尚不能由确定性规则完全验证。",
}

_PROVIDER_ERROR_MESSAGES = {
    ApiErrorCode.PROVIDER_UNAUTHORIZED: "外部服务凭证未通过验证。",
    ApiErrorCode.PROVIDER_RATE_LIMITED: "外部服务当前达到调用限制。",
    ApiErrorCode.PROVIDER_TIMEOUT: "外部服务响应超时。",
    ApiErrorCode.PROVIDER_UNAVAILABLE: "外部服务当前不可用。",
    ApiErrorCode.PROVIDER_SCHEMA_INVALID: "外部服务返回了无法安全解析的数据。",
    ApiErrorCode.DATA_MISSING: "外部服务没有返回可用数据。",
}


class ProviderPlanningJobExecutor:
    """Bridge the HTTP job resource to the provider-neutral orchestrator."""

    __slots__ = ("_clock", "_orchestrator", "_repository")

    def __init__(
        self,
        repository: PlanningJobRepository,
        orchestrator: OfflinePlanningOrchestrator,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._orchestrator = orchestrator
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(self, job_id: UUID) -> None:
        job = await self._repository.get(job_id)
        if job.status is PlanningStatus.DRAFT:
            job = await self._repository.advance(
                job_id,
                PlanningStatus.NORMALIZING,
                expected_version=job.version,
            )
        started_at = self._now()
        try:
            request = _offline_request(job.request, job_id=job_id, evaluated_at=started_at)
        except DomainInvariantError as error:
            await self._repository.record_result(
                job_id,
                _needs_input_result(field=error.field),
                expected_version=job.version,
            )
            return
        except (TypeError, ValueError):
            await self._repository.record_result(
                job_id,
                _needs_input_result(),
                expected_version=job.version,
            )
            return

        async def observe(target: PlanningStatus) -> None:
            nonlocal job
            if target in {
                PlanningStatus.READY,
                PlanningStatus.PARTIAL,
                PlanningStatus.CONFLICT,
                PlanningStatus.NEEDS_INPUT,
                PlanningStatus.FAILED,
            }:
                return
            current = await self._repository.get(job_id)
            if current.status is target:
                job = current
                return
            job = await self._repository.advance(
                job_id,
                target,
                expected_version=current.version,
            )

        try:
            outcome = await self._orchestrator.plan(request, state_observer=observe)
            current = await self._repository.get(job_id)
            result = _planning_result(
                outcome,
                job.request,
                job_id=job_id,
                evaluated_at=request.evaluated_at,
            )
            await self._repository.record_result(
                job_id,
                result,
                expected_version=current.version,
            )
        except Exception:
            current = await self._repository.get(job_id)
            await self._repository.record_result(
                job_id,
                _internal_failure_result(),
                expected_version=current.version,
            )

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("executor_clock_invalid")
        return value


def _offline_request(
    request: TripPlanRequest,
    *,
    job_id: UUID,
    evaluated_at: datetime,
) -> OfflinePlanningRequest:
    end_date = request.start_date + timedelta(days=1)
    trip = TripRequestInput(
        city=request.city,
        start_date=request.start_date,
        end_date=end_date,
        travelers=request.travelers,
        interests=request.preferences.interests,
        free_text=request.preferences.free_text,
        evaluated_at=evaluated_at,
    )
    user_source_id = _id(job_id, "source:user")
    system_source_id = _id(job_id, "source:system")
    costs = (
        _request_cost(
            job_id,
            "accommodation",
            DomainCostCategory.ACCOMMODATION,
            request.accommodation.one_night_cost,
            user_source_id,
        ),
        _request_cost(
            job_id,
            "intercity",
            DomainCostCategory.INTERCITY_TRANSPORT,
            request.intercity_transport_cost,
            user_source_id,
        ),
        BudgetCostItem(
            _id(job_id, "cost:meal"),
            DomainCostCategory.MEAL,
            DomainCostConfidence.ESTIMATED,
            DomainMoney(
                (request.meal_budget_per_person_per_day.amount * request.travelers * 2).quantize(
                    Decimal("0.01")
                )
            ),
            (system_source_id,),
        ),
        BudgetCostItem(
            _id(job_id, "cost:ticket"),
            DomainCostCategory.TICKET,
            DomainCostConfidence.UNKNOWN,
            None,
        ),
    )
    route_mode = (
        DomainRouteMode.PUBLIC_TRANSIT
        if TransportMode.PUBLIC_TRANSIT in request.transport_modes
        else DomainRouteMode.WALKING
    )
    keywords = request.preferences.interests or ("景点",)
    return OfflinePlanningRequest(
        trip=trip,
        budget=DomainMoney(request.total_budget.amount),
        hard_constraints=request.preferences.hard_constraints,
        weather_location_id=None,
        poi_keywords=keywords,
        poi_categories=("scenic_area", "museum"),
        poi_limit=6,
        route_mode=route_mode,
        accommodation=None,
        day_windows=tuple(
            DailyAvailability(item.day_offset, item.start_time, item.end_time)
            for item in request.day_windows
        ),
        cost_items=costs,
        evaluated_at=evaluated_at + _EVALUATION_GRACE,
        accommodation_query=request.accommodation.area_or_poi,
        derive_local_transport_cost=True,
    )


def _request_cost(
    job_id: UUID,
    name: str,
    category: DomainCostCategory,
    value: Money | None,
    user_source_id: UUID,
) -> BudgetCostItem:
    if value is None:
        return BudgetCostItem(
            _id(job_id, f"cost:{name}"),
            category,
            DomainCostConfidence.UNKNOWN,
            None,
        )
    return BudgetCostItem(
        _id(job_id, f"cost:{name}"),
        category,
        DomainCostConfidence.USER_PROVIDED,
        DomainMoney(value.amount),
        (user_source_id,),
    )


def _candidate_diagnostic_code(
    outcome: OfflinePlanningOutcome,
) -> CandidateResolutionDiagnosticCode:
    if outcome.candidate_validation_stage is None or outcome.candidate_validation_code is None:
        return CandidateResolutionDiagnosticCode.LOCAL_VALIDATION_FAILED
    return CandidateResolutionDiagnosticCode.from_failure(
        outcome.candidate_validation_stage,
        outcome.candidate_validation_code,
        outcome.candidate_time_failure,
    )


def _planning_result(
    outcome: OfflinePlanningOutcome,
    request: TripPlanRequest,
    *,
    job_id: UUID,
    evaluated_at: datetime,
) -> PlanningJobResult:
    provider_results = _provider_results(outcome)
    sources = _sources(provider_results, job_id=job_id, evaluated_at=evaluated_at)
    errors = _provider_errors(provider_results)
    if outcome.candidate_resolution_error is CandidateResolutionErrorCode.MODEL_OUTPUT_INVALID:
        errors = tuple(
            item
            for item in errors
            if not (
                item.provider == "deepseek" and item.code is ApiErrorCode.PROVIDER_SCHEMA_INVALID
            )
        ) + (
            ApiError(
                code=ApiErrorCode.MODEL_OUTPUT_INVALID,
                message="AI 生成结果未通过本地确定性校验。",
                provider="deepseek",
                diagnostic_code=_candidate_diagnostic_code(outcome).value,
                retryable=False,
            ),
        )
    if outcome.status is PlanningStatus.FAILED or outcome.final_validation is None:
        if not errors:
            errors = (
                ApiError(
                    code=ApiErrorCode.DATA_MISSING,
                    message="没有足够的外部数据形成旅行计划。",
                    provider="amap" if outcome.accommodation is None else None,
                    retryable=False,
                ),
            )
        return PlanningJobResult(
            status=PlanningStatus.FAILED,
            resolved_destination=_destination(outcome),
            plan=None,
            violations=(),
            warnings=(),
            uncertainties=(),
            sources=sources,
            errors=errors,
            retryable=any(item.retryable for item in errors),
        )

    validation = outcome.final_validation
    violations, uncertainties = _issues(validation.issues)
    plan = _plan(outcome, request, job_id=job_id)
    warnings = (
        tuple(outcome.candidate_result.data.warnings)
        if (outcome.candidate_result is not None and outcome.candidate_result.data is not None)
        else ()
    )
    retryable = validation.status is PlanningStatus.PARTIAL and any(
        item.retryable for item in errors
    )
    return PlanningJobResult(
        status=validation.status,
        resolved_destination=_destination(outcome),
        plan=plan,
        violations=violations,
        warnings=warnings,
        uncertainties=uncertainties,
        sources=sources,
        errors=errors,
        retryable=retryable,
    )


def _destination(outcome: OfflinePlanningOutcome) -> ResolvedDestination | None:
    if outcome.city_result is None or outcome.city_result.data is None:
        return None
    city = outcome.city_result.data
    return ResolvedDestination(
        city_name=city.city_name,
        adcode=city.adcode,
        center=_coordinates(city.center),
        source_ids=_source_ids(outcome.city_result),
    )


def _plan(
    outcome: OfflinePlanningOutcome,
    request: TripPlanRequest,
    *,
    job_id: UUID,
) -> TripPlan:
    assert outcome.city_result is not None and outcome.city_result.data is not None
    assert outcome.poi_result is not None and outcome.poi_result.data is not None
    assert outcome.candidate_result is not None and outcome.candidate_result.data is not None
    assert outcome.accommodation is not None
    assert outcome.final_validation is not None
    candidate = outcome.candidate_result.data
    locations = _locations(outcome, candidate, job_id=job_id)
    weather_by_date = _weather(outcome)
    routes_by_day = _routes(outcome, job_id=job_id)
    days = tuple(
        PlanDay(
            local_date=day.local_date,
            accommodation_location_id=outcome.accommodation.location_id,
            activities=tuple(
                ItineraryItem(
                    item_id=_id(job_id, f"activity:{day_offset}:{index}:{item.location_id}"),
                    location_id=item.location_id,
                    title=item.title,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    source_ids=item.source_ids,
                )
                for index, item in enumerate(day.activities)
            ),
            routes=routes_by_day[day_offset],
            weather=weather_by_date.get(day.local_date),
        )
        for day_offset, day in enumerate(candidate.days)
    )
    budget = outcome.final_validation.budget
    return TripPlan(
        plan_id=_id(job_id, "plan"),
        city_adcode=outcome.city_result.data.adcode,
        start_date=request.start_date,
        end_date=request.start_date + timedelta(days=1),
        locations=locations,
        days=days,
        budget_summary=BudgetSummary(
            budget=Money(amount=budget.budget.amount),
            known_total=Money(amount=budget.known_total.amount),
            unknown_count=budget.unknown_count,
            assessment=BudgetAssessment(budget.assessment.value),
            cost_items=tuple(_cost_item(item, job_id=job_id) for item in budget.cost_items),
        ),
    )


def _locations(
    outcome: OfflinePlanningOutcome,
    candidate: PlanCandidate,
    *,
    job_id: UUID,
) -> tuple[LocationRef, ...]:
    assert outcome.poi_result is not None and outcome.poi_result.data is not None
    assert outcome.accommodation is not None
    selected = {item.location_id for day in candidate.days for item in day.activities}
    poi_sources = _source_ids(outcome.poi_result)
    accommodation_candidate = _accommodation_candidate(outcome)
    accommodation_sources = (
        _source_ids(outcome.accommodation_result)
        if outcome.accommodation_result is not None
        else (_id(job_id, "source:user"),)
    )
    locations = [
        LocationRef(
            location_id=outcome.accommodation.location_id,
            provider=ProviderName.AMAP,
            name=(
                accommodation_candidate.name
                if accommodation_candidate is not None
                else "用户住宿锚点"
            ),
            category="accommodation_anchor",
            address=(
                accommodation_candidate.address if accommodation_candidate is not None else None
            ),
            city_adcode=outcome.accommodation.city_adcode,
            coordinates=_coordinates(outcome.accommodation.coordinates),
            source_ids=accommodation_sources,
        )
    ]
    locations.extend(
        LocationRef(
            location_id=item.location_id,
            provider=ProviderName.AMAP,
            name=item.name,
            category=item.category,
            address=item.address,
            city_adcode=item.city_adcode,
            coordinates=_coordinates(item.coordinates),
            source_ids=poi_sources,
        )
        for item in outcome.poi_result.data.candidates
        if item.location_id in selected
    )
    return tuple(locations)


def _accommodation_candidate(outcome: OfflinePlanningOutcome) -> PoiCandidate | None:
    if outcome.accommodation_result is None or outcome.accommodation_result.data is None:
        return None
    assert outcome.accommodation is not None
    return next(
        (
            item
            for item in outcome.accommodation_result.data.candidates
            if item.location_id == outcome.accommodation.location_id
        ),
        None,
    )


def _routes(
    outcome: OfflinePlanningOutcome,
    *,
    job_id: UUID,
) -> tuple[tuple[RouteLeg, ...], tuple[RouteLeg, ...]]:
    grouped: list[list[RouteLeg]] = [[], []]
    for index, item in enumerate(outcome.route_enrichments):
        if item.request is None or item.result is None or item.result.data is None:
            continue
        route = item.result.data
        if (
            route.origin_location_id != item.expected.origin_location_id
            or route.destination_location_id != item.expected.destination_location_id
            or route.mode is not item.request.mode
        ):
            continue
        grouped[item.day_offset].append(
            RouteLeg(
                route_id=_id(job_id, f"route:{item.day_offset}:{index}"),
                origin_location_id=route.origin_location_id,
                destination_location_id=route.destination_location_id,
                mode=RouteMode(route.mode.value),
                distance_meters=route.distance_meters,
                duration_minutes=route.duration_minutes,
                source_ids=route.source_ids,
            )
        )
    return tuple(grouped[0]), tuple(grouped[1])


def _weather(outcome: OfflinePlanningOutcome) -> dict[object, WeatherSnapshot]:
    if outcome.weather_result is None or outcome.weather_result.data is None:
        return {}
    forecast_sources = _source_ids(outcome.weather_result)
    alert_sources = _source_ids(outcome.alert_result) if outcome.alert_result is not None else ()
    alerts: tuple[WeatherAlert, ...] = ()
    if outcome.alert_result is not None and outcome.alert_result.data is not None:
        alerts = tuple(
            WeatherAlert(
                alert_id=item.alert_id,
                title=item.title,
                severity=item.severity,
                issued_at=item.issued_at,
                description=item.description,
                source_ids=alert_sources,
            )
            for item in outcome.alert_result.data.alerts
        )
    return {
        day.forecast_date: WeatherSnapshot(
            forecast_date=day.forecast_date,
            location_id=outcome.weather_result.data.location_id,
            condition_day=day.condition_day,
            condition_night=day.condition_night,
            temperature_min_celsius=day.temperature_min_celsius,
            temperature_max_celsius=day.temperature_max_celsius,
            alerts=alerts,
            source_ids=forecast_sources,
        )
        for day in outcome.weather_result.data.days
    }


def _cost_item(item: BudgetCostItem, *, job_id: UUID) -> CostItem:
    descriptions = {
        DomainCostCategory.ACCOMMODATION: "用户提供的一晚住宿费用"
        if item.amount
        else "住宿费用未知",
        DomainCostCategory.INTERCITY_TRANSPORT: "用户提供的城际交通费用"
        if item.amount
        else "城际交通费用未知",
        DomainCostCategory.LOCAL_TRANSPORT: "按每人每段 10 元计算的市内公交估算"
        if item.amount and item.amount.amount
        else "步行路线按 0 元计算",
        DomainCostCategory.TICKET: "门票费用缺少可靠来源",
        DomainCostCategory.MEAL: "按用户每日餐饮预算计算的两日估算",
        DomainCostCategory.OTHER: "其他费用",
    }
    source_ids = item.source_ids
    if item.confidence is DomainCostConfidence.ESTIMATED and not source_ids:
        source_ids = (_id(job_id, "source:system"),)
    return CostItem(
        cost_id=item.cost_id,
        category=CostCategory(item.category.value),
        confidence=CostConfidence(item.confidence.value),
        amount=Money(amount=item.amount.amount) if item.amount is not None else None,
        description=descriptions[item.category],
        source_ids=source_ids,
    )


def _sources(
    results: tuple[ProviderResult[object], ...],
    *,
    job_id: UUID,
    evaluated_at: datetime,
) -> tuple[SourceRecord, ...]:
    values = [
        SourceRecord(
            source_id=_id(job_id, "source:user"),
            provider=ProviderName.USER,
            source_type="user_input",
            fetched_at=evaluated_at,
            freshness=DataFreshness.UNKNOWN_VALIDITY,
            warnings=("来自本次用户输入。",),
        ),
        SourceRecord(
            source_id=_id(job_id, "source:system"),
            provider=ProviderName.SYSTEM,
            source_type="estimation_rule",
            fetched_at=evaluated_at,
            freshness=DataFreshness.UNKNOWN_VALIDITY,
            warnings=("使用项目固定估算规则。",),
        ),
    ]
    seen = {item.source_id for item in values}
    for result in results:
        for record in result.source_records:
            if record.source_id in seen:
                continue
            seen.add(record.source_id)
            freshness = evaluate_freshness(
                record.fetched_at,
                record.valid_until,
                evaluated_at,
            )
            values.append(
                SourceRecord(
                    source_id=record.source_id,
                    provider=ProviderName(record.provider.value),
                    source_type=record.source_type,
                    fetched_at=record.fetched_at,
                    valid_until=record.valid_until,
                    freshness=DataFreshness(freshness.value),
                    reference_url=cast(AnyHttpUrl | None, record.reference_url),
                    attributions=record.attributions,
                    warnings=result.warnings[:10],
                )
            )
    return tuple(values)


def _provider_results(outcome: OfflinePlanningOutcome) -> tuple[ProviderResult[object], ...]:
    raw = (
        outcome.city_result,
        outcome.accommodation_result,
        outcome.poi_result,
        outcome.weather_result,
        outcome.alert_result,
        outcome.candidate_result,
        *(item.result for item in outcome.route_enrichments),
    )
    return tuple(cast(ProviderResult[object], item) for item in raw if item is not None)


def _provider_errors(
    results: tuple[ProviderResult[object], ...],
) -> tuple[ApiError, ...]:
    errors: list[ApiError] = []
    seen: set[tuple[str, str]] = set()
    for result in results:
        if result.error is None:
            continue
        code = ApiErrorCode(result.error.code.value)
        key = (result.provider.value, code.value)
        if key in seen:
            continue
        seen.add(key)
        errors.append(
            ApiError(
                code=code,
                message=_PROVIDER_ERROR_MESSAGES[code],
                provider=result.provider.value,
                diagnostic_code=(
                    result.error.reason.value if result.error.reason is not None else None
                ),
                retryable=result.error.retryable,
            )
        )
    return tuple(errors)


def _issues(
    issues: tuple[FinalValidationIssue, ...],
) -> tuple[tuple[ConstraintViolation, ...], tuple[Uncertainty, ...]]:
    violations = tuple(
        ConstraintViolation(
            code=item.code.value,
            severity=ViolationSeverity.ERROR,
            message=_ISSUE_MESSAGES[item.code],
        )
        for item in issues
        if item.severity is FinalValidationSeverity.CONFLICT
    )
    uncertainties = tuple(
        Uncertainty(
            code=item.code.value,
            message=_ISSUE_MESSAGES[item.code],
        )
        for item in issues
        if item.severity is FinalValidationSeverity.PARTIAL
    )
    return violations, uncertainties


def _coordinates(value: object) -> Coordinates | None:
    from intelligent_travel_assistant.domain import Coordinates as DomainCoordinates

    if not isinstance(value, DomainCoordinates):
        return None
    return Coordinates(
        longitude=value.longitude,
        latitude=value.latitude,
        coordinate_system=CoordinateSystem(value.coordinate_system.value),
    )


def _source_ids[T](result: ProviderResult[T] | None) -> tuple[UUID, ...]:
    if result is None:
        return ()
    return tuple(item.source_id for item in result.source_records)


def _needs_input_result(*, field: str = "start_date") -> PlanningJobResult:
    return PlanningJobResult(
        status=PlanningStatus.NEEDS_INPUT,
        resolved_destination=None,
        plan=None,
        violations=(),
        warnings=(),
        uncertainties=(),
        sources=(),
        errors=(
            ApiError(
                code=ApiErrorCode.INPUT_INVALID,
                message="旅行日期已不在允许的 D+1 至 D+5 窗口内。",
                field=field,
                retryable=False,
            ),
        ),
        retryable=False,
    )


def _internal_failure_result() -> PlanningJobResult:
    return PlanningJobResult(
        status=PlanningStatus.FAILED,
        resolved_destination=None,
        plan=None,
        violations=(),
        warnings=(),
        uncertainties=(),
        sources=(),
        errors=(
            ApiError(
                code=ApiErrorCode.INTERNAL_ERROR,
                message="规划任务未能安全完成。",
                retryable=False,
            ),
        ),
        retryable=False,
    )


def _id(job_id: UUID, suffix: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"f-001:{job_id}:{suffix}")
