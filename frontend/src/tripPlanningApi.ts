import type { MoneyDto, TripPlanRequestDto } from "./tripRequest";
import {
  isConstraintViolation,
  isResolvedDestination,
  isSourceRecord,
  isTripPlan,
  isTripPlanV3,
  isUncertainty,
  type ConstraintViolationDto,
  type ResolvedDestinationDto,
  type SourceRecordDto,
  type TripPlanDto,
  type TripPlanV3Dto,
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

interface TripRequestSummaryDto {
  city: string;
  start_date: string;
  end_date: string;
  travelers: number;
  budget: MoneyDto;
}

interface TripRequestSummaryV2Dto extends TripRequestSummaryDto {
  request_version: "2";
}

export interface TripRequestSummaryV3Dto {
  request_version: "3";
  city_stays: Array<{ city: string; nights: number }>;
  start_date: string;
  end_date: string;
  travelers: number;
  budget: MoneyDto;
}

interface TripPlanResponseBaseDto {
  job_id: string;
  trace_id: string;
  client_request_id: string;
  status: PlanningStatus;
  attempt: number;
  request_summary: TripRequestSummaryDto;
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

export type LegacyTripPlanResponseDto = TripPlanResponseBaseDto;

export interface TripPlanResponseV2Dto extends TripPlanResponseBaseDto {
  response_version: "2";
  request_summary: TripRequestSummaryV2Dto;
}

export interface TripPlanResponseV3Dto {
  response_version: "3";
  job_id: string;
  trace_id: string;
  client_request_id: string;
  status: PlanningStatus;
  attempt: number;
  request_summary: TripRequestSummaryV3Dto;
  resolved_destinations: ResolvedDestinationDto[];
  plan: TripPlanV3Dto | null;
  violations: ConstraintViolationDto[];
  warnings: string[];
  uncertainties: UncertaintyDto[];
  sources: SourceRecordDto[];
  errors: ApiErrorDto[];
  retryable: boolean;
  created_at: string;
  updated_at: string;
}

export type TripPlanResponseDto =
  LegacyTripPlanResponseDto | TripPlanResponseV2Dto | TripPlanResponseV3Dto;

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
const RESPONSE_V2_KEYS = [...RESPONSE_KEYS, "response_version"] as const;
const RESPONSE_V3_KEYS = [
  "response_version",
  "job_id",
  "trace_id",
  "client_request_id",
  "status",
  "attempt",
  "request_summary",
  "resolved_destinations",
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
        response.plan.budget_summary.unknown_count === 0 &&
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

function v3UserIntercitySemanticsAreValid(
  response: TripPlanResponseDto,
): boolean {
  if (!("response_version" in response) || response.response_version !== "3")
    return true;
  if (response.plan === null) return true;
  if (!isTripPlanV3(response.plan)) return false;

  let elapsedNights = 0;
  const transferDates = response.request_summary.city_stays
    .slice(0, -1)
    .map((stay) => {
      elapsedNights += stay.nights;
      const timestamp =
        Date.parse(`${response.request_summary.start_date}T00:00:00Z`) +
        elapsedNights * 86_400_000;
      return new Date(timestamp).toISOString().slice(0, 10);
    });
  if (
    response.plan.intercity_segments.some(
      (segment, index) =>
        segment.departure_at.slice(0, 10) !== transferDates[index],
    )
  )
    return false;

  const sources = new Map(
    response.sources.map((source) => [source.source_id, source]),
  );
  return response.plan.intercity_segments.every((segment) =>
    segment.source_ids.every((sourceId) => {
      const source = sources.get(sourceId);
      return (
        source?.provider === "user" &&
        source.source_type === "user_provided_intercity_segment" &&
        source.provider_record_id === null &&
        source.valid_until === null &&
        source.freshness === "unknown_validity" &&
        source.reference_url === null &&
        source.attributions.length === 1 &&
        source.attributions[0] === "用户提供" &&
        source.warnings.length === 1 &&
        source.warnings[0] === "未核验班次、票价、余票或库存"
      );
    }),
  );
}

function sourceReferencesAreValid(response: TripPlanResponseDto): boolean {
  const knownSourceIds = new Set(
    response.sources.map((source) => source.source_id),
  );
  if (knownSourceIds.size !== response.sources.length) return false;

  const referencedSourceIds: string[] = [];
  const add = (sourceIds: readonly string[]) =>
    referencedSourceIds.push(...sourceIds);

  if ("response_version" in response && response.response_version === "3") {
    for (const destination of response.resolved_destinations)
      add(destination.source_ids);
  } else if (response.resolved_destination) {
    add(response.resolved_destination.source_ids);
  }
  for (const uncertainty of response.uncertainties) add(uncertainty.source_ids);

  if (response.plan) {
    for (const location of response.plan.locations) add(location.source_ids);
    for (const cost of response.plan.budget_summary.cost_items)
      add(cost.source_ids);
    if (isTripPlanV3(response.plan)) {
      for (const segment of response.plan.intercity_segments) {
        add(segment.source_ids);
        add(segment.fare.source_ids);
      }
    }
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

function isRequestSummary(
  value: unknown,
  version: "legacy" | "2" | "3",
): boolean {
  if (version === "3") {
    if (
      !isRecord(value) ||
      !hasExactKeys(value, [
        "request_version",
        "city_stays",
        "start_date",
        "end_date",
        "travelers",
        "budget",
      ]) ||
      value.request_version !== "3" ||
      !Array.isArray(value.city_stays) ||
      value.city_stays.length < 2 ||
      value.city_stays.length > 3 ||
      !value.city_stays.every(
        (stay) =>
          isRecord(stay) &&
          hasExactKeys(stay, ["city", "nights"]) &&
          typeof stay.city === "string" &&
          stay.city.trim().length >= 2 &&
          stay.city.length <= 30 &&
          Number.isInteger(stay.nights) &&
          Number(stay.nights) >= 1 &&
          Number(stay.nights) <= 6,
      )
    )
      return false;
    const dayCount =
      Math.round(
        (Date.parse(`${String(value.end_date)}T00:00:00Z`) -
          Date.parse(`${String(value.start_date)}T00:00:00Z`)) /
          86_400_000,
      ) + 1;
    return (
      isDate(value.start_date) &&
      isDate(value.end_date) &&
      dayCount >= 3 &&
      dayCount <= 7 &&
      value.city_stays.reduce(
        (total, stay) => total + Number(stay.nights),
        0,
      ) ===
        dayCount - 1 &&
      new Set(
        value.city_stays.map((stay) => String(stay.city).toLocaleLowerCase()),
      ).size === value.city_stays.length &&
      Number.isInteger(value.travelers) &&
      Number(value.travelers) >= 1 &&
      Number(value.travelers) <= 8 &&
      isMoney(value.budget)
    );
  }
  return (
    isRecord(value) &&
    hasExactKeys(
      value,
      version === "2"
        ? [
            "request_version",
            "city",
            "start_date",
            "end_date",
            "travelers",
            "budget",
          ]
        : ["city", "start_date", "end_date", "travelers", "budget"],
    ) &&
    (version !== "2" || value.request_version === "2") &&
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
  const version =
    isRecord(value) && value.response_version === "3"
      ? "3"
      : isRecord(value) && value.response_version === "2"
        ? "2"
        : "legacy";
  if (
    !isRecord(value) ||
    !hasExactKeys(
      value,
      version === "3"
        ? RESPONSE_V3_KEYS
        : version === "2"
          ? RESPONSE_V2_KEYS
          : RESPONSE_KEYS,
    ) ||
    ("response_version" in value &&
      value.response_version !== "2" &&
      value.response_version !== "3") ||
    !isUuid(value.job_id) ||
    !isUuid(value.trace_id) ||
    !isUuid(value.client_request_id) ||
    !PLANNING_STATUSES.includes(value.status as PlanningStatus) ||
    !Number.isInteger(value.attempt) ||
    Number(value.attempt) < 1 ||
    Number(value.attempt) > 3 ||
    !isRequestSummary(value.request_summary, version) ||
    (version === "3"
      ? !(
          Array.isArray(value.resolved_destinations) &&
          value.resolved_destinations.length <= 3 &&
          value.resolved_destinations.every(isResolvedDestination)
        )
      : !(
          value.resolved_destination === null ||
          isResolvedDestination(value.resolved_destination)
        )) ||
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
  const planVersionMatches =
    response.plan === null ||
    (version === "3"
      ? isTripPlanV3(response.plan)
      : version === "2"
        ? "plan_format_version" in response.plan &&
          response.plan.plan_format_version === "2"
        : !("plan_format_version" in response.plan));
  const requestAndPlanMatch = (() => {
    if (response.plan === null) return true;
    if (
      "response_version" in response &&
      response.response_version === "3" &&
      isTripPlanV3(response.plan)
    ) {
      return (
        response.plan.start_date === response.request_summary.start_date &&
        response.plan.end_date === response.request_summary.end_date &&
        response.plan.budget_summary.budget.amount ===
          response.request_summary.budget.amount &&
        response.plan.budget_summary.budget.currency ===
          response.request_summary.budget.currency &&
        response.resolved_destinations.length ===
          response.request_summary.city_stays.length &&
        response.resolved_destinations.map((item) => item.adcode).join(",") ===
          response.plan.city_adcodes.join(",")
      );
    }
    const singleCityResponse = response as
      LegacyTripPlanResponseDto | TripPlanResponseV2Dto;
    const singleCityPlan = singleCityResponse.plan;
    if (singleCityPlan === null || isTripPlanV3(singleCityPlan)) return false;
    return (
      singleCityPlan.start_date ===
        singleCityResponse.request_summary.start_date &&
      singleCityPlan.end_date === singleCityResponse.request_summary.end_date &&
      (singleCityResponse.resolved_destination === null ||
        singleCityPlan.city_adcode ===
          singleCityResponse.resolved_destination.adcode) &&
      singleCityPlan.budget_summary.budget.amount ===
        singleCityResponse.request_summary.budget.amount &&
      singleCityPlan.budget_summary.budget.currency ===
        singleCityResponse.request_summary.budget.currency
    );
  })();
  if (
    !terminalShapeIsValid(response) ||
    !sourceReferencesAreValid(response) ||
    !v3UserIntercitySemanticsAreValid(response) ||
    !planVersionMatches ||
    !requestAndPlanMatch
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
    ("response_version" in response && response.response_version === "3"
      ? response.resolved_destinations.length === 0
      : response.resolved_destination === null) &&
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
