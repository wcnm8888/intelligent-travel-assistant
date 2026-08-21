import { useCallback, useEffect, useRef, useState } from "react";

import {
  TERMINAL_STATUSES,
  TripPlanningClientError,
  isPlanningJobId,
  tripPlanningApi,
  type TripPlanningApi,
  type TripPlanResponseDto,
} from "./tripPlanningApi";
import type { TripPlanRequestDto } from "./tripRequest";

export type TripPlanningViewState =
  | { phase: "idle"; notice?: string }
  | { phase: "submitting"; action?: "create" | "restore" }
  | { phase: "retrying"; jobId: string; nextAttempt: number }
  | { phase: "tracking"; response: TripPlanResponseDto; restored?: boolean }
  | { phase: "paused"; response: TripPlanResponseDto; restored?: boolean }
  | { phase: "terminal"; response: TripPlanResponseDto; restored?: boolean }
  | {
      phase: "error";
      code: string;
      message: string;
      retryable: boolean;
      recoveryAvailable?: boolean;
    };

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

export const ACTIVE_JOB_STORAGE_KEY = "ita.last-local-job";
export const ACTIVE_V3_JOB_STORAGE_KEY = "ita.active-v3-job";
export const ACTIVE_V4_JOB_STORAGE_KEY = "ita.active-v4-job";

function multicityResponseVersion(
  response: TripPlanResponseDto,
): "3" | "4" | null {
  if (!("response_version" in response)) return null;
  return response.response_version === "3" || response.response_version === "4"
    ? response.response_version
    : null;
}

interface SavedJob {
  jobId: string;
  version: "3" | "4" | null;
}

interface SavedJobLookup {
  saved: SavedJob | null;
  invalidDiscarded: boolean;
}

function savedJob(): SavedJobLookup {
  let invalidDiscarded = false;
  const candidates = [
    { key: ACTIVE_JOB_STORAGE_KEY, version: null },
    { key: ACTIVE_V4_JOB_STORAGE_KEY, version: "4" },
    { key: ACTIVE_V3_JOB_STORAGE_KEY, version: "3" },
  ] as const;

  for (const candidate of candidates) {
    let jobId: string | null;
    try {
      jobId = window.localStorage.getItem(candidate.key);
    } catch {
      return { saved: null, invalidDiscarded };
    }
    if (!jobId) continue;
    if (isPlanningJobId(jobId)) {
      return {
        saved: { jobId, version: candidate.version },
        invalidDiscarded,
      };
    }
    try {
      window.localStorage.removeItem(candidate.key);
    } catch {
      // A blocked storage API must not prevent checking the next legacy key.
    }
    invalidDiscarded = true;
  }

  return { saved: null, invalidDiscarded };
}

function rememberJob(response: TripPlanResponseDto): void {
  try {
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, response.job_id);
    window.localStorage.removeItem(ACTIVE_V4_JOB_STORAGE_KEY);
    window.localStorage.removeItem(ACTIVE_V3_JOB_STORAGE_KEY);
  } catch {
    // Storage is a convenience pointer; the SQLite job remains authoritative.
  }
}

function forgetJob(): void {
  try {
    window.localStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
    window.localStorage.removeItem(ACTIVE_V3_JOB_STORAGE_KEY);
    window.localStorage.removeItem(ACTIVE_V4_JOB_STORAGE_KEY);
  } catch {
    // A blocked storage API must not prevent returning to the form.
  }
}

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
  const recoverableJob = useRef<SavedJob | null>(null);
  const busy = useRef(false);

  useEffect(
    () => () => {
      abortController.current?.abort();
    },
    [],
  );

  const track = useCallback(
    async (
      initial: TripPlanResponseDto,
      controller: AbortController,
      restored = false,
    ) => {
      setState({ phase: "tracking", response: initial, restored });
      const result = await poll(
        initial,
        api,
        policy,
        controller.signal,
        (response) => setState({ phase: "tracking", response, restored }),
      );
      setState(
        result.terminal
          ? { phase: "terminal", response: result.response, restored }
          : { phase: "paused", response: result.response, restored },
      );
    },
    [api, policy],
  );

  const showKnownJobError = useCallback((error: unknown) => {
    const safe = asSafeError(error);
    if (safe.code === "job_not_found") {
      recoverableJob.current = null;
      forgetJob();
      setState({
        phase: "idle",
        notice: "上次本机任务无法恢复，已返回新建。",
      });
      return;
    }
    setState({
      phase: "error",
      code: safe.code,
      message: safe.message,
      retryable: safe.retryable,
      recoveryAvailable: true,
    });
  }, []);

  const restore = useCallback(async () => {
    if (busy.current) return;
    const lookup = recoverableJob.current
      ? { saved: recoverableJob.current, invalidDiscarded: false }
      : savedJob();
    const saved = lookup.saved;
    if (!saved) {
      if (!lookup.invalidDiscarded) return;
      setState({
        phase: "idle",
        notice: "上次本机任务无法恢复，已返回新建。",
      });
      return;
    }

    busy.current = true;
    abortController.current?.abort();
    const controller = new AbortController();
    abortController.current = controller;
    setState({ phase: "submitting", action: "restore" });
    try {
      const response = await api.read(saved.jobId, controller.signal);
      if (
        response.job_id !== saved.jobId ||
        (saved.version !== null &&
          multicityResponseVersion(response) !== saved.version)
      ) {
        throw new TripPlanningClientError(
          "response_invalid",
          "已保存任务与本机计划服务返回的任务不一致。",
        );
      }
      recoverableJob.current = {
        jobId: response.job_id,
        version: multicityResponseVersion(response),
      };
      rememberJob(response);
      await track(response, controller, true);
    } catch (error) {
      if (!isAbort(error)) {
        showKnownJobError(error);
      }
    } finally {
      busy.current = false;
    }
  }, [api, showKnownJobError, track]);

  useEffect(() => {
    const handle = window.setTimeout(() => void restore(), 0);
    return () => window.clearTimeout(handle);
  }, [restore]);

  const start = useCallback(
    async (request: TripPlanRequestDto) => {
      if (busy.current) return;
      busy.current = true;
      abortController.current?.abort();
      const controller = new AbortController();
      abortController.current = controller;
      setState({ phase: "submitting", action: "create" });
      let jobKnown = false;

      try {
        const response = await api.create(request, controller.signal);
        recoverableJob.current = {
          jobId: response.job_id,
          version: multicityResponseVersion(response),
        };
        rememberJob(response);
        jobKnown = true;
        await track(response, controller);
      } catch (error) {
        if (!isAbort(error)) {
          if (jobKnown) {
            showKnownJobError(error);
            return;
          }
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
    [api, showKnownJobError, track],
  );

  const resume = useCallback(async () => {
    if (busy.current || state.phase !== "paused") return;
    busy.current = true;
    const controller = new AbortController();
    abortController.current = controller;
    try {
      await track(state.response, controller, state.restored);
    } catch (error) {
      if (!isAbort(error)) {
        showKnownJobError(error);
      }
    } finally {
      busy.current = false;
    }
  }, [showKnownJobError, state, track]);

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
      recoverableJob.current = {
        jobId: response.job_id,
        version: multicityResponseVersion(response),
      };
      await track(response, controller);
    } catch (error) {
      if (!isAbort(error)) {
        showKnownJobError(error);
      }
    } finally {
      busy.current = false;
    }
  }, [api, showKnownJobError, state, track]);

  const remove = useCallback(async () => {
    if (busy.current || state.phase !== "terminal") return;
    busy.current = true;
    abortController.current?.abort();
    const controller = new AbortController();
    abortController.current = controller;
    try {
      await api.remove(state.response.job_id, controller.signal);
      recoverableJob.current = null;
      forgetJob();
      setState({ phase: "idle", notice: "本机任务已删除。" });
    } catch (error) {
      if (isAbort(error)) return;
      throw asSafeError(error);
    } finally {
      busy.current = false;
    }
  }, [api, state]);

  const reset = useCallback(() => {
    abortController.current?.abort();
    busy.current = false;
    recoverableJob.current = null;
    forgetJob();
    setState({ phase: "idle" });
  }, []);

  return { state, start, resume, retry, restore, remove, reset };
}
