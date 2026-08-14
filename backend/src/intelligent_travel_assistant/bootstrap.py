"""Local composition root with credential-safe provider startup checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from time import monotonic
from typing import Final

from intelligent_travel_assistant.adapters.providers import (
    AmapAdapter,
    AmapAdapterConfig,
    DeepSeekAdapter,
    DeepSeekAdapterConfig,
    QWeatherAdapter,
    QWeatherAdapterConfig,
)
from intelligent_travel_assistant.application.execution import PlanningJobExecutor
from intelligent_travel_assistant.application.repositories import PlanningJobRepository
from intelligent_travel_assistant.application.services import (
    OfflinePlanningOrchestrator,
    ProviderPlanningJobExecutor,
)
from intelligent_travel_assistant.application.tooling import ToolCallGovernor
from intelligent_travel_assistant.settings import Settings

MAX_PRIVATE_KEY_BYTES: Final = 16_384


class StartupConfigurationError(RuntimeError):
    """Safe startup failure that never retains a credential or filesystem detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ProviderActivationState(StrEnum):
    """Non-sensitive provider state exposed to local startup diagnostics."""

    DISABLED = "disabled"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class ProviderStartupReport:
    """Credential-free result of local provider composition."""

    deepseek: ProviderActivationState
    amap: ProviderActivationState
    qweather: ProviderActivationState


@dataclass(frozen=True, slots=True)
class ProviderAdapters:
    """Concrete adapters available to a later production planning executor."""

    report: ProviderStartupReport
    deepseek: DeepSeekAdapter | None = field(default=None, repr=False)
    amap: AmapAdapter | None = field(default=None, repr=False)
    qweather: QWeatherAdapter | None = field(default=None, repr=False)


def build_provider_adapters(settings: Settings) -> ProviderAdapters:
    """Validate complete credential groups and construct adapters without network I/O."""

    deepseek = _build_deepseek(settings)
    amap = _build_amap(settings)
    qweather = _build_qweather(settings)
    return ProviderAdapters(
        deepseek=deepseek,
        amap=amap,
        qweather=qweather,
        report=ProviderStartupReport(
            deepseek=_state(deepseek),
            amap=_state(amap),
            qweather=_state(qweather),
        ),
    )


def build_planning_job_executor(
    repository: PlanningJobRepository,
    adapters: ProviderAdapters,
) -> PlanningJobExecutor | None:
    """Enable live-capable execution only when every required adapter is present."""

    if adapters.amap is None or adapters.qweather is None or adapters.deepseek is None:
        return None
    orchestrator = OfflinePlanningOrchestrator(
        adapters.amap,
        adapters.qweather,
        adapters.deepseek,
        lambda: ToolCallGovernor(clock=monotonic),
    )
    return ProviderPlanningJobExecutor(repository, orchestrator)


def _build_deepseek(settings: Settings) -> DeepSeekAdapter | None:
    secret = settings.deepseek_api_key
    if secret is None:
        return None
    try:
        return DeepSeekAdapter(
            DeepSeekAdapterConfig(
                api_key=secret.get_secret_value(),
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_model,
            )
        )
    except (TypeError, ValueError):
        raise StartupConfigurationError("deepseek_configuration_invalid") from None


def _build_amap(settings: Settings) -> AmapAdapter | None:
    secret = settings.amap_api_key
    if secret is None:
        return None
    try:
        return AmapAdapter(AmapAdapterConfig(web_service_key=secret.get_secret_value()))
    except (TypeError, ValueError):
        raise StartupConfigurationError("amap_configuration_invalid") from None


def _build_qweather(settings: Settings) -> QWeatherAdapter | None:
    values = (
        settings.qweather_api_host,
        settings.qweather_project_id,
        settings.qweather_credential_id,
        settings.qweather_private_key_path,
    )
    configured = tuple(value is not None for value in values)
    if not any(configured):
        return None
    if not all(configured):
        raise StartupConfigurationError("qweather_configuration_incomplete")

    api_host = settings.qweather_api_host
    project_id = settings.qweather_project_id
    credential_id = settings.qweather_credential_id
    private_key_path = settings.qweather_private_key_path
    if api_host is None or project_id is None or credential_id is None or private_key_path is None:
        raise StartupConfigurationError("qweather_configuration_incomplete")

    private_key = _read_private_key(private_key_path)
    try:
        return QWeatherAdapter(
            QWeatherAdapterConfig(
                api_host=api_host,
                project_id=project_id,
                credential_id=credential_id,
                private_key_pem=private_key,
            )
        )
    except (TypeError, ValueError):
        raise StartupConfigurationError("qweather_configuration_invalid") from None


def _read_private_key(path: Path) -> bytes:
    if not path.is_absolute():
        raise StartupConfigurationError("qweather_private_key_path_invalid")
    try:
        if not path.is_file():
            raise StartupConfigurationError("qweather_private_key_unavailable")
        if path.stat().st_size > MAX_PRIVATE_KEY_BYTES:
            raise StartupConfigurationError("qweather_private_key_invalid")
        private_key = path.read_bytes()
    except StartupConfigurationError:
        raise
    except OSError:
        raise StartupConfigurationError("qweather_private_key_unavailable") from None
    if not private_key or len(private_key) > MAX_PRIVATE_KEY_BYTES:
        raise StartupConfigurationError("qweather_private_key_invalid")
    return private_key


def _state(adapter: object | None) -> ProviderActivationState:
    return ProviderActivationState.DISABLED if adapter is None else ProviderActivationState.READY
