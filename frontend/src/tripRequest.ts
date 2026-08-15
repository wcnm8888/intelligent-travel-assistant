export const INTEREST_OPTIONS = ["自然", "历史", "美食", "亲子"] as const;
export type Interest = (typeof INTEREST_OPTIONS)[number];

export type Pace = "relaxed" | "balanced" | "intensive";
export type TransportMode = "walking" | "public_transit";

export interface TripRequestFormValues {
  city: string;
  startDate: string;
  travelers: string;
  totalBudget: string;
  interests: Interest[];
  pace: Pace;
  transportModes: TransportMode[];
  accommodation: string;
  oneNightCost: string;
  mealBudgetPerPersonPerDay: string;
  freeText: string;
}

export interface MoneyDto {
  amount: string;
  currency: "CNY";
}

export interface TripPlanRequestDto {
  client_request_id: string;
  city: string;
  start_date: string;
  travelers: number;
  total_budget: MoneyDto;
  preferences: {
    interests: Interest[];
    free_text: string;
    hard_constraints: string[];
  };
  pace: Pace;
  transport_modes: TransportMode[];
  accommodation: {
    area_or_poi: string;
    one_night_cost: MoneyDto | null;
  };
  day_windows: [
    { day_offset: 0; start_time: "09:00:00"; end_time: "20:00:00" },
    { day_offset: 1; start_time: "09:00:00"; end_time: "18:00:00" },
  ];
  intercity_transport_cost: MoneyDto | null;
  meal_budget_per_person_per_day: MoneyDto;
}

export type TripRequestField =
  | "city"
  | "startDate"
  | "travelers"
  | "totalBudget"
  | "transportModes"
  | "accommodation"
  | "oneNightCost"
  | "mealBudgetPerPersonPerDay"
  | "freeText";

export type TripRequestErrors = Partial<Record<TripRequestField, string>>;

const MONEY_PATTERN = /^(0|[1-9]\d*)(\.\d{1,2})?$/;
const DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

export function createInitialTripRequest(
  startDate = "",
): TripRequestFormValues {
  return {
    city: "",
    startDate,
    travelers: "2",
    totalBudget: "",
    interests: [],
    pace: "balanced",
    transportModes: ["walking", "public_transit"],
    accommodation: "",
    oneNightCost: "",
    mealBudgetPerPersonPerDay: "100.00",
    freeText: "",
  };
}

function isCalendarDate(value: string): boolean {
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

function isMoney(value: string): boolean {
  return MONEY_PATTERN.test(value);
}

export function validateTripRequest(
  values: TripRequestFormValues,
): TripRequestErrors {
  const errors: TripRequestErrors = {};
  const city = values.city.trim();
  const accommodation = values.accommodation.trim();

  if (city.length < 2 || city.length > 30) {
    errors.city = "请输入 2—30 个字符的中国大陆城市名称。";
  }
  if (!isCalendarDate(values.startDate)) {
    errors.startDate = "请选择有效的开始日期。";
  }

  const travelers = Number(values.travelers);
  if (!Number.isInteger(travelers) || travelers < 1 || travelers > 8) {
    errors.travelers = "同行人数必须是 1—8 的整数。";
  }
  if (!isMoney(values.totalBudget) || Number(values.totalBudget) <= 0) {
    errors.totalBudget = "请输入大于 0、最多两位小数的总预算。";
  }
  if (values.transportModes.length === 0) {
    errors.transportModes = "至少选择一种市内交通方式。";
  }
  if (accommodation.length < 1 || accommodation.length > 120) {
    errors.accommodation = "请输入住宿区域或明确 POI（最多 120 个字符）。";
  }
  if (values.oneNightCost && !isMoney(values.oneNightCost)) {
    errors.oneNightCost = "住宿费用最多保留两位小数，不清楚时可以留空。";
  }
  if (
    !isMoney(values.mealBudgetPerPersonPerDay) ||
    Number(values.mealBudgetPerPersonPerDay) < 0
  ) {
    errors.mealBudgetPerPersonPerDay =
      "餐饮预算必须是非负金额，最多保留两位小数。";
  }
  if (values.freeText.trim().length > 200) {
    errors.freeText = "补充要求不能超过 200 个字符。";
  }

  return errors;
}

function money(amount: string): MoneyDto {
  return { amount, currency: "CNY" };
}

export function toTripPlanRequest(
  values: TripRequestFormValues,
  clientRequestId: string,
): TripPlanRequestDto {
  return {
    client_request_id: clientRequestId,
    city: values.city.trim(),
    start_date: values.startDate,
    travelers: Number(values.travelers),
    total_budget: money(values.totalBudget),
    preferences: {
      interests: [...values.interests],
      free_text: values.freeText.trim(),
      hard_constraints: [],
    },
    pace: values.pace,
    transport_modes: [...values.transportModes],
    accommodation: {
      area_or_poi: values.accommodation.trim(),
      one_night_cost: values.oneNightCost ? money(values.oneNightCost) : null,
    },
    day_windows: [
      { day_offset: 0, start_time: "09:00:00", end_time: "20:00:00" },
      { day_offset: 1, start_time: "09:00:00", end_time: "18:00:00" },
    ],
    intercity_transport_cost: null,
    meal_budget_per_person_per_day: money(values.mealBudgetPerPersonPerDay),
  };
}
