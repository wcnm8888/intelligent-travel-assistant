import { useCallback, useEffect, useRef, useState } from "react";

import {
  TERMINAL_STATUSES,
  TripPlanningClientError,
  tripPlanningApi,
  type TripPlanningApi,
  type TripPlanResponseDto,
} from "./tripPlanningApi";
import type { TripPlanRequestDto } from "./tripRequest";

export type TripPlanningViewState =
  | { phase: "idle" }
  | { phase: "submitting" }
  | { phase: "retrying"; jobId: string; nextAttempt: number }
  | { phase: "tracking"; response: TripPlanResponseDto }
  | { phase: "paused"; response: TripPlanResponseDto }
  | { phase: "terminal"; response: TripPlanResponseDto }
  | { phase: "error"; code: string; message: string; retryable: boolean };

export interface PollingPolicy {
  maxPolls: number;
  wait(signal: AbortSignal): Promise<void>;
}

function waitForNextPoll(signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const finish = () => {
      signal.removeEventListener("abort", abort);
      resolve();
    };
    const timeout = window.setTimeout(finish, 2_000);
    const abort = () => {
      window.clearTimeout(timeout);
      signal.removeEventListener("abort", abort);
      reject(new DOMException("Polling cancelled", "AbortError"));
    };
    if (signal.aborted) {
      abort();
      return;
    }
    signal.addEventListener("abort", abort, { once: true });
  });
}

export const DEFAULT_POLLING_POLICY: PollingPolicy = {
  maxPolls: 15,
  wait: waitForNextPoll,
};

const DIRECT_NEXT_STATUS: Record<
  TripPlanResponseDto["status"],
  ReadonlySet<TripPlanResponseDto["status"]>
> = {
  draft: new Set(["normalizing"]),
  normalizing: new Set(["needs_input", "collecting", "failed"]),
  needs_input: new Set(),
  collecting: new Set(["planning", "partial", "failed"]),
  planning: new Set([
    "needs_input",
    "enriching_routes",
    "validating",
    "failed",
  ]),
  enriching_routes: new Set(["validating", "partial", "failed"]),
  validating: new Set(["ready", "partial", "conflict", "planning", "failed"]),
  ready: new Set(),
  partial: new Set(),
  conflict: new Set(),
  failed: new Set(),
};

function reachableStatuses(
  start: TripPlanResponseDto["status"],
): ReadonlySet<TripPlanResponseDto["status"]> {
  const reachable = new Set<TripPlanResponseDto["status"]>();
  const pending = [...DIRECT_NEXT_STATUS[start]];
  while (pending.length > 0) {
    const status = pending.pop();
    if (status === undefined || reachable.has(status)) continue;
    reachable.add(status);
    pending.push(...DIRECT_NEXT_STATUS[status]);
  }
  return reachable;
}

const OBSERVABLE_NEXT_STATUS = Object.fromEntries(
  Object.keys(DIRECT_NEXT_STATUS).map((status) => [
    status,
    reachableStatuses(status as TripPlanResponseDto["status"]),
  ]),
) as Record<
  TripPlanResponseDto["status"],
  ReadonlySet<TripPlanResponseDto["status"]>
>;

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function asSafeError(error: unknown): TripPlanningClientError {
  if (error instanceof TripPlanningClientError) return error;
  return new TripPlanningClientError(
    "client_error",
    "旅行任务暂时无法继续，请返回修改后重试。",
  );
}

async function poll(
  initial: TripPlanResponseDto,
  api: TripPlanningApi,
  policy: PollingPolicy,
  signal: AbortSignal,
  onUpdate: (response: TripPlanResponseDto) => void,
): Promise<{ response: TripPlanResponseDto; terminal: boolean }> {
  if (TERMINAL_STATUSES.has(initial.status)) {
    return { response: initial, terminal: true };
  }

  let current = initial;
  for (let index = 0; index < policy.maxPolls; index += 1) {
    await policy.wait(signal);
    const next = await api.read(current.job_id, signal);
    if (
      next.job_id !== initial.job_id ||
      next.client_request_id !== initial.client_request_id ||
      next.trace_id !== initial.trace_id ||
      next.attempt !== initial.attempt
    ) {
      throw new TripPlanningClientError(
        "response_invalid",
        "本机计划服务返回了不一致的任务标识，已停止刷新。",
      );
    }
    if (
      next.status !== current.status &&
      !OBSERVABLE_NEXT_STATUS[current.status].has(next.status)
    ) {
      throw new TripPlanningClientError(
        "response_invalid",
        "本机计划服务返回了不一致的任务状态，已停止刷新。",
      );
    }
    current = next;
    onUpdate(current);
    if (TERMINAL_STATUSES.has(current.status)) {
      return { response: current, terminal: true };
    }
  }
  return { response: current, terminal: false };
}

export function useTripPlanningJob(
  api: TripPlanningApi = tripPlanningApi,
  policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) {
  const [state, setState] = useState<TripPlanningViewState>({ phase: "idle" });
  const abortController = useRef<AbortController | null>(null);
  const busy = useRef(false);

  useEffect(
    () => () => {
      abortController.current?.abort();
    },
    [],
  );

  const track = useCallback(
    async (initial: TripPlanResponseDto, controller: AbortController) => {
      setState({ phase: "tracking", response: initial });
      const result = await poll(
        initial,
        api,
        policy,
        controller.signal,
        (response) => setState({ phase: "tracking", response }),
      );
      setState(
        result.terminal
          ? { phase: "terminal", response: result.response }
          : { phase: "paused", response: result.response },
      );
    },
    [api, policy],
  );

  const start = useCallback(
    async (request: TripPlanRequestDto) => {
      if (busy.current) return;
      busy.current = true;
      abortController.current?.abort();
      const controller = new AbortController();
      abortController.current = controller;
      setState({ phase: "submitting" });

      try {
        const response = await api.create(request, controller.signal);
        await track(response, controller);
      } catch (error) {
        if (!isAbort(error)) {
          const safe = asSafeError(error);
          setState({
            phase: "error",
            code: safe.code,
            message: safe.message,
            retryable: safe.retryable,
          });
        }
      } finally {
        busy.current = false;
      }
    },
    [api, track],
  );

  const resume = useCallback(async () => {
    if (busy.current || state.phase !== "paused") return;
    busy.current = true;
    const controller = new AbortController();
    abortController.current = controller;
    try {
      await track(state.response, controller);
    } catch (error) {
      if (!isAbort(error)) {
        const safe = asSafeError(error);
        setState({
          phase: "error",
          code: safe.code,
          message: safe.message,
          retryable: safe.retryable,
        });
      }
    } finally {
      busy.current = false;
    }
  }, [state, track]);

  const retry = useCallback(async () => {
    if (busy.current || state.phase !== "terminal") return;
    const previous = state.response;
    if (
      (previous.status !== "partial" && previous.status !== "failed") ||
      !previous.retryable ||
      previous.attempt >= 3
    )
      return;

    busy.current = true;
    abortController.current?.abort();
    const controller = new AbortController();
    abortController.current = controller;
    setState({
      phase: "retrying",
      jobId: previous.job_id,
      nextAttempt: previous.attempt + 1,
    });

    try {
      const response = await api.retry(previous.job_id, controller.signal);
      if (
        response.job_id !== previous.job_id ||
        response.client_request_id !== previous.client_request_id ||
        response.attempt !== previous.attempt + 1 ||
        response.trace_id === previous.trace_id
      ) {
        throw new TripPlanningClientError(
          "response_invalid",
          "本机计划服务返回了不一致的重试标识，已停止刷新。",
        );
      }
      await track(response, controller);
    } catch (error) {
      if (!isAbort(error)) {
        const safe = asSafeError(error);
        setState({
          phase: "error",
          code: safe.code,
          message: safe.message,
          retryable: safe.retryable,
        });
      }
    } finally {
      busy.current = false;
    }
  }, [api, state, track]);

  const reset = useCallback(() => {
    abortController.current?.abort();
    busy.current = false;
    setState({ phase: "idle" });
  }, []);

  return { state, start, resume, retry, reset };
}
