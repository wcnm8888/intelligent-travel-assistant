"""R5 formal-entry offline journeys with only Provider HTTP transport replaced."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from tests.browser_f008_production_support import (
    create_browser_app,
    create_production_app,
    request_payload,
)

from intelligent_travel_assistant.application.services import ProviderNeutralReplanExecutor
from intelligent_travel_assistant.application.services.provider_replan_planner import (
    ProviderReplanPlanner,
)
from intelligent_travel_assistant.bootstrap import PlanningStorageMode


def _create_plan(client: TestClient) -> tuple[str, dict[str, Any]]:
    created = client.post("/api/trip-plans", json=request_payload())
    assert created.status_code == 202
    url = f"/api/trip-plans/{created.json()['job_id']}"
    current: dict[str, Any] = client.get(url).json()
    assert current["status"] in {"ready", "partial"}, {
        key: current[key] for key in ("status", "errors", "warnings", "violations")
    }
    assert current["plan"] is not None
    return url, current


def _command(plan: dict[str, Any], operation: str) -> dict[str, Any]:
    day = plan["days"][0]
    target = day["activities"][0]
    if operation == "replace_activity":
        return {
            "operation": operation,
            "target_activity_id": target["item_id"],
            "replacement_categories": ["museum"],
        }
    if operation == "delete_activity":
        return {"operation": operation, "target_activity_id": target["item_id"]}
    if operation == "adjust_activity_time":
        start = datetime.strptime(target["start_time"], "%H:%M:%S")
        end = datetime.strptime(target["end_time"], "%H:%M:%S") - timedelta(minutes=15)
        assert end > start
        return {
            "operation": operation,
            "target_activity_id": target["item_id"],
            "start_time": target["start_time"],
            "end_time": end.time().isoformat(),
        }
    assert operation == "reorder_activities"
    identifiers = [item["item_id"] for item in day["activities"]]
    assert len(identifiers) == 2
    return {
        "operation": operation,
        "local_date": day["local_date"],
        "ordered_activity_ids": list(reversed(identifiers)),
    }


def _create_replan(
    client: TestClient,
    url: str,
    baseline: dict[str, Any],
    command: dict[str, Any],
    *,
    request_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = {
        "replan_request_id": request_id or str(uuid4()),
        "baseline_plan_id": baseline["plan"]["plan_id"],
        "command": command,
    }
    response = client.post(f"{url}/replans", json=payload)
    assert response.status_code == 202
    return payload, response.json()


def _approve_and_read(client: TestClient, url: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    replan_url = f"{url}/replans/{snapshot['replan_id']}"
    if snapshot["status"] == "awaiting_confirmation":
        decision = client.post(f"{replan_url}/decision", json={"choice": "approve"})
        assert decision.status_code == 202
    terminal: dict[str, Any] = client.get(replan_url).json()
    assert terminal["status"] not in {"analyzing", "replanning"}
    return terminal


def _assert_current_matches_result(current: dict[str, Any], result: dict[str, Any]) -> None:
    current_stable = copy.deepcopy(current)
    result_stable = copy.deepcopy(result)
    current_updated = datetime.fromisoformat(current_stable.pop("updated_at"))
    result_updated = datetime.fromisoformat(result_stable.pop("updated_at"))
    assert current_stable == result_stable
    assert current_updated.utcoffset() is not None
    assert result_updated.utcoffset() is not None
    assert current_updated >= result_updated


def _assert_operation_effect(
    operation: str, baseline: dict[str, Any], result: dict[str, Any]
) -> None:
    before = baseline["plan"]["days"][0]["activities"]
    after = result["plan"]["days"][0]["activities"]
    if operation == "replace_activity":
        assert after[0]["location_id"] != before[0]["location_id"]
        assert "合成替换博物馆" in after[0]["title"]
    elif operation == "delete_activity":
        assert len(after) == len(before) - 1
        assert before[0]["item_id"] not in {item["item_id"] for item in after}
    elif operation == "adjust_activity_time":
        assert after[0]["end_time"] != before[0]["end_time"]
    else:
        assert [item["item_id"] for item in after] == [item["item_id"] for item in reversed(before)]


def test_formal_entry_runs_all_four_commands_without_business_injection(
    tmp_path: Any,
) -> None:
    for operation in (
        "replace_activity",
        "delete_activity",
        "adjust_activity_time",
        "reorder_activities",
    ):
        application = create_production_app(tmp_path / operation)
        assert not hasattr(application.state.r5_transport, "planned_location_ids")
        assert application.state.planning_persistence.database is None
        assert application.state.planning_storage_mode is PlanningStorageMode.LIVE_MEMORY_ONLY
        service = application.state.replan_application_service
        assert service is not None
        assert isinstance(service._executor, ProviderNeutralReplanExecutor)
        assert service._planning_jobs is application.state.planning_job_repository
        assert service._replans is application.state.replan_repository
        assert isinstance(service._executor._planner, ProviderReplanPlanner)
        assert service._executor._planner.route_limiter is application.state.route_attempt_limiter
        sqlite_calls = 0

        def forbidden_sqlite(*_args: object, **_kwargs: object) -> None:
            nonlocal sqlite_calls
            sqlite_calls += 1
            raise AssertionError("r5_live_sqlite_forbidden")

        with (
            patch("sqlite3.connect", forbidden_sqlite),
            TestClient(application) as client,
        ):
            url, baseline = _create_plan(client)
            preserved = copy.deepcopy(baseline)
            command = _command(baseline["plan"], operation)
            _, pending = _create_replan(client, url, baseline, command)
            terminal = _approve_and_read(client, url, pending)
            assert terminal["status"] == "completed", terminal.get("errors")
            assert terminal["result"] is not None and terminal["change_set"] is not None
            current = client.get(url).json()
            _assert_current_matches_result(current, terminal["result"])
            assert current["plan"]["plan_id"] != baseline["plan"]["plan_id"]
            _assert_operation_effect(operation, preserved, current)
        assert sqlite_calls == 0
        assert application.state.r5_transport.calls


def test_formal_entry_consecutive_replacements_keep_requested_provider_category(
    tmp_path: Any,
) -> None:
    application = create_production_app(tmp_path / "replacement-categories")
    sqlite_calls = 0

    def forbidden_sqlite(*_args: object, **_kwargs: object) -> None:
        nonlocal sqlite_calls
        sqlite_calls += 1
        raise AssertionError("r5_live_sqlite_forbidden")

    with patch("sqlite3.connect", forbidden_sqlite), TestClient(application) as client:
        url, baseline = _create_plan(client)
        _, pending_museum = _create_replan(
            client, url, baseline, _command(baseline["plan"], "replace_activity")
        )
        museum = _approve_and_read(client, url, pending_museum)
        assert museum["status"] == "completed", museum.get("errors")
        after_museum = client.get(url).json()
        _assert_current_matches_result(after_museum, museum["result"])
        museum_activity = after_museum["plan"]["days"][0]["activities"][0]
        target = after_museum["plan"]["days"][1]["activities"][0]
        scenic_command = {
            "operation": "replace_activity",
            "target_activity_id": target["item_id"],
            "replacement_categories": ["scenic_area"],
        }
        _, pending_scenic = _create_replan(client, url, after_museum, scenic_command)
        scenic = _approve_and_read(client, url, pending_scenic)
        assert scenic["status"] == "completed", scenic.get("errors")
        current = client.get(url).json()
        _assert_current_matches_result(current, scenic["result"])
        scenic_activity = current["plan"]["days"][1]["activities"][0]
        locations = {item["location_id"]: item for item in current["plan"]["locations"]}
        assert scenic_activity["title"] == "合成替换景区"
        assert locations[scenic_activity["location_id"]]["category"] == "scenic_area"
        assert scenic_activity["location_id"] != museum_activity["location_id"]
        source_ids = {item["source_id"] for item in current["sources"]}
        assert set(museum_activity["source_ids"] + scenic_activity["source_ids"]) <= source_ids
        assert current["plan"]["days"][0] == after_museum["plan"]["days"][0]
        before_tail = after_museum["plan"]["days"][1]["activities"][1:]
        after_tail = current["plan"]["days"][1]["activities"][1:]
        assert after_tail == before_tail
        before_budget = after_museum["plan"]["budget_summary"]
        after_budget = current["plan"]["budget_summary"]
        assert after_budget["unknown_count"] == before_budget["unknown_count"] + 1
        assert after_budget["assessment"] == "budget_indeterminate"
        assert after_budget["cost_items"][-1]["amount"] is None
        assert current["plan"]["plan_id"] != after_museum["plan"]["plan_id"]
    assert sqlite_calls == 0


def test_formal_entry_failure_keeps_plan_and_new_request_recovers(tmp_path: Any) -> None:
    application = create_production_app(tmp_path / "recovery")
    with TestClient(application) as client:
        url, baseline = _create_plan(client)
        command = _command(baseline["plan"], "replace_activity")
        application.state.r5_transport.fail_next_amap_attempts()
        _, first = _create_replan(client, url, baseline, command)
        failed = _approve_and_read(client, url, first)
        assert failed["status"] == "failed"
        assert failed["errors"][0]["retryable"] is True
        assert client.get(url).json() == baseline

        _, second = _create_replan(client, url, baseline, command)
        completed = _approve_and_read(client, url, second)
        assert completed["status"] == "completed", completed.get("errors")
        assert client.get(f"{url}/replans/{first['replan_id']}").json() == failed
        _assert_current_matches_result(client.get(url).json(), completed["result"])


@pytest.mark.parametrize("deleted_index", [0, 1])
def test_continuous_edits_then_fault_recovers_with_new_request(
    tmp_path: Path, deleted_index: int
) -> None:
    application = create_production_app(tmp_path / "continuous-recovery")
    trace: list[dict[str, Any]] = []
    with patch("sqlite3.connect", side_effect=AssertionError("sqlite_forbidden")):
        with TestClient(application) as client:
            url, initial = _create_plan(client)

            def execute(command: dict[str, Any], label: str) -> dict[str, Any]:
                baseline = client.get(url).json()
                transport = application.state.r5_transport
                assert client.portal is not None
                repository = application.state.planning_job_repository
                job = client.portal.call(repository.get, UUID(initial["job_id"]))
                before_count = transport.failures_remaining
                call_start = len(transport.calls)
                payload, pending = _create_replan(client, url, baseline, command)
                terminal = _approve_and_read(client, url, pending)
                after = client.get(url).json()
                after_job = client.portal.call(repository.get, job.job_id)
                row = {
                    "step": label,
                    "request_id": payload["replan_request_id"],
                    "returned_request_id": terminal["replan_request_id"],
                    "status": terminal["status"],
                    "errors": terminal["errors"],
                    "plan_before": baseline["plan"]["plan_id"],
                    "plan_after": after["plan"]["plan_id"],
                    "version_before": job.version,
                    "version_after": after_job.version,
                    "fault_before": before_count,
                    "fault_after": transport.failures_remaining,
                    "old_plan_unchanged": after == baseline,
                    "provider_paths": transport.calls[call_start:],
                }
                trace.append(row)
                (tmp_path / "journey.json").write_text(
                    json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(json.dumps(row, ensure_ascii=False))
                assert payload["replan_request_id"] == terminal["replan_request_id"]
                return terminal

            for day_index, category in ((0, "museum"), (1, "scenic_area")):
                current = client.get(url).json()
                target = current["plan"]["days"][day_index]["activities"][0]
                terminal = execute(
                    {
                        "operation": "replace_activity",
                        "target_activity_id": target["item_id"],
                        "replacement_categories": [category],
                    },
                    category,
                )
                assert terminal["status"] == "completed", terminal["errors"]
            current = client.get(url).json()
            target = current["plan"]["days"][0]["activities"][deleted_index]
            deleted = execute(
                {"operation": "delete_activity", "target_activity_id": target["item_id"]},
                "delete",
            )
            assert deleted["status"] == "completed", deleted["errors"]
            current = client.get(url).json()
            day = current["plan"]["days"][1]
            adjusted = execute(
                {
                    "operation": "adjust_activity_time",
                    "target_activity_id": day["activities"][0]["item_id"],
                    "start_time": "09:45:00",
                    "end_time": "11:45:00",
                },
                "adjust",
            )
            assert adjusted["status"] == "completed", adjusted["errors"]
            reordered = execute(
                {
                    "operation": "reorder_activities",
                    "local_date": day["local_date"],
                    "ordered_activity_ids": [a["item_id"] for a in reversed(day["activities"])],
                },
                "reorder",
            )
            assert reordered["status"] == "completed", reordered["errors"]
            baseline = client.get(url).json()
            command = _command(baseline["plan"], "replace_activity")
            application.state.r5_transport.fail_next_amap_attempts()
            failed = execute(command, "fault")
            recovered = execute(command, "recovery")
            if recovered["status"] != "completed":
                execute(command, "recovery_probe")
            assert failed["status"] == "failed" and failed["errors"][0]["retryable"]
            fault = next(row for row in trace if row["step"] == "fault")
            assert fault["fault_before"] == 2 and fault["fault_after"] == 0
            assert fault["old_plan_unchanged"]
            assert fault["version_before"] == fault["version_after"]
            assert fault["errors"][0]["code"] == "provider_unavailable"
            assert fault["errors"][0]["diagnostic_code"] == "provider_unavailable"
            assert recovered["replan_request_id"] != failed["replan_request_id"]
            assert recovered["status"] == "completed", recovered["errors"]
            assert not trace[-1]["old_plan_unchanged"]
            assert trace[-1]["version_after"] == trace[-1]["version_before"] + 1
            assert client.get(f"{url}/replans/{failed['replan_id']}").json() == failed
            _assert_current_matches_result(client.get(url).json(), recovered["result"])


def test_exhausted_replacement_pool_requires_input_without_changing_plan(tmp_path: Path) -> None:
    application = create_production_app(tmp_path / "finite-candidates")
    with TestClient(application) as client:
        url, current = _create_plan(client)
        for expected_title in ("合成替换博物馆", "合成备用博物馆"):
            _, pending = _create_replan(
                client, url, current, _command(current["plan"], "replace_activity")
            )
            terminal = _approve_and_read(client, url, pending)
            assert terminal["status"] == "completed", terminal["errors"]
            current = client.get(url).json()
            assert current["plan"]["days"][0]["activities"][0]["title"] == expected_title
        before = copy.deepcopy(current)
        call_start = len(application.state.r5_transport.calls)
        _, pending = _create_replan(
            client, url, current, _command(current["plan"], "replace_activity")
        )
        exhausted = _approve_and_read(client, url, pending)
        assert exhausted["status"] == "needs_input"
        assert exhausted["errors"][0]["code"] == "data_missing"
        assert exhausted["errors"][0]["retryable"] is False
        assert "/chat/completions" not in application.state.r5_transport.calls[call_start:]
        assert client.get(url).json() == before


def test_formal_entry_replace_preserves_unrelated_unknown_intercity_cost(tmp_path: Any) -> None:
    application = create_production_app(tmp_path / "unknown-intercity")
    with TestClient(application) as client:
        payload = request_payload()
        payload["intercity_transport_cost"] = None
        created = client.post("/api/trip-plans", json=payload)
        assert created.status_code == 202
        url = f"/api/trip-plans/{created.json()['job_id']}"
        baseline: dict[str, Any] = client.get(url).json()
        assert baseline["plan"] is not None
        intercity = next(
            cost
            for cost in baseline["plan"]["budget_summary"]["cost_items"]
            if cost["category"] == "intercity_transport"
        )
        assert intercity["confidence"] == "unknown" and intercity["amount"] is None

        _, pending = _create_replan(
            client,
            url,
            baseline,
            _command(baseline["plan"], "replace_activity"),
        )
        terminal = _approve_and_read(client, url, pending)

        assert terminal["status"] == "completed", terminal.get("errors")
        result = terminal["result"]
        assert result is not None
        preserved = next(
            cost
            for cost in result["plan"]["budget_summary"]["cost_items"]
            if cost["category"] == "intercity_transport"
        )
        assert preserved == intercity
        additions = result["uncertainties"][len(baseline["uncertainties"]) :]
        assert any(item["code"] == "budget_indeterminate" for item in additions)
        assert all(intercity["cost_id"] not in item["affected_refs"] for item in additions)


def test_formal_entry_replace_then_cancel_and_complete_delete_on_same_job(tmp_path: Any) -> None:
    application = create_production_app(tmp_path / "replace-delete")
    assert application.state.planning_persistence.database is None
    assert application.state.planning_storage_mode is PlanningStorageMode.LIVE_MEMORY_ONLY
    sqlite_calls = 0

    def forbidden_sqlite(*_args: object, **_kwargs: object) -> None:
        nonlocal sqlite_calls
        sqlite_calls += 1
        raise AssertionError("r5_live_sqlite_forbidden")

    with patch("sqlite3.connect", forbidden_sqlite), TestClient(application) as client:
        url, baseline = _create_plan(client)
        _, pending_replace = _create_replan(
            client,
            url,
            baseline,
            _command(baseline["plan"], "replace_activity"),
        )
        replaced = _approve_and_read(client, url, pending_replace)
        assert replaced["status"] == "completed", replaced.get("errors")
        replace_url = f"{url}/replans/{pending_replace['replan_id']}"
        replaced_snapshot = copy.deepcopy(replaced)
        replaced_current = client.get(url).json()
        _assert_current_matches_result(replaced_current, replaced["result"])

        delete_command = _command(replaced_current["plan"], "delete_activity")
        _, pending_cancel = _create_replan(client, url, replaced_current, delete_command)
        cancel_url = f"{url}/replans/{pending_cancel['replan_id']}"
        cancelled = client.post(f"{cancel_url}/decision", json={"choice": "cancel"})
        assert cancelled.status_code == 200
        cancelled_snapshot = client.get(cancel_url).json()
        assert cancelled_snapshot["status"] == "cancelled"
        assert client.get(url).json() == replaced_current

        _, pending_delete = _create_replan(client, url, replaced_current, delete_command)
        deleted = _approve_and_read(client, url, pending_delete)

        assert deleted["status"] == "completed", deleted.get("errors")
        assert deleted["errors"] == []
        assert client.get(cancel_url).json() == cancelled_snapshot
        current = client.get(url).json()
        _assert_current_matches_result(current, deleted["result"])
        _assert_operation_effect("delete_activity", replaced_current, current)
        delete_url = f"{url}/replans/{pending_delete['replan_id']}"
        deleted_snapshot = copy.deepcopy(deleted)

        _, pending_adjust = _create_replan(
            client,
            url,
            current,
            _command(current["plan"], "adjust_activity_time"),
        )
        adjusted = _approve_and_read(client, url, pending_adjust)
        assert adjusted["status"] == "completed", adjusted.get("errors")
        adjusted_current = client.get(url).json()
        _assert_current_matches_result(adjusted_current, adjusted["result"])
        _assert_operation_effect("adjust_activity_time", current, adjusted_current)

        reorder_day = adjusted_current["plan"]["days"][1]
        reorder_ids = [activity["item_id"] for activity in reorder_day["activities"]]
        assert len(reorder_ids) == 2
        reorder_command = {
            "operation": "reorder_activities",
            "local_date": reorder_day["local_date"],
            "ordered_activity_ids": list(reversed(reorder_ids)),
        }
        _, pending_reorder = _create_replan(
            client,
            url,
            adjusted_current,
            reorder_command,
        )
        reordered = _approve_and_read(client, url, pending_reorder)
        assert reordered["status"] == "completed", reordered.get("errors")
        reordered_current = client.get(url).json()
        _assert_current_matches_result(reordered_current, reordered["result"])
        assert [
            activity["item_id"] for activity in reordered_current["plan"]["days"][1]["activities"]
        ] == list(reversed(reorder_ids))
        assert client.get(replace_url).json() == replaced_snapshot
        assert client.get(cancel_url).json() == cancelled_snapshot
        assert client.get(delete_url).json() == deleted_snapshot
    assert sqlite_calls == 0


def test_formal_entry_mismatched_replace_candidate_fails_closed(tmp_path: Any) -> None:
    for after_retryable_failure in (False, True):
        application = create_production_app(tmp_path / str(after_retryable_failure))
        with TestClient(application) as client:
            url, baseline = _create_plan(client)
            command = _command(baseline["plan"], "replace_activity")
            if after_retryable_failure:
                application.state.r5_transport.fail_next_amap_attempts()
                _, first = _create_replan(client, url, baseline, command)
                failed = _approve_and_read(client, url, first)
                assert failed["status"] == "failed"
                assert client.get(url).json() == baseline
            application.state.r5_transport.model_candidate_matches = False
            _, pending = _create_replan(client, url, baseline, command)
            failed_scope = _approve_and_read(client, url, pending)
            assert failed_scope["status"] == "failed"
            assert failed_scope["errors"][0]["code"] == "model_output_invalid"
            assert failed_scope["errors"][0]["diagnostic_code"] == "model_output_invalid"
            assert failed_scope["errors"][0]["retryable"] is False
            assert client.get(url).json() == baseline


def test_formal_entry_idempotency_cancel_and_competing_commits(tmp_path: Any) -> None:
    application = create_production_app(tmp_path / "idempotency")
    with TestClient(application) as client:
        url, baseline = _create_plan(client)
        first_command = _command(baseline["plan"], "delete_activity")
        first_id = str(uuid4())
        payload, first = _create_replan(client, url, baseline, first_command, request_id=first_id)
        repeated = client.post(f"{url}/replans", json=payload)
        assert repeated.status_code == 202
        assert repeated.json()["replan_id"] == first["replan_id"]

        changed = copy.deepcopy(payload)
        changed["command"] = _command(baseline["plan"], "adjust_activity_time")
        conflict = client.post(f"{url}/replans", json=changed)
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "replan_idempotency_conflict"

        _, competing = _create_replan(
            client,
            url,
            baseline,
            _command(baseline["plan"], "adjust_activity_time"),
        )
        first_terminal = _approve_and_read(client, url, first)
        assert first_terminal["status"] == "completed"
        second_decision = client.post(
            f"{url}/replans/{competing['replan_id']}/decision",
            json={"choice": "approve"},
        )
        assert second_decision.status_code == 409
        _assert_current_matches_result(client.get(url).json(), first_terminal["result"])

    cancelled_app = create_production_app(tmp_path / "cancel")
    with TestClient(cancelled_app) as client:
        url, baseline = _create_plan(client)
        _, pending = _create_replan(
            client, url, baseline, _command(baseline["plan"], "delete_activity")
        )
        replan_url = f"{url}/replans/{pending['replan_id']}"
        cancelled = client.post(f"{replan_url}/decision", json={"choice": "cancel"})
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert client.get(url).json() == baseline


def test_browser_failure_control_is_test_only_loopback_and_bounded(
    tmp_path: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("F008_R5_ROOT", str(tmp_path / "browser-control"))
    monkeypatch.setenv("F008_R5_START", "2026-09-10")
    application = create_browser_app()

    with TestClient(application, client=("127.0.0.1", 50000)) as client:
        armed = client.post("/__r5__/fail-next-amap")
        assert armed.status_code == 200
        assert armed.json() == {"armed": True, "attempts": 2}
        assert application.state.r5_transport.failures_remaining == 2
        assert client.post("/__r5__/fail-next-amap").status_code == 409

    with TestClient(application, client=("203.0.113.1", 50000)) as client:
        assert client.post("/__r5__/fail-next-amap").status_code == 403


def test_browser_readonly_diagnostics_are_scoped_and_do_not_consume_faults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("F008_R5_ROOT", str(tmp_path / "diagnostics"))
    monkeypatch.setenv("F008_R5_START", request_payload()["start_date"])
    application = create_browser_app()
    with TestClient(application, client=("127.0.0.1", 50000)) as client:
        url, baseline = _create_plan(client)
        endpoint = f"/__r5__/diagnostics?job_id={baseline['job_id']}"
        before = client.get(endpoint)
        assert before.status_code == 200
        assert before.json() == {
            "job_id": baseline["job_id"],
            "plan_id": baseline["plan"]["plan_id"],
            "version": 7,
            "fault_remaining": 0,
        }
        assert client.post("/__r5__/fail-next-amap").status_code == 200
        armed = dict(before.json(), fault_remaining=2)
        assert client.get(endpoint).json() == armed
        assert client.get(endpoint).json() == armed
        _, pending = _create_replan(
            client, url, baseline, _command(baseline["plan"], "replace_activity")
        )
        failed = _approve_and_read(client, url, pending)
        assert failed["status"] == "failed"
        assert client.get(endpoint).json() == before.json()
        _, pending = _create_replan(
            client, url, baseline, _command(baseline["plan"], "replace_activity")
        )
        recovered = _approve_and_read(client, url, pending)
        assert recovered["status"] == "completed"
        assert client.get(endpoint).json() == dict(
            before.json(), version=8, plan_id=recovered["result"]["plan"]["plan_id"]
        )
        assert client.get(f"/__r5__/diagnostics?job_id={uuid4()}").status_code == 404
        assert client.get("/__r5__/diagnostics?job_id=invalid").status_code == 422
        assert "/__r5__/diagnostics" not in client.get("/openapi.json").json()["paths"]
        monkeypatch.setenv("APP_ENV", "production")
        assert client.get(endpoint).status_code == 403
        monkeypatch.setenv("APP_ENV", "test")
    for host in ("203.0.113.1", "not-an-ip"):
        with TestClient(application, client=(host, 50000)) as client:
            assert client.get(endpoint).status_code == 403
    with TestClient(create_production_app(tmp_path / "no-control")) as client:
        assert client.get(endpoint).status_code == 404
