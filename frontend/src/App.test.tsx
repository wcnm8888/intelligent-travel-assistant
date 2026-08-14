import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import failedCase from "../../backend/tests/fixtures/synthetic_hangzhou_failed.json";
import needsInputCase from "../../backend/tests/fixtures/synthetic_hangzhou_needs_input.json";

import { App } from "./App";
import {
  FIXED_CLIENT_ID,
  FIXED_JOB_ID,
  partialPlanningResponse,
  planningResponse,
  readyPlanningResponse,
} from "./test/tripPlanningFixtures";
import {
  parseTripPlanResponse,
  TripPlanningClientError,
  type TripPlanningApi,
} from "./tripPlanningApi";
import type { TripPlanRequestDto } from "./tripRequest";
import type { PollingPolicy } from "./useTripPlanningJob";

const RETRY_TRACE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

function retryResponse() {
  return planningResponse("normalizing", {
    attempt: 2,
    trace_id: RETRY_TRACE_ID,
  });
}

function attemptTwoReadyResponse() {
  return {
    ...readyPlanningResponse(),
    attempt: 2,
    trace_id: RETRY_TRACE_ID,
  };
}

const immediatePolling: PollingPolicy = {
  maxPolls: 5,
  wait: vi.fn().mockResolvedValue(undefined),
};

async function submitValidRequest(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("目的地城市 *"), "杭州");
  await user.type(screen.getByLabelText("开始日期 *"), "2026-08-15");
  await user.type(screen.getByLabelText("总预算 *"), "4000.00");
  await user.type(screen.getByLabelText("住宿区域或 POI *"), "湖滨银泰附近");
  await user.click(screen.getByRole("button", { name: /生成双日计划/ }));
}

describe("App trip planning flow", () => {
  it("renders an idle product form without calling the network", () => {
    const api: TripPlanningApi = {
      create: vi.fn(),
      read: vi.fn(),
      retry: vi.fn(),
    };
    render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={immediatePolling}
      />,
    );

    expect(screen.getByRole("form", { name: "行前设定" })).toBeVisible();
    expect(screen.getByText("计划将在这里展开")).toBeVisible();
    expect(api.create).not.toHaveBeenCalled();
  });

  it("submits once, follows server phases and stops at the terminal status", async () => {
    const user = userEvent.setup();
    const api: TripPlanningApi = {
      create: vi.fn().mockResolvedValue(planningResponse("draft")),
      read: vi
        .fn()
        .mockResolvedValueOnce(planningResponse("normalizing"))
        .mockResolvedValueOnce(planningResponse("collecting"))
        .mockResolvedValueOnce(planningResponse("planning"))
        .mockResolvedValueOnce(planningResponse("validating"))
        .mockResolvedValueOnce(readyPlanningResponse()),
      retry: vi.fn(),
    };
    render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={immediatePolling}
      />,
    );

    await submitValidRequest(user);

    expect(await screen.findByText("西湖湖滨步行")).toBeVisible();
    expect(screen.getByRole("main")).toHaveClass("planning-workspace--result");
    expect(api.create).toHaveBeenCalledOnce();
    expect(api.read).toHaveBeenCalledTimes(5);
  });

  it("prevents duplicate submission while POST is unresolved", async () => {
    const user = userEvent.setup();
    let resolveCreate:
      ((value: ReturnType<typeof planningResponse>) => void) | undefined;
    const create = vi.fn(
      () =>
        new Promise<ReturnType<typeof planningResponse>>((resolve) => {
          resolveCreate = resolve;
        }),
    );
    const api: TripPlanningApi = { create, read: vi.fn(), retry: vi.fn() };
    render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={{ maxPolls: 0, wait: immediatePolling.wait }}
      />,
    );

    await submitValidRequest(user);

    expect(screen.getByRole("button", { name: "正在提交" })).toBeDisabled();
    expect(create).toHaveBeenCalledOnce();
    resolveCreate?.(planningResponse("draft"));
    expect(await screen.findByText("任务仍在等待")).toBeVisible();
  });

  it("pauses bounded polling and resumes from the latest server state", async () => {
    const user = userEvent.setup();
    const api: TripPlanningApi = {
      create: vi.fn().mockResolvedValue(planningResponse("draft")),
      read: vi
        .fn()
        .mockResolvedValueOnce(planningResponse("normalizing"))
        .mockResolvedValueOnce(planningResponse("collecting")),
      retry: vi.fn(),
    };
    render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={{ maxPolls: 1, wait: immediatePolling.wait }}
      />,
    );

    await submitValidRequest(user);
    expect(await screen.findByText("任务仍在等待")).toBeVisible();
    expect(screen.getByText("服务端状态 · normalizing")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "继续刷新" }));
    expect(await screen.findByText("服务端状态 · collecting")).toBeVisible();
    expect(api.read).toHaveBeenCalledTimes(2);
  });

  it("renders a safe client error without leaking transport details", async () => {
    const user = userEvent.setup();
    const api: TripPlanningApi = {
      create: vi
        .fn()
        .mockRejectedValue(
          new TripPlanningClientError(
            "network_unavailable",
            "无法连接本机计划服务，请确认 FastAPI 已启动。",
            true,
          ),
        ),
      read: vi.fn(),
      retry: vi.fn(),
    };
    render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={immediatePolling}
      />,
    );

    await submitValidRequest(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "无法连接本机计划服务",
    );
    expect(
      screen.queryByText(/sensitive|stack|token/i),
    ).not.toBeInTheDocument();
  });

  it("accepts a reachable status jump when polling misses intermediate snapshots", async () => {
    const user = userEvent.setup();
    const api: TripPlanningApi = {
      create: vi.fn().mockResolvedValue(planningResponse("draft")),
      read: vi
        .fn()
        .mockResolvedValueOnce(planningResponse("planning"))
        .mockResolvedValueOnce(readyPlanningResponse()),
      retry: vi.fn(),
    };
    render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={immediatePolling}
      />,
    );

    await submitValidRequest(user);

    expect(await screen.findByText("西湖湖滨步行")).toBeVisible();
    expect(api.read).toHaveBeenCalledTimes(2);
  });

  it("stops when the server reports an unreachable state transition", async () => {
    const user = userEvent.setup();
    const api: TripPlanningApi = {
      create: vi.fn().mockResolvedValue(planningResponse("planning")),
      read: vi.fn().mockResolvedValue(planningResponse("collecting")),
      retry: vi.fn(),
    };
    render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={{ maxPolls: 1, wait: immediatePolling.wait }}
      />,
    );

    await submitValidRequest(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "不一致的任务状态",
    );
  });

  it("aborts an in-flight request when the UI unmounts", async () => {
    const user = userEvent.setup();
    let observedSignal: AbortSignal | undefined;
    const api: TripPlanningApi = {
      create: vi.fn((_request: TripPlanRequestDto, signal?: AbortSignal) => {
        observedSignal = signal;
        return new Promise<ReturnType<typeof planningResponse>>(
          () => undefined,
        );
      }),
      read: vi.fn(),
      retry: vi.fn(),
    };
    const view = render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={immediatePolling}
      />,
    );

    await submitValidRequest(user);
    view.unmount();

    expect(observedSignal?.aborted).toBe(true);
  });

  it("retries a partial job once, clears stale output and tracks the same job", async () => {
    const user = userEvent.setup();
    let resolveRetry:
      ((value: ReturnType<typeof retryResponse>) => void) | undefined;
    const retry = vi.fn(
      () =>
        new Promise<ReturnType<typeof retryResponse>>((resolve) => {
          resolveRetry = resolve;
        }),
    );
    const api: TripPlanningApi = {
      create: vi.fn().mockResolvedValue(partialPlanningResponse()),
      retry,
      read: vi
        .fn()
        .mockResolvedValueOnce(
          planningResponse("collecting", {
            attempt: 2,
            trace_id: RETRY_TRACE_ID,
          }),
        )
        .mockResolvedValueOnce(
          planningResponse("planning", {
            attempt: 2,
            trace_id: RETRY_TRACE_ID,
          }),
        )
        .mockResolvedValueOnce(
          planningResponse("validating", {
            attempt: 2,
            trace_id: RETRY_TRACE_ID,
          }),
        )
        .mockResolvedValueOnce(attemptTwoReadyResponse()),
    };
    render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={immediatePolling}
      />,
    );

    await submitValidRequest(user);
    const retryButton = await screen.findByRole("button", {
      name: "重试缺失数据",
    });
    fireEvent.click(retryButton);
    fireEvent.click(retryButton);

    expect(retry).toHaveBeenCalledOnce();
    expect(retry).toHaveBeenCalledWith(FIXED_JOB_ID, expect.any(AbortSignal));
    expect(screen.getByText("重新核验缺失数据")).toBeVisible();
    expect(screen.queryByText("部分数据缺失 · 可查看已有计划")).toBeNull();

    resolveRetry?.(retryResponse());
    expect(await screen.findByText("代码校验通过 · 可用于决策")).toBeVisible();
    expect(screen.getByText(/尝试 2\/3/)).toBeVisible();
    expect(api.read).toHaveBeenCalledTimes(4);
  });

  it("renders a safe retry failure without restoring the stale terminal plan", async () => {
    const user = userEvent.setup();
    const api: TripPlanningApi = {
      create: vi
        .fn()
        .mockResolvedValue(parseTripPlanResponse(failedCase.response)),
      read: vi.fn(),
      retry: vi
        .fn()
        .mockRejectedValue(
          new TripPlanningClientError(
            "provider_unavailable",
            "规划服务暂时不可用，请稍后重试。",
            true,
          ),
        ),
    };
    render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={immediatePolling}
      />,
    );

    await submitValidRequest(user);
    await user.click(
      await screen.findByRole("button", { name: "重试本次任务" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "规划服务暂时不可用",
    );
    expect(screen.queryByText("暂时无法形成安全计划")).toBeNull();
  });

  it("rejects a retry that does not increment attempt or rotate trace", async () => {
    const user = userEvent.setup();
    const api: TripPlanningApi = {
      create: vi.fn().mockResolvedValue(partialPlanningResponse()),
      read: vi.fn(),
      retry: vi.fn().mockResolvedValue(
        planningResponse("normalizing", {
          attempt: 2,
          trace_id: partialPlanningResponse().trace_id,
        }),
      ),
    };
    render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={immediatePolling}
      />,
    );

    await submitValidRequest(user);
    await user.click(
      await screen.findByRole("button", { name: "重试缺失数据" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "不一致的重试标识",
    );
    expect(api.read).not.toHaveBeenCalled();
  });

  it("collapses non-initial input and restores focus to the requested field", async () => {
    const user = userEvent.setup();
    const api: TripPlanningApi = {
      create: vi
        .fn()
        .mockResolvedValue(parseTripPlanResponse(needsInputCase.response)),
      read: vi.fn(),
      retry: vi.fn(),
    };
    const { container } = render(
      <App
        createClientRequestId={() => FIXED_CLIENT_ID}
        tripPlanApi={api}
        pollingPolicy={immediatePolling}
      />,
    );

    await submitValidRequest(user);
    expect(await screen.findByText("需要补充旅行信息")).toBeVisible();
    expect(container.querySelector(".request-panel")).toHaveAttribute(
      "data-collapsed",
      "true",
    );
    expect(container.querySelector(".request-panel-toggle")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(container.querySelector(".request-panel-toggle")).toHaveTextContent(
      "查看旅行需求",
    );

    await user.click(screen.getByRole("button", { name: "补充旅行信息" }));
    expect(container.querySelector(".request-panel")).toHaveAttribute(
      "data-collapsed",
      "false",
    );
    await waitFor(() =>
      expect(screen.getByLabelText("住宿区域或 POI *")).toHaveFocus(),
    );
  });
});
