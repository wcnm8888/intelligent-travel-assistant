"""Validate the versioned, offline F-001 synthetic acceptance cases."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import pytest
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from intelligent_travel_assistant.contracts import (
    ApiErrorCode,
    BudgetAssessment,
    PlanningStatus,
    ProviderName,
    TripPlanRequest,
    TripPlanResponse,
)

FIXTURES = Path(__file__).parent / "fixtures"
REQUEST_FILE = "synthetic_hangzhou_request.json"
CASE_FILES = (
    "synthetic_hangzhou_ready.json",
    "synthetic_hangzhou_partial.json",
    "synthetic_hangzhou_conflict.json",
    "synthetic_hangzhou_needs_input.json",
    "synthetic_hangzhou_failed.json",
)
ExpectedAmount = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^(0|[1-9]\d*)(\.\d{1,2})?$"),
]


class FixtureModel(BaseModel):
    """Strict metadata shared by test-only acceptance fixture envelopes."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RequestFixture(FixtureModel):
    synthetic: Literal[True]
    fixed_now: datetime
    timezone: Literal["Asia/Shanghai"]
    request: TripPlanRequest

    @field_validator("fixed_now")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("fixed_now must include a timezone")
        return value


class AcceptanceExpectations(FixtureModel):
    expected_status: PlanningStatus
    plan_required: bool
    retryable: bool
    known_total: ExpectedAmount | None
    unknown_count: int | None = Field(ge=0)
    required_error_codes: tuple[ApiErrorCode, ...]
    required_violation_codes: tuple[str, ...]
    required_uncertainty_codes: tuple[str, ...]
    required_providers: tuple[ProviderName, ...]
    forbidden_claims: Annotated[tuple[str, ...], Field(min_length=1)]


class AcceptanceCase(FixtureModel):
    synthetic: Literal[True]
    case_id: str
    fixed_now: datetime
    request_file: Literal["synthetic_hangzhou_request.json"]
    expectations: AcceptanceExpectations
    response: TripPlanResponse

    @field_validator("fixed_now")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("fixed_now must include a timezone")
        return value


def load_json(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def request_fixture() -> RequestFixture:
    return RequestFixture.model_validate(load_json(REQUEST_FILE))


@pytest.mark.parametrize("case_file", CASE_FILES)
def test_acceptance_case_matches_the_strict_contract(
    case_file: str, request_fixture: RequestFixture
) -> None:
    case = AcceptanceCase.model_validate(load_json(case_file))
    expected = case.expectations
    response = case.response

    assert case.synthetic is True
    assert case.fixed_now == request_fixture.fixed_now
    assert response.client_request_id == request_fixture.request.client_request_id
    assert response.status is expected.expected_status
    assert response.retryable is expected.retryable
    assert (response.plan is not None) is expected.plan_required
    assert {error.code for error in response.errors} == set(expected.required_error_codes)
    assert {item.code for item in response.violations} == set(expected.required_violation_codes)
    assert {item.code for item in response.uncertainties} == set(
        expected.required_uncertainty_codes
    )
    assert set(expected.required_providers) <= {source.provider for source in response.sources}
    assert all(claim.strip() for claim in expected.forbidden_claims)
    response_text = json.dumps(response.model_dump(mode="json"), ensure_ascii=False)
    assert all(claim not in response_text for claim in expected.forbidden_claims)

    if response.plan is None:
        assert expected.known_total is None
        assert expected.unknown_count is None
    else:
        assert str(response.plan.budget_summary.known_total.amount) == expected.known_total
        assert response.plan.budget_summary.unknown_count == expected.unknown_count


def test_shared_request_freezes_the_hangzhou_two_day_reference_case(
    request_fixture: RequestFixture,
) -> None:
    request = request_fixture.request
    assert request.city == "杭州"
    assert request.start_date == request_fixture.fixed_now.date() + timedelta(days=2)
    assert request.travelers == 2
    assert len(request.day_windows) == 2
    assert {window.day_offset for window in request.day_windows} == {0, 1}
    assert str(request.meal_budget_per_person_per_day.amount) == "100.00"


def test_ready_case_is_complete_without_claiming_real_provider_evidence() -> None:
    case = AcceptanceCase.model_validate(load_json("synthetic_hangzhou_ready.json"))
    response = case.response

    assert response.status is PlanningStatus.READY
    assert response.plan is not None
    assert response.plan.budget_summary.assessment is BudgetAssessment.WITHIN_BUDGET
    assert response.plan.budget_summary.unknown_count == 0
    assert response.errors == ()
    assert response.violations == ()
    assert all(source.reference_url is None for source in response.sources)


def test_partial_case_keeps_a_plan_and_exposes_missing_evidence() -> None:
    case = AcceptanceCase.model_validate(load_json("synthetic_hangzhou_partial.json"))
    response = case.response

    assert response.status is PlanningStatus.PARTIAL
    assert response.plan is not None
    assert response.plan.budget_summary.assessment is BudgetAssessment.INDETERMINATE
    assert any(day.weather is None for day in response.plan.days)
    assert all(not day.routes for day in response.plan.days)


def test_conflict_case_never_downgrades_a_known_budget_violation() -> None:
    case = AcceptanceCase.model_validate(load_json("synthetic_hangzhou_conflict.json"))
    response = case.response

    assert response.status is PlanningStatus.CONFLICT
    assert response.plan is not None
    assert response.plan.budget_summary.assessment is BudgetAssessment.OVER_BUDGET
    assert response.plan.budget_summary.known_total.amount > response.request_summary.budget.amount
    assert response.retryable is False


def test_failed_case_has_no_plan_and_only_a_safe_retryable_error() -> None:
    case = AcceptanceCase.model_validate(load_json("synthetic_hangzhou_failed.json"))
    response = case.response

    assert response.status is PlanningStatus.FAILED
    assert response.plan is None
    assert response.retryable is True
    assert [error.code for error in response.errors] == [ApiErrorCode.PROVIDER_UNAVAILABLE]
    assert all("raw" not in error.message.lower() for error in response.errors)


def test_needs_input_case_has_no_plan_and_requires_a_new_user_decision() -> None:
    case = AcceptanceCase.model_validate(load_json("synthetic_hangzhou_needs_input.json"))
    response = case.response

    assert response.status is PlanningStatus.NEEDS_INPUT
    assert response.plan is None
    assert response.retryable is False
    assert [error.code for error in response.errors] == [ApiErrorCode.INPUT_INVALID]
    assert response.errors[0].field == "accommodation.area_or_poi"


@pytest.mark.parametrize("case_file", CASE_FILES)
def test_every_referenced_source_exists(case_file: str) -> None:
    response = AcceptanceCase.model_validate(load_json(case_file)).response
    known_source_ids = {source.source_id for source in response.sources}
    referenced_source_ids: set[UUID] = set()

    if response.resolved_destination is not None:
        referenced_source_ids.update(response.resolved_destination.source_ids)
    if response.plan is not None:
        for location in response.plan.locations:
            referenced_source_ids.update(location.source_ids)
        for cost in response.plan.budget_summary.cost_items:
            referenced_source_ids.update(cost.source_ids)
        for day in response.plan.days:
            if day.weather is not None:
                referenced_source_ids.update(day.weather.source_ids)
                for alert in day.weather.alerts:
                    referenced_source_ids.update(alert.source_ids)
            for activity in day.activities:
                referenced_source_ids.update(activity.source_ids)
                for cost in activity.cost_items:
                    referenced_source_ids.update(cost.source_ids)
            for route in day.routes:
                referenced_source_ids.update(route.source_ids)
                if route.fare is not None:
                    referenced_source_ids.update(route.fare.source_ids)
    for uncertainty in response.uncertainties:
        referenced_source_ids.update(uncertainty.source_ids)

    assert referenced_source_ids <= known_source_ids


@pytest.mark.parametrize(
    "case_file",
    (
        "synthetic_hangzhou_ready.json",
        "synthetic_hangzhou_partial.json",
        "synthetic_hangzhou_conflict.json",
    ),
)
def test_every_plan_location_reference_resolves(case_file: str) -> None:
    plan = AcceptanceCase.model_validate(load_json(case_file)).response.plan
    assert plan is not None
    known_location_ids = {location.location_id for location in plan.locations}
    referenced_location_ids: set[UUID] = set()

    for day in plan.days:
        referenced_location_ids.add(day.accommodation_location_id)
        for activity in day.activities:
            referenced_location_ids.add(activity.location_id)
        for route in day.routes:
            referenced_location_ids.add(route.origin_location_id)
            referenced_location_ids.add(route.destination_location_id)
        if day.weather is not None:
            referenced_location_ids.add(day.weather.location_id)

    assert referenced_location_ids <= known_location_ids


def test_fixture_directory_contains_only_the_approved_synthetic_set() -> None:
    observed = {path.name for path in FIXTURES.glob("*.json")}
    assert observed == {REQUEST_FILE, *CASE_FILES}

    for path in FIXTURES.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert path.name.startswith("synthetic_")
        assert '"synthetic": true' in text
        assert "http://" not in text
        assert "https://" not in text
        assert "BEGIN PRIVATE KEY" not in text
        assert "api_key" not in text.lower()


def test_fixed_clock_keeps_the_reference_dates_inside_the_approved_window(
    request_fixture: RequestFixture,
) -> None:
    start = request_fixture.request.start_date
    fixed_date: date = request_fixture.fixed_now.date()
    assert fixed_date + timedelta(days=1) <= start <= fixed_date + timedelta(days=5)
    assert start + timedelta(days=1) == date(2026, 8, 16)
