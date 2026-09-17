import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  ReplanningClientError,
  type ReplanningApi,
  type ReplanCommand,
  type ReplanResponseDto,
} from "./replanningApi";
import { ReplanPanel } from "./ReplanPanel";
import {
  partialPlanningResponse,
  readyPlanningResponse,
} from "./test/tripPlanningFixtures";

const REPLAN_ID = "44444444-4444-4444-8444-444444444444";
const REPLAN_REQUEST_ID = "55555555-5555-4555-8555-555555555555";

function awaitingConfirmationResponse(): ReplanResponseDto {
  const baseline = readyPlanningResponse();
  if (!baseline.plan) throw new Error("fixture plan missing");
  return {
    job_id: baseline.job_id,
    replan_id: REPLAN_ID,
    replan_request_id: REPLAN_REQUEST_ID,
    trace_id: "66666666-6666-4666-8666-666666666666",
    baseline_plan_id: baseline.plan.plan_id,
    operation: "delete_activity",
    status: "awaiting_confirmation",
    impact: {
      categories: ["budget_risk", "source_refresh"],
      direct_refs: [baseline.plan.days[0].activities[0].item_id],
      transitive_refs: [baseline.plan.days[0].routes[0].route_id],
      affected_dates: [baseline.plan.days[0].local_date],
      route_refs: [baseline.plan.days[0].routes[0].route_id],
      budget_effect: null,
      source_actions: [
        {
          source_id: baseline.sources[0].source_id,
          action: "refresh",
          freshness: "unknown_validity",
          reason: "unknown_validity",
        },
      ],
      required_validations: ["route_chain", "budget"],
      confirmation_required: true,
    },
    confirmation_expires_at: "2026-08-14T10:15:00+08:00",
    decision: null,
    result: null,
    change_set: null,
    errors: [],
    created_at: "2026-08-14T10:00:00+08:00",
    updated_at: "2026-08-14T10:00:01+08:00",
  };
}

function completedResponse(): ReplanResponseDto {
  const response = awaitingConfirmationResponse();
  const result = partialPlanningResponse();
  if (!result.plan) throw new Error("fixture plan missing");
  return {
    ...response,
    status: "completed",
    decision: {
      decision_id: "77777777-7777-4777-8777-777777777777",
      choice: "approve",
      decided_at: "2026-08-14T10:03:00+08:00",
    },
    result,
    change_set: {
      baseline_plan_id: response.baseline_plan_id,
      result_plan_id: result.plan.plan_id,
      added_refs: [],
      removed_refs: [response.impact!.direct_refs[0]],
      changed_refs: response.impact!.transitive_refs,
      change_codes: ["activity_removed", "route_changed", "cost_changed"],
    },
  };
}

describe("ReplanPanel", () => {
  it("does not claim the original plan is unchanged after a lost create response", async () => {
    const user = userEvent.setup();
    const baseline = readyPlanningResponse();
    if (!baseline.plan) throw new Error("fixture plan missing");
    const create = vi
      .fn()
      .mockRejectedValue(
        new ReplanningClientError(
          "network_unavailable",
          "无法连接本机服务，原计划保持不变。",
          true,
        ),
      );
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    render(
      <ReplanPanel
        api={{ create, read: vi.fn(), decide: vi.fn() }}
        baseline={{ ...baseline, plan: baseline.plan }}
        command={{
          operation: "delete_activity",
          target_activity_id: baseline.plan.days[0].activities[0].item_id,
        }}
        commandLabel="删除活动"
        onClose={vi.fn()}
        onCompleted={vi.fn()}
        onRefresh={onRefresh}
      />,
    );
    await user.click(screen.getByRole("button", { name: "分析影响" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "最终状态尚待确认",
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("原计划保持不变");
    expect(screen.queryByRole("button", { name: "重新发起调整" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "刷新当前计划" }));
    expect(onRefresh).toHaveBeenCalledOnce();
    expect(create).toHaveBeenCalledOnce();
  });

  it.each([
    ["needs_input", "data_missing", false, "修改调整内容"],
    ["conflict", "version_conflict", false, "刷新当前计划"],
    ["failed", "version_conflict", false, "刷新当前计划"],
    ["expired", "confirmation_expired", false, "刷新当前计划"],
    ["failed", "provider_unauthorized", true, "停止并保留原计划"],
    ["failed", "internal_error", true, "停止并保留原计划"],
    ["rejected", "replan_scope_not_supported", false, "停止并保留原计划"],
  ] as const)(
    "maps %s/%s to one working recovery action",
    async (status, code, retryable, label) => {
      const user = userEvent.setup();
      const baseline = readyPlanningResponse();
      if (!baseline.plan) throw new Error("fixture plan missing");
      const onClose = vi.fn();
      const onModify = vi.fn();
      const onRefresh = vi.fn().mockResolvedValue(undefined);
      const onCompleted = vi.fn();
      render(
        <ReplanPanel
          api={{
            create: vi.fn().mockResolvedValue({
              ...awaitingConfirmationResponse(),
              status,
              errors: [{ code, retryable }],
            }),
            read: vi.fn(),
            decide: vi.fn(),
          }}
          baseline={{ ...baseline, plan: baseline.plan }}
          command={{
            operation: "delete_activity",
            target_activity_id: baseline.plan.days[0].activities[0].item_id,
          }}
          commandLabel="删除活动"
          onClose={onClose}
          onModify={onModify}
          onRefresh={onRefresh}
          onCompleted={onCompleted}
        />,
      );
      await user.click(screen.getByRole("button", { name: "分析影响" }));
      const alert = await screen.findByRole("alert");
      expect(within(alert).getByText("没有替换当前计划")).toHaveFocus();
      expect(within(alert).getAllByRole("button")).toHaveLength(1);
      await user.click(within(alert).getByRole("button", { name: label }));
      expect(onCompleted).not.toHaveBeenCalled();
      if (label === "刷新当前计划") expect(onRefresh).toHaveBeenCalledOnce();
      else if (label === "修改调整内容")
        expect(onModify).toHaveBeenCalledOnce();
      else expect(onClose).toHaveBeenCalledOnce();
    },
  );

  it("offers one retry-new-request action for a transient terminal failure", async () => {
    const user = userEvent.setup();
    const baseline = readyPlanningResponse();
    if (!baseline.plan) throw new Error("fixture plan missing");
    const failed: ReplanResponseDto = {
      ...awaitingConfirmationResponse(),
      status: "failed",
      impact: null,
      errors: [
        {
          code: "provider_timeout",
          message: "外部服务响应超时。",
          field: null,
          provider: "amap",
          diagnostic_code: "provider_timeout",
          retryable: true,
        },
      ],
    };
    const create = vi.fn().mockResolvedValue(failed);
    render(
      <ReplanPanel
        api={{ create, read: vi.fn(), decide: vi.fn() }}
        baseline={{ ...baseline, plan: baseline.plan }}
        command={{
          operation: "delete_activity",
          target_activity_id: baseline.plan.days[0].activities[0].item_id,
        }}
        commandLabel="删除活动"
        onClose={vi.fn()}
        onCompleted={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "分析影响" }));
    expect(
      await screen.findByRole("button", { name: "重新发起调整" }),
    ).toBeEnabled();
    expect(screen.getByRole("alert")).toHaveTextContent("原计划未改变");
    expect(screen.queryByRole("button", { name: "修改调整内容" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "重新发起调整" }));
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[0][1].replan_request_id).not.toBe(
      create.mock.calls[1][1].replan_request_id,
    );
  });

  it("previews impact, does not auto-focus approve, and completes only after confirmation", async () => {
    const user = userEvent.setup();
    const pending = awaitingConfirmationResponse() as ReplanResponseDto;
    const completed = completedResponse();
    const api: ReplanningApi = {
      create: vi.fn().mockResolvedValue(pending),
      read: vi.fn().mockResolvedValue(completed),
      decide: vi.fn().mockResolvedValue({ ...pending, status: "replanning" }),
    };
    const onCompleted = vi.fn();
    const baseline = readyPlanningResponse();
    if (!baseline.plan) throw new Error("fixture plan missing");
    render(
      <ReplanPanel
        api={api}
        baseline={{ ...baseline, plan: baseline.plan }}
        command={{
          operation: "delete_activity",
          target_activity_id: baseline.plan.days[0].activities[0].item_id,
        }}
        commandLabel="删除 · 西湖湖滨步行"
        onClose={vi.fn()}
        onCompleted={onCompleted}
        pollingPolicy={{
          maxPolls: 2,
          wait: vi.fn().mockResolvedValue(undefined),
        }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "删除 · 西湖湖滨步行" }),
    ).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "分析影响" }));
    const impact = await screen.findByRole("region", { name: "修改影响" });
    expect(impact).toHaveTextContent("预算风险");
    expect(impact).toHaveTextContent("来源需刷新");
    expect(impact).toHaveTextContent("金额未知时不会按 0 计算");
    expect(
      screen.getByRole("button", { name: "确认并生成新版本" }),
    ).not.toHaveFocus();

    await user.click(screen.getByRole("button", { name: "确认并生成新版本" }));
    expect(api.decide).toHaveBeenCalledOnce();
    expect(await screen.findByText("本次版本变化")).toBeVisible();
    expect(screen.getByText("本次版本变化")).toHaveFocus();
    expect(screen.getByText(/删除对象：/)).toHaveTextContent(
      completed.change_set!.removed_refs[0],
    );
    expect(screen.getByText(/金额未知 · 1 项/)).toBeVisible();
    expect(onCompleted).toHaveBeenCalledWith(
      completed.result,
      completed.change_set,
    );
  });

  it("cancels without replacing the baseline and restores the trigger focus", async () => {
    const user = userEvent.setup();
    const pending = awaitingConfirmationResponse() as ReplanResponseDto;
    const api: ReplanningApi = {
      create: vi.fn().mockResolvedValue(pending),
      read: vi.fn(),
      decide: vi.fn().mockResolvedValue({ ...pending, status: "cancelled" }),
    };
    const onClose = vi.fn();
    const baseline = readyPlanningResponse();
    if (!baseline.plan) throw new Error("fixture plan missing");
    render(
      <ReplanPanel
        api={api}
        baseline={{ ...baseline, plan: baseline.plan }}
        command={{
          operation: "delete_activity",
          target_activity_id: pending.impact!.direct_refs[0],
        }}
        commandLabel="删除活动"
        onClose={onClose}
        onCompleted={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "分析影响" }));
    await user.click(
      await screen.findByRole("button", { name: "取消并保留原计划" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("原计划未改变");
    await user.click(screen.getByRole("button", { name: "关闭局部调整" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("keeps safe failures separate from the still-readable original plan", async () => {
    const user = userEvent.setup();
    const pending = awaitingConfirmationResponse() as ReplanResponseDto;
    const api: ReplanningApi = {
      create: vi.fn().mockResolvedValue({
        ...pending,
        status: "failed",
        errors: [
          { code: "internal_error", message: "暂时无法安全完成局部调整。" },
        ],
      }),
      read: vi.fn(),
      decide: vi.fn(),
    };
    const baseline = readyPlanningResponse();
    if (!baseline.plan) throw new Error("fixture plan missing");
    render(
      <ReplanPanel
        api={api}
        baseline={{ ...baseline, plan: baseline.plan }}
        command={{
          operation: "delete_activity",
          target_activity_id: pending.impact!.direct_refs[0],
        }}
        commandLabel="删除活动"
        onClose={vi.fn()}
        onCompleted={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "分析影响" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("原计划未改变");
    expect(
      within(screen.getByRole("alert")).queryByText(/token|provider body/i),
    ).toBeNull();
  });

  it("disables a repeated confirmation while the first decision is pending", async () => {
    const user = userEvent.setup();
    const pending = awaitingConfirmationResponse();
    const decide = vi.fn(() => new Promise<ReplanResponseDto>(() => undefined));
    const baseline = readyPlanningResponse();
    if (!baseline.plan) throw new Error("fixture plan missing");
    render(
      <ReplanPanel
        api={{
          create: vi.fn().mockResolvedValue(pending),
          read: vi.fn(),
          decide,
        }}
        baseline={{ ...baseline, plan: baseline.plan }}
        command={{
          operation: "delete_activity",
          target_activity_id: pending.impact!.direct_refs[0],
        }}
        commandLabel="删除活动"
        onClose={vi.fn()}
        onCompleted={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "分析影响" }));
    const approve = await screen.findByRole("button", {
      name: "确认并生成新版本",
    });
    await user.click(approve);
    expect(approve).toBeDisabled();
    expect(decide).toHaveBeenCalledOnce();
  });

  it("keeps polling recoverable when the background result read fails", async () => {
    const user = userEvent.setup();
    const pending = awaitingConfirmationResponse();
    const replanning = { ...pending, status: "replanning" as const };
    const read = vi
      .fn()
      .mockRejectedValueOnce(
        new ReplanningClientError("network_error", "读取失败"),
      )
      .mockResolvedValueOnce(completedResponse());
    const baseline = readyPlanningResponse();
    if (!baseline.plan) throw new Error("fixture plan missing");
    render(
      <ReplanPanel
        api={{
          create: vi.fn().mockResolvedValue(replanning),
          read,
          decide: vi.fn(),
        }}
        baseline={{ ...baseline, plan: baseline.plan }}
        command={{
          operation: "delete_activity",
          target_activity_id: pending.impact!.direct_refs[0],
        }}
        commandLabel="删除活动"
        onClose={vi.fn()}
        onCompleted={vi.fn()}
        pollingPolicy={{
          maxPolls: 1,
          wait: vi.fn().mockResolvedValue(undefined),
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "分析影响" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "后台可能仍在执行",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("最终状态尚待确认");
    await user.click(screen.getByRole("button", { name: "继续刷新局部调整" }));
    expect(await screen.findByText("本次版本变化")).toBeVisible();
  });

  it("removes stale confirmation actions after a decision conflict", async () => {
    const user = userEvent.setup();
    const pending = awaitingConfirmationResponse();
    const baseline = readyPlanningResponse();
    if (!baseline.plan) throw new Error("fixture plan missing");
    render(
      <ReplanPanel
        api={{
          create: vi.fn().mockResolvedValue(pending),
          read: vi.fn(),
          decide: vi
            .fn()
            .mockRejectedValue(
              new ReplanningClientError("version_conflict", "版本冲突"),
            ),
        }}
        baseline={{ ...baseline, plan: baseline.plan }}
        command={{
          operation: "delete_activity",
          target_activity_id: pending.impact!.direct_refs[0],
        }}
        commandLabel="删除活动"
        onClose={vi.fn()}
        onCompleted={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "分析影响" }));
    await user.click(
      await screen.findByRole("button", { name: "确认并生成新版本" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("版本冲突");
    expect(
      within(screen.getByRole("alert")).getByText("没有替换当前计划"),
    ).toHaveFocus();
    expect(
      screen.queryByRole("button", { name: "确认并生成新版本" }),
    ).toBeNull();
  });

  it("can poll after an approved decision response is lost", async () => {
    const user = userEvent.setup();
    const pending = awaitingConfirmationResponse();
    const baseline = readyPlanningResponse();
    if (!baseline.plan) throw new Error("fixture plan missing");
    render(
      <ReplanPanel
        api={{
          create: vi.fn().mockResolvedValue(pending),
          read: vi.fn().mockResolvedValue(completedResponse()),
          decide: vi
            .fn()
            .mockRejectedValue(
              new ReplanningClientError("http_error", "响应丢失", true),
            ),
        }}
        baseline={{ ...baseline, plan: baseline.plan }}
        command={{
          operation: "delete_activity",
          target_activity_id: pending.impact!.direct_refs[0],
        }}
        commandLabel="删除活动"
        onClose={vi.fn()}
        onCompleted={vi.fn()}
        pollingPolicy={{
          maxPolls: 1,
          wait: vi.fn().mockResolvedValue(undefined),
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "分析影响" }));
    await user.click(
      await screen.findByRole("button", { name: "确认并生成新版本" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "最终状态尚待确认",
    );
    await user.click(screen.getByRole("button", { name: "继续刷新局部调整" }));
    expect(await screen.findByText("本次版本变化")).toBeVisible();
  });

  it.each([
    "replace_activity",
    "delete_activity",
    "adjust_activity_time",
    "reorder_activities",
  ] as const)("submits only the structured %s command", async (operation) => {
    const user = userEvent.setup();
    const baseline = readyPlanningResponse();
    if (!baseline.plan) throw new Error("fixture plan missing");
    const day = baseline.plan.days[0];
    const target = day.activities[0];
    let command: ReplanCommand;
    if (operation === "replace_activity") {
      command = {
        operation,
        target_activity_id: target.item_id,
        replacement_categories: ["museum"],
      };
    } else if (operation === "delete_activity") {
      command = { operation, target_activity_id: target.item_id };
    } else if (operation === "adjust_activity_time") {
      command = {
        operation,
        target_activity_id: target.item_id,
        start_time: "10:00:00",
        end_time: "11:00:00",
      };
    } else {
      command = {
        operation,
        local_date: day.local_date,
        ordered_activity_ids: day.activities
          .map((item) => item.item_id)
          .reverse(),
      };
    }
    const create = vi.fn().mockResolvedValue({
      ...awaitingConfirmationResponse(),
      operation,
    });
    render(
      <ReplanPanel
        api={{ create, read: vi.fn(), decide: vi.fn() }}
        baseline={{ ...baseline, plan: baseline.plan }}
        command={command}
        commandLabel={`结构化 ${operation}`}
        onClose={vi.fn()}
        onCompleted={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "分析影响" }));
    expect(create).toHaveBeenCalledOnce();
    expect(create.mock.calls[0][1].command).toEqual(command);
    expect(JSON.stringify(create.mock.calls[0][1])).not.toMatch(/prompt/i);
  });
});
