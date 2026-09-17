"""Application-owned, in-memory F-009 preplanning lifecycle."""

from __future__ import annotations

from asyncio import Lock
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from itertools import pairwise
from typing import Final, TypeVar
from uuid import UUID, uuid4, uuid5

from intelligent_travel_assistant.application.f009.ports import (
    F009CityFact,
    F009MapProvider,
    F009Narrative,
    F009NarrativeProvider,
    F009NarrativeRequest,
    F009PoiQuery,
    F009ProviderFailure,
    F009ProviderFailureKind,
    F009ProviderOutcome,
    F009RouteFact,
    F009RouteQuery,
    F014AdvisorProvider,
    F014AdvisorRequest,
)
from intelligent_travel_assistant.application.f009.solver import (
    ScheduleCandidate,
    enumerate_schedule_candidates,
    haversine_meters,
    transport_budget_minutes,
    validate_route_fact,
)
from intelligent_travel_assistant.application.tooling import PacedAttemptLimiter
from intelligent_travel_assistant.contracts.errors import ApiError, ApiErrorCode
from intelligent_travel_assistant.contracts.f009 import (
    AccommodationMode,
    FeasibilityConflict,
    FeasibilityConflictCode,
    FeasibilityDay,
    FeasibilityStop,
    Gcj02Point,
    MapDayLayerV1,
    MapMarkerV1,
    MapPinResponse,
    MapPlanV1,
    MapPolylineV1,
    PlanDayV5,
    PlanLocationV5,
    PlanRouteSummaryV5,
    PlanStopV5,
    PoiConfirmationStatus,
    PoiImportance,
    PoiIntent,
    PoiOption,
    PoiPurpose,
    PoiScopeKind,
    PoiSearchQuery,
    PoiSearchResponse,
    PoiSelectionSource,
    PreflightResponse,
    PreplanningSelection,
    PreplanningSelectionUpdate,
    PreplanningSessionCreateRequest,
    PreplanningSessionResponse,
    PreplanningState,
    PreplanningTripInput,
    PreplanningTripUpdate,
    RoutePreflightLeg,
    SafeCallCounts,
    TripPlanRequestV5,
    TripPlanResponseV5,
    TripPlanV5,
    TripRequestSummaryV5,
)
from intelligent_travel_assistant.contracts.f014 import (
    AdvisorActionRequest,
    AdvisorConversationEntry,
    AdvisorPhase,
    AdvisorPreferencePatch,
    AdvisorSnapshotResponse,
    AdvisorSuggestion,
    AdvisorTurnRequest,
)
from intelligent_travel_assistant.contracts.f015 import (
    PlanOptionKind,
    PlanOptionV6,
    PreflightResponseV6,
    RecoveryActionKind,
    RecoveryActionRequestV6,
    TripPlanRequestV6,
    TripPlanResponseV6,
    TripPlanV6,
    TripRequestSummaryV6,
    WeatherEvidenceStatus,
)
from intelligent_travel_assistant.contracts.trip_planning import PlanningStatus, TransportMode
from intelligent_travel_assistant.domain import Provider, ProviderOperation

SLIDING_TTL: Final = timedelta(minutes=30)
ABSOLUTE_TTL: Final = timedelta(hours=2)
POI_CACHE_TTL: Final = timedelta(minutes=5)
ROUTE_CACHE_TTL: Final = timedelta(minutes=10)
MAX_POI_CALLS: Final = 25
MAX_REVERSE_GEOCODE_CALLS: Final = 4
MAX_ROUTE_CALLS: Final = 24
MAX_TOTAL_CALLS: Final = 60
MAX_MAP_PLAN_BYTES: Final = 2_000_000
MAX_ADVISOR_CONVERSATION: Final = 12
MAP_PIN_NAMESPACE: Final = UUID("8e948b85-7ec9-45f3-9227-e206af49a1ca")
ROUTE_NAMESPACE: Final = UUID("218ddf41-acde-48e2-a85c-bdf66c4b1b91")
_T = TypeVar("_T")


class F009ServiceErrorCode(StrEnum):
    SESSION_NOT_FOUND = "preplanning_session_not_found"
    SESSION_EXPIRED = "preplanning_session_expired"
    REVISION_CONFLICT = "selection_revision_conflict"
    SELECTION_INVALID = "selection_invalid"
    CALL_BUDGET_EXCEEDED = "preplanning_call_budget_exceeded"
    FEASIBILITY_STALE = "feasibility_stale"
    MAP_GEOMETRY_UNAVAILABLE = "map_geometry_unavailable"
    NARRATIVE_RETRY_NOT_ALLOWED = "narrative_retry_not_allowed"
    NARRATIVE_RETRY_CONFLICT = "narrative_retry_conflict"


class F009ServiceError(Exception):
    __slots__ = ("code",)

    def __init__(self, code: F009ServiceErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(slots=True)
class _CacheEntry:
    expires_at: datetime
    value: tuple[PoiOption, ...]


@dataclass(slots=True)
class _RouteCacheEntry:
    expires_at: datetime
    value: F009ProviderOutcome[F009RouteFact]


@dataclass(frozen=True, slots=True)
class _Feasibility:
    feasibility_id: UUID
    revision: int
    response: PreflightResponse
    route_facts: dict[UUID, F009RouteFact]


@dataclass(frozen=True, slots=True)
class _CandidateEvaluation:
    days: tuple[FeasibilityDay, ...] | None = None
    conflicts: tuple[FeasibilityConflict, ...] = ()
    route_facts: dict[UUID, F009RouteFact] = field(default_factory=dict)
    provider_unavailable: bool = False


@dataclass(frozen=True, slots=True)
class _RoutedLeg:
    leg: RoutePreflightLeg | None = None
    fact: F009RouteFact | None = None
    conflict: FeasibilityConflict | None = None
    provider_unavailable: bool = False


@dataclass(frozen=True, slots=True)
class _V5Job:
    session_id: UUID
    request: TripPlanRequestV5
    response: TripPlanResponseV5
    map_plan: MapPlanV1
    geometry_expires_at: datetime
    narrative_lock: Lock = field(default_factory=Lock, compare=False)


@dataclass(frozen=True, slots=True)
class _V6Option:
    public: PlanOptionV6
    route_facts: dict[UUID, F009RouteFact]


@dataclass(frozen=True, slots=True)
class _V6FeasibilitySet:
    feasibility_set_id: UUID
    revision: int
    options: dict[UUID, _V6Option]


@dataclass(frozen=True, slots=True)
class _V6Job:
    session_id: UUID
    request: TripPlanRequestV6
    response: TripPlanResponseV6
    map_plan: MapPlanV1
    geometry_expires_at: datetime
    narrative_lock: Lock = field(default_factory=Lock, compare=False)


@dataclass(slots=True)
class _Session:
    session_id: UUID
    trip: PreplanningTripInput
    created_at: datetime
    touched_at: datetime
    absolute_expires_at: datetime
    state: PreplanningState
    city: F009CityFact | None
    revision: int = 0
    selection: PreplanningSelection | None = None
    candidates: dict[UUID, PoiOption] = field(default_factory=dict)
    poi_calls: int = 0
    reverse_geocode_calls: int = 0
    route_calls: int = 0
    poi_cache: OrderedDict[str, _CacheEntry] = field(default_factory=OrderedDict)
    route_cache: OrderedDict[str, _RouteCacheEntry] = field(default_factory=OrderedDict)
    feasibility: _Feasibility | None = None
    v6_feasibility: _V6FeasibilitySet | None = None
    search_lock: Lock = field(default_factory=Lock)
    preflight_lock: Lock = field(default_factory=Lock)
    advisor_lock: Lock = field(default_factory=Lock)
    advisor_phase: AdvisorPhase = AdvisorPhase.INTERVIEW
    advisor_preferences: AdvisorPreferencePatch = field(default_factory=AdvisorPreferencePatch)
    advisor_suggestions: tuple[AdvisorSuggestion, ...] = ()
    advisor_question: str | None = "你更在意少走路、避开拥挤，还是尽量覆盖必去地点？"
    advisor_conversation: tuple[AdvisorConversationEntry, ...] = ()
    advisor_turns: dict[UUID, tuple[AdvisorTurnRequest, AdvisorSnapshotResponse]] = field(
        default_factory=dict
    )
    advisor_actions: dict[UUID, tuple[AdvisorActionRequest, AdvisorSnapshotResponse]] = field(
        default_factory=dict
    )
    recovery_actions: dict[UUID, tuple[RecoveryActionRequestV6, PreplanningSessionResponse]] = (
        field(default_factory=dict)
    )


class PreplanningService:
    """Own ephemeral provider-derived facts and reject stale selection revisions."""

    __slots__ = (
        "_client_jobs",
        "_clock",
        "_id_factory",
        "_jobs",
        "_lock",
        "_narrative",
        "_provider",
        "_route_limiter",
        "_monotonic",
        "_narrative_retry_clients",
        "_advisor",
        "_sessions",
        "_v6_client_jobs",
        "_v6_jobs",
        "_v6_narrative_retry_clients",
    )

    def __init__(
        self,
        provider: F009MapProvider,
        *,
        narrative: F009NarrativeProvider | None = None,
        advisor: F014AdvisorProvider | None = None,
        route_limiter: PacedAttemptLimiter | None = None,
        monotonic_clock: Callable[[], float] | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._provider = provider
        self._route_limiter = route_limiter
        if route_limiter is not None and monotonic_clock is None:
            raise ValueError("F-009 paced route calls require a monotonic clock")
        self._monotonic = monotonic_clock
        if narrative is None:
            from intelligent_travel_assistant.application.f009.unavailable import (
                UnavailableF009NarrativeProvider,
            )

            narrative = UnavailableF009NarrativeProvider()
        self._narrative = narrative
        if advisor is None:
            from intelligent_travel_assistant.application.f009.unavailable import (
                UnavailableF014AdvisorProvider,
            )

            advisor = UnavailableF014AdvisorProvider()
        assert advisor is not None
        self._advisor = advisor
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory
        self._sessions: dict[UUID, _Session] = {}
        self._jobs: dict[UUID, _V5Job] = {}
        self._client_jobs: dict[UUID, UUID] = {}
        self._narrative_retry_clients: dict[UUID, UUID] = {}
        self._v6_jobs: dict[UUID, _V6Job] = {}
        self._v6_client_jobs: dict[UUID, UUID] = {}
        self._v6_narrative_retry_clients: dict[UUID, UUID] = {}
        self._lock = Lock()

    async def create(self, request: PreplanningSessionCreateRequest) -> PreplanningSessionResponse:
        now = self._now()
        if await self._acquire_amap_slot():
            outcome = await self._provider.resolve_city(request.trip.city)
        else:
            outcome = self._paced_timeout()
        city = outcome.data
        state = (
            PreplanningState.DRAFT if city is not None else PreplanningState.PROVIDER_UNAVAILABLE
        )
        session = _Session(
            session_id=self._id_factory(),
            trip=request.trip,
            created_at=now,
            touched_at=now,
            absolute_expires_at=now + ABSOLUTE_TTL,
            state=state,
            city=city,
        )
        async with self._lock:
            self._sessions[session.session_id] = session
        return self._response(session, now=now)

    async def get(self, session_id: UUID) -> PreplanningSessionResponse:
        async with self._lock:
            session, now = self._require_session(session_id)
            self._touch(session, now)
            return self._response(session, now=now)

    async def get_advisor(self, session_id: UUID) -> AdvisorSnapshotResponse:
        async with self._lock:
            session, now = self._require_session(session_id)
            self._touch(session, now)
            return self._advisor_response(session)

    async def advisor_turn(
        self, session_id: UUID, request: AdvisorTurnRequest
    ) -> AdvisorSnapshotResponse:
        async with self._lock:
            session, _ = self._require_session(session_id)
            lock = session.advisor_lock
        async with lock:
            return await self._advisor_turn_serialized(session_id, request)

    async def _advisor_turn_serialized(
        self, session_id: UUID, request: AdvisorTurnRequest
    ) -> AdvisorSnapshotResponse:
        recommendation_requested = _advisor_recommendation_requested(request.message)
        async with self._lock:
            session, _ = self._require_session(session_id)
            self._require_revision(session, request.expected_revision)
            previous = session.advisor_turns.get(request.client_request_id)
            if previous is not None:
                if previous[0] != request:
                    raise F009ServiceError(F009ServiceErrorCode.REVISION_CONFLICT)
                return previous[1]

        if recommendation_requested:
            await self.search(
                session_id,
                PoiSearchQuery(
                    purpose=PoiPurpose.VISIT,
                    keywords=_advisor_discovery_keywords(request.message),
                    page=1,
                    page_size=20,
                ),
            )

        async with self._lock:
            session, _ = self._require_session(session_id)
            self._require_revision(session, request.expected_revision)
            previous = session.advisor_turns.get(request.client_request_id)
            if previous is not None:
                if previous[0] != request:
                    raise F009ServiceError(F009ServiceErrorCode.REVISION_CONFLICT)
                return previous[1]
            candidates = tuple(
                (index, option.location_id, option.name, option.category_label)
                for index, option in enumerate(
                    sorted(
                        (
                            item
                            for item in session.candidates.values()
                            if item.purpose is PoiPurpose.VISIT
                            and item.scope_kind is PoiScopeKind.POINT
                            and item.confirmation_status is PoiConfirmationStatus.VERIFIED
                        ),
                        key=lambda item: str(item.location_id),
                    )[:20],
                    start=1,
                )
            )
            advisor_request = F014AdvisorRequest(
                user_message=request.message,
                confirmed_preferences=_advisor_preference_values(session.advisor_preferences),
                candidates=candidates,
                conversation=tuple(
                    (entry.role, entry.text) for entry in session.advisor_conversation[-10:]
                ),
                recommendation_requested=recommendation_requested,
            )

        outcome = await self._advisor.generate(advisor_request)
        if outcome.data is None and (
            outcome.failure is not None and outcome.failure.kind is F009ProviderFailureKind.SCHEMA
        ):
            outcome = await self._advisor.repair(advisor_request)

        async with self._lock:
            session, now = self._require_session(session_id)
            self._require_revision(session, request.expected_revision)
            draft = outcome.data
            if draft is None:
                session.advisor_phase = AdvisorPhase.DEGRADED
                session.advisor_question = "旅行顾问暂时不可用，你仍可继续手工选点和预检。"
                session.advisor_suggestions = ()
            else:
                suggestions: list[AdvisorSuggestion] = []
                preference_patch = _advisor_patch(draft.preference_values)
                if preference_patch is not None and not preference_patch.is_empty():
                    suggestions.append(
                        AdvisorSuggestion(
                            suggestion_id=self._id_factory(),
                            kind="preference_patch",
                            title="确认你的旅行偏好",
                            reason="顾问从本轮回答中整理出的偏好，接受后才会生效。",
                            preference_patch=preference_patch,
                        )
                    )
                candidate_by_index = {item[0]: item for item in candidates}
                for index, reason in zip(
                    draft.candidate_indices, draft.candidate_reasons, strict=True
                ):
                    _, location_id, name, category = candidate_by_index[index]
                    suggestions.append(
                        AdvisorSuggestion(
                            suggestion_id=self._id_factory(),
                            kind="poi",
                            title=f"考虑 {name}",
                            reason=reason,
                            location_id=location_id,
                            location_name=name,
                            category=category,
                        )
                    )
                session.advisor_phase = AdvisorPhase(draft.role)
                session.advisor_question = draft.question
                session.advisor_suggestions = tuple(suggestions[:6])
            session.advisor_conversation = (
                *session.advisor_conversation,
                AdvisorConversationEntry(role="user", text=request.message),
                AdvisorConversationEntry(
                    role="advisor",
                    text=session.advisor_question or "你可以继续手工选点和预检。",
                ),
            )[-MAX_ADVISOR_CONVERSATION:]
            self._touch(session, now)
            response = self._advisor_response(session)
            session.advisor_turns[request.client_request_id] = (request, response)
            return response

    async def advisor_action(
        self, session_id: UUID, request: AdvisorActionRequest
    ) -> AdvisorSnapshotResponse:
        async with self._lock:
            session, now = self._require_session(session_id)
            previous = session.advisor_actions.get(request.client_request_id)
            if previous is not None:
                if previous[0] != request:
                    raise F009ServiceError(F009ServiceErrorCode.REVISION_CONFLICT)
                return previous[1]
            self._require_revision(session, request.expected_revision)
            suggestion = next(
                (
                    item
                    for item in session.advisor_suggestions
                    if item.suggestion_id == request.suggestion_id
                ),
                None,
            )
            if suggestion is None:
                raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
            if request.action == "accept":
                if suggestion.kind == "preference_patch":
                    if suggestion.preference_patch is None:
                        raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
                    session.advisor_preferences = _merge_advisor_preferences(
                        session.advisor_preferences,
                        suggestion.preference_patch,
                    )
                else:
                    base_selection = request.selection_context or session.selection
                    if base_selection is None or suggestion.location_id is None:
                        raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
                    self._validate_selection(session, base_selection)
                    option = session.candidates.get(suggestion.location_id)
                    if option is None or option.purpose is not PoiPurpose.VISIT:
                        raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
                    pois = base_selection.pois
                    if all(item.location_id != suggestion.location_id for item in pois):
                        pois = (
                            *pois,
                            PoiIntent(
                                location_id=option.location_id,
                                route_anchor_location_id=option.location_id,
                                importance=request.importance,
                                source=PoiSelectionSource.USER_SELECTED,
                            ),
                        )
                    try:
                        updated_selection = PreplanningSelection(
                            accommodation=base_selection.accommodation,
                            pois=pois,
                            allow_system_recommendations=(
                                base_selection.allow_system_recommendations
                            ),
                        )
                    except ValueError:
                        raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID) from None
                    self._validate_selection(session, updated_selection)
                    session.selection = updated_selection
                session.revision += 1
                session.state = PreplanningState.NEEDS_CONFIRMATION
                session.feasibility = None
                session.v6_feasibility = None
                session.route_cache.clear()
            session.advisor_suggestions = tuple(
                item
                for item in session.advisor_suggestions
                if item.suggestion_id != request.suggestion_id
            )
            if not session.advisor_suggestions:
                session.advisor_phase = AdvisorPhase.READY
            self._touch(session, now)
            response = self._advisor_response(session)
            session.advisor_actions[request.client_request_id] = (request, response)
            return response

    async def apply_recovery_action(
        self,
        session_id: UUID,
        request: RecoveryActionRequestV6,
    ) -> PreplanningSessionResponse:
        """Apply one explicit, typed user-confirmed conflict recovery action."""

        async with self._lock:
            session, now = self._require_session(session_id)
            previous = session.recovery_actions.get(request.client_request_id)
            if previous is not None:
                if previous[0] != request:
                    raise F009ServiceError(F009ServiceErrorCode.REVISION_CONFLICT)
                return previous[1]
            self._require_revision(session, request.expected_revision)
            selection = session.selection
            if selection is None:
                raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
            target = next(
                (item for item in selection.pois if item.location_id == request.location_id),
                None,
            )
            if target is None:
                raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
            intents = list(selection.pois)
            target_index = intents.index(target)
            if request.action is RecoveryActionKind.MOVE_TO_DAY:
                if request.target_day is None or request.target_day >= session.trip.day_count:
                    raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
                intents[target_index] = target.model_copy(
                    update={"preferred_day": request.target_day}
                )
            elif request.action is RecoveryActionKind.SHORTEN_VISIT:
                current_duration = target.expected_duration_minutes or 90
                if request.duration_minutes is None or request.duration_minutes >= current_duration:
                    raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
                intents[target_index] = target.model_copy(
                    update={"expected_duration_minutes": request.duration_minutes}
                )
            elif request.action is RecoveryActionKind.ALLOW_OMISSION:
                if target.importance is not PoiImportance.OPTIONAL:
                    raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
                intents[target_index] = target.model_copy(update={"omission_allowed": True})
            elif request.action is RecoveryActionKind.REMOVE_OPTIONAL:
                if target.importance is not PoiImportance.OPTIONAL:
                    raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
                intents.pop(target_index)
            else:
                either_group = target.either_or_group_id
                visit_group = target.visit_group_id
                if either_group is None and visit_group is None:
                    raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
                intents = [
                    item.model_copy(
                        update={
                            "either_or_group_id": (
                                None
                                if either_group is not None
                                and item.either_or_group_id == either_group
                                else item.either_or_group_id
                            ),
                            "visit_group_id": (
                                None
                                if visit_group is not None and item.visit_group_id == visit_group
                                else item.visit_group_id
                            ),
                        }
                    )
                    for item in intents
                ]
            try:
                updated_selection = PreplanningSelection(
                    accommodation=selection.accommodation,
                    pois=tuple(intents),
                    allow_system_recommendations=selection.allow_system_recommendations,
                )
            except ValueError:
                raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID) from None
            self._validate_selection(session, updated_selection)
            session.selection = updated_selection
            session.revision += 1
            session.state = PreplanningState.NEEDS_CONFIRMATION
            session.feasibility = None
            session.v6_feasibility = None
            session.route_cache.clear()
            self._touch(session, now)
            response = self._response(session, now=now)
            session.recovery_actions[request.client_request_id] = (request, response)
            return response

    async def delete(self, session_id: UUID) -> None:
        async with self._lock:
            session, _ = self._require_session(session_id)
            del self._sessions[session.session_id]
            for job_id in tuple(
                job_id for job_id, job in self._jobs.items() if job.session_id == session_id
            ):
                self._client_jobs.pop(self._jobs[job_id].request.client_request_id, None)
                del self._jobs[job_id]
            for job_id in tuple(
                job_id for job_id, job in self._v6_jobs.items() if job.session_id == session_id
            ):
                self._v6_client_jobs.pop(self._v6_jobs[job_id].request.client_request_id, None)
                del self._v6_jobs[job_id]

    async def search(self, session_id: UUID, query: PoiSearchQuery) -> PoiSearchResponse:
        async with self._lock:
            session, _ = self._require_session(session_id)
            search_lock = session.search_lock
        async with search_lock:
            return await self._search_serialized(session_id, query)

    async def _search_serialized(
        self,
        session_id: UUID,
        query: PoiSearchQuery,
    ) -> PoiSearchResponse:
        """Single-flight searches so concurrent identical queries share the cache result."""

        cache_key = query.model_dump_json()
        async with self._lock:
            session, now = self._require_session(session_id)
            city = session.city
            if city is None:
                return self._poi_response(session, query, (), now=now)
            cached = session.poi_cache.get(cache_key)
            if cached is not None and cached.expires_at >= now:
                session.poi_cache.move_to_end(cache_key)
                self._touch(session, now)
                return self._poi_response(session, query, cached.value, now=now)
            self._reserve_call(session, "poi")
            session.state = PreplanningState.DISCOVERING
            revision = session.revision

        if await self._acquire_amap_slot():
            outcome = await self._provider.search_pois(
                F009PoiQuery(
                    city_adcode=city.city_adcode,
                    purpose=query.purpose,
                    keywords=query.keywords,
                    district_adcode=query.district_adcode,
                    center=query.center,
                    radius_m=query.radius_m,
                    category_codes=query.category_codes,
                    page=query.page,
                    page_size=query.page_size,
                )
            )
        else:
            outcome = self._paced_timeout()

        async with self._lock:
            session, now = self._require_session(session_id)
            if session.revision != revision:
                raise F009ServiceError(F009ServiceErrorCode.REVISION_CONFLICT)
            if outcome.data is None:
                if (
                    outcome.failure is not None
                    and outcome.failure.kind is F009ProviderFailureKind.EMPTY_RESULT
                ):
                    items: tuple[PoiOption, ...] = ()
                    session.state = PreplanningState.NEEDS_CONFIRMATION
                else:
                    items = ()
                    session.state = PreplanningState.PROVIDER_UNAVAILABLE
            else:
                items = tuple(outcome.data)
                for item in items:
                    session.candidates[item.location_id] = item
                session.state = PreplanningState.NEEDS_CONFIRMATION
                session.poi_cache[cache_key] = _CacheEntry(now + POI_CACHE_TTL, items)
                session.poi_cache.move_to_end(cache_key)
                while len(session.poi_cache) > 100:
                    session.poi_cache.popitem(last=False)
            self._touch(session, now)
            return self._poi_response(session, query, items, now=now)

    async def create_map_pin(
        self,
        session_id: UUID,
        *,
        expected_revision: int,
        coordinate: Gcj02Point,
    ) -> MapPinResponse:
        async with self._lock:
            session, _ = self._require_session(session_id)
            self._require_revision(session, expected_revision)
            self._reserve_call(session, "reverse")
            revision = session.revision

        if await self._acquire_amap_slot():
            outcome = await self._provider.reverse_geocode(coordinate)
        else:
            outcome = self._paced_timeout()

        async with self._lock:
            session, now = self._require_session(session_id)
            self._require_revision(session, revision)
            fact = outcome.data
            if fact is None or session.city is None or fact.city_adcode != session.city.city_adcode:
                session.state = PreplanningState.PROVIDER_UNAVAILABLE
                raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
            location_id = uuid5(
                MAP_PIN_NAMESPACE,
                f"{fact.city_adcode}:{fact.coordinate.longitude:.6f}:{fact.coordinate.latitude:.6f}",
            )
            session.candidates[location_id] = PoiOption(
                location_id=location_id,
                provider_place_id=f"map-pin:{location_id}",
                name=fact.label,
                address=fact.label,
                city_adcode=fact.city_adcode,
                district_adcode=fact.district_adcode,
                category_code="map_pin",
                category_label="地图锚点",
                coordinate_gcj02=fact.coordinate,
                purpose=PoiPurpose.ACCOMMODATION,
                scope_kind=PoiScopeKind.POINT,
                confirmation_status=PoiConfirmationStatus.VERIFIED,
            )
            self._touch(session, now)
            return MapPinResponse(
                session_id=session.session_id,
                revision=session.revision,
                location_id=location_id,
                label=fact.label,
                city_adcode=fact.city_adcode,
                district_adcode=fact.district_adcode,
                coordinate=fact.coordinate,
                calls=self._call_counts(session),
            )

    async def update_selection(
        self,
        session_id: UUID,
        update: PreplanningSelectionUpdate,
    ) -> PreplanningSessionResponse:
        async with self._lock:
            session, now = self._require_session(session_id)
            self._require_revision(session, update.expected_revision)
            self._validate_selection(session, update.selection)
            session.selection = update.selection
            session.revision += 1
            session.state = PreplanningState.NEEDS_CONFIRMATION
            session.feasibility = None
            session.v6_feasibility = None
            session.route_cache.clear()
            self._touch(session, now)
            return self._response(session, now=now)

    async def update_trip(
        self,
        session_id: UUID,
        update: PreplanningTripUpdate,
    ) -> PreplanningSessionResponse:
        """Replace mutable trip details without changing the resolved city identity."""

        async with self._lock:
            session, now = self._require_session(session_id)
            self._require_revision(session, update.expected_revision)
            if update.trip.city != session.trip.city:
                raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
            if update.trip == session.trip:
                self._touch(session, now)
                return self._response(session, now=now)
            session.trip = update.trip
            session.revision += 1
            session.state = (
                PreplanningState.NEEDS_CONFIRMATION
                if session.selection is not None
                else PreplanningState.DRAFT
            )
            session.feasibility = None
            session.v6_feasibility = None
            session.route_cache.clear()
            self._touch(session, now)
            return self._response(session, now=now)

    async def preflight(
        self,
        session_id: UUID,
        *,
        expected_revision: int,
    ) -> PreflightResponse:
        """Build and route-check up to three deterministic candidates."""

        async with self._lock:
            session, _ = self._require_session(session_id)
            self._require_revision(session, expected_revision)
            lock = session.preflight_lock
        async with lock:
            async with self._lock:
                session, now = self._require_session(session_id)
                self._require_revision(session, expected_revision)
                selection = session.selection
                if selection is None or session.city is None:
                    raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
                session.state = PreplanningState.PRECHECKING
                trip = session.trip
                city = session.city
                options = dict(session.candidates)
                self._touch(session, now)

            candidates = enumerate_schedule_candidates(
                trip=trip,
                selection=selection,
                options=options,
            )
            if not candidates:
                return await self._record_conflict(
                    session_id,
                    expected_revision,
                    FeasibilityConflict(
                        code=FeasibilityConflictCode.NO_FEASIBLE_SCHEDULE,
                        message="已确认地点无法在每日容量与空间初筛内形成完整行程。",
                        recovery_options=("减少地点", "调整联合游览或二选一关系", "增加可用天数"),
                    ),
                )

            feasible: list[
                tuple[int, ScheduleCandidate, tuple[FeasibilityDay, ...], dict[UUID, F009RouteFact]]
            ] = []
            retained_conflicts: list[FeasibilityConflict] = []
            for candidate in candidates:
                evaluated = await self._evaluate_candidate(
                    session_id=session_id,
                    revision=expected_revision,
                    candidate=candidate,
                    trip=trip,
                    selection=selection,
                    options=options,
                    citycode=city.citycode,
                )
                if evaluated.provider_unavailable:
                    return await self._provider_unavailable_response(
                        session_id,
                        expected_revision,
                    )
                if evaluated.days is not None:
                    feasible.append(
                        (
                            sum(day.total_transport_minutes for day in evaluated.days),
                            candidate,
                            evaluated.days,
                            evaluated.route_facts,
                        )
                    )
                else:
                    retained_conflicts.extend(evaluated.conflicts)

            if not feasible:
                for replacement_selection in _system_replacement_selections(
                    selection,
                    options,
                ):
                    for candidate in enumerate_schedule_candidates(
                        trip=trip,
                        selection=replacement_selection,
                        options=options,
                    ):
                        evaluated = await self._evaluate_candidate(
                            session_id=session_id,
                            revision=expected_revision,
                            candidate=candidate,
                            trip=trip,
                            selection=replacement_selection,
                            options=options,
                            citycode=city.citycode,
                        )
                        if evaluated.provider_unavailable:
                            return await self._provider_unavailable_response(
                                session_id,
                                expected_revision,
                            )
                        if evaluated.days is not None:
                            feasible.append(
                                (
                                    sum(day.total_transport_minutes for day in evaluated.days),
                                    candidate,
                                    evaluated.days,
                                    evaluated.route_facts,
                                )
                            )
                        else:
                            retained_conflicts.extend(evaluated.conflicts)

            if not feasible:
                conflicts = tuple(retained_conflicts[:50]) or (
                    FeasibilityConflict(
                        code=FeasibilityConflictCode.NO_FEASIBLE_SCHEDULE,
                        message="真实路线复核后没有可行日程。",
                        recovery_options=("调整日期或地点", "允许其他交通方式"),
                    ),
                )
                return await self._record_conflicts(
                    session_id,
                    expected_revision,
                    conflicts,
                )

            feasible.sort(
                key=lambda item: (
                    len(item[1].omitted_location_ids),
                    item[1].preferred_day_deviation,
                    item[0],
                    item[1].tie_break,
                )
            )
            _, _, days, route_facts = feasible[0]
            feasibility_id = self._id_factory()
            async with self._lock:
                session, now = self._require_session(session_id)
                self._require_revision(session, expected_revision)
                response = PreflightResponse(
                    session_id=session_id,
                    revision=session.revision,
                    state=PreplanningState.FEASIBLE,
                    feasibility_id=feasibility_id,
                    days=days,
                    calls=self._call_counts(session),
                )
                session.state = PreplanningState.FEASIBLE
                session.feasibility = _Feasibility(
                    feasibility_id,
                    session.revision,
                    response,
                    route_facts,
                )
                self._touch(session, now)
                return response

    async def preflight_v6(
        self,
        session_id: UUID,
        *,
        expected_revision: int,
    ) -> PreflightResponseV6:
        """Return up to three distinct, fully route-checked deterministic options."""

        async with self._lock:
            session, _ = self._require_session(session_id)
            self._require_revision(session, expected_revision)
            lock = session.preflight_lock
        async with lock:
            async with self._lock:
                session, now = self._require_session(session_id)
                self._require_revision(session, expected_revision)
                selection = session.selection
                if selection is None or session.city is None:
                    raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
                session.state = PreplanningState.PRECHECKING
                session.feasibility = None
                session.v6_feasibility = None
                trip = session.trip
                city = session.city
                options = dict(session.candidates)
                confirmed_preferences = len(_advisor_preference_values(session.advisor_preferences))
                self._touch(session, now)

            candidates = enumerate_schedule_candidates(
                trip=trip,
                selection=selection,
                options=options,
            )
            if not candidates:
                return await self._record_v6_conflicts(
                    session_id,
                    expected_revision,
                    (
                        FeasibilityConflict(
                            code=FeasibilityConflictCode.NO_FEASIBLE_SCHEDULE,
                            message="已确认地点无法在每日容量与空间初筛内形成完整行程。",
                            recovery_options=(
                                "减少地点",
                                "调整联合游览或二选一关系",
                                "增加可用天数",
                            ),
                        ),
                    ),
                )

            feasible: list[
                tuple[int, ScheduleCandidate, tuple[FeasibilityDay, ...], dict[UUID, F009RouteFact]]
            ] = []
            conflicts: list[FeasibilityConflict] = []
            for candidate in candidates:
                evaluated = await self._evaluate_candidate(
                    session_id=session_id,
                    revision=expected_revision,
                    candidate=candidate,
                    trip=trip,
                    selection=selection,
                    options=options,
                    citycode=city.citycode,
                )
                if evaluated.provider_unavailable:
                    return await self._record_v6_provider_unavailable(session_id, expected_revision)
                if evaluated.days is None:
                    conflicts.extend(evaluated.conflicts)
                    continue
                feasible.append(
                    (
                        sum(day.total_transport_minutes for day in evaluated.days),
                        candidate,
                        evaluated.days,
                        evaluated.route_facts,
                    )
                )

            if not feasible:
                return await self._record_v6_conflicts(
                    session_id,
                    expected_revision,
                    tuple(conflicts[:50])
                    or (
                        FeasibilityConflict(
                            code=FeasibilityConflictCode.NO_FEASIBLE_SCHEDULE,
                            message="真实路线复核后没有可行方案。",
                            recovery_options=("调整日期或地点", "允许其他交通方式"),
                        ),
                    ),
                )

            ranked = _rank_v6_candidates(feasible)
            internal_options: dict[UUID, _V6Option] = {}
            public_options: list[PlanOptionV6] = []
            titles = {
                PlanOptionKind.LESS_TRANSPORT: "交通更少",
                PlanOptionKind.RELAXED_PACE: "节奏更轻松",
                PlanOptionKind.PREFERENCE_COVERAGE: "偏好覆盖更高",
            }
            for kind, item in ranked:
                total_transport, candidate, days, route_facts = item
                option_id = self._id_factory()
                coverage = max(
                    0,
                    100
                    - 20 * len(candidate.omitted_location_ids)
                    - 10 * candidate.preferred_day_deviation,
                )
                explanation = _v6_option_explanation(
                    kind,
                    total_transport=total_transport,
                    preferred_day_deviation=candidate.preferred_day_deviation,
                    confirmed_preferences=confirmed_preferences,
                )
                public = PlanOptionV6(
                    option_id=option_id,
                    kind=kind,
                    title=titles[kind],
                    explanation=explanation,
                    days=days,
                    omitted_location_ids=candidate.omitted_location_ids,
                    total_transport_minutes=total_transport,
                    preferred_day_deviation=candidate.preferred_day_deviation,
                    preference_coverage_score=coverage,
                    weather_status=WeatherEvidenceStatus.NOT_COVERED,
                    weather_message="天气尚不可核验",
                )
                public_options.append(public)
                internal_options[option_id] = _V6Option(public, dict(route_facts))

            feasibility_set_id = self._id_factory()
            async with self._lock:
                session, now = self._require_session(session_id)
                self._require_revision(session, expected_revision)
                response = PreflightResponseV6(
                    session_id=session_id,
                    revision=session.revision,
                    state=PreplanningState.FEASIBLE,
                    feasibility_set_id=feasibility_set_id,
                    options=tuple(public_options),
                    calls=self._call_counts(session),
                )
                session.state = PreplanningState.FEASIBLE
                session.v6_feasibility = _V6FeasibilitySet(
                    feasibility_set_id,
                    session.revision,
                    internal_options,
                )
                self._touch(session, now)
                return response

    async def create_v5_job(self, request: TripPlanRequestV5) -> TripPlanResponseV5:
        """Consume one current feasibility token and create an in-memory V5 result."""

        async with self._lock:
            existing_id = self._client_jobs.get(request.client_request_id)
            if existing_id is not None:
                existing = self._jobs[existing_id]
                if existing.request != request:
                    raise F009ServiceError(F009ServiceErrorCode.FEASIBILITY_STALE)
                return existing.response
            session, now = self._require_session(request.session_id)
            feasibility = session.feasibility
            if (
                feasibility is None
                or session.state is not PreplanningState.FEASIBLE
                or request.selection_revision != session.revision
                or request.selection_revision != feasibility.revision
                or request.feasibility_id != feasibility.feasibility_id
                or request.trip != session.trip
                or request.selection != session.selection
            ):
                raise F009ServiceError(F009ServiceErrorCode.FEASIBILITY_STALE)
            job_id = self._id_factory()
            trace_id = self._id_factory()
            plan_id = self._id_factory()
            days = feasibility.response.days
            route_facts = dict(feasibility.route_facts)
            options = dict(session.candidates)
            city_adcode = session.city.city_adcode if session.city is not None else None
            if city_adcode is None:
                raise F009ServiceError(F009ServiceErrorCode.FEASIBILITY_STALE)
            session.feasibility = None
            session.v6_feasibility = None

        narrative_request = _narrative_request(request, days)
        narrative = await self._narrative.generate(narrative_request)
        valid_narrative = _validated_narrative(narrative.data, days)
        narrative_diagnostic = _narrative_diagnostic(
            narrative,
            valid=valid_narrative is not None,
            stage="generation",
        )
        repairable_schema_failure = (
            narrative.failure is not None
            and narrative.failure.kind is F009ProviderFailureKind.SCHEMA
        )
        if valid_narrative is None and (narrative.data is not None or repairable_schema_failure):
            repaired = await self._narrative.repair(narrative_request)
            valid_narrative = _validated_narrative(repaired.data, days)
            narrative_diagnostic = _narrative_diagnostic(
                repaired,
                valid=valid_narrative is not None,
                stage="repair",
            )
        plan = _build_v5_plan(
            plan_id=plan_id,
            city_adcode=city_adcode,
            request=request,
            days=days,
            options=options,
            narrative=valid_narrative,
        )
        map_plan = _build_map_plan(
            job_id=job_id,
            plan=plan,
            days=days,
            options=options,
            route_facts=route_facts,
        )
        updated_at = self._now()
        response = TripPlanResponseV5(
            job_id=job_id,
            trace_id=trace_id,
            client_request_id=request.client_request_id,
            status=(
                PlanningStatus.READY if valid_narrative is not None else PlanningStatus.PARTIAL
            ),
            request_summary=TripRequestSummaryV5(
                city=request.trip.city,
                start_date=request.trip.start_date,
                end_date=request.trip.end_date,
                travelers=request.trip.travelers,
                budget=request.trip.total_budget,
                selected_poi_count=len(request.selection.pois),
            ),
            plan=plan,
            warnings=(
                () if valid_narrative is not None else ("确定性计划已保留；模型说明不可用。",)
            ),
            errors=(
                ()
                if valid_narrative is not None
                else (
                    ApiError(
                        code=ApiErrorCode.MODEL_OUTPUT_INVALID,
                        message="DeepSeek 说明未通过受约束校验；确定性行程与路线已保留。",
                        provider="deepseek",
                        diagnostic_code=narrative_diagnostic[0],
                        retryable=narrative_diagnostic[1],
                    ),
                )
            ),
            retryable=valid_narrative is None,
            created_at=now,
            updated_at=updated_at,
        )
        job = _V5Job(
            session_id=request.session_id,
            request=request,
            response=response,
            map_plan=map_plan,
            geometry_expires_at=updated_at + ROUTE_CACHE_TTL,
        )
        async with self._lock:
            session, _ = self._require_session(request.session_id)
            self._require_revision(session, request.selection_revision)
            self._jobs[job_id] = job
            self._client_jobs[request.client_request_id] = job_id
        return response

    async def create_v6_job(self, request: TripPlanRequestV6) -> TripPlanResponseV6:
        """Create a V6 plan only from an explicitly selected feasible option."""

        async with self._lock:
            existing_id = self._v6_client_jobs.get(request.client_request_id)
            if existing_id is not None:
                existing = self._v6_jobs[existing_id]
                if existing.request != request:
                    raise F009ServiceError(F009ServiceErrorCode.FEASIBILITY_STALE)
                return existing.response
            session, now = self._require_session(request.session_id)
            feasibility = session.v6_feasibility
            if (
                feasibility is None
                or session.state is not PreplanningState.FEASIBLE
                or request.selection_revision != session.revision
                or request.selection_revision != feasibility.revision
                or request.feasibility_set_id != feasibility.feasibility_set_id
                or request.option_id not in feasibility.options
                or request.trip != session.trip
                or request.selection != session.selection
            ):
                raise F009ServiceError(F009ServiceErrorCode.FEASIBILITY_STALE)
            chosen = feasibility.options[request.option_id]
            job_id = self._id_factory()
            trace_id = self._id_factory()
            plan_id = self._id_factory()
            days = chosen.public.days
            route_facts = dict(chosen.route_facts)
            options = dict(session.candidates)
            city_adcode = session.city.city_adcode if session.city is not None else None
            if city_adcode is None:
                raise F009ServiceError(F009ServiceErrorCode.FEASIBILITY_STALE)
            session.v6_feasibility = None
            session.feasibility = None

        compatibility_request = TripPlanRequestV5(
            request_version="5",
            client_request_id=request.client_request_id,
            session_id=request.session_id,
            selection_revision=request.selection_revision,
            feasibility_id=request.feasibility_set_id,
            trip=request.trip,
            selection=request.selection,
        )
        narrative_request = _narrative_request(compatibility_request, days)
        narrative = await self._narrative.generate(narrative_request)
        valid_narrative = _validated_narrative(narrative.data, days)
        narrative_diagnostic = _narrative_diagnostic(
            narrative,
            valid=valid_narrative is not None,
            stage="generation",
        )
        repairable = (
            narrative.failure is not None
            and narrative.failure.kind is F009ProviderFailureKind.SCHEMA
        )
        if valid_narrative is None and (narrative.data is not None or repairable):
            repaired = await self._narrative.repair(narrative_request)
            valid_narrative = _validated_narrative(repaired.data, days)
            narrative_diagnostic = _narrative_diagnostic(
                repaired,
                valid=valid_narrative is not None,
                stage="repair",
            )

        base_plan = _build_v5_plan(
            plan_id=plan_id,
            city_adcode=city_adcode,
            request=compatibility_request,
            days=days,
            options=options,
            narrative=valid_narrative,
        )
        plan = TripPlanV6(
            plan_id=base_plan.plan_id,
            selected_option_id=request.option_id,
            option_kind=chosen.public.kind,
            city_adcode=base_plan.city_adcode,
            start_date=base_plan.start_date,
            end_date=base_plan.end_date,
            accommodation=base_plan.accommodation,
            locations=base_plan.locations,
            days=base_plan.days,
            global_notes=base_plan.global_notes,
            weather_status=chosen.public.weather_status,
            weather_message=chosen.public.weather_message,
        )
        map_plan = _build_map_plan(
            job_id=job_id,
            plan=base_plan,
            days=days,
            options=options,
            route_facts=route_facts,
        )
        updated_at = self._now()
        response = TripPlanResponseV6(
            job_id=job_id,
            trace_id=trace_id,
            client_request_id=request.client_request_id,
            status=(
                PlanningStatus.READY if valid_narrative is not None else PlanningStatus.PARTIAL
            ),
            request_summary=TripRequestSummaryV6(
                city=request.trip.city,
                start_date=request.trip.start_date,
                end_date=request.trip.end_date,
                travelers=request.trip.travelers,
                budget=request.trip.total_budget,
                selected_poi_count=len(request.selection.pois),
            ),
            plan=plan,
            warnings=(
                () if valid_narrative is not None else ("确定性计划已保留；游览提示暂不可用。",)
            ),
            errors=(
                ()
                if valid_narrative is not None
                else (
                    ApiError(
                        code=ApiErrorCode.MODEL_OUTPUT_INVALID,
                        message="游览提示未通过受约束校验；确定性行程与路线已保留。",
                        provider="deepseek",
                        diagnostic_code=narrative_diagnostic[0],
                        retryable=narrative_diagnostic[1],
                    ),
                )
            ),
            retryable=valid_narrative is None,
            created_at=now,
            updated_at=updated_at,
        )
        job = _V6Job(
            session_id=request.session_id,
            request=request,
            response=response,
            map_plan=map_plan,
            geometry_expires_at=updated_at + ROUTE_CACHE_TTL,
        )
        async with self._lock:
            session, _ = self._require_session(request.session_id)
            self._require_revision(session, request.selection_revision)
            self._v6_jobs[job_id] = job
            self._v6_client_jobs[request.client_request_id] = job_id
        return response

    async def retry_v5_narrative(
        self,
        job_id: UUID,
        *,
        client_request_id: UUID,
    ) -> TripPlanResponseV5:
        """Retry only narrative over an immutable V5 plan and MapPlan."""

        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise F009ServiceError(F009ServiceErrorCode.SESSION_NOT_FOUND)
            retry_lock = job.narrative_lock

        async with retry_lock:
            async with self._lock:
                previous_job_id = self._narrative_retry_clients.get(client_request_id)
                if previous_job_id is not None:
                    if previous_job_id != job_id:
                        raise F009ServiceError(F009ServiceErrorCode.NARRATIVE_RETRY_CONFLICT)
                    return self._jobs[job_id].response
                job = self._jobs.get(job_id)
                if job is None:
                    raise F009ServiceError(F009ServiceErrorCode.SESSION_NOT_FOUND)
                plan = job.response.plan
                if (
                    job.response.status is not PlanningStatus.PARTIAL
                    or plan is None
                    or not any(
                        error.code is ApiErrorCode.MODEL_OUTPUT_INVALID
                        for error in job.response.errors
                    )
                ):
                    raise F009ServiceError(F009ServiceErrorCode.NARRATIVE_RETRY_NOT_ALLOWED)

            narrative_request = _narrative_request_from_plan(job.request, plan)
            narrative = await self._narrative.generate(narrative_request)
            valid_narrative = _validated_narrative_for_plan(narrative.data, plan)
            narrative_diagnostic = _narrative_diagnostic(
                narrative,
                valid=valid_narrative is not None,
                stage="generation",
            )
            repairable_schema_failure = (
                narrative.failure is not None
                and narrative.failure.kind is F009ProviderFailureKind.SCHEMA
            )
            if valid_narrative is None and (
                narrative.data is not None or repairable_schema_failure
            ):
                repaired = await self._narrative.repair(narrative_request)
                valid_narrative = _validated_narrative_for_plan(repaired.data, plan)
                narrative_diagnostic = _narrative_diagnostic(
                    repaired,
                    valid=valid_narrative is not None,
                    stage="repair",
                )

            updated_plan = (
                _apply_narrative_to_plan(plan, valid_narrative)
                if valid_narrative is not None
                else plan
            )
            updated_at = self._now()
            response = job.response.model_copy(
                update={
                    "status": (
                        PlanningStatus.READY
                        if valid_narrative is not None
                        else PlanningStatus.PARTIAL
                    ),
                    "plan": updated_plan,
                    "warnings": (
                        ()
                        if valid_narrative is not None
                        else ("确定性计划已保留；模型说明不可用。",)
                    ),
                    "errors": (
                        ()
                        if valid_narrative is not None
                        else (
                            ApiError(
                                code=ApiErrorCode.MODEL_OUTPUT_INVALID,
                                message=("DeepSeek 说明未通过受约束校验；确定性行程与路线已保留。"),
                                provider="deepseek",
                                diagnostic_code=narrative_diagnostic[0],
                                retryable=narrative_diagnostic[1],
                            ),
                        )
                    ),
                    "retryable": valid_narrative is None,
                    "updated_at": updated_at,
                }
            )
            updated_job = _V5Job(
                session_id=job.session_id,
                request=job.request,
                response=response,
                map_plan=job.map_plan,
                geometry_expires_at=job.geometry_expires_at,
                narrative_lock=retry_lock,
            )
            async with self._lock:
                self._jobs[job_id] = updated_job
                self._narrative_retry_clients[client_request_id] = job_id
            return response

    async def get_v5_job(self, job_id: UUID) -> TripPlanResponseV5:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise F009ServiceError(F009ServiceErrorCode.SESSION_NOT_FOUND)
            return job.response

    async def retry_v6_narrative(
        self,
        job_id: UUID,
        *,
        client_request_id: UUID,
    ) -> TripPlanResponseV6:
        """Retry V6 narrative without rerunning POI, routes, solver, or weather."""

        async with self._lock:
            job = self._v6_jobs.get(job_id)
            if job is None:
                raise F009ServiceError(F009ServiceErrorCode.SESSION_NOT_FOUND)
            retry_lock = job.narrative_lock
        async with retry_lock:
            async with self._lock:
                previous = self._v6_narrative_retry_clients.get(client_request_id)
                if previous is not None:
                    if previous != job_id:
                        raise F009ServiceError(F009ServiceErrorCode.NARRATIVE_RETRY_CONFLICT)
                    return self._v6_jobs[job_id].response
                job = self._v6_jobs.get(job_id)
                if job is None:
                    raise F009ServiceError(F009ServiceErrorCode.SESSION_NOT_FOUND)
                plan = job.response.plan
                if (
                    job.response.status is not PlanningStatus.PARTIAL
                    or plan is None
                    or not any(
                        error.code is ApiErrorCode.MODEL_OUTPUT_INVALID
                        for error in job.response.errors
                    )
                ):
                    raise F009ServiceError(F009ServiceErrorCode.NARRATIVE_RETRY_NOT_ALLOWED)

            base_plan = _v6_as_v5(plan)
            compatibility_request = TripPlanRequestV5(
                request_version="5",
                client_request_id=job.request.client_request_id,
                session_id=job.request.session_id,
                selection_revision=job.request.selection_revision,
                feasibility_id=job.request.feasibility_set_id,
                trip=job.request.trip,
                selection=job.request.selection,
            )
            narrative_request = _narrative_request_from_plan(compatibility_request, base_plan)
            outcome = await self._narrative.generate(narrative_request)
            valid = _validated_narrative_for_plan(outcome.data, base_plan)
            diagnostic = _narrative_diagnostic(outcome, valid=valid is not None, stage="generation")
            repairable = (
                outcome.failure is not None
                and outcome.failure.kind is F009ProviderFailureKind.SCHEMA
            )
            if valid is None and (outcome.data is not None or repairable):
                repaired = await self._narrative.repair(narrative_request)
                valid = _validated_narrative_for_plan(repaired.data, base_plan)
                diagnostic = _narrative_diagnostic(
                    repaired, valid=valid is not None, stage="repair"
                )
            if valid is not None:
                base_plan = _apply_narrative_to_plan(base_plan, valid)
                updated_plan = _v6_from_v5(plan, base_plan)
            else:
                updated_plan = plan
            updated_at = self._now()
            response = job.response.model_copy(
                update={
                    "status": PlanningStatus.READY if valid is not None else PlanningStatus.PARTIAL,
                    "plan": updated_plan,
                    "warnings": (
                        () if valid is not None else ("确定性计划已保留；游览提示暂不可用。",)
                    ),
                    "errors": (
                        ()
                        if valid is not None
                        else (
                            ApiError(
                                code=ApiErrorCode.MODEL_OUTPUT_INVALID,
                                message="游览提示未通过受约束校验；确定性行程与路线已保留。",
                                provider="deepseek",
                                diagnostic_code=diagnostic[0],
                                retryable=diagnostic[1],
                            ),
                        )
                    ),
                    "retryable": valid is None,
                    "updated_at": updated_at,
                }
            )
            updated_job = _V6Job(
                session_id=job.session_id,
                request=job.request,
                response=response,
                map_plan=job.map_plan,
                geometry_expires_at=job.geometry_expires_at,
                narrative_lock=retry_lock,
            )
            async with self._lock:
                self._v6_jobs[job_id] = updated_job
                self._v6_narrative_retry_clients[client_request_id] = job_id
            return response

    async def get_v6_job(self, job_id: UUID) -> TripPlanResponseV6:
        async with self._lock:
            job = self._v6_jobs.get(job_id)
            if job is None:
                raise F009ServiceError(F009ServiceErrorCode.SESSION_NOT_FOUND)
            return job.response

    async def delete_v5_job(self, job_id: UUID) -> None:
        async with self._lock:
            job = self._jobs.pop(job_id, None)
            if job is None:
                raise F009ServiceError(F009ServiceErrorCode.SESSION_NOT_FOUND)
            self._client_jobs.pop(job.request.client_request_id, None)
            self._narrative_retry_clients = {
                request_id: mapped_job_id
                for request_id, mapped_job_id in self._narrative_retry_clients.items()
                if mapped_job_id != job_id
            }

    async def delete_v6_job(self, job_id: UUID) -> None:
        async with self._lock:
            job = self._v6_jobs.pop(job_id, None)
            if job is None:
                raise F009ServiceError(F009ServiceErrorCode.SESSION_NOT_FOUND)
            self._v6_client_jobs.pop(job.request.client_request_id, None)
            self._v6_narrative_retry_clients = {
                request_id: mapped_job_id
                for request_id, mapped_job_id in self._v6_narrative_retry_clients.items()
                if mapped_job_id != job_id
            }

    async def get_map_plan(self, job_id: UUID) -> MapPlanV1:
        async with self._lock:
            job = self._jobs.get(job_id) or self._v6_jobs.get(job_id)
            if job is None:
                raise F009ServiceError(F009ServiceErrorCode.SESSION_NOT_FOUND)
            if self._now() > job.geometry_expires_at:
                raise F009ServiceError(F009ServiceErrorCode.MAP_GEOMETRY_UNAVAILABLE)
            return job.map_plan

    async def is_v5_job(self, job_id: UUID) -> bool:
        async with self._lock:
            return job_id in self._jobs

    async def is_v6_job(self, job_id: UUID) -> bool:
        async with self._lock:
            return job_id in self._v6_jobs

    async def _evaluate_candidate(
        self,
        *,
        session_id: UUID,
        revision: int,
        candidate: ScheduleCandidate,
        trip: PreplanningTripInput,
        selection: PreplanningSelection,
        options: dict[UUID, PoiOption],
        citycode: str,
    ) -> _CandidateEvaluation:
        lodging = options[selection.accommodation.route_anchor_location_id]
        days: list[FeasibilityDay] = []
        route_facts: dict[UUID, F009RouteFact] = {}
        conflicts: list[FeasibilityConflict] = []
        window_by_day = {window.day_offset: window for window in trip.day_windows}
        for candidate_day in candidate.days:
            chain = (
                lodging,
                *(options[intent.route_anchor_location_id] for intent in candidate_day.intents),
                lodging,
            )
            route_legs: list[RoutePreflightLeg] = []
            for origin, destination in pairwise(chain):
                routed = await self._route_leg(
                    session_id=session_id,
                    revision=revision,
                    origin=origin,
                    destination=destination,
                    citycode=citycode,
                    modes=trip.transport_modes,
                )
                if routed.provider_unavailable:
                    return _CandidateEvaluation(provider_unavailable=True)
                if routed.leg is None or routed.fact is None:
                    conflicts.append(
                        routed.conflict
                        or FeasibilityConflict(
                            code=FeasibilityConflictCode.ROUTE_UNREACHABLE,
                            message="至少一段已确认地点之间没有可用路线。",
                            location_ids=(origin.location_id, destination.location_id),
                            recovery_options=("调整顺序", "切换允许的交通方式", "换日"),
                        )
                    )
                    break
                route_legs.append(routed.leg)
                route_facts[routed.leg.route_id] = routed.fact
            if conflicts:
                break
            window = window_by_day[candidate_day.day_offset]
            local_date = trip.start_date + timedelta(days=candidate_day.day_offset)
            scheduled = _schedule_day(
                local_date=local_date,
                day_offset=candidate_day.day_offset,
                window_start=window.start_time,
                window_end=window.end_time,
                intents=candidate_day.intents,
                options=options,
                routes=tuple(route_legs),
            )
            if scheduled is None:
                conflicts.append(
                    FeasibilityConflict(
                        code=FeasibilityConflictCode.DAILY_CAPACITY_EXCEEDED,
                        message=f"{local_date.isoformat()} 的活动与路线超出当日时间窗口。",
                        location_ids=tuple(item.location_id for item in candidate_day.intents),
                        recovery_options=("调整地点日期", "缩短预计游览时长", "减少可省略地点"),
                    )
                )
                break
            if scheduled.total_transport_minutes > transport_budget_minutes(trip.pace):
                conflicts.append(
                    FeasibilityConflict(
                        code=FeasibilityConflictCode.DAILY_TRANSPORT_BUDGET_EXCEEDED,
                        message=f"{local_date.isoformat()} 超过当前节奏的每日软交通预算。",
                        location_ids=tuple(item.location_id for item in candidate_day.intents),
                        recovery_options=("确认更紧凑的节奏", "调整地点日期"),
                    )
                )
                break
            days.append(scheduled)
        return _CandidateEvaluation(
            days=tuple(days) if not conflicts and len(days) == trip.day_count else None,
            conflicts=tuple(conflicts),
            route_facts=route_facts,
        )

    async def _route_leg(
        self,
        *,
        session_id: UUID,
        revision: int,
        origin: PoiOption,
        destination: PoiOption,
        citycode: str,
        modes: tuple[TransportMode, ...],
    ) -> _RoutedLeg:
        straight = haversine_meters(origin.coordinate_gcj02, destination.coordinate_gcj02)
        if straight > 120_000:
            return _RoutedLeg(
                conflict=FeasibilityConflict(
                    code=FeasibilityConflictCode.EXTREME_SAME_CITY_LEG,
                    message="同日相邻地点的直线距离超过 120 km。",
                    location_ids=(origin.location_id, destination.location_id),
                    recovery_options=("移除异地候选", "重新确认同名地点"),
                )
            )
        ordered_modes = _ordered_modes(modes, straight)
        last_conflict: FeasibilityConflict | None = None
        for mode in ordered_modes:
            outcome = await self._cached_route(
                session_id,
                revision=revision,
                query=F009RouteQuery(
                    origin_location_id=origin.location_id,
                    destination_location_id=destination.location_id,
                    origin_provider_place_id=origin.provider_place_id,
                    destination_provider_place_id=destination.provider_place_id,
                    origin=origin.coordinate_gcj02,
                    destination=destination.coordinate_gcj02,
                    origin_citycode=citycode,
                    destination_citycode=citycode,
                    mode=mode,
                ),
            )
            if outcome.data is None:
                if (
                    outcome.failure is None
                    or outcome.failure.kind is not F009ProviderFailureKind.EMPTY_RESULT
                ):
                    return _RoutedLeg(provider_unavailable=True)
                last_conflict = FeasibilityConflict(
                    code=FeasibilityConflictCode.ROUTE_UNREACHABLE,
                    message="Provider 明确返回该交通方式无路线。",
                    location_ids=(origin.location_id, destination.location_id),
                    recovery_options=("切换允许的交通方式", "调整日期或顺序"),
                )
                continue
            validation = validate_route_fact(
                origin=origin.coordinate_gcj02,
                destination=destination.coordinate_gcj02,
                mode=mode,
                fact=outcome.data,
            )
            if not validation.accepted:
                if validation.code is FeasibilityConflictCode.ROUTE_ENDPOINT_MISMATCH:
                    return _RoutedLeg(provider_unavailable=True)
                last_conflict = FeasibilityConflict(
                    code=validation.code or FeasibilityConflictCode.ROUTE_UNREACHABLE,
                    message="路线未通过空间异常与交通方式可行性校验。",
                    location_ids=(origin.location_id, destination.location_id),
                    recovery_options=("切换允许的交通方式", "重新确认地点"),
                )
                continue
            route_id = uuid5(
                ROUTE_NAMESPACE,
                f"{origin.location_id}:{destination.location_id}:{mode.value}",
            )
            return _RoutedLeg(
                leg=RoutePreflightLeg(
                    route_id=route_id,
                    origin_location_id=origin.location_id,
                    destination_location_id=destination.location_id,
                    mode=mode,
                    straight_line_meters=straight,
                    distance_meters=outcome.data.distance_meters,
                    duration_minutes=outcome.data.duration_minutes,
                ),
                fact=outcome.data,
            )
        return _RoutedLeg(conflict=last_conflict)

    async def _cached_route(
        self,
        session_id: UUID,
        *,
        revision: int,
        query: F009RouteQuery,
    ) -> F009ProviderOutcome[F009RouteFact]:
        key = repr(query)
        async with self._lock:
            session, now = self._require_session(session_id)
            self._require_revision(session, revision)
            cached = session.route_cache.get(key)
            if cached is not None and cached.expires_at >= now:
                session.route_cache.move_to_end(key)
                return cached.value
            self._reserve_call(session, "route")
        outcome: F009ProviderOutcome[F009RouteFact]
        if await self._acquire_amap_slot():
            outcome = await self._provider.calculate_route(query)
        else:
            outcome = self._paced_timeout()
        async with self._lock:
            session, now = self._require_session(session_id)
            self._require_revision(session, revision)
            session.route_cache[key] = _RouteCacheEntry(now + ROUTE_CACHE_TTL, outcome)
            session.route_cache.move_to_end(key)
            while len(session.route_cache) > 100:
                session.route_cache.popitem(last=False)
            return outcome

    async def _acquire_amap_slot(self) -> bool:
        """Share the existing 2 QPS no-burst timeline across all F-009 Amap calls."""

        if self._route_limiter is None:
            return True
        assert self._monotonic is not None
        slot = await self._route_limiter.acquire(
            provider=Provider.AMAP,
            operation=ProviderOperation.CALCULATE_ROUTES,
            latest_start_at=self._monotonic() + 30.0,
        )
        return slot.granted

    @staticmethod
    def _paced_timeout() -> F009ProviderOutcome[_T]:
        return F009ProviderOutcome(
            None,
            F009ProviderFailure(F009ProviderFailureKind.TIMEOUT, retryable=True),
        )

    async def _provider_unavailable_response(
        self,
        session_id: UUID,
        revision: int,
    ) -> PreflightResponse:
        async with self._lock:
            session, now = self._require_session(session_id)
            self._require_revision(session, revision)
            session.state = PreplanningState.PROVIDER_UNAVAILABLE
            session.feasibility = None
            session.v6_feasibility = None
            self._touch(session, now)
            return PreflightResponse(
                session_id=session_id,
                revision=revision,
                state=PreplanningState.PROVIDER_UNAVAILABLE,
                conflicts=(
                    FeasibilityConflict(
                        code=FeasibilityConflictCode.PROVIDER_UNAVAILABLE,
                        message="路线 Provider 当前不可用，无法判断地点是否可达。",
                        recovery_options=("稍后重新预检",),
                    ),
                ),
                calls=self._call_counts(session),
            )

    async def _record_v6_provider_unavailable(
        self,
        session_id: UUID,
        revision: int,
    ) -> PreflightResponseV6:
        async with self._lock:
            session, now = self._require_session(session_id)
            self._require_revision(session, revision)
            session.state = PreplanningState.PROVIDER_UNAVAILABLE
            session.feasibility = None
            session.v6_feasibility = None
            self._touch(session, now)
            return PreflightResponseV6(
                session_id=session_id,
                revision=revision,
                state=PreplanningState.PROVIDER_UNAVAILABLE,
                conflicts=(
                    FeasibilityConflict(
                        code=FeasibilityConflictCode.PROVIDER_UNAVAILABLE,
                        message="路线 Provider 当前不可用，无法判断地点是否可达。",
                        recovery_options=("稍后重新预检",),
                    ),
                ),
                calls=self._call_counts(session),
            )

    async def _record_v6_conflicts(
        self,
        session_id: UUID,
        revision: int,
        conflicts: tuple[FeasibilityConflict, ...],
    ) -> PreflightResponseV6:
        async with self._lock:
            session, now = self._require_session(session_id)
            self._require_revision(session, revision)
            session.state = PreplanningState.CONFLICTED
            session.feasibility = None
            session.v6_feasibility = None
            self._touch(session, now)
            return PreflightResponseV6(
                session_id=session_id,
                revision=revision,
                state=PreplanningState.CONFLICTED,
                conflicts=conflicts,
                calls=self._call_counts(session),
            )

    async def _record_conflict(
        self,
        session_id: UUID,
        revision: int,
        conflict: FeasibilityConflict,
    ) -> PreflightResponse:
        return await self._record_conflicts(session_id, revision, (conflict,))

    async def _record_conflicts(
        self,
        session_id: UUID,
        revision: int,
        conflicts: tuple[FeasibilityConflict, ...],
    ) -> PreflightResponse:
        async with self._lock:
            session, now = self._require_session(session_id)
            self._require_revision(session, revision)
            session.state = PreplanningState.CONFLICTED
            session.feasibility = None
            session.v6_feasibility = None
            self._touch(session, now)
            return PreflightResponse(
                session_id=session_id,
                revision=revision,
                state=PreplanningState.CONFLICTED,
                conflicts=conflicts,
                calls=self._call_counts(session),
            )

    def _validate_selection(self, session: _Session, selection: PreplanningSelection) -> None:
        accommodation = selection.accommodation
        anchor = session.candidates.get(accommodation.route_anchor_location_id)
        if anchor is None or getattr(anchor, "purpose", None) is not PoiPurpose.ACCOMMODATION:
            raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
        if accommodation.mode is AccommodationMode.EXACT_POI and (
            accommodation.semantic_location_id != getattr(anchor, "location_id", None)
            or getattr(anchor, "confirmation_status", None) is not PoiConfirmationStatus.VERIFIED
        ):
            raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)

        for intent in selection.pois:
            semantic = session.candidates.get(intent.location_id)
            route_anchor = session.candidates.get(intent.route_anchor_location_id)
            if (
                semantic is None
                or route_anchor is None
                or getattr(semantic, "purpose", None) is not PoiPurpose.VISIT
                or getattr(route_anchor, "purpose", None) is not PoiPurpose.VISIT
            ):
                raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)
            if (
                getattr(semantic, "confirmation_status", None) is PoiConfirmationStatus.VERIFIED
                and intent.location_id != intent.route_anchor_location_id
            ):
                raise F009ServiceError(F009ServiceErrorCode.SELECTION_INVALID)

    def _require_session(self, session_id: UUID) -> tuple[_Session, datetime]:
        session = self._sessions.get(session_id)
        if session is None:
            raise F009ServiceError(F009ServiceErrorCode.SESSION_NOT_FOUND)
        now = self._now()
        if now > session.absolute_expires_at or now > session.touched_at + SLIDING_TTL:
            session.state = PreplanningState.EXPIRED
            raise F009ServiceError(F009ServiceErrorCode.SESSION_EXPIRED)
        return session, now

    @staticmethod
    def _require_revision(session: _Session, expected: int) -> None:
        if session.revision != expected:
            raise F009ServiceError(F009ServiceErrorCode.REVISION_CONFLICT)

    def _reserve_call(self, session: _Session, kind: str) -> None:
        if self._total_calls(session) >= MAX_TOTAL_CALLS:
            raise F009ServiceError(F009ServiceErrorCode.CALL_BUDGET_EXCEEDED)
        if kind == "poi":
            if session.poi_calls >= MAX_POI_CALLS:
                raise F009ServiceError(F009ServiceErrorCode.CALL_BUDGET_EXCEEDED)
            session.poi_calls += 1
        elif kind == "reverse":
            if session.reverse_geocode_calls >= MAX_REVERSE_GEOCODE_CALLS:
                raise F009ServiceError(F009ServiceErrorCode.CALL_BUDGET_EXCEEDED)
            session.reverse_geocode_calls += 1
        elif kind == "route":
            if session.route_calls >= MAX_ROUTE_CALLS:
                raise F009ServiceError(F009ServiceErrorCode.CALL_BUDGET_EXCEEDED)
            session.route_calls += 1
        else:
            raise ValueError("unknown F-009 call kind")

    @staticmethod
    def _total_calls(session: _Session) -> int:
        return session.poi_calls + session.reverse_geocode_calls + session.route_calls

    def _call_counts(self, session: _Session) -> SafeCallCounts:
        return SafeCallCounts(
            poi_search=session.poi_calls,
            reverse_geocode=session.reverse_geocode_calls,
            route=session.route_calls,
            total=self._total_calls(session),
        )

    def _response(self, session: _Session, *, now: datetime) -> PreplanningSessionResponse:
        return PreplanningSessionResponse(
            session_id=session.session_id,
            revision=session.revision,
            state=session.state,
            trip=session.trip,
            city_adcode=session.city.city_adcode if session.city is not None else None,
            city_name=session.city.city_name if session.city is not None else None,
            selection=session.selection,
            calls=self._call_counts(session),
            created_at=session.created_at,
            expires_at=min(session.touched_at + SLIDING_TTL, session.absolute_expires_at),
            absolute_expires_at=session.absolute_expires_at,
        )

    def _advisor_response(self, session: _Session) -> AdvisorSnapshotResponse:
        confirmed_count = len(_advisor_preference_values(session.advisor_preferences))
        poi_count = sum(item.kind == "poi" for item in session.advisor_suggestions)
        return AdvisorSnapshotResponse(
            session_id=session.session_id,
            revision=session.revision,
            phase=session.advisor_phase,
            conversation=session.advisor_conversation,
            confirmed_preferences=session.advisor_preferences,
            pending_suggestions=session.advisor_suggestions,
            question=session.advisor_question,
            safety_summary=(
                f"已确认 {confirmed_count} 项偏好，发现 {poi_count} 个待确认地点；"
                "未接受的建议不会进入行程。"
            ),
        )

    def _poi_response(
        self,
        session: _Session,
        query: PoiSearchQuery,
        items: tuple[PoiOption, ...],
        *,
        now: datetime,
    ) -> PoiSearchResponse:
        return PoiSearchResponse(
            session_id=session.session_id,
            revision=session.revision,
            state=session.state,
            page=query.page,
            page_size=query.page_size,
            has_more=len(items) == query.page_size and query.page < 5,
            items=items,
            calls=self._call_counts(session),
        )

    def _touch(self, session: _Session, now: datetime) -> None:
        session.touched_at = min(now, session.absolute_expires_at)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("F-009 clock must be timezone aware")
        return value


def _advisor_preference_values(
    preferences: AdvisorPreferencePatch,
) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    if preferences.walking_tolerance is not None:
        values.append(("walking_tolerance", preferences.walking_tolerance))
    if preferences.crowd_tolerance is not None:
        values.append(("crowd_tolerance", preferences.crowd_tolerance))
    if preferences.day_start is not None:
        values.append(("day_start", preferences.day_start.strftime("%H:%M")))
    if preferences.food_preferences:
        values.append(("food_preferences", ",".join(preferences.food_preferences)))
    if preferences.budget_flexibility is not None:
        values.append(("budget_flexibility", preferences.budget_flexibility))
    if preferences.party_notes:
        values.append(("party_notes", ",".join(preferences.party_notes)))
    return tuple(values)


def _rank_v6_candidates(
    feasible: list[
        tuple[int, ScheduleCandidate, tuple[FeasibilityDay, ...], dict[UUID, F009RouteFact]]
    ],
) -> tuple[
    tuple[
        PlanOptionKind,
        tuple[int, ScheduleCandidate, tuple[FeasibilityDay, ...], dict[UUID, F009RouteFact]],
    ],
    ...,
]:
    """Choose one distinct winner per user-visible optimization objective."""

    selectors = (
        (
            PlanOptionKind.LESS_TRANSPORT,
            lambda item: (
                item[0],
                item[1].preferred_day_deviation,
                item[1].tie_break,
            ),
        ),
        (
            PlanOptionKind.RELAXED_PACE,
            lambda item: (
                max(day.total_transport_minutes for day in item[2]),
                item[0],
                item[1].tie_break,
            ),
        ),
        (
            PlanOptionKind.PREFERENCE_COVERAGE,
            lambda item: (
                len(item[1].omitted_location_ids),
                item[1].preferred_day_deviation,
                item[0],
                item[1].tie_break,
            ),
        ),
    )
    ranked: list[
        tuple[
            PlanOptionKind,
            tuple[
                int,
                ScheduleCandidate,
                tuple[FeasibilityDay, ...],
                dict[UUID, F009RouteFact],
            ],
        ]
    ] = []
    seen: set[tuple[str, ...]] = set()
    for kind, selector in selectors:
        item = min(feasible, key=selector)
        if item[1].tie_break not in seen:
            ranked.append((kind, item))
            seen.add(item[1].tie_break)
    return tuple(ranked)


def _advisor_recommendation_requested(message: str) -> bool:
    normalized = message.strip().lower()
    if "不推荐" in normalized:
        return False
    return any(
        marker in normalized
        for marker in ("推荐", "有什么好玩", "有哪些好玩", "哪里好玩", "值得去", "景点")
    )


def _advisor_discovery_keywords(message: str) -> str:
    if any(marker in message for marker in ("自然", "山水", "洞", "湖", "公园")):
        return "自然景点"
    if any(marker in message for marker in ("历史", "文化", "古迹", "博物馆")):
        return "文化景点"
    if any(marker in message for marker in ("亲子", "儿童", "孩子")):
        return "亲子景点"
    return "景点"


def _v6_option_explanation(
    kind: PlanOptionKind,
    *,
    total_transport: int,
    preferred_day_deviation: int,
    confirmed_preferences: int,
) -> str:
    if kind is PlanOptionKind.LESS_TRANSPORT:
        focus = "在全部可行方案中优先减少总交通时间"
    elif kind is PlanOptionKind.RELAXED_PACE:
        focus = "优先让每日交通负担更均匀，保留更从容的游览节奏"
    else:
        focus = "优先满足已确认的日期偏好并减少授权省略"
    return (
        f"{focus}；总交通约 {total_transport} 分钟，"
        f"日期偏离 {preferred_day_deviation} 项，已参考 {confirmed_preferences} 项确认偏好。"
    )


def _advisor_patch(values: tuple[tuple[str, str], ...]) -> AdvisorPreferencePatch | None:
    if len({key for key, _ in values}) != len(values):
        return None
    raw = dict(values)
    try:
        day_start = time.fromisoformat(raw["day_start"]) if "day_start" in raw else None
        return AdvisorPreferencePatch.model_validate(
            {
                "walking_tolerance": raw.get("walking_tolerance"),
                "crowd_tolerance": raw.get("crowd_tolerance"),
                "day_start": day_start,
                "food_preferences": tuple(
                    item.strip()
                    for item in raw.get("food_preferences", "").split(",")
                    if item.strip()
                )[:5],
                "budget_flexibility": raw.get("budget_flexibility"),
                "party_notes": tuple(
                    item.strip() for item in raw.get("party_notes", "").split(",") if item.strip()
                )[:5],
            }
        )
    except (TypeError, ValueError):
        return None


def _merge_advisor_preferences(
    current: AdvisorPreferencePatch,
    patch: AdvisorPreferencePatch,
) -> AdvisorPreferencePatch:
    return AdvisorPreferencePatch(
        walking_tolerance=patch.walking_tolerance or current.walking_tolerance,
        crowd_tolerance=patch.crowd_tolerance or current.crowd_tolerance,
        day_start=patch.day_start or current.day_start,
        food_preferences=patch.food_preferences or current.food_preferences,
        budget_flexibility=patch.budget_flexibility or current.budget_flexibility,
        party_notes=patch.party_notes or current.party_notes,
    )


def _ordered_modes(
    modes: tuple[TransportMode, ...], straight_line_meters: int
) -> tuple[TransportMode, ...]:
    preferred = (
        TransportMode.WALKING
        if straight_line_meters <= 3_000 and TransportMode.WALKING in modes
        else TransportMode.PUBLIC_TRANSIT
    )
    return tuple(sorted(modes, key=lambda mode: (mode is not preferred, mode.value)))


def _system_replacement_selections(
    selection: PreplanningSelection,
    options: dict[UUID, PoiOption],
) -> tuple[PreplanningSelection, ...]:
    """Enumerate bounded, verified 5 km substitutions only for system recommendations."""

    if not selection.allow_system_recommendations:
        return ()
    selected_ids = {intent.location_id for intent in selection.pois}
    variants: list[PreplanningSelection] = []
    for index, intent in enumerate(selection.pois):
        if intent.source is not PoiSelectionSource.SYSTEM_RECOMMENDATION:
            continue
        original = options[intent.route_anchor_location_id]
        replacements = sorted(
            (
                option
                for option in options.values()
                if option.location_id not in selected_ids
                and option.purpose is PoiPurpose.VISIT
                and option.city_adcode == original.city_adcode
                and option.category_code == original.category_code
                and option.scope_kind is PoiScopeKind.POINT
                and option.confirmation_status is PoiConfirmationStatus.VERIFIED
                and haversine_meters(
                    original.coordinate_gcj02,
                    option.coordinate_gcj02,
                )
                <= 5_000
            ),
            key=lambda option: str(option.location_id),
        )
        for replacement in replacements:
            replacement_intent = intent.model_copy(
                update={
                    "location_id": replacement.location_id,
                    "route_anchor_location_id": replacement.location_id,
                }
            )
            intents = list(selection.pois)
            intents[index] = replacement_intent
            variants.append(selection.model_copy(update={"pois": tuple(intents)}))
    return tuple(variants)


def _schedule_day(
    *,
    local_date: date,
    day_offset: int,
    window_start: time,
    window_end: time,
    intents: tuple[PoiIntent, ...],
    options: dict[UUID, PoiOption],
    routes: tuple[RoutePreflightLeg, ...],
) -> FeasibilityDay | None:
    if len(routes) != len(intents) + 1:
        return None
    cursor = datetime.combine(local_date, window_start)
    deadline = datetime.combine(local_date, window_end)
    stops: list[FeasibilityStop] = []
    for index, intent in enumerate(intents):
        cursor += timedelta(minutes=routes[index].duration_minutes + 15)
        duration = intent.expected_duration_minutes or _default_duration(
            options[intent.location_id].category_code
        )
        end = cursor + timedelta(minutes=duration)
        if end > deadline:
            return None
        semantic = options[intent.location_id]
        stops.append(
            FeasibilityStop(
                location_id=intent.location_id,
                route_anchor_location_id=intent.route_anchor_location_id,
                name=semantic.name,
                category=semantic.category_label,
                importance=intent.importance,
                expected_duration_minutes=duration,
                start_time=cursor.time(),
                end_time=end.time(),
                preferred_day_satisfied=(
                    intent.preferred_day is None or intent.preferred_day == day_offset
                ),
                source=intent.source,
            )
        )
        cursor = end
    cursor += timedelta(minutes=routes[-1].duration_minutes + 15)
    if cursor > deadline:
        return None
    return FeasibilityDay(
        local_date=local_date,
        stops=tuple(stops),
        routes=routes,
        total_transport_minutes=sum(route.duration_minutes for route in routes),
    )


def _default_duration(category_code: str) -> int:
    return {
        "scenic_area": 120,
        "historic_site": 120,
        "museum": 120,
        "culture": 90,
        "leisure": 90,
        "shopping": 90,
        "food": 90,
    }.get(category_code, 90)


def _narrative_request(
    request: TripPlanRequestV5,
    days: tuple[FeasibilityDay, ...],
) -> F009NarrativeRequest:
    return F009NarrativeRequest(
        days=tuple(
            (
                day.local_date,
                tuple((stop.location_id, stop.name, stop.category) for stop in day.stops),
            )
            for day in days
        ),
        pace=request.trip.pace.value,
        uncertainties=("营业时间未核验",),
    )


def _narrative_request_from_plan(
    request: TripPlanRequestV5,
    plan: TripPlanV5,
) -> F009NarrativeRequest:
    locations = {location.location_id: location for location in plan.locations}
    return F009NarrativeRequest(
        days=tuple(
            (
                day.local_date,
                tuple(
                    (
                        stop.location_id,
                        locations[stop.location_id].name,
                        locations[stop.location_id].category,
                    )
                    for stop in day.stops
                ),
            )
            for day in plan.days
        ),
        pace=request.trip.pace.value,
        uncertainties=("营业时间未核验",),
    )


def _validated_narrative(
    narrative: F009Narrative | None,
    days: tuple[FeasibilityDay, ...],
) -> F009Narrative | None:
    if narrative is None or len(narrative.days) != len(days):
        return None
    for narrative_day, day in zip(narrative.days, days, strict=True):
        expected_ids = tuple(stop.location_id for stop in day.stops)
        if (
            narrative_day.local_date != day.local_date
            or narrative_day.location_ids != expected_ids
            or len(narrative_day.stop_narratives) != len(expected_ids)
        ):
            return None
    return narrative


def _validated_narrative_for_plan(
    narrative: F009Narrative | None,
    plan: TripPlanV5,
) -> F009Narrative | None:
    if narrative is None or len(narrative.days) != len(plan.days):
        return None
    for narrative_day, day in zip(narrative.days, plan.days, strict=True):
        expected_ids = tuple(stop.location_id for stop in day.stops)
        if (
            narrative_day.local_date != day.local_date
            or narrative_day.location_ids != expected_ids
            or len(narrative_day.stop_narratives) != len(expected_ids)
        ):
            return None
    return narrative


def _apply_narrative_to_plan(
    plan: TripPlanV5,
    narrative: F009Narrative,
) -> TripPlanV5:
    narrative_by_date = {day.local_date: day for day in narrative.days}
    return plan.model_copy(
        update={
            "days": tuple(
                day.model_copy(
                    update={
                        "stops": tuple(
                            stop.model_copy(
                                update={
                                    "narrative": narrative_by_date[day.local_date].stop_narratives[
                                        index
                                    ]
                                }
                            )
                            for index, stop in enumerate(day.stops)
                        ),
                        "pace_note": narrative_by_date[day.local_date].pace_note,
                        "rationale": narrative_by_date[day.local_date].rationale,
                    }
                )
                for day in plan.days
            ),
            "global_notes": narrative.global_notes,
        }
    )


def _v6_as_v5(plan: TripPlanV6) -> TripPlanV5:
    return TripPlanV5(
        plan_id=plan.plan_id,
        city_adcode=plan.city_adcode,
        start_date=plan.start_date,
        end_date=plan.end_date,
        accommodation=plan.accommodation,
        locations=plan.locations,
        days=plan.days,
        global_notes=plan.global_notes,
    )


def _v6_from_v5(original: TripPlanV6, plan: TripPlanV5) -> TripPlanV6:
    return original.model_copy(
        update={
            "locations": plan.locations,
            "days": plan.days,
            "global_notes": plan.global_notes,
        }
    )


def _narrative_diagnostic(
    outcome: F009ProviderOutcome[F009Narrative],
    *,
    valid: bool,
    stage: str,
) -> tuple[str, bool]:
    """Project-owned diagnosis only; provider bodies and model text never escape."""

    if valid:
        return (f"narrative_{stage}_valid", False)
    if outcome.data is not None:
        return (f"narrative_{stage}_identity_invalid", False)
    failure = outcome.failure
    if failure is not None and failure.kind is F009ProviderFailureKind.SCHEMA:
        return (f"narrative_{stage}_schema_invalid", failure.retryable)
    return (
        f"narrative_{stage}_provider_unavailable",
        failure.retryable if failure is not None else False,
    )


def _build_v5_plan(
    *,
    plan_id: UUID,
    city_adcode: str,
    request: TripPlanRequestV5,
    days: tuple[FeasibilityDay, ...],
    options: dict[UUID, PoiOption],
    narrative: F009Narrative | None,
) -> TripPlanV5:
    accommodation_id = request.selection.accommodation.route_anchor_location_id
    accommodation = options[accommodation_id]
    ordered_ids: list[UUID] = [accommodation_id]
    for day in days:
        for stop in day.stops:
            if stop.location_id not in ordered_ids:
                ordered_ids.append(stop.location_id)
    narrative_by_date = (
        {day.local_date: day for day in narrative.days} if narrative is not None else {}
    )
    return TripPlanV5(
        plan_id=plan_id,
        city_adcode=city_adcode,
        start_date=request.trip.start_date,
        end_date=request.trip.end_date,
        accommodation=request.selection.accommodation,
        locations=tuple(
            PlanLocationV5(
                location_id=location_id,
                name=options[location_id].name,
                category=options[location_id].category_label,
                district_adcode=options[location_id].district_adcode,
                source=(
                    "accommodation"
                    if location_id == accommodation_id
                    else next(
                        stop.source
                        for day in days
                        for stop in day.stops
                        if stop.location_id == location_id
                    )
                ),
            )
            for location_id in ordered_ids
        ),
        days=tuple(
            PlanDayV5(
                local_date=day.local_date,
                accommodation_location_id=accommodation.location_id,
                stops=tuple(
                    PlanStopV5(
                        location_id=stop.location_id,
                        visit_order=index,
                        start_time=stop.start_time,
                        end_time=stop.end_time,
                        importance=stop.importance,
                        narrative=(
                            narrative_by_date[day.local_date].stop_narratives[index - 1]
                            if day.local_date in narrative_by_date
                            else None
                        ),
                    )
                    for index, stop in enumerate(day.stops, start=1)
                ),
                routes=tuple(
                    PlanRouteSummaryV5(
                        route_id=route.route_id,
                        origin_location_id=(
                            accommodation.location_id
                            if index == 0
                            else day.stops[index - 1].location_id
                        ),
                        destination_location_id=(
                            accommodation.location_id
                            if index == len(day.stops)
                            else day.stops[index].location_id
                        ),
                        mode=route.mode,
                        distance_meters=route.distance_meters,
                        duration_minutes=route.duration_minutes,
                    )
                    for index, route in enumerate(day.routes)
                ),
                pace_note=(
                    narrative_by_date[day.local_date].pace_note
                    if day.local_date in narrative_by_date
                    else None
                ),
                rationale=(
                    narrative_by_date[day.local_date].rationale
                    if day.local_date in narrative_by_date
                    else None
                ),
            )
            for day in days
        ),
        global_notes=narrative.global_notes if narrative is not None else (),
    )


def _build_map_plan(
    *,
    job_id: UUID,
    plan: TripPlanV5,
    days: tuple[FeasibilityDay, ...],
    options: dict[UUID, PoiOption],
    route_facts: dict[UUID, F009RouteFact],
) -> MapPlanV1:
    accommodation_id = plan.accommodation.route_anchor_location_id
    accommodation = options[accommodation_id]
    colors = ("day-1", "day-2", "day-3", "day-4", "day-5", "day-6", "day-7")
    map_plan = MapPlanV1(
        job_id=job_id,
        plan_id=plan.plan_id,
        accommodation=MapMarkerV1(
            location_id=accommodation.location_id,
            name=accommodation.name,
            coordinate=accommodation.coordinate_gcj02,
        ),
        days=tuple(
            MapDayLayerV1(
                local_date=day.local_date,
                color_token=colors[index],  # type: ignore[arg-type]
                markers=tuple(
                    MapMarkerV1(
                        location_id=stop.location_id,
                        name=stop.name,
                        coordinate=options[stop.route_anchor_location_id].coordinate_gcj02,
                        visit_order=order,
                    )
                    for order, stop in enumerate(day.stops, start=1)
                ),
                routes=tuple(
                    MapPolylineV1(
                        route_id=route.route_id,
                        origin_location_id=plan_route.origin_location_id,
                        destination_location_id=plan_route.destination_location_id,
                        mode=route.mode,
                        distance_meters=route.distance_meters,
                        duration_minutes=route.duration_minutes,
                        points=_simplify_points(route_facts[route.route_id].points),
                    )
                    for route, plan_route in zip(day.routes, plan_day.routes, strict=True)
                ),
            )
            for index, (day, plan_day) in enumerate(zip(days, plan.days, strict=True))
        ),
    )
    return _fit_map_plan_size(map_plan)


def _fit_map_plan_size(
    plan: MapPlanV1,
    *,
    max_bytes: int = MAX_MAP_PLAN_BYTES,
) -> MapPlanV1:
    """Keep the strict map response bounded while preserving the textual plan."""

    if len(plan.model_dump_json().encode("utf-8")) <= max_bytes:
        return plan
    endpoint_days = tuple(
        day.model_copy(
            update={
                "routes": tuple(
                    route.model_copy(update={"points": (route.points[0], route.points[-1])})
                    for route in day.routes
                )
            }
        )
        for day in plan.days
    )
    warning = "地图几何超过响应上限，已进行确定性降级；完整路线摘要仍保留在列表中。"
    endpoint_plan = plan.model_copy(
        update={"days": endpoint_days, "warnings": (*plan.warnings[:19], warning)}
    )
    if len(endpoint_plan.model_dump_json().encode("utf-8")) <= max_bytes:
        return endpoint_plan
    return endpoint_plan.model_copy(
        update={"days": tuple(day.model_copy(update={"routes": ()}) for day in endpoint_days)}
    )


def _simplify_points(points: tuple[Gcj02Point, ...]) -> tuple[Gcj02Point, ...]:
    if len(points) <= 500:
        return points
    step = (len(points) - 1) / 499
    indexes = {round(index * step) for index in range(500)}
    indexes.update({0, len(points) - 1})
    sampled = tuple(points[index] for index in sorted(indexes))
    if len(sampled) <= 500:
        return sampled
    return (*sampled[:499], sampled[-1])
