"""R5 transport-only offline composition for the formal application entrypoint."""

from __future__ import annotations

import json
import os
import socket
import tempfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx2
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.repositories import PlanningJobRepositoryError
from intelligent_travel_assistant.settings import SETTINGS_ENV_FILE, Settings

START = date.today() + timedelta(days=1)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "synthetic_hangzhou_request.json"


def request_payload(start: date = START) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(_FIXTURE.read_text(encoding="utf-8"))["request"]
    payload["client_request_id"] = str(uuid4())
    payload["start_date"] = start.isoformat()
    return payload


def _poi(provider_id: str, name: str, typecode: str, location: str) -> dict[str, object]:
    return {
        "id": provider_id,
        "name": name,
        "type": "科教文化服务;博物馆" if typecode == "140100" else "风景名胜;风景名胜",
        "typecode": typecode,
        "pname": "浙江省",
        "cityname": "杭州市",
        "adname": "西湖区",
        "address": "合成地址",
        "pcode": "330000",
        "adcode": "330100",
        "citycode": "0571",
        "location": location,
    }


@dataclass
class OfflineProviderTransport:
    """Deterministic synthetic HTTP boundary shared by all three real adapters."""

    start: date = START
    calls: list[str] = field(default_factory=list)
    failures_remaining: int = 0
    model_candidate_matches: bool = True

    def fail_next_amap_attempts(self, count: int = 2) -> None:
        self.failures_remaining = count

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        self.calls.append(path)
        if request.url.host not in {
            "restapi.amap.com",
            "api.deepseek.com",
            "r5.qweatherapi.com",
        }:
            raise AssertionError("r5_unapproved_provider_host")
        if path == "/v3/geocode/geo" and self.failures_remaining:
            self.failures_remaining -= 1
            return httpx2.Response(503)
        if path == "/v3/geocode/geo":
            return httpx2.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "count": "1",
                    "geocodes": [
                        {
                            "formatted_address": "浙江省杭州市",
                            "country": "中国",
                            "province": "浙江省",
                            "city": "杭州市",
                            "citycode": "0571",
                            "district": [],
                            "street": [],
                            "number": [],
                            "adcode": "330100",
                            "location": "120.155070,30.274085",
                            "level": "市",
                        }
                    ],
                },
            )
        if path == "/v5/place/text":
            keywords = request.url.params.get("keywords", "")
            categories = request.url.params.get("types", "")
            if keywords == "西湖附近":
                pois = [_poi("R5HOTEL", "合成住宿锚点", "110000", "120.155070,30.274085")]
            elif categories == "140100":
                pois = [
                    _poi("R5REPLACE", "合成替换博物馆", "140100", "120.170000,30.260000"),
                    _poi("R5REPLACE2", "合成备用博物馆", "140100", "120.175000,30.265000"),
                ]
            elif categories == "110000":
                pois = [
                    _poi("R5SCENIC", "合成替换景区", "110000", "120.180000,30.270000"),
                    _poi("R5SCENIC2", "合成备用景区", "110000", "120.185000,30.275000"),
                ]
            else:
                pois = [
                    _poi("R5POI01", "合成西湖一", "110000", "120.148674,30.242879"),
                    _poi("R5POI02", "合成博物馆二", "140100", "120.147350,30.252030"),
                    _poi("R5POI03", "合成西湖三", "110000", "120.160000,30.250000"),
                    _poi("R5POI04", "合成博物馆四", "140100", "120.165000,30.255000"),
                ]
            return httpx2.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "count": str(len(pois)),
                    "pois": pois,
                },
            )
        if path.startswith("/weather/v1/daily/"):
            weather_days: list[dict[str, Any]] = []
            for offset in range(7):
                local_date = self.start + timedelta(days=offset)
                weather_days.append(
                    {
                        "forecastStartTime": f"{local_date}T00:00+08:00",
                        "forecastEndTime": f"{local_date + timedelta(days=1)}T00:00+08:00",
                        "temperatureMin": {"value": 20, "unit": "°C"},
                        "temperatureMax": {"value": 30, "unit": "°C"},
                        "daytime": {"condition": {"text": "多云", "code": "101"}},
                        "nighttime": {"condition": {"text": "多云", "code": "101"}},
                    }
                )
            return httpx2.Response(
                200,
                json={
                    "metadata": {
                        "tag": "r5-synthetic",
                        "attributions": ["https://dev.qweather.com/"],
                    },
                    "days": weather_days,
                },
            )
        if path.startswith("/weatheralert/"):
            return httpx2.Response(
                200,
                json={
                    "metadata": {
                        "tag": "r5-synthetic",
                        "zeroResult": True,
                        "attributions": ["https://dev.qweather.com/"],
                    },
                    "alerts": [],
                },
            )
        if path == "/chat/completions":
            body: dict[str, Any] = json.loads(request.content)
            context: dict[str, Any] = json.loads(body["messages"][-1]["content"])
            values = context.get("repair_brief", context)
            locations = values["locations"]
            source_ids = values.get("activity_source_ids", [])
            dates = values.get("expected_dates")
            if not dates:
                first = date.fromisoformat(values["start_date"])
                last = date.fromisoformat(values["end_date"])
                dates = [
                    (first + timedelta(days=offset)).isoformat()
                    for offset in range((last - first).days + 1)
                ]
            chunk = max(1, len(locations) // len(dates))
            location_ids = tuple(str(item["location_id"]) for item in locations)
            scope = values.get("replan_selection_scope")
            if scope is not None:
                planned_lists = [list(day) for day in scope["baseline_location_ids_by_day"]]
                target_day = dates.index(scope["target_local_date"])
                target_index = scope["target_selection_index"]
                selected_location_id = scope["allowed_candidate_location_ids"][0]
                if not self.model_candidate_matches:
                    selected_location_id = planned_lists[target_day][target_index]
                planned_lists[target_day][target_index] = selected_location_id
                planned = tuple(tuple(day) for day in planned_lists)
            else:
                planned = tuple(
                    location_ids[index * chunk : (index + 1) * chunk] for index in range(len(dates))
                )
            by_id = {str(item["location_id"]): item for item in locations}
            proposal_days: list[dict[str, Any]] = []
            for index, local_date in enumerate(dates):
                selected_locations = tuple(by_id[item] for item in planned[index])
                proposal_days.append(
                    {
                        "local_date": local_date,
                        "selections": [
                            {
                                "location_id": item["location_id"],
                                "local_date": local_date,
                                "title": "合成离线活动",
                                "priority_rank": rank,
                                "selection_kind": "required",
                                "duration_class": "standard",
                                "source_ids": source_ids,
                            }
                            for rank, item in enumerate(selected_locations, start=1)
                        ],
                    }
                )
            content = json.dumps(
                {
                    "intent_summary": "R5正式组合离线计划",
                    "days": proposal_days,
                    "explanation": "仅使用合成MockTransport数据。",
                    "warnings": [],
                },
                ensure_ascii=False,
            )
            return httpx2.Response(
                200,
                json={
                    "object": "chat.completion",
                    "model": "deepseek-v4-flash",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": content},
                        }
                    ],
                },
            )
        if path in {"/v5/direction/walking", "/v5/direction/transit/integrated"}:
            key = "transits" if "transit" in path else "paths"
            route = {
                "origin": request.url.params["origin"],
                "destination": request.url.params["destination"],
                key: [
                    {
                        "distance": "1200",
                        "cost": {"duration": "900", "transit_fee": "2"},
                        "steps": [],
                        "segments": [],
                    }
                ],
            }
            return httpx2.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "count": "1",
                    "route": route,
                },
            )
        raise AssertionError(f"r5_unhandled_provider_path:{path}")


def _allowed_root(root: Path) -> Path:
    resolved = root.resolve()
    temporary = Path(tempfile.gettempdir()).resolve()
    evidence = (_PROJECT_ROOT / "output" / "f008-r5").resolve()
    if not (resolved.is_relative_to(temporary) or resolved.is_relative_to(evidence)):
        raise RuntimeError("r5_owned_output_path_required")
    return resolved


def create_production_app(root: Path, start: date = START) -> FastAPI:
    """Call create_app with settings only, then replace adapter HTTP transports."""

    if os.environ.get("APP_ENV") != "test" or SETTINGS_ENV_FILE is not None:
        raise RuntimeError("r5_test_environment_required")
    owned = _allowed_root(root)
    owned.mkdir(parents=True, exist_ok=True)
    private_key_path = owned / "synthetic-qweather-ed25519.pem"
    if not private_key_path.exists():
        private_key_path.write_bytes(
            Ed25519PrivateKey.generate().private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    settings = Settings.model_validate(
        {
            "app_env": "test",
            "sqlite_database_path": None,
            "deepseek_api_key": "r5-synthetic-deepseek",
            "amap_api_key": "r5-synthetic-amap",
            "qweather_api_host": "r5.qweatherapi.com",
            "qweather_project_id": "r5_project",
            "qweather_credential_id": "r5_credential",
            "qweather_private_key_path": private_key_path,
        }
    )
    application = create_app(settings=settings)
    transport = OfflineProviderTransport(start)
    adapters = application.state.provider_adapters
    if adapters.deepseek is None or adapters.amap is None or adapters.qweather is None:
        raise RuntimeError("r5_complete_adapters_required")
    mock = httpx2.MockTransport(transport)
    adapters.deepseek._transport = mock
    adapters.amap._transport = mock
    adapters.qweather._transport = mock
    application.state.r5_transport = transport
    application.state.r5_private_key_path = private_key_path
    return application


def create_browser_app() -> FastAPI:
    """Uvicorn factory for the formal R5 app plus the built frontend."""

    original_connect = socket.socket.connect

    def loopback_only(instance: socket.socket, address: Any) -> None:
        if not isinstance(address, tuple) or not ip_address(address[0]).is_loopback:
            raise RuntimeError("r5_non_loopback_forbidden")
        original_connect(instance, address)

    socket.socket.connect = loopback_only  # type: ignore[assignment]
    root = Path(os.environ["F008_R5_ROOT"])
    application = create_production_app(root, date.fromisoformat(os.environ["F008_R5_START"]))

    def require_local_control(request: Request) -> None:
        client = request.client
        try:
            local = client is not None and ip_address(client.host).is_loopback
        except ValueError:
            local = False
        if os.environ.get("APP_ENV") != "test" or not local:
            raise HTTPException(status_code=403, detail="r5_loopback_control_required")

    @application.get("/__r5__/diagnostics", include_in_schema=False)
    async def diagnostics(request: Request, job_id: UUID) -> dict[str, object]:
        require_local_control(request)
        try:
            job = await application.state.planning_job_repository.get(job_id)
        except PlanningJobRepositoryError:
            raise HTTPException(status_code=404, detail="job_not_found") from None
        plan = job.result.plan if job.result is not None else None
        return {
            "job_id": str(job.job_id),
            "plan_id": str(plan.plan_id) if plan is not None else None,
            "version": job.version,
            "fault_remaining": application.state.r5_transport.failures_remaining,
        }

    @application.post("/__r5__/fail-next-amap", include_in_schema=False)
    def fail_next_amap(request: Request) -> dict[str, object]:
        require_local_control(request)
        transport = application.state.r5_transport
        if transport.failures_remaining:
            raise HTTPException(status_code=409, detail="r5_failure_already_armed")
        transport.fail_next_amap_attempts()
        return {"armed": True, "attempts": 2}

    frontend = _PROJECT_ROOT / "frontend" / "dist"
    application.mount("/", StaticFiles(directory=frontend, html=True), name="r5_frontend")
    return application
