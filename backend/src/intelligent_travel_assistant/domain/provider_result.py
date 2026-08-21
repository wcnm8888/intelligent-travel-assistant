"""Provider-neutral results, safe error policy, and deterministic freshness."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Final

from intelligent_travel_assistant.domain.foundation import (
    DomainInvariantError,
    Provider,
    SourceRecord,
)

_EXTERNAL_PROVIDERS: Final = frozenset({Provider.DEEPSEEK, Provider.AMAP, Provider.QWEATHER})
_UNSAFE_WARNING_PATTERN: Final = re.compile(
    r"https?://|authorization\s*:|(?:api[_-]?key|token|secret|password)\s*[=:]",
    re.IGNORECASE,
)


class ProviderResultStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class ProviderErrorCategory(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    SERVER = "server"
    AUTH = "auth"
    SCHEMA = "schema"
    EMPTY_RESULT = "empty_result"
    UNKNOWN = "unknown"


class ProviderErrorCode(StrEnum):
    TIMEOUT = "provider_timeout"
    RATE_LIMITED = "provider_rate_limited"
    UNAVAILABLE = "provider_unavailable"
    UNAUTHORIZED = "provider_unauthorized"
    SCHEMA_INVALID = "provider_schema_invalid"
    DATA_MISSING = "data_missing"


class ProviderErrorReason(StrEnum):
    """Safe internal diagnostic; values and upstream text are never retained."""

    REQUEST_REJECTED = "request_rejected"
    RESPONSE_TOO_LARGE = "response_too_large"
    RESPONSE_JSON_INVALID = "response_json_invalid"
    RESPONSE_ENVELOPE_INVALID = "response_envelope_invalid"
    MODEL_MISMATCH = "model_mismatch"
    CHOICES_INVALID = "choices_invalid"
    FINISH_REASON_INVALID = "finish_reason_invalid"
    MESSAGE_INVALID = "message_invalid"
    CONTENT_TOO_LARGE = "content_too_large"
    PROVIDER_ATTEMPT_TIMEOUT = "provider_attempt_timeout"
    RETRY_BUDGET_EXHAUSTED = "retry_budget_exhausted"
    RETRY_DEADLINE_EXHAUSTED = "retry_deadline_exhausted"
    RETRY_AFTER_INVALID = "retry_after_invalid"


class DataFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN_VALIDITY = "unknown_validity"


_ERROR_CODES: Final = MappingProxyType(
    {
        ProviderErrorCategory.TIMEOUT: ProviderErrorCode.TIMEOUT,
        ProviderErrorCategory.RATE_LIMITED: ProviderErrorCode.RATE_LIMITED,
        ProviderErrorCategory.SERVER: ProviderErrorCode.UNAVAILABLE,
        ProviderErrorCategory.AUTH: ProviderErrorCode.UNAUTHORIZED,
        ProviderErrorCategory.SCHEMA: ProviderErrorCode.SCHEMA_INVALID,
        ProviderErrorCategory.EMPTY_RESULT: ProviderErrorCode.DATA_MISSING,
        ProviderErrorCategory.UNKNOWN: ProviderErrorCode.UNAVAILABLE,
    }
)
_RETRYABLE_CATEGORIES: Final = frozenset(
    {
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.RATE_LIMITED,
        ProviderErrorCategory.SERVER,
    }
)


@dataclass(frozen=True, slots=True)
class ProviderError:
    """Safe project-owned classification without provider raw text."""

    category: ProviderErrorCategory
    reason: ProviderErrorReason | None = None
    retry_after_seconds: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.category, ProviderErrorCategory):
            raise DomainInvariantError("provider_error_category_invalid", field="category")
        if self.reason is not None and not isinstance(self.reason, ProviderErrorReason):
            raise DomainInvariantError("provider_error_reason_invalid", field="reason")
        if self.retry_after_seconds is not None:
            if self.category is not ProviderErrorCategory.RATE_LIMITED:
                raise DomainInvariantError(
                    "provider_retry_after_not_allowed",
                    field="retry_after_seconds",
                )
            if (
                not isinstance(self.retry_after_seconds, int | float)
                or isinstance(self.retry_after_seconds, bool)
                or not isfinite(self.retry_after_seconds)
                or not 0 <= self.retry_after_seconds <= 2
            ):
                raise DomainInvariantError(
                    "provider_retry_after_invalid",
                    field="retry_after_seconds",
                )
            object.__setattr__(self, "retry_after_seconds", float(self.retry_after_seconds))

    @property
    def code(self) -> ProviderErrorCode:
        return _ERROR_CODES[self.category]

    @property
    def retryable(self) -> bool:
        return self.category in _RETRYABLE_CATEGORIES


@dataclass(frozen=True, slots=True)
class ProviderResult[T]:
    status: ProviderResultStatus
    provider: Provider
    data: T | None
    fetched_at: datetime | None
    valid_until: datetime | None
    warnings: tuple[str, ...]
    error: ProviderError | None
    source_records: tuple[SourceRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, ProviderResultStatus):
            raise DomainInvariantError("provider_result_status_invalid", field="status")
        if self.provider not in _EXTERNAL_PROVIDERS:
            raise DomainInvariantError("external_provider_invalid", field="provider")
        _require_safe_warnings(self.warnings)
        _require_source_records(self.source_records, provider=self.provider)

        if self.status is ProviderResultStatus.OK:
            self._require_available_data()
            if self.error is not None:
                raise DomainInvariantError("ok_result_has_error", field="error")
        elif self.status is ProviderResultStatus.PARTIAL:
            self._require_available_data()
            if not isinstance(self.error, ProviderError):
                raise DomainInvariantError("partial_result_missing_error", field="error")
            if not self.warnings:
                raise DomainInvariantError("partial_result_missing_warning", field="warnings")
        else:
            if self.data is not None:
                raise DomainInvariantError("unavailable_result_has_data", field="data")
            if not isinstance(self.error, ProviderError):
                raise DomainInvariantError("unavailable_result_missing_error", field="error")
            if self.fetched_at is not None:
                raise DomainInvariantError("unavailable_result_has_fetch_time", field="fetched_at")
            if self.valid_until is not None:
                raise DomainInvariantError("unavailable_result_has_validity", field="valid_until")
            if self.source_records:
                raise DomainInvariantError("unavailable_result_has_sources", field="source_records")

    @property
    def retryable(self) -> bool:
        return self.error.retryable if self.error is not None else False

    def _require_available_data(self) -> None:
        if self.data is None:
            raise DomainInvariantError("available_result_missing_data", field="data")
        if self.fetched_at is None:
            raise DomainInvariantError("available_result_missing_fetch_time", field="fetched_at")
        _require_aware_datetime(self.fetched_at, field="fetched_at")
        if self.valid_until is not None:
            _require_aware_datetime(self.valid_until, field="valid_until")
            if self.valid_until < self.fetched_at:
                raise DomainInvariantError("source_validity_precedes_fetch", field="valid_until")
        elif not self.warnings:
            raise DomainInvariantError("unknown_validity_missing_warning", field="warnings")
        if not self.source_records:
            raise DomainInvariantError("available_result_missing_sources", field="source_records")


def evaluate_freshness(
    fetched_at: datetime,
    valid_until: datetime | None,
    evaluated_at: datetime,
) -> DataFreshness:
    _require_aware_datetime(fetched_at, field="fetched_at")
    _require_aware_datetime(evaluated_at, field="evaluated_at")
    if valid_until is not None:
        _require_aware_datetime(valid_until, field="valid_until")
        if valid_until < fetched_at:
            raise DomainInvariantError("source_validity_precedes_fetch", field="valid_until")
    if evaluated_at < fetched_at:
        raise DomainInvariantError("evaluation_precedes_fetch", field="evaluated_at")
    if valid_until is None:
        return DataFreshness.UNKNOWN_VALIDITY
    if evaluated_at <= valid_until:
        return DataFreshness.FRESH
    return DataFreshness.STALE


def _require_source_records(
    value: object,
    *,
    provider: Provider,
) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, SourceRecord) for item in value):
        raise DomainInvariantError("source_records_invalid", field="source_records")
    if len({item.source_id for item in value}) != len(value):
        raise DomainInvariantError("duplicate_source_id", field="source_records")
    if any(item.provider is not provider for item in value):
        raise DomainInvariantError("provider_source_mismatch", field="source_records")


def _require_safe_warnings(value: object) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        raise DomainInvariantError("provider_warnings_invalid", field="warnings")
    for warning in value:
        if (
            not warning.strip()
            or warning != warning.strip()
            or len(warning) > 300
            or "\n" in warning
            or "\r" in warning
            or _UNSAFE_WARNING_PATTERN.search(warning) is not None
        ):
            raise DomainInvariantError("unsafe_provider_warning", field="warnings")


def _require_aware_datetime(value: object, *, field: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DomainInvariantError("timezone_required", field=field)
