"""Provider-neutral result, error classification, and freshness rules."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from intelligent_travel_assistant.contracts import TripPlanResponse
from intelligent_travel_assistant.domain import (
    DataFreshness,
    DomainInvariantError,
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorCode,
    ProviderResult,
    ProviderResultStatus,
    SourceRecord,
    evaluate_freshness,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
FETCHED_AT = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
VALID_UNTIL = FETCHED_AT + timedelta(minutes=30)
SOURCE_ID = UUID("50000000-0000-4000-8000-000000000001")


def source(
    *,
    provider: Provider = Provider.AMAP,
    valid_until: datetime | None = VALID_UNTIL,
) -> SourceRecord:
    return SourceRecord(
        source_id=SOURCE_ID,
        provider=provider,
        source_type="synthetic_result",
        fetched_at=FETCHED_AT,
        valid_until=valid_until,
    )


def ok_result(**overrides: object) -> ProviderResult[dict[str, str]]:
    values: dict[str, object] = {
        "status": ProviderResultStatus.OK,
        "provider": Provider.AMAP,
        "data": {"city": "杭州"},
        "fetched_at": FETCHED_AT,
        "valid_until": VALID_UNTIL,
        "warnings": (),
        "error": None,
        "source_records": (source(),),
    }
    values.update(overrides)
    return ProviderResult(**values)  # type: ignore[arg-type]


def test_ok_partial_and_unavailable_results_have_distinct_legal_shapes() -> None:
    ok = ok_result()
    partial = ok_result(
        status=ProviderResultStatus.PARTIAL,
        error=ProviderError(ProviderErrorCategory.TIMEOUT),
        warnings=("路线数据部分缺失",),
    )
    unavailable = ProviderResult[dict[str, str]](
        status=ProviderResultStatus.UNAVAILABLE,
        provider=Provider.DEEPSEEK,
        data=None,
        fetched_at=None,
        valid_until=None,
        warnings=("模型暂时不可用",),
        error=ProviderError(ProviderErrorCategory.SERVER),
        source_records=(),
    )

    assert ok.error is None
    assert partial.data == {"city": "杭州"}
    assert unavailable.data is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"data": None},
        {"error": ProviderError(ProviderErrorCategory.TIMEOUT)},
        {"fetched_at": None},
        {"source_records": ()},
    ],
)
def test_ok_result_rejects_missing_success_evidence_or_an_error(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(DomainInvariantError):
        ok_result(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": ProviderResultStatus.PARTIAL},
        {
            "status": ProviderResultStatus.PARTIAL,
            "data": None,
            "error": ProviderError(ProviderErrorCategory.TIMEOUT),
        },
    ],
)
def test_partial_requires_both_usable_data_and_a_stable_error(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(DomainInvariantError):
        ok_result(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"error": None},
        {"data": {"fake": "success"}},
        {"fetched_at": FETCHED_AT},
        {"valid_until": VALID_UNTIL},
        {"source_records": (source(provider=Provider.DEEPSEEK),)},
    ],
)
def test_unavailable_rejects_success_data_time_or_sources(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "status": ProviderResultStatus.UNAVAILABLE,
        "provider": Provider.DEEPSEEK,
        "data": None,
        "fetched_at": None,
        "valid_until": None,
        "warnings": (),
        "error": ProviderError(ProviderErrorCategory.SERVER),
        "source_records": (),
    }
    values.update(overrides)
    with pytest.raises(DomainInvariantError):
        ProviderResult(**values)  # type: ignore[arg-type]


def test_available_result_with_unknown_validity_requires_a_warning() -> None:
    with pytest.raises(DomainInvariantError) as error:
        ok_result(valid_until=None, warnings=())
    assert error.value.code == "unknown_validity_missing_warning"

    result = ok_result(valid_until=None, warnings=("数据有效期未知",))
    assert result.valid_until is None


def test_external_result_rejects_user_or_system_and_mismatched_sources() -> None:
    with pytest.raises(DomainInvariantError) as error:
        ok_result(provider=Provider.USER)
    assert error.value.code == "external_provider_invalid"

    with pytest.raises(DomainInvariantError) as error:
        ok_result(source_records=(source(provider=Provider.QWEATHER),))
    assert error.value.code == "provider_source_mismatch"


@pytest.mark.parametrize(
    ("category", "expected_code", "retryable"),
    [
        (ProviderErrorCategory.TIMEOUT, ProviderErrorCode.TIMEOUT, True),
        (ProviderErrorCategory.RATE_LIMITED, ProviderErrorCode.RATE_LIMITED, True),
        (ProviderErrorCategory.SERVER, ProviderErrorCode.UNAVAILABLE, True),
        (ProviderErrorCategory.AUTH, ProviderErrorCode.UNAUTHORIZED, False),
        (ProviderErrorCategory.SCHEMA, ProviderErrorCode.SCHEMA_INVALID, False),
        (ProviderErrorCategory.EMPTY_RESULT, ProviderErrorCode.DATA_MISSING, False),
        (ProviderErrorCategory.UNKNOWN, ProviderErrorCode.UNAVAILABLE, False),
    ],
)
def test_error_category_controls_safe_code_and_retryability(
    category: ProviderErrorCategory,
    expected_code: ProviderErrorCode,
    retryable: bool,
) -> None:
    error = ProviderError(category)
    assert error.code is expected_code
    assert error.retryable is retryable


@pytest.mark.parametrize(
    ("evaluated_at", "expected"),
    [
        (VALID_UNTIL - timedelta(microseconds=1), DataFreshness.FRESH),
        (VALID_UNTIL, DataFreshness.FRESH),
        (VALID_UNTIL + timedelta(microseconds=1), DataFreshness.STALE),
    ],
)
def test_freshness_boundary_is_inclusive_at_valid_until(
    evaluated_at: datetime, expected: DataFreshness
) -> None:
    assert evaluate_freshness(FETCHED_AT, VALID_UNTIL, evaluated_at) is expected


def test_unknown_validity_is_explicit_and_does_not_read_system_time() -> None:
    assert (
        evaluate_freshness(
            FETCHED_AT,
            None,
            datetime(2099, 1, 1, tzinfo=UTC),
        )
        is DataFreshness.UNKNOWN_VALIDITY
    )


@pytest.mark.parametrize(
    ("fetched_at", "valid_until", "evaluated_at", "expected_code"),
    [
        (
            datetime(2026, 8, 13, 10, 0),
            VALID_UNTIL,
            VALID_UNTIL,
            "timezone_required",
        ),
        (
            FETCHED_AT,
            datetime(2026, 8, 13, 10, 30),
            VALID_UNTIL,
            "timezone_required",
        ),
        (
            FETCHED_AT,
            VALID_UNTIL,
            datetime(2026, 8, 13, 10, 30),
            "timezone_required",
        ),
        (
            FETCHED_AT,
            FETCHED_AT - timedelta(microseconds=1),
            FETCHED_AT,
            "source_validity_precedes_fetch",
        ),
        (
            FETCHED_AT,
            VALID_UNTIL,
            FETCHED_AT - timedelta(microseconds=1),
            "evaluation_precedes_fetch",
        ),
    ],
)
def test_freshness_rejects_naive_or_impossible_timestamps(
    fetched_at: datetime,
    valid_until: datetime | None,
    evaluated_at: datetime,
    expected_code: str,
) -> None:
    with pytest.raises(DomainInvariantError) as error:
        evaluate_freshness(fetched_at, valid_until, evaluated_at)
    assert error.value.code == expected_code


@pytest.mark.parametrize(
    "warning",
    [
        "https://provider.example/private?key=secret",
        "Authorization: Bearer secret",
        "api_key=secret",
        "line one\nraw body",
        "x" * 301,
    ],
)
def test_warnings_reject_urls_secret_markers_multiline_and_oversize_text(
    warning: str,
) -> None:
    with pytest.raises(DomainInvariantError) as error:
        ok_result(warnings=(warning,))
    assert error.value.code == "unsafe_provider_warning"


def provider_from_contract(value: object) -> Provider:
    return Provider(str(value))


@pytest.mark.parametrize(
    "fixture_name",
    [
        "synthetic_hangzhou_ready.json",
        "synthetic_hangzhou_partial.json",
        "synthetic_hangzhou_failed.json",
    ],
)
def test_synthetic_source_freshness_recomputes_without_drift(fixture_name: str) -> None:
    fixture = json.loads((FIXTURE_ROOT / fixture_name).read_text(encoding="utf-8"))
    response = TripPlanResponse.model_validate(fixture["response"])

    for item in response.sources:
        freshness = evaluate_freshness(
            item.fetched_at,
            item.valid_until,
            response.updated_at,
        )
        assert freshness.value == item.freshness.value


def test_synthetic_provider_errors_follow_retry_policy() -> None:
    partial_fixture = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_partial.json").read_text(encoding="utf-8")
    )
    failed_fixture = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_failed.json").read_text(encoding="utf-8")
    )
    partial = TripPlanResponse.model_validate(partial_fixture["response"])
    failed = TripPlanResponse.model_validate(failed_fixture["response"])

    timeout = ProviderError(ProviderErrorCategory.TIMEOUT)
    server = ProviderError(ProviderErrorCategory.SERVER)
    assert timeout.code.value == partial.errors[0].code.value
    assert timeout.retryable is partial.errors[0].retryable
    assert server.code.value == failed.errors[0].code.value
    assert server.retryable is failed.errors[0].retryable
