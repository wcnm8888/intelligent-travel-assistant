"""Offline regression tests for parent advisor confirmation and single-flight."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from tests.application.test_f014_advisor import prepared_service, trip

from intelligent_travel_assistant.adapters.fakes import (
    SyntheticF009MapProvider,
    SyntheticF014AdvisorProvider,
)
from intelligent_travel_assistant.adapters.fakes.f009 import SYNTHETIC_F009_POIS
from intelligent_travel_assistant.application.f009 import (
    F009PoiQuery,
    F009ProviderOutcome,
    F009ServiceError,
    F009ServiceErrorCode,
    F014AdvisorDraft,
    F014AdvisorRequest,
    PreplanningService,
)
from intelligent_travel_assistant.contracts.f009 import (
    AccommodationChoice,
    AccommodationConfidence,
    AccommodationMode,
    PoiImportance,
    PoiIntent,
    PoiOption,
    PoiPurpose,
    PoiSearchQuery,
    PreplanningSelection,
    PreplanningSelectionUpdate,
    PreplanningSessionCreateRequest,
)
from intelligent_travel_assistant.contracts.f014 import AdvisorActionRequest, AdvisorTurnRequest


def intent(location_id: UUID) -> PoiIntent:
    return PoiIntent(
        location_id=location_id,
        route_anchor_location_id=location_id,
        importance=PoiImportance.MUST_VISIT,
    )


def turn_request(revision: int) -> AdvisorTurnRequest:
    return AdvisorTurnRequest(
        advisor_version="1",
        client_request_id=uuid4(),
        expected_revision=revision,
        message="第一次来，希望少走路。",
    )


def test_complete_local_context_preserves_unsaved_poi_and_replays_acceptance() -> None:
    async def scenario() -> None:
        service, session_id = await prepared_service()
        before = await service.get(session_id)
        assert before.selection is not None
        advisor = await service.advisor_turn(session_id, turn_request(before.revision))
        suggestion = next(item for item in advisor.pending_suggestions if item.kind == "poi")
        assert suggestion.location_id is not None
        local_id = UUID("91000000-0000-4000-8000-000000000005")
        context = PreplanningSelection(
            accommodation=before.selection.accommodation,
            pois=(*before.selection.pois, intent(local_id), intent(suggestion.location_id)),
        )
        request = AdvisorActionRequest(
            advisor_version="1",
            client_request_id=uuid4(),
            expected_revision=before.revision,
            suggestion_id=suggestion.suggestion_id,
            action="accept",
            selection_context=context,
        )
        accepted = await service.advisor_action(session_id, request)
        assert await service.advisor_action(session_id, request) == accepted
        latest = await service.get(session_id)
        assert latest.selection == context
        assert latest.revision == before.revision + 1

    asyncio.run(scenario())


def test_invalid_context_preserves_pending_and_allows_corrected_retry() -> None:
    async def scenario() -> None:
        service, session_id = await prepared_service()
        before = await service.get(session_id)
        assert before.selection is not None
        advisor = await service.advisor_turn(session_id, turn_request(before.revision))
        suggestion = next(item for item in advisor.pending_suggestions if item.kind == "poi")
        context = PreplanningSelection(
            accommodation=before.selection.accommodation,
            pois=(*before.selection.pois, intent(uuid4())),
        )
        request = AdvisorActionRequest(
            advisor_version="1",
            client_request_id=uuid4(),
            expected_revision=before.revision,
            suggestion_id=suggestion.suggestion_id,
            action="accept",
            selection_context=context,
        )
        with pytest.raises(F009ServiceError) as raised:
            await service.advisor_action(session_id, request)
        assert raised.value.code is F009ServiceErrorCode.SELECTION_INVALID
        latest = await service.get(session_id)
        assert latest.selection == before.selection
        assert latest.revision == before.revision
        assert await service.get_advisor(session_id) == advisor
        corrected = request.model_copy(update={"selection_context": before.selection})
        accepted = await service.advisor_action(session_id, corrected)
        assert accepted.revision == before.revision + 1

    asyncio.run(scenario())


class ExpandedMapProvider(SyntheticF009MapProvider):
    async def search_pois(self, query: F009PoiQuery) -> F009ProviderOutcome[tuple[PoiOption, ...]]:
        if query.purpose is not PoiPurpose.VISIT:
            return await super().search_pois(query)
        template = SYNTHETIC_F009_POIS[2].model_dump()
        return F009ProviderOutcome(
            tuple(
                PoiOption.model_validate(
                    {
                        **template,
                        "location_id": UUID(int=index),
                        "provider_place_id": f"synthetic-expanded-{index}",
                        "name": f"合成景点 {index}",
                    }
                )
                for index in range(1, 11)
            )
        )


def test_null_context_cannot_append_a_ninth_poi_or_consume_pending() -> None:
    async def scenario() -> None:
        service = PreplanningService(ExpandedMapProvider(), advisor=SyntheticF014AdvisorProvider())
        created = await service.create(PreplanningSessionCreateRequest(trip=trip()))
        lodging = await service.search(
            created.session_id,
            PoiSearchQuery(purpose=PoiPurpose.ACCOMMODATION, keywords="湖滨"),
        )
        await service.search(
            created.session_id, PoiSearchQuery(purpose=PoiPurpose.VISIT, keywords="景点")
        )
        location_id = lodging.items[0].location_id
        selection = PreplanningSelection(
            accommodation=AccommodationChoice(
                mode=AccommodationMode.EXACT_POI,
                label="测试住宿",
                confidence=AccommodationConfidence.EXACT,
                semantic_location_id=location_id,
                route_anchor_location_id=location_id,
            ),
            pois=tuple(intent(UUID(int=index)) for index in range(3, 11)),
        )
        before = await service.update_selection(
            created.session_id,
            PreplanningSelectionUpdate(expected_revision=0, selection=selection),
        )
        advisor = await service.advisor_turn(created.session_id, turn_request(before.revision))
        suggestion = next(item for item in advisor.pending_suggestions if item.kind == "poi")
        with pytest.raises(F009ServiceError) as raised:
            await service.advisor_action(
                created.session_id,
                AdvisorActionRequest(
                    advisor_version="1",
                    client_request_id=uuid4(),
                    expected_revision=before.revision,
                    suggestion_id=suggestion.suggestion_id,
                    action="accept",
                ),
            )
        assert raised.value.code is F009ServiceErrorCode.SELECTION_INVALID
        latest = await service.get(created.session_id)
        assert latest.selection == selection
        assert latest.revision == before.revision
        assert await service.get_advisor(created.session_id) == advisor

    asyncio.run(scenario())


class BlockingAdvisor(SyntheticF014AdvisorProvider):
    def __init__(self) -> None:
        self.calls = 0
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, request: F014AdvisorRequest) -> F009ProviderOutcome[F014AdvisorDraft]:
        self.calls += 1
        self.entered.set()
        await self.release.wait()
        return await super().generate(request)


def test_concurrent_duplicate_turns_share_one_generation_and_conversation_pair() -> None:
    async def scenario() -> None:
        provider = BlockingAdvisor()
        service = PreplanningService(SyntheticF009MapProvider(), advisor=provider)
        session = await service.create(PreplanningSessionCreateRequest(trip=trip()))
        request = turn_request(session.revision)
        first = asyncio.create_task(service.advisor_turn(session.session_id, request))
        await provider.entered.wait()
        second = asyncio.create_task(service.advisor_turn(session.session_id, request))
        await asyncio.sleep(0)
        provider.release.set()
        responses = await asyncio.gather(first, second)
        assert provider.calls == 1
        assert responses[0] == responses[1]
        assert len(responses[0].conversation) == 2
        assert await service.advisor_turn(session.session_id, request) == responses[0]
        assert provider.calls == 1

    asyncio.run(asyncio.wait_for(scenario(), timeout=3))
