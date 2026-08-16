import {
  parseTripPlanResponse,
  TripPlanningClientError,
  type ApiErrorDto,
  type TripPlanResponseDto,
} from "./tripPlanningApi";
import type { DataFreshness } from "./tripPlanModels";

export type ReplanStatus =
  | "analyzing"
  | "awaiting_confirmation"
  | "replanning"
  | "completed"
  | "needs_input"
  | "conflict"
  | "failed"
  | "cancelled"
  | "expired"
  | "rejected";

export type ReplanCommand =
  | {
      operation: "replace_activity";
      target_activity_id: string;
      replacement_categories: string[];
      reason_code?: string;
    }
  | {
      operation: "delete_activity";
      target_activity_id: string;
      reason_code?: string;
    }
  | {
      operation: "adjust_activity_time";
      target_activity_id: string;
      start_time: string;
      end_time: string;
      reason_code?: string;
    }
  | {
      operation: "reorder_activities";
      local_date: string;
      ordered_activity_ids: string[];
      reason_code?: string;
    };

export interface ReplanRequestDto {
  replan_request_id: string;
  baseline_plan_id: string;
  command: ReplanCommand;
}

export interface ReplanImpactDto {
  categories: string[];
  direct_refs: string[];
  transitive_refs: string[];
  affected_dates: string[];
  route_refs: string[];
  budget_effect: {
    known_total_delta: string;
    unknown_count_delta: number;
    risk_increased: boolean;
  } | null;
  source_actions: Array<{
    source_id: string;
    action: "reuse" | "refresh" | "drop";
    freshness: DataFreshness;
    reason: string;
  }>;
  required_validations: string[];
  confirmation_required: boolean;
}

export interface ReplanChangeSetDto {
  baseline_plan_id: string;
  result_plan_id: string;
  added_refs: string[];
  removed_refs: string[];
  changed_refs: string[];
  change_codes: string[];
}

export interface ReplanResponseDto {
  job_id: string;
  replan_id: string;
  replan_request_id: string;
  trace_id: string;
  baseline_plan_id: string;
  operation: ReplanCommand["operation"];
  status: ReplanStatus;
  impact: ReplanImpactDto | null;
  confirmation_expires_at: string;
  decision: {
    decision_id: string | null;
    choice: "approve" | "cancel" | null;
    decided_at: string | null;
  } | null;
  result: TripPlanResponseDto | null;
  change_set: ReplanChangeSetDto | null;
  errors: ApiErrorDto[];
  created_at: string;
  updated_at: string;
}

export interface ReplanningApi {
  create(
    jobId: string,
    payload: ReplanRequestDto,
    signal?: AbortSignal,
  ): Promise<ReplanResponseDto>;
  read(
    jobId: string,
    replanId: string,
    signal?: AbortSignal,
  ): Promise<ReplanResponseDto>;
  decide(
    jobId: string,
    replanId: string,
    choice: "approve" | "cancel",
    signal?: AbortSignal,
  ): Promise<ReplanResponseDto>;
}

export class ReplanningClientError extends TripPlanningClientError {
  constructor(code: string, message: string, retryable = false) {
    super(code, message, retryable);
    this.name = "ReplanningClientError";
  }
}

type RequestFunction = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const DATETIME =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;
const DECIMAL = /^-?(?:0|[1-9]\d*)(?:\.\d+)?$/;
const UNSAFE =
  /authorization\s*:|(?:api[_-]?key|token|secret|password|cookie)\s*[=:]/i;
const STATUSES: ReplanStatus[] = [
  "analyzing",
  "awaiting_confirmation",
  "replanning",
  "completed",
  "needs_input",
  "conflict",
  "failed",
  "cancelled",
  "expired",
  "rejected",
];
const OPERATIONS: ReplanCommand["operation"][] = [
  "replace_activity",
  "delete_activity",
  "adjust_activity_time",
  "reorder_activities",
];

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, keys: string[]): boolean {
  return Object.keys(value).sort().join("|") === [...keys].sort().join("|");
}
function uuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}
function strings(
  value: unknown,
  check: (item: string) => boolean = () => true,
): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= 100 &&
    value.every((item) => typeof item === "string" && check(item))
  );
}
function uuids(value: unknown): value is string[] {
  return strings(value, (item) => UUID.test(item));
}

function isError(value: unknown): value is ApiErrorDto {
  return (
    record(value) &&
    [
      ["code", "message", "field", "provider", "retryable"],
      ["code", "message", "field", "provider", "diagnostic_code", "retryable"],
    ].some((keys) => exact(value, keys)) &&
    typeof value.code === "string" &&
    typeof value.message === "string" &&
    value.message.length <= 500 &&
    !UNSAFE.test(value.message) &&
    (value.field === null || typeof value.field === "string") &&
    (value.provider === null || typeof value.provider === "string") &&
    typeof value.retryable === "boolean"
  );
}

function isImpact(value: unknown): value is ReplanImpactDto {
  if (
    !record(value) ||
    !exact(value, [
      "categories",
      "direct_refs",
      "transitive_refs",
      "affected_dates",
      "route_refs",
      "budget_effect",
      "source_actions",
      "required_validations",
      "confirmation_required",
    ])
  )
    return false;
  const budget = value.budget_effect;
  const budgetOk =
    budget === null ||
    (record(budget) &&
      exact(budget, [
        "known_total_delta",
        "unknown_count_delta",
        "risk_increased",
      ]) &&
      typeof budget.known_total_delta === "string" &&
      DECIMAL.test(budget.known_total_delta) &&
      Number.isInteger(budget.unknown_count_delta) &&
      typeof budget.risk_increased === "boolean");
  const sourcesOk =
    Array.isArray(value.source_actions) &&
    value.source_actions.length <= 100 &&
    value.source_actions.every(
      (source) =>
        record(source) &&
        exact(source, ["source_id", "action", "freshness", "reason"]) &&
        uuid(source.source_id) &&
        ["reuse", "refresh", "drop"].includes(String(source.action)) &&
        ["fresh", "stale", "unknown_validity"].includes(
          String(source.freshness),
        ) &&
        typeof source.reason === "string",
    );
  return (
    strings(value.categories) &&
    uuids(value.direct_refs) &&
    uuids(value.transitive_refs) &&
    strings(value.affected_dates, (item) => DATE.test(item)) &&
    uuids(value.route_refs) &&
    budgetOk &&
    sourcesOk &&
    strings(value.required_validations) &&
    typeof value.confirmation_required === "boolean"
  );
}

function isChangeSet(value: unknown): value is ReplanChangeSetDto {
  return (
    record(value) &&
    exact(value, [
      "baseline_plan_id",
      "result_plan_id",
      "added_refs",
      "removed_refs",
      "changed_refs",
      "change_codes",
    ]) &&
    uuid(value.baseline_plan_id) &&
    uuid(value.result_plan_id) &&
    uuids(value.added_refs) &&
    uuids(value.removed_refs) &&
    uuids(value.changed_refs) &&
    strings(value.change_codes)
  );
}

export function parseReplanResponse(value: unknown): ReplanResponseDto {
  if (
    !record(value) ||
    !exact(value, [
      "job_id",
      "replan_id",
      "replan_request_id",
      "trace_id",
      "baseline_plan_id",
      "operation",
      "status",
      "impact",
      "confirmation_expires_at",
      "decision",
      "result",
      "change_set",
      "errors",
      "created_at",
      "updated_at",
    ]) ||
    !uuid(value.job_id) ||
    !uuid(value.replan_id) ||
    !uuid(value.replan_request_id) ||
    !uuid(value.trace_id) ||
    !uuid(value.baseline_plan_id) ||
    !OPERATIONS.includes(value.operation as ReplanCommand["operation"]) ||
    !STATUSES.includes(value.status as ReplanStatus) ||
    !(value.impact === null || isImpact(value.impact)) ||
    typeof value.confirmation_expires_at !== "string" ||
    !DATETIME.test(value.confirmation_expires_at) ||
    !(
      value.decision === null ||
      (record(value.decision) &&
        exact(value.decision, ["decision_id", "choice", "decided_at"]) &&
        (value.decision.decision_id === null ||
          uuid(value.decision.decision_id)) &&
        (value.decision.choice === null ||
          ["approve", "cancel"].includes(String(value.decision.choice))) &&
        (value.decision.decided_at === null ||
          (typeof value.decision.decided_at === "string" &&
            DATETIME.test(value.decision.decided_at))))
    ) ||
    !(value.result === null || record(value.result)) ||
    !(value.change_set === null || isChangeSet(value.change_set)) ||
    !Array.isArray(value.errors) ||
    !value.errors.every(isError) ||
    typeof value.created_at !== "string" ||
    !DATETIME.test(value.created_at) ||
    typeof value.updated_at !== "string" ||
    !DATETIME.test(value.updated_at)
  ) {
    throw new ReplanningClientError(
      "response_invalid",
      "本机计划服务返回了无法识别的局部调整数据。",
    );
  }
  let result: TripPlanResponseDto | null = null;
  if (value.result !== null) result = parseTripPlanResponse(value.result);
  const completed = value.status === "completed";
  if (completed !== (result !== null && value.change_set !== null))
    throw new ReplanningClientError(
      "response_invalid",
      "局部调整结果状态不一致，原计划保持不变。",
    );
  if (
    completed &&
    (result?.job_id !== value.job_id ||
      result.plan?.plan_id !== value.change_set?.result_plan_id ||
      value.change_set?.baseline_plan_id !== value.baseline_plan_id)
  ) {
    throw new ReplanningClientError(
      "response_invalid",
      "局部调整版本引用不一致，原计划保持不变。",
    );
  }
  return { ...(value as unknown as ReplanResponseDto), result };
}

async function requestJson(
  request: RequestFunction,
  input: string,
  init: RequestInit,
  expected: number[],
): Promise<ReplanResponseDto> {
  let response: Response;
  try {
    response = await request(input, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ReplanningClientError(
      "network_unavailable",
      "无法连接本机局部调整服务，原计划保持不变。",
      true,
    );
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ReplanningClientError(
      "response_invalid",
      "本机局部调整服务返回了无法识别的数据。",
    );
  }
  if (!response.ok || !expected.includes(response.status)) {
    const error =
      record(payload) && record(payload.error) && isError(payload.error)
        ? payload.error
        : null;
    throw new ReplanningClientError(
      error?.code ?? "http_error",
      error?.message ?? "本机局部调整服务暂时无法处理请求。",
      error?.retryable ?? response.status >= 500,
    );
  }
  return parseReplanResponse(payload);
}

function validId(value: string): void {
  if (!UUID.test(value))
    throw new ReplanningClientError(
      "response_invalid",
      "局部调整资源标识无效。",
    );
}

export function createReplanningApi(
  request: RequestFunction = fetch,
): ReplanningApi {
  const headers = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  return {
    create: (jobId, payload, signal) => {
      validId(jobId);
      return requestJson(
        request,
        `/api/trip-plans/${encodeURIComponent(jobId)}/replans`,
        { method: "POST", headers, body: JSON.stringify(payload), signal },
        [202],
      );
    },
    read: (jobId, replanId, signal) => {
      validId(jobId);
      validId(replanId);
      return requestJson(
        request,
        `/api/trip-plans/${encodeURIComponent(jobId)}/replans/${encodeURIComponent(replanId)}`,
        { method: "GET", headers: { Accept: "application/json" }, signal },
        [200],
      );
    },
    decide: (jobId, replanId, choice, signal) => {
      validId(jobId);
      validId(replanId);
      return requestJson(
        request,
        `/api/trip-plans/${encodeURIComponent(jobId)}/replans/${encodeURIComponent(replanId)}/decision`,
        { method: "POST", headers, body: JSON.stringify({ choice }), signal },
        [200, 202],
      );
    },
  };
}
