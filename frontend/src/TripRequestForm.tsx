import { useId, useState, type FormEvent } from "react";

import {
  addCalendarDays,
  createInitialTripRequest,
  currentShanghaiDate,
  emptyCityStay,
  emptyIntercitySegment,
  INTERCITY_BUFFERS,
  INTEREST_OPTIONS,
  syncDayWindows,
  toTripPlanRequest,
  tripDayCount,
  validateTripRequest,
  type Interest,
  type IntercityMode,
  type Pace,
  type TransportMode,
  type TripPlanRequestDto,
  type TripRequestErrors,
  type TripRequestField,
  type TripRequestFormValues,
  type TripScope,
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

const INTERCITY_OPTIONS: ReadonlyArray<{
  value: IntercityMode;
  label: string;
}> = [
  { value: "rail", label: "铁路" },
  { value: "air", label: "航空" },
  { value: "coach", label: "长途客运" },
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
  const [multicityNotice, setMulticityNotice] = useState("");

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

  const changeScope = (scope: TripScope) => {
    if (scope === values.scope) return;
    const hasIncompatibleInput =
      values.scope === "single_city"
        ? Boolean(
            values.city.trim() ||
            values.accommodation.trim() ||
            values.oneNightCost,
          )
        : values.cityStays.some(
            (stay) =>
              stay.city.trim() ||
              stay.accommodation.trim() ||
              stay.oneNightCost,
          ) ||
          values.intercitySegments.some(
            (segment) =>
              segment.departureStation.trim() ||
              segment.arrivalStation.trim() ||
              segment.fare,
          );
    if (
      hasIncompatibleInput &&
      !window.confirm("切换行程范围会清除城市、住宿和城际段输入，是否继续？")
    )
      return;
    setValues((current) => ({
      ...current,
      scope,
      city: "",
      accommodation: "",
      oneNightCost: "",
      cityStays: [emptyCityStay(), emptyCityStay()],
      intercitySegments: [emptyIntercitySegment()],
    }));
    setErrors({});
    setMulticityNotice(
      scope === "multi_city"
        ? "已切换为多城市模式；请按顺序填写城市和相邻城际段。"
        : "已切换为单城市模式。",
    );
  };

  const updateCityStay = (
    index: number,
    key: "city" | "accommodation" | "oneNightCost" | "nights",
    value: string,
  ) => {
    setValues((current) => ({
      ...current,
      cityStays: current.cityStays.map((stay, stayIndex) =>
        stayIndex === index ? { ...stay, [key]: value } : stay,
      ),
    }));
    setErrors((current) => ({
      ...current,
      [`cityStays.${index}.${key}`]: undefined,
    }));
  };

  const updateIntercitySegment = (
    index: number,
    key:
      | "mode"
      | "departureStation"
      | "arrivalStation"
      | "departureTime"
      | "arrivalTime"
      | "fare",
    value: string,
  ) => {
    setValues((current) => ({
      ...current,
      intercitySegments: current.intercitySegments.map(
        (segment, segmentIndex) =>
          segmentIndex === index ? { ...segment, [key]: value } : segment,
      ),
    }));
    setErrors((current) => ({
      ...current,
      [`intercitySegments.${index}.${key}`]: undefined,
    }));
  };

  const moveCity = (index: number, delta: number) => {
    const destination = index + delta;
    if (destination < 0 || destination >= values.cityStays.length) return;
    setValues((current) => {
      const cityStays = [...current.cityStays];
      [cityStays[index], cityStays[destination]] = [
        cityStays[destination],
        cityStays[index],
      ];
      return {
        ...current,
        cityStays,
        intercitySegments: cityStays.slice(1).map(emptyIntercitySegment),
      };
    });
    setErrors({});
    setMulticityNotice(
      "城市顺序已更新；为防止站点和时间绑定错误，全部城际段已清空。",
    );
    window.setTimeout(
      () =>
        document
          .querySelector<HTMLElement>(`[data-city-heading="${destination}"]`)
          ?.focus(),
      0,
    );
  };

  const addCity = () => {
    if (values.cityStays.length >= 3) return;
    setValues((current) => ({
      ...current,
      cityStays: [...current.cityStays, emptyCityStay()],
      intercitySegments: [
        ...current.intercitySegments,
        emptyIntercitySegment(),
      ],
    }));
    setMulticityNotice("已添加第 3 城；请调整结束日期和住宿夜数。");
    window.setTimeout(
      () =>
        document
          .querySelector<HTMLElement>('[data-field="cityStays.2.city"]')
          ?.focus(),
      0,
    );
  };

  const removeThirdCity = () => {
    if (values.cityStays.length !== 3) return;
    setValues((current) => ({
      ...current,
      cityStays: current.cityStays.slice(0, 2),
      intercitySegments: current.intercitySegments.slice(0, 1),
    }));
    setErrors({});
    setMulticityNotice("已删除第 3 城及其相邻城际段。");
    window.setTimeout(
      () =>
        document.querySelector<HTMLElement>('[data-city-heading="1"]')?.focus(),
      0,
    );
  };

  const fieldOrder: TripRequestField[] = [
    ...(values.scope === "single_city" ? (["city"] as TripRequestField[]) : []),
    "startDate",
    "endDate",
    "travelers",
    ...values.dayWindows.flatMap((_, index) => [
      `dayWindows.${index}.startTime` as TripRequestField,
      `dayWindows.${index}.endTime` as TripRequestField,
    ]),
    ...(values.scope === "multi_city"
      ? values.cityStays.flatMap((_, index) => [
          `cityStays.${index}.city` as TripRequestField,
          `cityStays.${index}.nights` as TripRequestField,
          `cityStays.${index}.accommodation` as TripRequestField,
          `cityStays.${index}.oneNightCost` as TripRequestField,
        ])
      : []),
    ...(values.scope === "multi_city"
      ? values.intercitySegments.flatMap((_, index) => [
          `intercitySegments.${index}.mode` as TripRequestField,
          `intercitySegments.${index}.departureStation` as TripRequestField,
          `intercitySegments.${index}.arrivalStation` as TripRequestField,
          `intercitySegments.${index}.departureTime` as TripRequestField,
          `intercitySegments.${index}.arrivalTime` as TripRequestField,
          `intercitySegments.${index}.fare` as TripRequestField,
        ])
      : []),
    "totalBudget",
    "transportModes",
    ...(values.scope === "single_city"
      ? (["accommodation", "oneNightCost"] as TripRequestField[])
      : []),
    "mealBudgetPerPersonPerDay",
    "freeText",
  ];

  const focusFirstError = (
    form: HTMLFormElement,
    nextErrors: TripRequestErrors,
  ) => {
    const first = fieldOrder.find((field) => nextErrors[field]);
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
  const expectedNights = dayCount === null ? null : dayCount - 1;
  const actualNights = values.cityStays.reduce(
    (total, stay) => total + Number(stay.nights || 0),
    0,
  );
  const orderedErrors = fieldOrder.flatMap((field) =>
    errors[field] ? [{ field, message: errors[field] }] : [],
  );

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
        <span>
          {values.scope === "multi_city"
            ? "3—7 日 · 2—3 城"
            : "2—7 日 · 单城市"}
        </span>
      </div>

      <fieldset
        className="scope-selector"
        aria-describedby={`${formId}-scope-hint`}
      >
        <legend>行程范围</legend>
        <label>
          <input
            type="radio"
            name={`${formId}-scope`}
            checked={values.scope === "single_city"}
            onChange={() => changeScope("single_city")}
          />
          <span>单城市</span>
        </label>
        <label>
          <input
            type="radio"
            name={`${formId}-scope`}
            checked={values.scope === "multi_city"}
            onChange={() => changeScope("multi_city")}
          />
          <span>多城市</span>
        </label>
      </fieldset>
      <p className="field-hint scope-hint" id={`${formId}-scope-hint`}>
        只有明确选择“多城市”才会提交 V3；不会按输入内容猜测版本。
      </p>
      <p className="sr-only" aria-live="polite">
        {multicityNotice}
      </p>
      {orderedErrors.length > 0 && (
        <section className="form-error-summary" role="alert">
          <h3>请检查 {orderedErrors.length} 个字段</h3>
          <ul>
            {orderedErrors.map(({ field }, index) => (
              <li key={field}>
                <a
                  href={`#${errorId(field)}`}
                  onClick={(event) => {
                    event.preventDefault();
                    event.currentTarget
                      .closest("form")
                      ?.querySelector<HTMLElement>(`[data-field="${field}"]`)
                      ?.focus();
                  }}
                >
                  错误 {index + 1} · {field}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="field-grid">
        {values.scope === "single_city" && (
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
        )}

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

        {values.scope === "multi_city" && (
          <section
            className="multicity-editor field--wide"
            aria-labelledby={`${formId}-cities-title`}
          >
            <div className="multicity-editor__heading">
              <div>
                <p className="section-kicker">ORDERED STAYS / 路线顺序</p>
                <h3 id={`${formId}-cities-title`}>城市停留</h3>
              </div>
              <button
                type="button"
                onClick={addCity}
                disabled={values.cityStays.length >= 3}
                aria-label="添加第 3 城"
                title={
                  values.cityStays.length >= 3 ? "最多支持 3 城" : undefined
                }
              >
                + 添加城市
              </button>
            </div>
            <p className="night-balance" role="status">
              行程需住宿 {expectedNights ?? "?"} 晚 · 当前分配 {actualNights} 晚
              {expectedNights === actualNights ? " · 已平衡" : " · 请调整夜数"}
            </p>

            <div className="city-stay-list">
              {values.cityStays.map((stay, index) => {
                const cityField = `cityStays.${index}.city` as TripRequestField;
                const accommodationField =
                  `cityStays.${index}.accommodation` as TripRequestField;
                const costField =
                  `cityStays.${index}.oneNightCost` as TripRequestField;
                const nightsField =
                  `cityStays.${index}.nights` as TripRequestField;
                return (
                  <fieldset className="city-stay-card" key={index}>
                    <legend>
                      <span data-city-heading={index} tabIndex={-1}>
                        第 {index + 1} 城
                        {stay.city.trim() ? ` · ${stay.city.trim()}` : ""}
                      </span>
                    </legend>
                    <div
                      className="card-order-actions"
                      aria-label={`城市顺序操作 ${index + 1}`}
                    >
                      <button
                        type="button"
                        disabled={index === 0}
                        onClick={() => moveCity(index, -1)}
                        aria-label={`第 ${index + 1} 城上移`}
                      >
                        ↑ 上移
                      </button>
                      <button
                        type="button"
                        disabled={index === values.cityStays.length - 1}
                        onClick={() => moveCity(index, 1)}
                        aria-label={`第 ${index + 1} 城下移`}
                      >
                        ↓ 下移
                      </button>
                      {index === 2 && (
                        <button type="button" onClick={removeThirdCity}>
                          删除第 3 城
                        </button>
                      )}
                    </div>
                    <div className="city-stay-card__fields">
                      <div className="field">
                        <label htmlFor={`${formId}-city-stay-${index}`}>
                          城市 *
                        </label>
                        <input
                          id={`${formId}-city-stay-${index}`}
                          data-field={cityField}
                          value={stay.city}
                          maxLength={30}
                          aria-invalid={Boolean(errors[cityField])}
                          aria-describedby={
                            errors[cityField] ? errorId(cityField) : undefined
                          }
                          onChange={(event) =>
                            updateCityStay(index, "city", event.target.value)
                          }
                        />
                        <FieldError
                          id={errorId(cityField)}
                          message={errors[cityField]}
                        />
                      </div>
                      <div className="field">
                        <label htmlFor={`${formId}-city-nights-${index}`}>
                          住宿夜数 *
                        </label>
                        <input
                          id={`${formId}-city-nights-${index}`}
                          data-field={nightsField}
                          type="number"
                          min="1"
                          max="6"
                          step="1"
                          value={stay.nights}
                          aria-invalid={Boolean(errors[nightsField])}
                          aria-describedby={
                            errors[nightsField]
                              ? errorId(nightsField)
                              : undefined
                          }
                          onChange={(event) =>
                            updateCityStay(index, "nights", event.target.value)
                          }
                        />
                        <p className="field-hint">
                          全程当前 {actualNights} / {expectedNights ?? "?"}{" "}
                          晚；不会自动改写。
                        </p>
                        <FieldError
                          id={errorId(nightsField)}
                          message={errors[nightsField]}
                        />
                      </div>
                      <div className="field field--wide">
                        <label
                          htmlFor={`${formId}-city-accommodation-${index}`}
                        >
                          住宿区域或 POI *
                        </label>
                        <input
                          id={`${formId}-city-accommodation-${index}`}
                          data-field={accommodationField}
                          value={stay.accommodation}
                          maxLength={120}
                          aria-invalid={Boolean(errors[accommodationField])}
                          aria-describedby={
                            errors[accommodationField]
                              ? errorId(accommodationField)
                              : undefined
                          }
                          onChange={(event) =>
                            updateCityStay(
                              index,
                              "accommodation",
                              event.target.value,
                            )
                          }
                        />
                        <FieldError
                          id={errorId(accommodationField)}
                          message={errors[accommodationField]}
                        />
                      </div>
                      <div className="field field--wide">
                        <label htmlFor={`${formId}-city-cost-${index}`}>
                          一晚住宿费用
                        </label>
                        <input
                          id={`${formId}-city-cost-${index}`}
                          data-field={costField}
                          inputMode="decimal"
                          value={stay.oneNightCost}
                          placeholder="未知可留空"
                          aria-invalid={Boolean(errors[costField])}
                          aria-describedby={
                            errors[costField] ? errorId(costField) : undefined
                          }
                          onChange={(event) =>
                            updateCityStay(
                              index,
                              "oneNightCost",
                              event.target.value,
                            )
                          }
                        />
                        <FieldError
                          id={errorId(costField)}
                          message={errors[costField]}
                        />
                      </div>
                    </div>
                  </fieldset>
                );
              })}
            </div>

            <div className="intercity-card-list">
              {values.intercitySegments.map((segment, index) => {
                const fields = {
                  mode: `intercitySegments.${index}.mode` as TripRequestField,
                  departureStation:
                    `intercitySegments.${index}.departureStation` as TripRequestField,
                  arrivalStation:
                    `intercitySegments.${index}.arrivalStation` as TripRequestField,
                  departureTime:
                    `intercitySegments.${index}.departureTime` as TripRequestField,
                  arrivalTime:
                    `intercitySegments.${index}.arrivalTime` as TripRequestField,
                  fare: `intercitySegments.${index}.fare` as TripRequestField,
                };
                const transferOffset = values.cityStays
                  .slice(0, index + 1)
                  .reduce((total, item) => total + Number(item.nights || 0), 0);
                const transferDate = addCalendarDays(
                  values.startDate,
                  transferOffset,
                );
                return (
                  <fieldset className="intercity-card" key={index}>
                    <legend>
                      城际段 {index + 1} · 第 {index + 1} 城 → 第 {index + 2} 城
                    </legend>
                    <p className="transfer-date">
                      转移日 {transferDate || "待日期/夜数有效后派生"} ·
                      上海时区 UTC+08:00
                    </p>
                    <div className="intercity-card__fields">
                      <div className="field field--wide">
                        <label htmlFor={`${formId}-segment-mode-${index}`}>
                          方式 *
                        </label>
                        <select
                          id={`${formId}-segment-mode-${index}`}
                          data-field={fields.mode}
                          value={segment.mode}
                          onChange={(event) =>
                            updateIntercitySegment(
                              index,
                              "mode",
                              event.target.value,
                            )
                          }
                        >
                          {INTERCITY_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                        <p className="buffer-badge">
                          缓冲 · {INTERCITY_BUFFERS[segment.mode].label}
                        </p>
                      </div>
                      {(["departureStation", "arrivalStation"] as const).map(
                        (key) => (
                          <div className="field" key={key}>
                            <label htmlFor={`${formId}-${key}-${index}`}>
                              {key === "departureStation" ? "出发站" : "到达站"}{" "}
                              *
                            </label>
                            <input
                              id={`${formId}-${key}-${index}`}
                              data-field={fields[key]}
                              value={segment[key]}
                              maxLength={120}
                              aria-invalid={Boolean(errors[fields[key]])}
                              aria-describedby={
                                errors[fields[key]]
                                  ? errorId(fields[key])
                                  : undefined
                              }
                              onChange={(event) =>
                                updateIntercitySegment(
                                  index,
                                  key,
                                  event.target.value,
                                )
                              }
                            />
                            <FieldError
                              id={errorId(fields[key])}
                              message={errors[fields[key]]}
                            />
                          </div>
                        ),
                      )}
                      {(["departureTime", "arrivalTime"] as const).map(
                        (key) => (
                          <div className="field" key={key}>
                            <label htmlFor={`${formId}-${key}-${index}`}>
                              {key === "departureTime"
                                ? "出发时间"
                                : "到达时间"}{" "}
                              *
                            </label>
                            <input
                              id={`${formId}-${key}-${index}`}
                              data-field={fields[key]}
                              type="time"
                              value={segment[key]}
                              aria-invalid={Boolean(errors[fields[key]])}
                              aria-describedby={
                                errors[fields[key]]
                                  ? errorId(fields[key])
                                  : undefined
                              }
                              onChange={(event) =>
                                updateIntercitySegment(
                                  index,
                                  key,
                                  event.target.value,
                                )
                              }
                            />
                            <FieldError
                              id={errorId(fields[key])}
                              message={errors[fields[key]]}
                            />
                          </div>
                        ),
                      )}
                      <div className="field field--wide">
                        <label htmlFor={`${formId}-segment-fare-${index}`}>
                          票价
                        </label>
                        <input
                          id={`${formId}-segment-fare-${index}`}
                          data-field={fields.fare}
                          inputMode="decimal"
                          value={segment.fare}
                          placeholder="未知，将影响预算完整性"
                          aria-invalid={Boolean(errors[fields.fare])}
                          aria-describedby={
                            errors[fields.fare]
                              ? errorId(fields.fare)
                              : undefined
                          }
                          onChange={(event) =>
                            updateIntercitySegment(
                              index,
                              "fare",
                              event.target.value,
                            )
                          }
                        />
                        <p className="field-hint">
                          {segment.fare
                            ? "用户提供，未核验"
                            : "未知，将影响预算完整性"}
                        </p>
                        <FieldError
                          id={errorId(fields.fare)}
                          message={errors[fields.fare]}
                        />
                      </div>
                    </div>
                  </fieldset>
                );
              })}
            </div>
            <p className="intercity-disclosure" role="note">
              系统不会查询或确认班次、票价、余票、库存或可预订性，请核对用户提供的信息。
            </p>
          </section>
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

        {values.scope === "single_city" && (
          <>
            <div className="field field--wide">
              <label htmlFor={`${formId}-accommodation`}>
                住宿区域或 POI *
              </label>
              <input
                id={`${formId}-accommodation`}
                name="accommodation"
                data-field="accommodation"
                value={values.accommodation}
                aria-invalid={Boolean(errors.accommodation)}
                aria-describedby={`${formId}-accommodation-hint${errors.accommodation ? ` ${errorId("accommodation")}` : ""}`}
                maxLength={120}
                placeholder="例如：湖滨银泰附近"
                onChange={(event) =>
                  update("accommodation", event.target.value)
                }
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
                  onChange={(event) =>
                    update("oneNightCost", event.target.value)
                  }
                />
              </div>
              <FieldError
                id={errorId("oneNightCost")}
                message={errors.oneNightCost}
              />
            </div>
          </>
        )}

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
              : values.scope === "multi_city"
                ? `生成${dayCount && dayCount >= 3 && dayCount <= 7 ? dayCount : "多城市"}日计划`
                : `生成${dayCount && dayCount >= 2 && dayCount <= 7 ? dayCount : 2}日计划`}
          </span>
          <span aria-hidden="true">→</span>
        </button>
        <p>请求仅发送至本机后端；自动刷新有次数上限，可随时手动继续。</p>
      </div>
    </form>
  );
}
