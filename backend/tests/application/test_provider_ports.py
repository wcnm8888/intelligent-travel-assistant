"""Narrow provider port contracts and dependency boundaries."""

import ast
import inspect
from collections.abc import Callable
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, Protocol, cast, get_args, get_origin, get_type_hints

import pytest

from intelligent_travel_assistant.application.ports import (
    AmapPort,
    CityResolution,
    CityResolutionRequest,
    CurrentWeatherAlertsRequest,
    DeepSeekPort,
    ModelTextOutput,
    PlanCandidate,
    PlanCandidateRepairRequest,
    PlanningContext,
    PlanningToolName,
    PoiSearchRequest,
    PoiSearchResult,
    QWeatherPort,
    RouteCalculationRequest,
    WeatherAlert,
    WeatherAlertsResult,
    WeatherForecastRequest,
    WeatherForecastResult,
)
from intelligent_travel_assistant.domain import ProviderResult, RouteLeg

PORTS_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "intelligent_travel_assistant"
    / "application"
    / "ports"
)
FORBIDDEN_IMPORT_ROOTS = {
    "fastapi",
    "httpx",
    "httpx2",
    "openai",
    "os",
    "pydantic",
    "pydantic_settings",
    "requests",
    "sqlalchemy",
    "sqlite3",
}
FORBIDDEN_PROJECT_MODULES = {
    "intelligent_travel_assistant.adapters",
    "intelligent_travel_assistant.api",
    "intelligent_travel_assistant.config",
    "intelligent_travel_assistant.infrastructure",
    "intelligent_travel_assistant.settings",
}
FORBIDDEN_PARAMETER_MARKERS = {
    "api_key",
    "authorization",
    "base_url",
    "credential",
    "header",
    "http",
    "jwt",
    "password",
    "secret",
    "token",
}


class DataclassParams(Protocol):
    frozen: bool


def test_five_tool_methods_match_the_approved_whitelist_exactly() -> None:
    tool_methods = {
        name
        for port in (AmapPort, QWeatherPort)
        for name, value in port.__dict__.items()
        if inspect.isfunction(value) and not name.startswith("_")
    }

    assert tool_methods == {item.value for item in PlanningToolName}
    assert tool_methods == {
        "resolve_city",
        "search_pois",
        "calculate_routes",
        "get_weather_forecast",
        "get_current_weather_alerts",
    }


@pytest.mark.parametrize(
    ("port", "methods"),
    [
        (AmapPort, ("resolve_city", "search_pois", "calculate_routes")),
        (
            QWeatherPort,
            ("get_weather_forecast", "get_current_weather_alerts"),
        ),
        (DeepSeekPort, ("generate_plan_candidate", "repair_plan_candidate")),
    ],
)
def test_all_provider_operations_are_async(port: type[object], methods: tuple[str, ...]) -> None:
    for method in methods:
        assert inspect.iscoroutinefunction(getattr(port, method))


@pytest.mark.parametrize(
    ("method", "request_type", "payload_type"),
    [
        (AmapPort.resolve_city, CityResolutionRequest, CityResolution),
        (AmapPort.search_pois, PoiSearchRequest, PoiSearchResult),
        (AmapPort.calculate_routes, RouteCalculationRequest, RouteLeg),
        (
            QWeatherPort.get_weather_forecast,
            WeatherForecastRequest,
            WeatherForecastResult,
        ),
        (
            QWeatherPort.get_current_weather_alerts,
            CurrentWeatherAlertsRequest,
            WeatherAlertsResult,
        ),
        (DeepSeekPort.generate_plan_candidate, PlanningContext, ModelTextOutput),
        (
            DeepSeekPort.repair_plan_candidate,
            PlanCandidateRepairRequest,
            ModelTextOutput,
        ),
    ],
)
def test_port_signatures_use_typed_requests_and_provider_results(
    method: Callable[..., object], request_type: type[object], payload_type: type[object]
) -> None:
    signature = inspect.signature(method)
    hints = get_type_hints(method)

    assert tuple(signature.parameters) == ("self", "request")
    assert hints["request"] is request_type
    assert get_origin(hints["return"]) is ProviderResult
    assert get_args(hints["return"]) == (payload_type,)


def test_port_boundary_values_are_frozen_slotted_dataclasses() -> None:
    values = (
        CityResolutionRequest,
        CityResolution,
        PoiSearchRequest,
        PoiSearchResult,
        RouteCalculationRequest,
        WeatherForecastRequest,
        WeatherForecastResult,
        CurrentWeatherAlertsRequest,
        WeatherAlert,
        WeatherAlertsResult,
        PlanningContext,
        ModelTextOutput,
        PlanCandidateRepairRequest,
        PlanCandidate,
    )
    for value in values:
        assert is_dataclass(value)
        dataclass_params = cast(DataclassParams, vars(value)["__dataclass_params__"])
        assert dataclass_params.frozen is True
        assert "__slots__" in value.__dict__


def test_deepseek_candidate_cannot_declare_terminal_status() -> None:
    assert "status" not in PlanCandidate.__dataclass_fields__
    assert "retryable" not in PlanCandidate.__dataclass_fields__
    assert "provider" not in PlanCandidate.__dataclass_fields__


def test_ports_do_not_import_framework_transport_sdk_or_configuration_modules() -> None:
    observed: list[str] = []
    for path in PORTS_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: tuple[str, ...]
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = (node.module,)
            else:
                continue
            for module in modules:
                root = module.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS or any(
                    module == forbidden or module.startswith(f"{forbidden}.")
                    for forbidden in FORBIDDEN_PROJECT_MODULES
                ):
                    observed.append(f"{path.name}:{module}")

    assert observed == []


def test_port_methods_have_no_secret_transport_or_generic_request_parameters() -> None:
    for port in (AmapPort, QWeatherPort, DeepSeekPort):
        for name, value in port.__dict__.items():
            if name.startswith("_") or not inspect.isfunction(value):
                continue
            parameters = inspect.signature(value).parameters
            assert tuple(parameters) == ("self", "request")
            joined = " ".join(parameters).lower()
            assert all(marker not in joined for marker in FORBIDDEN_PARAMETER_MARKERS)


def test_port_annotations_contain_no_any_or_mapping_payloads() -> None:
    forbidden_origins = {dict}

    def assert_safe(annotation: object) -> None:
        assert annotation is not Any
        origin = get_origin(annotation)
        assert origin not in forbidden_origins
        for argument in get_args(annotation):
            assert_safe(argument)

    for path in PORTS_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rendered = ast.unparse(tree).lower()
        assert "mapping[" not in rendered
        assert "dict[" not in rendered
        assert "request(" not in rendered

    for port in (AmapPort, QWeatherPort, DeepSeekPort):
        for name, value in port.__dict__.items():
            if name.startswith("_") or not inspect.isfunction(value):
                continue
            for annotation in get_type_hints(value).values():
                assert_safe(annotation)
