import type { MoneyDto } from "./tripRequest";

export const COST_CONFIDENCES = [
  "verified",
  "estimated",
  "user_provided",
  "unknown",
] as const;
export type CostConfidence = (typeof COST_CONFIDENCES)[number];

export const COST_CATEGORIES = [
  "accommodation",
  "intercity_transport",
  "local_transport",
  "ticket",
  "meal",
  "other",
] as const;
export type CostCategory = (typeof COST_CATEGORIES)[number];

export type RouteMode = "walking" | "public_transit";
export type BudgetAssessment =
  "within_budget" | "over_budget" | "budget_indeterminate";
export type ProviderName = "deepseek" | "amap" | "qweather" | "user" | "system";
export type DataFreshness = "fresh" | "stale" | "unknown_validity";

export interface CoordinatesDto {
  longitude: string;
  latitude: string;
  coordinate_system: "provider_native" | "wgs84" | "unknown";
}

export interface ResolvedDestinationDto {
  city_name: string;
  adcode: string;
  center: CoordinatesDto | null;
  source_ids: string[];
}

export interface LocationRefDto {
  location_id: string;
  provider: ProviderName;
  provider_place_id: string | null;
  name: string;
  category: string;
  address: string | null;
  city_adcode: string;
  coordinates: CoordinatesDto | null;
  source_ids: string[];
}

export interface CostItemDto {
  cost_id: string;
  category: CostCategory;
  confidence: CostConfidence;
  amount: MoneyDto | null;
  description: string;
  source_ids: string[];
}

export interface RouteLegDto {
  route_id: string;
  origin_location_id: string;
  destination_location_id: string;
  mode: RouteMode;
  distance_meters: number;
  duration_minutes: number;
  fare: CostItemDto | null;
  source_ids: string[];
}

export interface WeatherAlertDto {
  alert_id: string;
  title: string;
  severity: string | null;
  issued_at: string | null;
  description: string;
  source_ids: string[];
}

export interface WeatherSnapshotDto {
  forecast_date: string;
  location_id: string;
  condition_day: string;
  condition_night: string;
  temperature_min_celsius: string;
  temperature_max_celsius: string;
  alerts: WeatherAlertDto[];
  source_ids: string[];
}

export interface ItineraryItemDto {
  item_id: string;
  location_id: string;
  title: string;
  start_time: string;
  end_time: string;
  cost_items: CostItemDto[];
  source_ids: string[];
}

export interface PlanDayDto {
  local_date: string;
  accommodation_location_id: string;
  activities: ItineraryItemDto[];
  routes: RouteLegDto[];
  weather: WeatherSnapshotDto | null;
}

export interface BudgetSummaryDto {
  budget: MoneyDto;
  known_total: MoneyDto;
  unknown_count: number;
  assessment: BudgetAssessment;
  cost_items: CostItemDto[];
}

interface TripPlanBaseDto {
  plan_id: string;
  city_adcode: string;
  start_date: string;
  end_date: string;
  locations: LocationRefDto[];
  days: PlanDayDto[];
  budget_summary: BudgetSummaryDto;
}

export type LegacyTripPlanDto = TripPlanBaseDto;

export interface TripPlanV2Dto extends TripPlanBaseDto {
  plan_format_version: "2";
}

export type TripPlanDto = LegacyTripPlanDto | TripPlanV2Dto;

export interface ConstraintViolationDto {
  code: string;
  severity: "warning" | "error";
  message: string;
  affected_refs: string[];
}

export interface UncertaintyDto {
  code: string;
  message: string;
  affected_refs: string[];
  source_ids: string[];
}

export interface SourceRecordDto {
  source_id: string;
  provider: ProviderName;
  source_type: string;
  provider_record_id: string | null;
  fetched_at: string;
  valid_until: string | null;
  freshness: DataFreshness;
  reference_url: string | null;
  attributions: string[];
  warnings: string[];
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const TIME_PATTERN = /^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$/;
const DATETIME_PATTERN =
  /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/;
const MONEY_PATTERN = /^(0|[1-9]\d*)(\.\d{1,2})?$/;
const DECIMAL_PATTERN = /^-?(0|[1-9]\d*)(\.\d+)?$/;
const ADCODE_PATTERN = /^\d{6}$/;
const UNSAFE_RESULT_TEXT =
  /authorization\s*:|(?:api[_-]?key|token|secret|password)\s*[=:]/i;

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

function isText(value: unknown, maxLength = 500): value is string {
  return (
    typeof value === "string" &&
    value.trim().length > 0 &&
    value.length <= maxLength
  );
}

function isStringArray(
  value: unknown,
  maxLength: number,
  maxTextLength = 500,
): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= maxLength &&
    value.every((item) => isText(item, maxTextLength))
  );
}

function isHttpUrl(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 2048) return false;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" || parsed.protocol === "http:";
  } catch {
    return false;
  }
}

function isSafeResultText(value: unknown, maxLength = 500): value is string {
  return isText(value, maxLength) && !UNSAFE_RESULT_TEXT.test(value);
}

function isUuidArray(
  value: unknown,
  maxLength: number,
  requireValue = false,
): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= maxLength &&
    (!requireValue || value.length > 0) &&
    value.every(isUuid)
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

function isCoordinates(value: unknown): value is CoordinatesDto {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["longitude", "latitude", "coordinate_system"]) ||
    typeof value.longitude !== "string" ||
    typeof value.latitude !== "string" ||
    !DECIMAL_PATTERN.test(value.longitude) ||
    !DECIMAL_PATTERN.test(value.latitude) ||
    !["provider_native", "wgs84", "unknown"].includes(
      value.coordinate_system as string,
    )
  ) {
    return false;
  }
  const longitude = Number(value.longitude);
  const latitude = Number(value.latitude);
  return (
    longitude >= -180 && longitude <= 180 && latitude >= -90 && latitude <= 90
  );
}

function isCostItem(value: unknown): value is CostItemDto {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "cost_id",
      "category",
      "confidence",
      "amount",
      "description",
      "source_ids",
    ]) ||
    !isUuid(value.cost_id) ||
    !COST_CATEGORIES.includes(value.category as CostCategory) ||
    !COST_CONFIDENCES.includes(value.confidence as CostConfidence) ||
    !isText(value.description) ||
    !isUuidArray(value.source_ids, 20)
  ) {
    return false;
  }
  if (value.confidence === "unknown") return value.amount === null;
  if (!isMoney(value.amount)) return false;
  return value.confidence !== "verified" || value.source_ids.length > 0;
}

function isRoute(value: unknown): value is RouteLegDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "route_id",
      "origin_location_id",
      "destination_location_id",
      "mode",
      "distance_meters",
      "duration_minutes",
      "fare",
      "source_ids",
    ]) &&
    isUuid(value.route_id) &&
    isUuid(value.origin_location_id) &&
    isUuid(value.destination_location_id) &&
    ["walking", "public_transit"].includes(value.mode as string) &&
    Number.isInteger(value.distance_meters) &&
    Number(value.distance_meters) >= 0 &&
    Number.isInteger(value.duration_minutes) &&
    Number(value.duration_minutes) >= 1 &&
    Number(value.duration_minutes) <= 1440 &&
    (value.fare === null || isCostItem(value.fare)) &&
    isUuidArray(value.source_ids, 20, true)
  );
}

function isWeatherAlert(value: unknown): value is WeatherAlertDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "alert_id",
      "title",
      "severity",
      "issued_at",
      "description",
      "source_ids",
    ]) &&
    isText(value.alert_id) &&
    isText(value.title) &&
    (value.severity === null || isText(value.severity)) &&
    (value.issued_at === null || isDateTime(value.issued_at)) &&
    isText(value.description) &&
    isUuidArray(value.source_ids, 20, true)
  );
}

function isWeather(value: unknown): value is WeatherSnapshotDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "forecast_date",
      "location_id",
      "condition_day",
      "condition_night",
      "temperature_min_celsius",
      "temperature_max_celsius",
      "alerts",
      "source_ids",
    ]) &&
    isDate(value.forecast_date) &&
    isUuid(value.location_id) &&
    isText(value.condition_day) &&
    isText(value.condition_night) &&
    typeof value.temperature_min_celsius === "string" &&
    DECIMAL_PATTERN.test(value.temperature_min_celsius) &&
    typeof value.temperature_max_celsius === "string" &&
    DECIMAL_PATTERN.test(value.temperature_max_celsius) &&
    Array.isArray(value.alerts) &&
    value.alerts.length <= 20 &&
    value.alerts.every(isWeatherAlert) &&
    isUuidArray(value.source_ids, 20, true)
  );
}

function isActivity(value: unknown): value is ItineraryItemDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "item_id",
      "location_id",
      "title",
      "start_time",
      "end_time",
      "cost_items",
      "source_ids",
    ]) &&
    isUuid(value.item_id) &&
    isUuid(value.location_id) &&
    isText(value.title) &&
    typeof value.start_time === "string" &&
    TIME_PATTERN.test(value.start_time) &&
    typeof value.end_time === "string" &&
    TIME_PATTERN.test(value.end_time) &&
    Array.isArray(value.cost_items) &&
    value.cost_items.length <= 20 &&
    value.cost_items.every(isCostItem) &&
    isUuidArray(value.source_ids, 20, true)
  );
}

function isPlanDay(value: unknown): value is PlanDayDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "local_date",
      "accommodation_location_id",
      "activities",
      "routes",
      "weather",
    ]) &&
    isDate(value.local_date) &&
    isUuid(value.accommodation_location_id) &&
    Array.isArray(value.activities) &&
    value.activities.length <= 3 &&
    value.activities.every(isActivity) &&
    Array.isArray(value.routes) &&
    value.routes.length <= 4 &&
    value.routes.every(isRoute) &&
    (value.weather === null || isWeather(value.weather))
  );
}

function isLocation(value: unknown): value is LocationRefDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "location_id",
      "provider",
      "provider_place_id",
      "name",
      "category",
      "address",
      "city_adcode",
      "coordinates",
      "source_ids",
    ]) &&
    isUuid(value.location_id) &&
    ["deepseek", "amap", "qweather", "user", "system"].includes(
      value.provider as string,
    ) &&
    (value.provider_place_id === null || isText(value.provider_place_id)) &&
    isText(value.name) &&
    isText(value.category) &&
    (value.address === null || isText(value.address)) &&
    typeof value.city_adcode === "string" &&
    ADCODE_PATTERN.test(value.city_adcode) &&
    (value.coordinates === null || isCoordinates(value.coordinates)) &&
    isUuidArray(value.source_ids, 20, true)
  );
}

function isBudgetSummary(value: unknown): value is BudgetSummaryDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "budget",
      "known_total",
      "unknown_count",
      "assessment",
      "cost_items",
    ]) &&
    isMoney(value.budget) &&
    isMoney(value.known_total) &&
    Number.isInteger(value.unknown_count) &&
    Number(value.unknown_count) >= 0 &&
    ["within_budget", "over_budget", "budget_indeterminate"].includes(
      value.assessment as string,
    ) &&
    Array.isArray(value.cost_items) &&
    value.cost_items.length <= 50 &&
    value.cost_items.every(isCostItem) &&
    value.cost_items.filter(
      (item: CostItemDto) => item.confidence === "unknown",
    ).length === value.unknown_count
  );
}

export function isResolvedDestination(
  value: unknown,
): value is ResolvedDestinationDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["city_name", "adcode", "center", "source_ids"]) &&
    isText(value.city_name) &&
    typeof value.adcode === "string" &&
    ADCODE_PATTERN.test(value.adcode) &&
    (value.center === null || isCoordinates(value.center)) &&
    isUuidArray(value.source_ids, 20, true)
  );
}

export function isTripPlan(value: unknown): value is TripPlanDto {
  const isVersion2 = isRecord(value) && "plan_format_version" in value;
  if (
    !isRecord(value) ||
    !hasExactKeys(
      value,
      isVersion2
        ? [
            "plan_format_version",
            "plan_id",
            "city_adcode",
            "start_date",
            "end_date",
            "locations",
            "days",
            "budget_summary",
          ]
        : [
            "plan_id",
            "city_adcode",
            "start_date",
            "end_date",
            "locations",
            "days",
            "budget_summary",
          ],
    ) ||
    (isVersion2 && value.plan_format_version !== "2") ||
    !isUuid(value.plan_id) ||
    typeof value.city_adcode !== "string" ||
    !ADCODE_PATTERN.test(value.city_adcode) ||
    !isDate(value.start_date) ||
    !isDate(value.end_date) ||
    !Array.isArray(value.locations) ||
    value.locations.length < 1 ||
    value.locations.length > 20 ||
    !value.locations.every(isLocation) ||
    !Array.isArray(value.days) ||
    (isVersion2
      ? value.days.length < 2 || value.days.length > 7
      : value.days.length !== 2) ||
    !value.days.every(isPlanDay) ||
    !isBudgetSummary(value.budget_summary)
  ) {
    return false;
  }

  const plan = value as unknown as TripPlanDto;
  const locations = new Set(
    plan.locations.map((location) => location.location_id),
  );
  if (locations.size !== plan.locations.length) return false;
  const dayDifference = Math.round(
    (Date.parse(`${plan.end_date}T00:00:00Z`) -
      Date.parse(`${plan.start_date}T00:00:00Z`)) /
      86_400_000,
  );
  if (dayDifference + 1 !== plan.days.length) return false;
  if (
    plan.days.some(
      (day, index) =>
        day.local_date !==
        new Date(
          Date.parse(`${plan.start_date}T00:00:00Z`) + index * 86_400_000,
        )
          .toISOString()
          .slice(0, 10),
    )
  )
    return false;
  if (
    isVersion2 &&
    (plan.days.some(
      (day) =>
        day.activities.length < 1 ||
        day.activities.length > 2 ||
        day.routes.length > 3 ||
        (day.weather !== null && day.weather.forecast_date !== day.local_date),
    ) ||
      new Set(plan.days.map((day) => day.accommodation_location_id)).size !== 1)
  )
    return false;
  return plan.days.every(
    (day) =>
      locations.has(day.accommodation_location_id) &&
      day.activities.every((activity) => locations.has(activity.location_id)) &&
      day.routes.every(
        (route) =>
          locations.has(route.origin_location_id) &&
          locations.has(route.destination_location_id),
      ) &&
      (day.weather === null || locations.has(day.weather.location_id)),
  );
}

export function isConstraintViolation(
  value: unknown,
): value is ConstraintViolationDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["code", "severity", "message", "affected_refs"]) &&
    isText(value.code) &&
    ["warning", "error"].includes(value.severity as string) &&
    isSafeResultText(value.message) &&
    isUuidArray(value.affected_refs, 20)
  );
}

export function isUncertainty(value: unknown): value is UncertaintyDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["code", "message", "affected_refs", "source_ids"]) &&
    isText(value.code) &&
    isSafeResultText(value.message) &&
    isUuidArray(value.affected_refs, 20) &&
    isUuidArray(value.source_ids, 20)
  );
}

export function isSourceRecord(value: unknown): value is SourceRecordDto {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "source_id",
      "provider",
      "source_type",
      "provider_record_id",
      "fetched_at",
      "valid_until",
      "freshness",
      "reference_url",
      "attributions",
      "warnings",
    ]) &&
    isUuid(value.source_id) &&
    ["deepseek", "amap", "qweather", "user", "system"].includes(
      value.provider as string,
    ) &&
    isText(value.source_type) &&
    (value.provider_record_id === null || isText(value.provider_record_id)) &&
    isDateTime(value.fetched_at) &&
    (value.valid_until === null || isDateTime(value.valid_until)) &&
    ["fresh", "stale", "unknown_validity"].includes(
      value.freshness as string,
    ) &&
    (value.reference_url === null || isHttpUrl(value.reference_url)) &&
    isStringArray(value.attributions, 10) &&
    value.attributions.every((item) => isSafeResultText(item)) &&
    isStringArray(value.warnings, 10) &&
    value.warnings.every((item) => isSafeResultText(item))
  );
}
