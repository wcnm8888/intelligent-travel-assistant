"""Local composition root with credential-safe provider startup checks."""

from __future__ import annotations

import sqlite3
from asyncio import sleep
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from random import uniform
from time import monotonic
from typing import Final, cast

from intelligent_travel_assistant.adapters.persistence import (
    MigrationRunner,
    SqliteConnectionConfig,
    SqliteDatabase,
    SqlitePlanningJobRepository,
)
from intelligent_travel_assistant.adapters.providers import (
    AmapAdapter,
    AmapAdapterConfig,
    DeepSeekAdapter,
    DeepSeekAdapterConfig,
    QWeatherAdapter,
    QWeatherAdapterConfig,
)
from intelligent_travel_assistant.adapters.repositories import (
    InMemoryPlanningJobRepository,
    InMemoryReplanRepository,
)
from intelligent_travel_assistant.application.execution import PlanningJobExecutor
from intelligent_travel_assistant.application.replanning import ReplanApplicationService
from intelligent_travel_assistant.application.repositories import (
    PlanningJobMaintenanceRepository,
    PlanningJobRepository,
    ReplanRepository,
)
from intelligent_travel_assistant.application.services import (
    ConfigurationMissingPlanningJobExecutor,
    MultiCityPlanningOrchestrator,
    OfflinePlanningOrchestrator,
    ProviderNeutralReplanExecutor,
    ProviderPlanningJobExecutor,
)
from intelligent_travel_assistant.application.services.provider_replan_planner import (
    ProviderReplanPlanner,
)
from intelligent_travel_assistant.application.services.provider_replanning import (
    PlanSnapshotPort,
    ReplanBudgetEffectPort,
    ReplanImpactContextPort,
)
from intelligent_travel_assistant.application.services.replan_facts import ReplanFactProjector
from intelligent_travel_assistant.application.tooling import (
    PacedAttemptLimiter,
    ProviderAttemptRuntime,
    ToolCallGovernor,
    multicity_task_timeout_seconds,
    multicity_tool_call_policies,
    multiday_task_timeout_seconds,
    multiday_tool_call_policies,
)
from intelligent_travel_assistant.domain import (
    Provider,
    ProviderOperation,
    attempt_pacing_policy_for,
)
from intelligent_travel_assistant.settings import Settings, default_local_sqlite_database_path

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


class PlanningStorageMode(StrEnum):
    """Non-sensitive production persistence selection for planning composition."""

    LIVE_MEMORY_ONLY = "live_memory_only"
    SAFE_UNAVAILABLE_SQLITE = "safe_unavailable_sqlite"


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


@dataclass(frozen=True, slots=True)
class PlanningPersistence:
    """Application-owned Repository plus optional SQLite lifecycle resources."""

    repository: PlanningJobRepository = field(repr=False)
    replan_repository: ReplanRepository | None = field(default=None, repr=False)
    storage_mode: PlanningStorageMode | None = None
    maintenance: PlanningJobMaintenanceRepository | None = field(default=None, repr=False)
    database: SqliteDatabase | None = field(default=None, repr=False)
    database_path: Path | None = field(default=None, repr=False)

    async def start(self) -> None:
        """Migrate and clean expired rows before the application serves requests."""

        if self.database is None:
            return
        path = self.database_path
        if path is None:
            raise StartupConfigurationError("sqlite_persistence_invalid")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            connection = self.database.open()
            MigrationRunner().run(connection)
            if self.maintenance is not None:
                await self.maintenance.cleanup_expired(datetime.now(UTC))
        except (OSError, sqlite3.Error, RuntimeError, ValueError):
            self.database.close()
            raise StartupConfigurationError("sqlite_persistence_unavailable") from None

    def close(self) -> None:
        """Close an owned SQLite connection without affecting injected repositories."""

        if self.database is not None:
            self.database.close()


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    """App-owned execution services and the only shared mutable route limiter."""

    planning_job_executor: PlanningJobExecutor
    replan_application_service: ReplanApplicationService | None
    route_attempt_limiter: PacedAttemptLimiter | None = field(default=None, repr=False)


def build_planning_persistence(
    settings: Settings,
    adapters: ProviderAdapters | None = None,
) -> PlanningPersistence:
    """Compose the default local Repository without opening or creating files."""

    if adapters is not None and provider_adapters_are_complete(adapters):
        return _build_live_memory_persistence()

    if settings.app_env == "test" and settings.sqlite_database_path is None:
        return PlanningPersistence(repository=InMemoryPlanningJobRepository())

    path = settings.sqlite_database_path or default_local_sqlite_database_path()
    try:
        database = SqliteDatabase(SqliteConnectionConfig(path=path))
        repository = SqlitePlanningJobRepository(database)
    except (TypeError, ValueError):
        raise StartupConfigurationError("sqlite_persistence_invalid") from None
    return PlanningPersistence(
        repository=repository,
        storage_mode=PlanningStorageMode.SAFE_UNAVAILABLE_SQLITE,
        maintenance=repository,
        database=database,
        database_path=path,
    )


def provider_adapters_are_complete(adapters: ProviderAdapters) -> bool:
    """Return whether production execution has every required Provider adapter."""

    return (
        adapters.deepseek is not None
        and adapters.amap is not None
        and adapters.qweather is not None
    )


def require_live_memory_repository(
    repository: PlanningJobRepository,
    adapters: ProviderAdapters,
) -> None:
    """Reject an injected persistence backdoor for a complete Provider composition."""

    if provider_adapters_are_complete(adapters) and not isinstance(
        repository, InMemoryPlanningJobRepository
    ):
        raise StartupConfigurationError("live_provider_persistence_must_be_memory")


def _build_live_memory_persistence() -> PlanningPersistence:
    try:
        planning_repository = InMemoryPlanningJobRepository()
        replan_repository = InMemoryReplanRepository(planning_jobs=planning_repository)
    except Exception:
        raise StartupConfigurationError("live_provider_persistence_must_be_memory") from None
    if not isinstance(planning_repository, InMemoryPlanningJobRepository) or not isinstance(
        replan_repository, InMemoryReplanRepository
    ):
        raise StartupConfigurationError("live_provider_persistence_must_be_memory")
    return PlanningPersistence(
        repository=planning_repository,
        replan_repository=replan_repository,
        storage_mode=PlanningStorageMode.LIVE_MEMORY_ONLY,
    )


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
    *,
    route_attempt_limiter: PacedAttemptLimiter | None = None,
) -> PlanningJobExecutor:
    """Compose live execution or a safe zero-call terminal executor."""

    if adapters.amap is None or adapters.qweather is None or adapters.deepseek is None:
        return ConfigurationMissingPlanningJobExecutor(repository)
    route_pacing_policy = attempt_pacing_policy_for(
        Provider.AMAP,
        ProviderOperation.CALCULATE_ROUTES,
    )
    if route_pacing_policy is None:
        raise StartupConfigurationError("amap_route_pacing_policy_missing")
    if route_attempt_limiter is None:
        route_attempt_limiter = PacedAttemptLimiter(
            provider=Provider.AMAP,
            operation=ProviderOperation.CALCULATE_ROUTES,
            policy=route_pacing_policy,
            clock=monotonic,
            sleeper=sleep,
        )
    orchestrator = OfflinePlanningOrchestrator(
        adapters.amap,
        adapters.qweather,
        adapters.deepseek,
        lambda: ToolCallGovernor(clock=monotonic),
        request_governor_factory=lambda request: ToolCallGovernor(
            clock=monotonic,
            policies=multiday_tool_call_policies(request.day_count),
            task_timeout_seconds=multiday_task_timeout_seconds(request.day_count),
        ),
    )
    multicity_orchestrator = MultiCityPlanningOrchestrator(
        adapters.amap,
        adapters.qweather,
        adapters.deepseek,
        lambda city_count, day_count: ToolCallGovernor(
            clock=monotonic,
            policies=multicity_tool_call_policies(
                city_count=city_count,
                day_count=day_count,
            ),
            task_timeout_seconds=multicity_task_timeout_seconds(
                city_count=city_count,
                day_count=day_count,
            ),
        ),
    )
    return ProviderPlanningJobExecutor(
        repository,
        orchestrator,
        multicity_orchestrator=multicity_orchestrator,
        attempt_runtime_factory=lambda timeout: ProviderAttemptRuntime(
            clock=monotonic,
            sleeper=sleep,
            jitter=lambda: uniform(0.0, 0.2),
            task_timeout_seconds=timeout,
            attempt_limiter=route_attempt_limiter,
        ),
    )


def build_application_services(
    persistence: PlanningPersistence,
    adapters: ProviderAdapters,
) -> ApplicationServices:
    """Compose default planning/replan services without transport or persistence I/O."""

    if not provider_adapters_are_complete(adapters):
        return ApplicationServices(
            build_planning_job_executor(persistence.repository, adapters), None
        )
    if (
        persistence.storage_mode is not PlanningStorageMode.LIVE_MEMORY_ONLY
        or not isinstance(persistence.repository, InMemoryPlanningJobRepository)
        or not isinstance(persistence.replan_repository, InMemoryReplanRepository)
        or persistence.replan_repository._planning_jobs is not persistence.repository
    ):
        raise StartupConfigurationError("live_provider_persistence_must_be_memory")
    route_pacing_policy = attempt_pacing_policy_for(
        Provider.AMAP,
        ProviderOperation.CALCULATE_ROUTES,
    )
    if route_pacing_policy is None:
        raise StartupConfigurationError("amap_route_pacing_policy_missing")
    route_attempt_limiter = PacedAttemptLimiter(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        policy=route_pacing_policy,
        clock=monotonic,
        sleeper=sleep,
    )
    planning_job_executor = build_planning_job_executor(
        persistence.repository,
        adapters,
        route_attempt_limiter=route_attempt_limiter,
    )
    if adapters.amap is None:
        raise StartupConfigurationError("amap_configuration_invalid")
    planner = ProviderReplanPlanner(
        amap=adapters.amap,
        deepseek=adapters.deepseek,
        qweather=adapters.qweather,
        route_limiter=route_attempt_limiter,
        clock=lambda: datetime.now(UTC),
        monotonic=monotonic,
        sleeper=sleep,
        jitter=lambda: uniform(0.0, 0.2),
    )
    facts = ReplanFactProjector()
    replan_executor = ProviderNeutralReplanExecutor(
        cast(ReplanImpactContextPort, facts),
        cast(ReplanBudgetEffectPort, facts),
        planner,
        cast(PlanSnapshotPort, facts),
        facts=facts,
        clock=lambda: datetime.now(UTC),
    )
    replan_application_service = ReplanApplicationService(
        persistence.repository,
        persistence.replan_repository,
        replan_executor,
    )
    return ApplicationServices(
        planning_job_executor,
        replan_application_service,
        route_attempt_limiter,
    )


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
