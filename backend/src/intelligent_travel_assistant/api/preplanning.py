"""HTTP adapter for F-009 ephemeral preplanning sessions."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from pydantic import ValidationError

from intelligent_travel_assistant.api.errors import PlanningHttpError, input_invalid_error
from intelligent_travel_assistant.application.f009 import (
    F009ServiceError,
    F009ServiceErrorCode,
    PreplanningService,
)
from intelligent_travel_assistant.contracts import ApiErrorCode, ApiErrorResponse
from intelligent_travel_assistant.contracts.f009 import (
    Gcj02Point,
    MapPinCreateRequest,
    MapPinResponse,
    PoiPurpose,
    PoiSearchQuery,
    PoiSearchResponse,
    PreflightRequest,
    PreflightResponse,
    PreplanningSelectionUpdate,
    PreplanningSessionCreateRequest,
    PreplanningSessionResponse,
    PreplanningTripUpdate,
)
from intelligent_travel_assistant.contracts.f014 import (
    AdvisorActionRequest,
    AdvisorSnapshotResponse,
    AdvisorTurnRequest,
)
from intelligent_travel_assistant.contracts.f015 import (
    PreflightRequestV6,
    PreflightResponseV6,
    RecoveryActionRequestV6,
)


def preplanning_http_error(error: F009ServiceError) -> PlanningHttpError:
    mapping = {
        F009ServiceErrorCode.SESSION_NOT_FOUND: (
            404,
            ApiErrorCode.PREPLANNING_SESSION_NOT_FOUND,
            "The preplanning session was not found.",
        ),
        F009ServiceErrorCode.SESSION_EXPIRED: (
            410,
            ApiErrorCode.PREPLANNING_SESSION_EXPIRED,
            "The preplanning session has expired.",
        ),
        F009ServiceErrorCode.REVISION_CONFLICT: (
            409,
            ApiErrorCode.SELECTION_REVISION_CONFLICT,
            "The preplanning selection has changed.",
        ),
        F009ServiceErrorCode.SELECTION_INVALID: (
            422,
            ApiErrorCode.SELECTION_INVALID,
            "The selected accommodation or POI identity is invalid.",
        ),
        F009ServiceErrorCode.CALL_BUDGET_EXCEEDED: (
            409,
            ApiErrorCode.PREPLANNING_CALL_BUDGET_EXCEEDED,
            "The preplanning call budget is exhausted.",
        ),
        F009ServiceErrorCode.FEASIBILITY_STALE: (
            409,
            ApiErrorCode.FEASIBILITY_STALE,
            "The feasibility snapshot is no longer current.",
        ),
        F009ServiceErrorCode.MAP_GEOMETRY_UNAVAILABLE: (
            410,
            ApiErrorCode.MAP_GEOMETRY_UNAVAILABLE,
            "The map geometry is no longer available.",
        ),
    }
    status_code, code, message = mapping[error.code]
    return PlanningHttpError(status_code, code, message)


def _center(raw: str | None) -> Gcj02Point | None:
    if raw is None:
        return None
    parts = raw.split(",")
    if len(parts) != 2:
        raise PlanningHttpError(
            422,
            ApiErrorCode.INPUT_INVALID,
            "The map center must contain longitude and latitude.",
        )
    try:
        return Gcj02Point(longitude=float(parts[0]), latitude=float(parts[1]))
    except (TypeError, ValueError):
        raise PlanningHttpError(
            422,
            ApiErrorCode.INPUT_INVALID,
            "The map center is invalid.",
        ) from None


def create_preplanning_router(service: PreplanningService) -> APIRouter:
    router = APIRouter(prefix="/api/preplanning-sessions", tags=["preplanning"])

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        response_model=PreplanningSessionResponse,
        responses={422: {"model": ApiErrorResponse}},
    )
    async def create_session(
        request: PreplanningSessionCreateRequest,
        response: Response,
    ) -> PreplanningSessionResponse:
        result = await service.create(request)
        response.headers["Location"] = f"/api/preplanning-sessions/{result.session_id}"
        return result

    @router.get(
        "/{session_id}",
        response_model=PreplanningSessionResponse,
        responses={404: {"model": ApiErrorResponse}, 410: {"model": ApiErrorResponse}},
    )
    async def get_session(session_id: UUID) -> PreplanningSessionResponse:
        try:
            return await service.get(session_id)
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None

    @router.get(
        "/{session_id}/advisor",
        response_model=AdvisorSnapshotResponse,
        responses={404: {"model": ApiErrorResponse}, 410: {"model": ApiErrorResponse}},
    )
    async def get_advisor(session_id: UUID) -> AdvisorSnapshotResponse:
        try:
            return await service.get_advisor(session_id)
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None

    @router.post(
        "/{session_id}/advisor-turns",
        response_model=AdvisorSnapshotResponse,
        responses={
            404: {"model": ApiErrorResponse},
            409: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
        },
    )
    async def advisor_turn(
        session_id: UUID, request: AdvisorTurnRequest
    ) -> AdvisorSnapshotResponse:
        try:
            return await service.advisor_turn(session_id, request)
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None

    @router.post(
        "/{session_id}/advisor-actions",
        response_model=AdvisorSnapshotResponse,
        responses={
            404: {"model": ApiErrorResponse},
            409: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
        },
    )
    async def advisor_action(
        session_id: UUID, request: AdvisorActionRequest
    ) -> AdvisorSnapshotResponse:
        try:
            return await service.advisor_action(session_id, request)
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None

    @router.get(
        "/{session_id}/pois",
        response_model=PoiSearchResponse,
        responses={404: {"model": ApiErrorResponse}, 410: {"model": ApiErrorResponse}},
    )
    async def search_pois(
        session_id: UUID,
        purpose: PoiPurpose,
        keywords: str = Query(min_length=1, max_length=80),
        district_adcode: str | None = Query(default=None, pattern=r"^\d{6}$"),
        center: str | None = None,
        radius_m: int | None = Query(default=None, ge=100, le=50_000),
        category_codes: tuple[str, ...] = Query(default=()),
        page: int = Query(default=1, ge=1, le=5),
        page_size: int = Query(default=20, ge=1, le=20),
    ) -> PoiSearchResponse:
        try:
            query = PoiSearchQuery(
                purpose=purpose,
                keywords=keywords,
                district_adcode=district_adcode,
                center=_center(center),
                radius_m=radius_m,
                category_codes=category_codes,
                page=page,
                page_size=page_size,
            )
        except ValidationError:
            raise input_invalid_error() from None
        try:
            return await service.search(session_id, query)
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None

    @router.post(
        "/{session_id}/map-pins",
        status_code=status.HTTP_201_CREATED,
        response_model=MapPinResponse,
        responses={404: {"model": ApiErrorResponse}, 409: {"model": ApiErrorResponse}},
    )
    async def create_map_pin(session_id: UUID, request: MapPinCreateRequest) -> MapPinResponse:
        try:
            return await service.create_map_pin(
                session_id,
                expected_revision=request.expected_revision,
                coordinate=request.coordinate,
            )
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None

    @router.put(
        "/{session_id}/trip",
        response_model=PreplanningSessionResponse,
        responses={
            404: {"model": ApiErrorResponse},
            409: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
        },
    )
    async def update_trip(
        session_id: UUID, request: PreplanningTripUpdate
    ) -> PreplanningSessionResponse:
        try:
            return await service.update_trip(session_id, request)
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None

    @router.put(
        "/{session_id}/selection",
        response_model=PreplanningSessionResponse,
        responses={
            404: {"model": ApiErrorResponse},
            409: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
        },
    )
    async def update_selection(
        session_id: UUID, request: PreplanningSelectionUpdate
    ) -> PreplanningSessionResponse:
        try:
            return await service.update_selection(session_id, request)
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None

    @router.post(
        "/{session_id}/preflight",
        response_model=PreflightResponse,
        responses={
            404: {"model": ApiErrorResponse},
            409: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
        },
    )
    async def preflight(session_id: UUID, request: PreflightRequest) -> PreflightResponse:
        try:
            return await service.preflight(
                session_id,
                expected_revision=request.expected_revision,
            )
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None

    @router.post(
        "/{session_id}/v6/preflight",
        response_model=PreflightResponseV6,
        responses={
            404: {"model": ApiErrorResponse},
            409: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
        },
    )
    async def preflight_v6(session_id: UUID, request: PreflightRequestV6) -> PreflightResponseV6:
        try:
            return await service.preflight_v6(
                session_id,
                expected_revision=request.expected_revision,
            )
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None

    @router.post(
        "/{session_id}/advisor-recovery-actions",
        response_model=PreplanningSessionResponse,
        responses={
            404: {"model": ApiErrorResponse},
            409: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
        },
    )
    async def apply_recovery_action(
        session_id: UUID, request: RecoveryActionRequestV6
    ) -> PreplanningSessionResponse:
        try:
            return await service.apply_recovery_action(session_id, request)
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None

    @router.delete(
        "/{session_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={404: {"model": ApiErrorResponse}, 410: {"model": ApiErrorResponse}},
    )
    async def delete_session(session_id: UUID) -> Response:
        try:
            await service.delete(session_id)
        except F009ServiceError as error:
            raise preplanning_http_error(error) from None
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
