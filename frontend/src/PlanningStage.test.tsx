import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import conflictCase from "../../backend/tests/fixtures/synthetic_hangzhou_conflict.json";
import failedCase from "../../backend/tests/fixtures/synthetic_hangzhou_failed.json";
import needsInputCase from "../../backend/tests/fixtures/synthetic_hangzhou_needs_input.json";

import { PlanningStage } from "./PlanningStage";
import { planningResponse } from "./test/tripPlanningFixtures";
import { parseTripPlanResponse } from "./tripPlanningApi";

describe("PlanningStage", () => {
  it("marks only the real server phase as active", () => {
    render(
      <PlanningStage
        state={{ phase: "tracking", response: planningResponse("collecting") }}
        onResume={vi.fn()}
        onRetry={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText("服务端状态 · collecting")).toBeVisible();
    expect(screen.getByText("收集旅行事实").closest("li")).toHaveTextContent(
      "进行中",
    );
    expect(screen.getByText("任务登记").closest("li")).toHaveTextContent(
      "完成",
    );
    expect(screen.getByText("生成结构计划").closest("li")).toHaveTextContent(
      "等待",
    );
  });

  it("explains bounded polling and lets the user resume", async () => {
    const user = userEvent.setup();
    const onResume = vi.fn();
    render(
      <PlanningStage
        state={{ phase: "paused", response: planningResponse("draft") }}
        onResume={onResume}
        onRetry={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("自动刷新已经暂停");
    await user.click(screen.getByRole("button", { name: "继续刷新" }));
    expect(onResume).toHaveBeenCalledOnce();
  });

  it("keeps a malformed terminal snapshot in a safe minimal state", () => {
    render(
      <PlanningStage
        state={{ phase: "terminal", response: planningResponse("ready") }}
        onResume={vi.fn()}
        onRetry={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("计划已通过校验");
    expect(screen.getByRole("status")).toHaveTextContent("结果载荷不可用");
  });

  it("renders a deterministic conflict without claiming the plan passed", () => {
    const response = parseTripPlanResponse(conflictCase.response);
    render(
      <PlanningStage
        state={{ phase: "terminal", response }}
        onResume={vi.fn()}
        onRetry={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: /杭州2日旅笺/ })).toBeVisible();
    expect(
      screen.getAllByText(/已知费用4500元超过用户总预算4000元/),
    ).toHaveLength(2);
    expect(screen.getByText("已知费用超过预算")).toBeVisible();
    expect(screen.queryByText("完整\n可用")).not.toBeInTheDocument();
  });

  it("asks for the exact missing input and returns to the form", async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    const response = parseTripPlanResponse(needsInputCase.response);
    render(
      <PlanningStage
        state={{ phase: "terminal", response }}
        onResume={vi.fn()}
        onRetry={vi.fn()}
        onReset={onReset}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "需要补充旅行信息" }),
    ).toBeVisible();
    expect(screen.getByText(/住宿区域无法唯一定位/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "补充旅行信息" }));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it("shows only the safe failed result and enables the bounded retry", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    const response = parseTripPlanResponse(failedCase.response);
    render(
      <PlanningStage
        state={{ phase: "terminal", response }}
        onResume={vi.fn()}
        onRetry={onRetry}
        onReset={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "暂时无法形成安全计划" }),
    ).toBeVisible();
    expect(screen.getByText(/规划模型.*暂时不可用/)).toBeVisible();
    expect(screen.getByText("可安全重试")).toBeVisible();
    expect(screen.getByRole("button", { name: "重试本次任务" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "重试本次任务" }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(
      screen.queryByText(/raw error|Authorization|secret/i),
    ).not.toBeInTheDocument();
  });

  it("does not offer another retry after attempt three", () => {
    const response = parseTripPlanResponse({
      ...failedCase.response,
      attempt: 3,
    });
    render(
      <PlanningStage
        state={{ phase: "terminal", response }}
        onResume={vi.fn()}
        onRetry={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "重试本次任务" })).toBeNull();
    expect(screen.getByText(/达到 3 次尝试上限/)).toBeVisible();
  });

  it("keeps provider schema failures non-retryable without an AI source claim", () => {
    const response = parseTripPlanResponse({
      ...failedCase.response,
      errors: [
        {
          code: "provider_schema_invalid",
          message: "AI 服务返回结果未通过安全解析。",
          field: null,
          provider: "deepseek",
          diagnostic_code: "response_envelope_invalid",
          retryable: false,
        },
      ],
      retryable: false,
    });

    render(
      <PlanningStage
        state={{ phase: "terminal", response }}
        onResume={vi.fn()}
        onRetry={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText("AI 服务返回结果未通过安全解析。")).toBeVisible();
    expect(screen.getByText("需要调整或确认")).toBeVisible();
    expect(screen.queryByRole("button", { name: "重试本次任务" })).toBeNull();
    expect(screen.queryByText(/本计划包含 DeepSeek AI 生成内容/)).toBeNull();
  });

  it("shows only the normalized safe client error", () => {
    render(
      <PlanningStage
        state={{
          phase: "error",
          code: "network_unavailable",
          message: "无法连接本机计划服务，请确认 FastAPI 已启动。",
          retryable: true,
        }}
        onResume={vi.fn()}
        onRetry={vi.fn()}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("无法连接本机计划服务");
  });
});
