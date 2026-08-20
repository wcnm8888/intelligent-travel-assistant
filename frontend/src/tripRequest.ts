export const INTEREST_OPTIONS = ["自然", "历史", "美食", "亲子"] as const;
export type Interest = (typeof INTEREST_OPTIONS)[number];

export type Pace = "relaxed" | "balanced" | "intensive";
export type TransportMode = "walking" | "public_transit";

export interface DayWindowFormValue {
  localDate: string;
  startTime: string;
  endTime: string;
}

export interface TripRequestFormValues {
  city: string;
  startDate: string;
  endDate: string;
  dayWindows: DayWindowFormValue[];
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

interface TripPlanRequestBaseDto {
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
  intercity_transport_cost: MoneyDto | null;
  meal_budget_per_person_per_day: MoneyDto;
}

export interface LegacyTripPlanRequestDto extends TripPlanRequestBaseDto {
  day_windows: [
    { day_offset: 0; start_time: string; end_time: string },
    { day_offset: 1; start_time: string; end_time: string },
  ];
}

export interface TripPlanRequestV2Dto extends TripPlanRequestBaseDto {
  request_version: "2";
  end_date: string;
  day_windows: Array<{
    day_offset: number;
    start_time: string;
    end_time: string;
  }>;
}

export type TripPlanRequestDto =
  LegacyTripPlanRequestDto | TripPlanRequestV2Dto;

export type TripRequestField =
  | "city"
  | "startDate"
  | "endDate"
  | "travelers"
  | "totalBudget"
  | "transportModes"
  | "accommodation"
  | "oneNightCost"
  | "mealBudgetPerPersonPerDay"
  | "freeText"
  | `dayWindows.${number}.startTime`
  | `dayWindows.${number}.endTime`;

export type TripRequestErrors = Partial<Record<TripRequestField, string>>;

const MONEY_PATTERN = /^(0|[1-9]\d*)(\.\d{1,2})?$/;
const DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const TIME_PATTERN = /^(?:[01]\d|2[0-3]):[0-5]\d$/;

export function currentShanghaiDate(now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const value = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  );
  return `${value.year}-${value.month}-${value.day}`;
}

export function addCalendarDays(value: string, days: number): string {
  if (!isCalendarDate(value)) return "";
  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day + days));
  return parsed.toISOString().slice(0, 10);
}

function calendarDayDifference(start: string, end: string): number | null {
  if (!isCalendarDate(start) || !isCalendarDate(end)) return null;
  const startTime = Date.parse(`${start}T00:00:00Z`);
  const endTime = Date.parse(`${end}T00:00:00Z`);
  return Math.round((endTime - startTime) / 86_400_000);
}

export function tripDayCount(start: string, end: string): number | null {
  const difference = calendarDayDifference(start, end);
  return difference === null ? null : difference + 1;
}

function defaultWindow(localDate: string, index: number): DayWindowFormValue {
  return {
    localDate,
    startTime: "09:00",
    endTime: index === 0 ? "20:00" : "18:00",
  };
}

export function syncDayWindows(
  current: readonly DayWindowFormValue[],
  startDate: string,
  endDate: string,
): DayWindowFormValue[] {
  const count = tripDayCount(startDate, endDate);
  if (count === null || count < 2 || count > 7) return [];
  const byDate = new Map(current.map((item) => [item.localDate, item]));
  return Array.from({ length: count }, (_, index) => {
    const localDate = addCalendarDays(startDate, index);
    return byDate.get(localDate) ?? defaultWindow(localDate, index);
  });
}

export function createInitialTripRequest(
  startDate = "",
): TripRequestFormValues {
  const endDate = addCalendarDays(startDate, 1);
  return {
    city: "",
    startDate,
    endDate,
    dayWindows: syncDayWindows([], startDate, endDate),
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

export function isCalendarDate(value: string): boolean {
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
  planningToday?: string,
): TripRequestErrors {
  const errors: TripRequestErrors = {};
  const city = values.city.trim();
  const accommodation = values.accommodation.trim();

  if (city.length < 2 || city.length > 30) {
    errors.city = "请输入 2—30 个字符的中国大陆城市名称。";
  }
  if (!isCalendarDate(values.startDate)) {
    errors.startDate = "请选择有效的开始日期。";
  } else if (
    planningToday &&
    (values.startDate < addCalendarDays(planningToday, 1) ||
      values.startDate > addCalendarDays(planningToday, 5))
  ) {
    errors.startDate = "开始日期必须在明天至未来第 5 天之间。";
  }
  if (!isCalendarDate(values.endDate)) {
    errors.endDate = "请选择有效的结束日期。";
  } else if (isCalendarDate(values.startDate)) {
    const count = tripDayCount(values.startDate, values.endDate);
    if (count === null || count < 2 || count > 7) {
      errors.endDate = "行程必须连续覆盖 2—7 天，结束日期需晚于开始日期。";
    }
  }
  const expectedWindows = syncDayWindows(
    values.dayWindows,
    values.startDate,
    values.endDate,
  );
  if (
    expectedWindows.length > 0 &&
    (values.dayWindows.length !== expectedWindows.length ||
      values.dayWindows.some(
        (item, index) => item.localDate !== expectedWindows[index]?.localDate,
      ))
  ) {
    errors.endDate = "逐日时间窗口与日期范围不一致。";
  }
  values.dayWindows.forEach((window, index) => {
    if (!TIME_PATTERN.test(window.startTime)) {
      errors[`dayWindows.${index}.startTime`] = "请选择有效的开始时间。";
    }
    if (
      !TIME_PATTERN.test(window.endTime) ||
      (TIME_PATTERN.test(window.startTime) &&
        window.endTime <= window.startTime)
    ) {
      errors[`dayWindows.${index}.endTime`] =
        "结束时间必须晚于开始时间，且不能跨夜。";
    }
  });

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
  useVersion2 = false,
): TripPlanRequestDto {
  const common: TripPlanRequestBaseDto = {
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
    intercity_transport_cost: null,
    meal_budget_per_person_per_day: money(values.mealBudgetPerPersonPerDay),
  };
  if (useVersion2) {
    return {
      ...common,
      request_version: "2",
      end_date: values.endDate,
      day_windows: values.dayWindows.map((window, dayOffset) => ({
        day_offset: dayOffset,
        start_time: `${window.startTime}:00`,
        end_time: `${window.endTime}:00`,
      })),
    };
  }
  return {
    ...common,
    day_windows: [
      {
        day_offset: 0,
        start_time: `${values.dayWindows[0]?.startTime ?? "09:00"}:00`,
        end_time: `${values.dayWindows[0]?.endTime ?? "20:00"}:00`,
      },
      {
        day_offset: 1,
        start_time: `${values.dayWindows[1]?.startTime ?? "09:00"}:00`,
        end_time: `${values.dayWindows[1]?.endTime ?? "18:00"}:00`,
      },
    ],
  };
}
