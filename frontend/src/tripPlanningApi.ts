import type { MoneyDto, TripPlanRequestDto } from "./tripRequest";
import {
  isConstraintViolation,
  isResolvedDestination,
  isSourceRecord,
  isTripPlan,
  isUncertainty,
  type ConstraintViolationDto,
  type ResolvedDestinationDto,
  type SourceRecordDto,
  type TripPlanDto,
  type UncertaintyDto,
} from "./tripPlanModels";

export const PLANNING_STATUSES = [
  "draft",
  "normalizing",
  "needs_input",
  "collecting",
  "planning",
  "enriching_routes",
  "validating",
  "ready",
  "partial",
  "conflict",
  "failed",
] as const;

export type PlanningStatus = (typeof PLANNING_STATUSES)[number];

export const TERMINAL_STATUSES: ReadonlySet<PlanningStatus> = new Set([
  "needs_input",
  "ready",
  "partial",
  "conflict",
  "failed",
]);

const API_ERROR_CODES = [
  "input_invalid",
  "configuration_missing",
  "provider_unauthorized",
  "provider_rate_limited",
  "provider_timeout",
  "provider_unavailable",
  "provider_schema_invalid",
  "data_missing",
  "data_stale",
  "model_output_invalid",
  "constraint_conflict",
  "budget_incomplete",
  "idempotency_conflict",
  "job_not_found",
  "retry_not_allowed",
  "internal_error",
] as const;

export interface ApiErrorDto {
  code: string;
  message: string;
  field: string | null;
  provider: string | null;
  diagnostic_code?: string | null;
  retryable: boolean;
}

export interface TripPlanResponseDto {
  job_id: string;
  trace_id: string;
  client_request_id: string;
  status: PlanningStatus;
  attempt: number;
  request_summary: {
    city: string;
    start_date: string;
    end_date: string;
    travelers: number;
    budget: MoneyDto;
  };
  resolved_destination: ResolvedDestinationDto | null;
  plan: TripPlanDto | null;
  violations: ConstraintViolationDto[];
  warnings: string[];
  uncertainties: UncertaintyDto[];
  sources: SourceRecordDto[];
  errors: ApiErrorDto[];
  retryable: boolean;
  created_at: string;
  updated_at: string;
}

export interface TripPlanningApi {
  create(
    request: TripPlanRequestDto,
    signal?: AbortSignal,
  ): Promise<TripPlanResponseDto>;
  read(jobId: string, signal?: AbortSignal): Promise<TripPlanResponseDto>;
  retry(jobId: string, signal?: AbortSignal): Promise<TripPlanResponseDto>;
}

export class TripPlanningClientError extends Error {
  readonly code: string;
  readonly retryable: boolean;

  constructor(code: string, message: string, retryable = false) {
    super(message);
    this.name = "TripPlanningClientError";
    this.code = code;
    this.retryable = retryable;
  }
}

type RequestFunction = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const DATETIME_PATTERN =
  /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/;
const MONEY_PATTERN = /^(0|[1-9]\d*)(\.\d{1,2})?$/;
const UNSAFE_RESULT_TEXT =
  /authorization\s*:|(?:api[_-]?key|token|secret|password)\s*[=:]/i;
const RESPONSE_KEYS = [
  "job_id",
  "trace_id",
  "client_request_id",
  "status",
  "attempt",
  "request_summary",
  "resolved_destination",
  "plan",
  "violations",
  "warnings",
  "uncertainties",
  "sources",
  "errors",
  "retryable",
  "created_at",
  "updated_at",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function isDate(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const match = DATE_PATTERN.exec(value);
  if (!match) return false;
  const [, year, month, day] = match;
  const parsed = new Date(
    Date.UTC(Number(year), Number(month) - 1, Number(day)),
  );
  return (
    parsed.getUTCFullYear() === Number(year) &&
    parsed.getUTCMonth() === Number(month) - 1 &&
    parsed.getUTCDate() === Number(day)
  );
}

function isDateTime(value: unknown): value is string {
  return (
    typeof value === "string" &&
    DATETIME_PATTERN.test(value) &&
    isDate(value.slice(0, 10)) &&
    !Number.isNaN(Date.parse(value))
  );
}

function isMoney(value: unknown): value is MoneyDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["amount", "currency"]) &&
    typeof value.amount === "string" &&
    MONEY_PATTERN.test(value.amount) &&
    value.currency === "CNY"
  );
}

function isApiError(value: unknown): value is ApiErrorDto {
  const baseKeys = ["code", "message", "field", "provider", "retryable"];
  return (
    isRecord(value) &&
    (hasExactKeys(value, baseKeys) ||
      hasExactKeys(value, [...baseKeys, "diagnostic_code"])) &&
    API_ERROR_CODES.includes(value.code as (typeof API_ERROR_CODES)[number]) &&
    typeof value.message === "string" &&
    value.message.trim().length > 0 &&
    value.message.length <= 300 &&
    !UNSAFE_RESULT_TEXT.test(value.message) &&
    (value.field === null ||
      (typeof value.field === "string" &&
        value.field.trim().length > 0 &&
        value.field.length <= 120)) &&
    (value.provider === null ||
      (typeof value.provider === "string" && value.provider.length <= 40)) &&
    (value.diagnostic_code === undefined ||
      value.diagnostic_code === null ||
      (typeof value.diagnostic_code === "string" &&
        /^[a-z][a-z0-9_]{0,79}$/.test(value.diagnostic_code))) &&
    typeof value.retryable === "boolean"
  );
}

function terminalShapeIsValid(response: TripPlanResponseDto): boolean {
  const hasDiagnostics =
    response.violations.length > 0 ||
    response.warnings.length > 0 ||
    response.uncertainties.length > 0 ||
    response.errors.length > 0;
  const hasRetryableError = response.errors.some((error) => error.retryable);

  switch (response.status) {
    case "ready":
      return (
        response.plan !== null &&
        !response.retryable &&
        response.errors.length === 0 &&
        response.violations.length === 0
      );
    case "partial":
      return (
        response.plan !== null &&
        hasDiagnostics &&
        (!response.retryable || hasRetryableError)
      );
    case "conflict":
      return (
        !response.retryable &&
        (response.violations.length > 0 || response.errors.length > 0)
      );
    case "needs_input":
      return (
        response.plan === null &&
        !response.retryable &&
        response.errors.length > 0
      );
    case "failed":
      return (
        response.plan === null &&
        response.errors.length > 0 &&
        (!response.retryable || hasRetryableError)
      );
    default:
      return true;
  }
}

function sourceReferencesAreValid(response: TripPlanResponseDto): boolean {
  const knownSourceIds = new Set(
    response.sources.map((source) => source.source_id),
  );
  if (knownSourceIds.size !== response.sources.length) return false;

  const referencedSourceIds: string[] = [];
  const add = (sourceIds: readonly string[]) =>
    referencedSourceIds.push(...sourceIds);

  if (response.resolved_destination)
    add(response.resolved_destination.source_ids);
  for (const uncertainty of response.uncertainties) add(uncertainty.source_ids);

  if (response.plan) {
    for (const location of response.plan.locations) add(location.source_ids);
    for (const cost of response.plan.budget_summary.cost_items)
      add(cost.source_ids);
    for (const day of response.plan.days) {
      if (day.weather) {
        add(day.weather.source_ids);
        for (const alert of day.weather.alerts) add(alert.source_ids);
      }
      for (const activity of day.activities) {
        add(activity.source_ids);
        for (const cost of activity.cost_items) add(cost.source_ids);
      }
      for (const route of day.routes) {
        add(route.source_ids);
        if (route.fare) add(route.fare.source_ids);
      }
    }
  }

  return referencedSourceIds.every((sourceId) => knownSourceIds.has(sourceId));
}

function isRequestSummary(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "city",
      "start_date",
      "end_date",
      "travelers",
      "budget",
    ]) &&
    typeof value.city === "string" &&
    isDate(value.start_date) &&
    isDate(value.end_date) &&
    Number.isInteger(value.travelers) &&
    Number(value.travelers) >= 1 &&
    Number(value.travelers) <= 8 &&
    isMoney(value.budget)
  );
}

export function parseTripPlanResponse(value: unknown): TripPlanResponseDto {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, RESPONSE_KEYS) ||
    !isUuid(value.job_id) ||
    !isUuid(value.trace_id) ||
    !isUuid(value.client_request_id) ||
    !PLANNING_STATUSES.includes(value.status as PlanningStatus) ||
    !Number.isInteger(value.attempt) ||
    Number(value.attempt) < 1 ||
    Number(value.attempt) > 3 ||
    !isRequestSummary(value.request_summary) ||
    !(
      value.resolved_destination === null ||
      isResolvedDestination(value.resolved_destination)
    ) ||
    !(value.plan === null || isTripPlan(value.plan)) ||
    !(
      Array.isArray(value.violations) &&
      value.violations.length <= 50 &&
      value.violations.every(isConstraintViolation)
    ) ||
    !(
      Array.isArray(value.warnings) &&
      value.warnings.length <= 50 &&
      value.warnings.every(
        (warning) =>
          typeof warning === "string" &&
          warning.trim().length > 0 &&
          warning.length <= 500 &&
          !UNSAFE_RESULT_TEXT.test(warning),
      )
    ) ||
    !(
      Array.isArray(value.uncertainties) &&
      value.uncertainties.length <= 50 &&
      value.uncertainties.every(isUncertainty)
    ) ||
    !(
      Array.isArray(value.sources) &&
      value.sources.length <= 100 &&
      value.sources.every(isSourceRecord)
    ) ||
    !(
      Array.isArray(value.errors) &&
      value.errors.length <= 20 &&
      value.errors.every(isApiError)
    ) ||
    typeof value.retryable !== "boolean" ||
    !isDateTime(value.created_at) ||
    !isDateTime(value.updated_at)
  ) {
    throw new TripPlanningClientError(
      "response_invalid",
      "本机计划服务返回了无法识别的数据，已停止刷新。",
    );
  }

  const response = value as unknown as TripPlanResponseDto;
  if (
    !terminalShapeIsValid(response) ||
    !sourceReferencesAreValid(response) ||
    (response.plan !== null &&
      (response.plan.start_date !== response.request_summary.start_date ||
        response.plan.end_date !== response.request_summary.end_date ||
        (response.resolved_destination !== null &&
          response.plan.city_adcode !== response.resolved_destination.adcode) ||
        response.plan.budget_summary.budget.amount !==
          response.request_summary.budget.amount ||
        response.plan.budget_summary.budget.currency !==
          response.request_summary.budget.currency))
  ) {
    throw new TripPlanningClientError(
      "response_invalid",
      "本机计划服务返回了不一致的计划结果，已停止刷新。",
    );
  }

  return response;
}

function parseErrorEnvelope(value: unknown): ApiErrorDto | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["trace_id", "error"]) ||
    !(value.trace_id === null || isUuid(value.trace_id)) ||
    !isApiError(value.error)
  ) {
    return null;
  }
  return value.error;
}

async function json(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new TripPlanningClientError(
      "response_invalid",
      "本机计划服务返回了无法识别的数据，已停止刷新。",
    );
  }
}

async function requestJson(
  request: RequestFunction,
  input: string,
  init: RequestInit,
  expectedStatus: number,
): Promise<TripPlanResponseDto> {
  let response: Response;
  try {
    response = await request(input, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new TripPlanningClientError(
      "network_unavailable",
      "无法连接本机计划服务，请确认 FastAPI 已启动。",
      true,
    );
  }

  const payload = await json(response);
  if (!response.ok || response.status !== expectedStatus) {
    const safeError = parseErrorEnvelope(payload);
    if (safeError) {
      throw new TripPlanningClientError(
        safeError.code,
        safeError.message,
        safeError.retryable,
      );
    }
    throw new TripPlanningClientError(
      "http_error",
      "本机计划服务暂时无法处理请求。",
      response.status >= 500,
    );
  }

  return parseTripPlanResponse(payload);
}

function invalidJobId(): TripPlanningClientError {
  return new TripPlanningClientError(
    "response_invalid",
    "本机计划服务返回了无法识别的任务标识。",
  );
}

function retrySnapshotIsCleared(response: TripPlanResponseDto): boolean {
  return (
    response.status === "normalizing" &&
    response.attempt >= 2 &&
    response.resolved_destination === null &&
    response.plan === null &&
    response.violations.length === 0 &&
    response.warnings.length === 0 &&
    response.uncertainties.length === 0 &&
    response.sources.length === 0 &&
    response.errors.length === 0 &&
    !response.retryable
  );
}

export function createTripPlanningApi(
  request: RequestFunction = fetch,
): TripPlanningApi {
  return {
    create: (tripRequest, signal) =>
      requestJson(
        request,
        "/api/trip-plans",
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(tripRequest),
          signal,
        },
        202,
      ),
    read: (jobId, signal) => {
      if (!isUuid(jobId)) {
        return Promise.reject(invalidJobId());
      }
      return requestJson(
        request,
        `/api/trip-plans/${encodeURIComponent(jobId)}`,
        { method: "GET", headers: { Accept: "application/json" }, signal },
        200,
      );
    },
    retry: async (jobId, signal) => {
      if (!isUuid(jobId)) {
        throw invalidJobId();
      }
      const response = await requestJson(
        request,
        `/api/trip-plans/${encodeURIComponent(jobId)}/retry`,
        { method: "POST", headers: { Accept: "application/json" }, signal },
        202,
      );
      if (!retrySnapshotIsCleared(response)) {
        throw new TripPlanningClientError(
          "response_invalid",
          "本机计划服务返回了不一致的重试快照，已停止刷新。",
        );
      }
      return response;
    },
  };
}

export const tripPlanningApi = createTripPlanningApi();
