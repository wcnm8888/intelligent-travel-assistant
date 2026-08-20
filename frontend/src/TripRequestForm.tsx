import { useId, useState, type FormEvent } from "react";

import {
  addCalendarDays,
  createInitialTripRequest,
  currentShanghaiDate,
  INTEREST_OPTIONS,
  syncDayWindows,
  toTripPlanRequest,
  tripDayCount,
  validateTripRequest,
  type Interest,
  type Pace,
  type TransportMode,
  type TripPlanRequestDto,
  type TripRequestErrors,
  type TripRequestField,
  type TripRequestFormValues,
} from "./tripRequest";

interface TripRequestFormProps {
  onSubmit: (request: TripPlanRequestDto) => void;
  createClientRequestId?: () => string;
  initialStartDate?: string;
  planningToday?: string;
  submitting?: boolean;
}

const PACE_OPTIONS: ReadonlyArray<{ value: Pace; label: string }> = [
  { value: "relaxed", label: "舒缓" },
  { value: "balanced", label: "均衡" },
  { value: "intensive", label: "紧凑" },
];

const TRANSPORT_OPTIONS: ReadonlyArray<{
  value: TransportMode;
  label: string;
}> = [
  { value: "walking", label: "步行" },
  { value: "public_transit", label: "公共交通" },
];

function FieldError({
  id,
  message,
}: {
  id: string;
  message: string | undefined;
}) {
  if (!message) return null;
  return (
    <p className="field-error" id={id} role="alert">
      {message}
    </p>
  );
}

export function TripRequestForm({
  onSubmit,
  createClientRequestId = () => crypto.randomUUID(),
  initialStartDate = "",
  planningToday = currentShanghaiDate(),
  submitting = false,
}: TripRequestFormProps) {
  const formId = useId();
  const [values, setValues] = useState<TripRequestFormValues>(() =>
    createInitialTripRequest(initialStartDate),
  );
  const [errors, setErrors] = useState<TripRequestErrors>({});
  const [endDateEdited, setEndDateEdited] = useState(false);

  const update = <Key extends keyof TripRequestFormValues>(
    key: Key,
    value: TripRequestFormValues[Key],
  ) => {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const updateStartDate = (startDate: string) => {
    setValues((current) => {
      const automaticEndDate = endDateEdited
        ? current.endDate
        : addCalendarDays(startDate, 1);
      return {
        ...current,
        startDate,
        endDate: automaticEndDate,
        dayWindows: syncDayWindows(
          current.dayWindows,
          startDate,
          automaticEndDate,
        ),
      };
    });
    setErrors((current) => ({
      ...current,
      startDate: undefined,
      endDate: undefined,
    }));
  };

  const updateEndDate = (endDate: string) => {
    setEndDateEdited(true);
    setValues((current) => ({
      ...current,
      endDate,
      dayWindows: syncDayWindows(
        current.dayWindows,
        current.startDate,
        endDate,
      ),
    }));
    setErrors((current) => ({ ...current, endDate: undefined }));
  };

  const updateDayWindow = (
    index: number,
    key: "startTime" | "endTime",
    value: string,
  ) => {
    setValues((current) => ({
      ...current,
      dayWindows: current.dayWindows.map((window, windowIndex) =>
        windowIndex === index ? { ...window, [key]: value } : window,
      ),
    }));
    setErrors((current) => ({
      ...current,
      [`dayWindows.${index}.${key}`]: undefined,
    }));
  };

  const toggleInterest = (interest: Interest) => {
    update(
      "interests",
      values.interests.includes(interest)
        ? values.interests.filter((item) => item !== interest)
        : [...values.interests, interest],
    );
  };

  const toggleTransport = (mode: TransportMode) => {
    update(
      "transportModes",
      values.transportModes.includes(mode)
        ? values.transportModes.filter((item) => item !== mode)
        : [...values.transportModes, mode],
    );
  };

  const focusFirstError = (
    form: HTMLFormElement,
    nextErrors: TripRequestErrors,
  ) => {
    const order: TripRequestField[] = [
      "city",
      "startDate",
      "endDate",
      ...values.dayWindows.flatMap((_, index) => [
        `dayWindows.${index}.startTime` as TripRequestField,
        `dayWindows.${index}.endTime` as TripRequestField,
      ]),
      "travelers",
      "totalBudget",
      "transportModes",
      "accommodation",
      "oneNightCost",
      "mealBudgetPerPersonPerDay",
      "freeText",
    ];
    const first = order.find((field) => nextErrors[field]);
    if (!first) return;
    form.querySelector<HTMLElement>(`[data-field="${first}"]`)?.focus();
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;

    const nextErrors = validateTripRequest(values, planningToday);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      focusFirstError(event.currentTarget, nextErrors);
      return;
    }

    onSubmit(toTripPlanRequest(values, createClientRequestId(), endDateEdited));
  };

  const errorId = (field: TripRequestField) =>
    `${formId}-${field.replaceAll(".", "-")}-error`;
  const dayCount = tripDayCount(values.startDate, values.endDate);

  return (
    <form
      className="trip-form"
      aria-labelledby={`${formId}-title`}
      noValidate
      onSubmit={submit}
    >
      <div className="form-heading">
        <div>
          <p className="section-kicker">YOUR TRIP / 01</p>
          <h2 id={`${formId}-title`}>行前设定</h2>
        </div>
        <span>2—7 日 · 单城市</span>
      </div>

      <div className="field-grid">
        <div className="field field--wide">
          <label htmlFor={`${formId}-city`}>目的地城市 *</label>
          <input
            id={`${formId}-city`}
            name="city"
            data-field="city"
            value={values.city}
            aria-invalid={Boolean(errors.city)}
            aria-describedby={errors.city ? errorId("city") : undefined}
            autoComplete="address-level1"
            maxLength={30}
            placeholder="例如：杭州"
            onChange={(event) => update("city", event.target.value)}
          />
          <p className="field-hint">第一版仅支持中国大陆单城市自由行。</p>
          <FieldError id={errorId("city")} message={errors.city} />
        </div>

        <div className="field">
          <label htmlFor={`${formId}-start-date`}>开始日期 *</label>
          <input
            id={`${formId}-start-date`}
            name="startDate"
            data-field="startDate"
            type="date"
            value={values.startDate}
            aria-invalid={Boolean(errors.startDate)}
            aria-describedby={
              errors.startDate ? errorId("startDate") : undefined
            }
            onChange={(event) => updateStartDate(event.target.value)}
          />
          <FieldError id={errorId("startDate")} message={errors.startDate} />
        </div>

        <div className="field">
          <label htmlFor={`${formId}-end-date`}>结束日期 *</label>
          <input
            id={`${formId}-end-date`}
            name="endDate"
            data-field="endDate"
            type="date"
            value={values.endDate}
            aria-invalid={Boolean(errors.endDate)}
            aria-describedby={errors.endDate ? errorId("endDate") : undefined}
            onChange={(event) => updateEndDate(event.target.value)}
          />
          <p className="field-hint">
            连续 2—7 日；手动修改后不会被开始日期静默覆盖。
          </p>
          <FieldError id={errorId("endDate")} message={errors.endDate} />
        </div>

        <div className="field">
          <label htmlFor={`${formId}-travelers`}>同行人数 *</label>
          <input
            id={`${formId}-travelers`}
            name="travelers"
            data-field="travelers"
            type="number"
            min="1"
            max="8"
            step="1"
            inputMode="numeric"
            value={values.travelers}
            aria-invalid={Boolean(errors.travelers)}
            aria-describedby={
              errors.travelers ? errorId("travelers") : undefined
            }
            onChange={(event) => update("travelers", event.target.value)}
          />
          <FieldError id={errorId("travelers")} message={errors.travelers} />
        </div>

        {values.dayWindows.length > 0 && (
          <fieldset className="field field--wide day-window-fieldset">
            <legend>逐日可用时间 *</legend>
            <p className="field-hint">
              共 {dayCount} 天；每一天都使用目的地当地时间，不支持跨夜。
            </p>
            <div className="day-window-list">
              {values.dayWindows.map((window, index) => {
                const startField =
                  `dayWindows.${index}.startTime` as TripRequestField;
                const endField =
                  `dayWindows.${index}.endTime` as TripRequestField;
                return (
                  <div className="day-window-row" key={window.localDate}>
                    <div className="day-window-date">
                      <strong>第 {index + 1} 天</strong>
                      <span>{window.localDate}</span>
                    </div>
                    <div className="field">
                      <label htmlFor={`${formId}-day-${index}-start`}>
                        第 {index + 1} 天开始时间
                      </label>
                      <input
                        id={`${formId}-day-${index}-start`}
                        data-field={startField}
                        type="time"
                        value={window.startTime}
                        aria-invalid={Boolean(errors[startField])}
                        aria-describedby={
                          errors[startField] ? errorId(startField) : undefined
                        }
                        onChange={(event) =>
                          updateDayWindow(
                            index,
                            "startTime",
                            event.target.value,
                          )
                        }
                      />
                      <FieldError
                        id={errorId(startField)}
                        message={errors[startField]}
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`${formId}-day-${index}-end`}>
                        第 {index + 1} 天结束时间
                      </label>
                      <input
                        id={`${formId}-day-${index}-end`}
                        data-field={endField}
                        type="time"
                        value={window.endTime}
                        aria-invalid={Boolean(errors[endField])}
                        aria-describedby={
                          errors[endField] ? errorId(endField) : undefined
                        }
                        onChange={(event) =>
                          updateDayWindow(index, "endTime", event.target.value)
                        }
                      />
                      <FieldError
                        id={errorId(endField)}
                        message={errors[endField]}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </fieldset>
        )}

        <div className="field field--wide">
          <label htmlFor={`${formId}-total-budget`}>总预算 *</label>
          <div className="money-input">
            <span aria-hidden="true">¥</span>
            <input
              id={`${formId}-total-budget`}
              name="totalBudget"
              data-field="totalBudget"
              inputMode="decimal"
              value={values.totalBudget}
              aria-invalid={Boolean(errors.totalBudget)}
              aria-describedby={`${formId}-budget-hint${errors.totalBudget ? ` ${errorId("totalBudget")}` : ""}`}
              placeholder="4000.00"
              onChange={(event) => update("totalBudget", event.target.value)}
            />
            <span>CNY</span>
          </div>
          <p className="field-hint" id={`${formId}-budget-hint`}>
            覆盖住宿、城际/市内交通、门票、餐饮等全部费用。
          </p>
          <FieldError
            id={errorId("totalBudget")}
            message={errors.totalBudget}
          />
        </div>

        <fieldset className="field field--wide option-field">
          <legend>兴趣偏好</legend>
          <div className="choice-row">
            {INTEREST_OPTIONS.map((interest) => (
              <label className="choice-chip" key={interest}>
                <input
                  type="checkbox"
                  checked={values.interests.includes(interest)}
                  onChange={() => toggleInterest(interest)}
                />
                <span>{interest}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="field field--wide">
          <label htmlFor={`${formId}-pace`}>行程节奏</label>
          <select
            id={`${formId}-pace`}
            value={values.pace}
            onChange={(event) => update("pace", event.target.value as Pace)}
          >
            {PACE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <fieldset
          className="field field--wide option-field"
          aria-describedby={
            errors.transportModes ? errorId("transportModes") : undefined
          }
        >
          <legend>市内交通 *</legend>
          <div className="choice-row">
            {TRANSPORT_OPTIONS.map((option, index) => (
              <label className="choice-chip" key={option.value}>
                <input
                  type="checkbox"
                  data-field={index === 0 ? "transportModes" : undefined}
                  checked={values.transportModes.includes(option.value)}
                  onChange={() => toggleTransport(option.value)}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
          <FieldError
            id={errorId("transportModes")}
            message={errors.transportModes}
          />
        </fieldset>

        <div className="field field--wide">
          <label htmlFor={`${formId}-accommodation`}>住宿区域或 POI *</label>
          <input
            id={`${formId}-accommodation`}
            name="accommodation"
            data-field="accommodation"
            value={values.accommodation}
            aria-invalid={Boolean(errors.accommodation)}
            aria-describedby={`${formId}-accommodation-hint${errors.accommodation ? ` ${errorId("accommodation")}` : ""}`}
            maxLength={120}
            placeholder="例如：湖滨银泰附近"
            onChange={(event) => update("accommodation", event.target.value)}
          />
          <p className="field-hint" id={`${formId}-accommodation-hint`}>
            不是实时酒店库存，也不代表可预订。
          </p>
          <FieldError
            id={errorId("accommodation")}
            message={errors.accommodation}
          />
        </div>

        <div className="field">
          <label htmlFor={`${formId}-night-cost`}>一晚住宿费用</label>
          <div className="money-input money-input--compact">
            <span aria-hidden="true">¥</span>
            <input
              id={`${formId}-night-cost`}
              name="oneNightCost"
              data-field="oneNightCost"
              inputMode="decimal"
              value={values.oneNightCost}
              aria-invalid={Boolean(errors.oneNightCost)}
              aria-describedby={
                errors.oneNightCost ? errorId("oneNightCost") : undefined
              }
              placeholder="不清楚可留空"
              onChange={(event) => update("oneNightCost", event.target.value)}
            />
          </div>
          <FieldError
            id={errorId("oneNightCost")}
            message={errors.oneNightCost}
          />
        </div>

        <div className="field">
          <label htmlFor={`${formId}-meal-budget`}>餐饮 / 人 / 天</label>
          <div className="money-input money-input--compact">
            <span aria-hidden="true">¥</span>
            <input
              id={`${formId}-meal-budget`}
              name="mealBudgetPerPersonPerDay"
              data-field="mealBudgetPerPersonPerDay"
              inputMode="decimal"
              value={values.mealBudgetPerPersonPerDay}
              aria-invalid={Boolean(errors.mealBudgetPerPersonPerDay)}
              aria-describedby={`${formId}-meal-hint${errors.mealBudgetPerPersonPerDay ? ` ${errorId("mealBudgetPerPersonPerDay")}` : ""}`}
              onChange={(event) =>
                update("mealBudgetPerPersonPerDay", event.target.value)
              }
            />
          </div>
          <p className="field-hint" id={`${formId}-meal-hint`}>
            默认 100 元，可自行修改。
          </p>
          <FieldError
            id={errorId("mealBudgetPerPersonPerDay")}
            message={errors.mealBudgetPerPersonPerDay}
          />
        </div>

        <div className="field field--wide">
          <label htmlFor={`${formId}-free-text`}>补充要求</label>
          <textarea
            id={`${formId}-free-text`}
            name="freeText"
            data-field="freeText"
            rows={4}
            maxLength={201}
            value={values.freeText}
            aria-invalid={Boolean(errors.freeText)}
            aria-describedby={`${formId}-free-text-count${errors.freeText ? ` ${errorId("freeText")}` : ""}`}
            placeholder="例如：节奏不要太赶；博物馆优先安排在白天。"
            onChange={(event) => update("freeText", event.target.value)}
          />
          <p
            className="field-hint field-count"
            id={`${formId}-free-text-count`}
          >
            {values.freeText.length} / 200
          </p>
          <FieldError id={errorId("freeText")} message={errors.freeText} />
        </div>
      </div>

      <div className="form-actions">
        <button className="submit-button" type="submit" disabled={submitting}>
          <span>
            {submitting
              ? "正在提交"
              : `生成${dayCount && dayCount >= 2 && dayCount <= 7 ? dayCount : 2}日计划`}
          </span>
          <span aria-hidden="true">→</span>
        </button>
        <p>请求仅发送至本机后端；自动刷新有次数上限，可随时手动继续。</p>
      </div>
    </form>
  );
}
