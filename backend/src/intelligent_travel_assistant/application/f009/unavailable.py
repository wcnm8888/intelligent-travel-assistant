"""Zero-network F-009 provider used when Amap configuration is absent."""

from intelligent_travel_assistant.application.f009.ports import (
    F009CityFact,
    F009MapPinFact,
    F009Narrative,
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
from intelligent_travel_assistant.contracts.f009 import Gcj02Point, PoiOption


class UnavailableF009MapProvider:
    """Return safe configuration-unavailable outcomes without I/O."""

    @staticmethod
    def _failure[T]() -> F009ProviderOutcome[T]:
        return F009ProviderOutcome(
            data=None,
            failure=F009ProviderFailure(F009ProviderFailureKind.UNKNOWN, retryable=False),
        )

    async def resolve_city(self, city: str) -> F009ProviderOutcome[F009CityFact]:
        del city
        return self._failure()

    async def search_pois(self, query: F009PoiQuery) -> F009ProviderOutcome[tuple[PoiOption, ...]]:
        del query
        return self._failure()

    async def reverse_geocode(self, coordinate: Gcj02Point) -> F009ProviderOutcome[F009MapPinFact]:
        del coordinate
        return self._failure()

    async def calculate_route(self, query: F009RouteQuery) -> F009ProviderOutcome[F009RouteFact]:
        del query
        return self._failure()


class UnavailableF009NarrativeProvider:
    """Skip model I/O and allow the deterministic plan to degrade to partial."""

    @staticmethod
    def _failure[T]() -> F009ProviderOutcome[T]:
        return F009ProviderOutcome(
            data=None,
            failure=F009ProviderFailure(F009ProviderFailureKind.UNKNOWN, retryable=False),
        )

    async def generate(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        del request
        return self._failure()

    async def repair(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        del request
        return self._failure()


class UnavailableF014AdvisorProvider:
    async def generate(self, _request: F014AdvisorRequest) -> F009ProviderOutcome[F014AdvisorDraft]:
        return F009ProviderOutcome(
            None,
            F009ProviderFailure(F009ProviderFailureKind.UNKNOWN, retryable=False),
        )

    async def repair(self, _request: F014AdvisorRequest) -> F009ProviderOutcome[F014AdvisorDraft]:
        return F009ProviderOutcome(
            None,
            F009ProviderFailure(F009ProviderFailureKind.UNKNOWN, retryable=False),
        )
