import { useEffect, useRef, useState } from "react";

import { ReplanPanel } from "./ReplanPanel";
import { MulticityTripPlanResult } from "./MulticityTripPlanResult";
import { TripDayNavigation } from "./TripDayNavigation";
import type {
  LegacyTripPlanResponseDto,
  TripPlanResponseDto,
  TripPlanResponseV2Dto,
  TripPlanResponseV4Dto,
} from "./tripPlanningApi";
import type { ReplanCommand, ReplanningApi } from "./replanningApi";
import type { MoneyDto } from "./tripRequest";
import { ResultDiagnostics, SourceEvidence } from "./ResultEvidence";
import type {
  BudgetAssessment,
  CostCategory,
  CostConfidence,
  LocationRefDto,
  LegacyTripPlanDto,
  PlanDayDto,
  TripPlanV2Dto,
  TripPlanV3Dto,
  TripPlanV4Dto,
  ResolvedDestinationDto,
} from "./tripPlanModels";
import type { TripPlanResponseV3Dto } from "./tripPlanningApi";

type TripPlanResponseViewDto = Pick<
  TripPlanResponseDto,
  | "job_id"
  | "trace_id"
  | "client_request_id"
  | "status"
  | "attempt"
  | "request_summary"
  | "plan"
  | "violations"
  | "warnings"
  | "uncertainties"
  | "sources"
  | "errors"
  | "retryable"
  | "created_at"
  | "updated_at"
> & {
  response_version?: "2" | "3" | "4";
  resolved_destination?: ResolvedDestinationDto | null;
  resolved_destinations?: ResolvedDestinationDto[];
};

interface TripPlanResultProps {
  response: TripPlanResponseViewDto;
  onRetry?: () => void;
  onReset?: (field?: string | null) => void;
  replanApi?: ReplanningApi;
}

type SingleCityTripPlanResultProps = Omit<TripPlanResultProps, "response"> & {
  response: (LegacyTripPlanResponseDto | TripPlanResponseV2Dto) & {
    plan: LegacyTripPlanDto | TripPlanV2Dto;
  };
};

type EditTarget =
  | {
      operation:
        "replace_activity" | "delete_activity" | "adjust_activity_time";
      activity: PlanDayDto["activities"][number];
    }
  | { operation: "reorder_activities"; day: PlanDayDto };

const CATEGORY_LABELS: Record<CostCategory, string> = {
  accommodation: "住宿",
  intercity_transport: "城际交通",
  local_transport: "市内交通",
  ticket: "门票",
  meal: "餐饮",
  other: "其他",
};

const CONFIDENCE_LABELS: Record<CostConfidence, string> = {
  verified: "已核实",
  estimated: "规则估算",
  user_provided: "用户提供",
  unknown: "金额未知",
};

const ASSESSMENT_LABELS: Record<BudgetAssessment, string> = {
  within_budget: "预算可完整判定",
  over_budget: "已知费用超过预算",
  budget_indeterminate: "完整预算不可判定",
};

const ROUTE_MODE_LABELS = {
  walking: "步行",
  public_transit: "公共交通",
} as const;

function formatMoney(money: MoneyDto): string {
  const [whole, decimal = ""] = money.amount.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `¥${decimal.length > 0 ? `${grouped}.${decimal}` : grouped}`;
}

function formatTime(value: string): string {
  return value.slice(0, 5);
}

function dateParts(value: string): { day: string; weekday: string } {
  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return {
    day: String(day).padStart(2, "0"),
    weekday: new Intl.DateTimeFormat("zh-CN", {
      weekday: "short",
      timeZone: "UTC",
    }).format(parsed),
  };
}

function locationName(
  locations: ReadonlyMap<string, LocationRefDto>,
  locationId: string,
): string {
  return locations.get(locationId)?.name ?? "未识别地点";
}

function DayCard({
  day,
  dayIndex,
  locations,
  onEdit,
  replanEnabled,
  current,
}: {
  day: PlanDayDto;
  dayIndex: number;
  locations: ReadonlyMap<string, LocationRefDto>;
  onEdit: (target: EditTarget, trigger: HTMLButtonElement) => void;
  replanEnabled: boolean;
  current: boolean;
}) {
  const date = dateParts(day.local_date);
  return (
    <article
      className={`itinerary-day${current ? " itinerary-day--current" : ""}`}
      data-current={current}
      id={`trip-day-${dayIndex + 1}`}
      tabIndex={-1}
      aria-label={`第 ${dayIndex + 1} 天，${day.local_date} 行程`}
    >
      <header className="day-heading">
        <div className="day-date" aria-label={day.local_date}>
          <strong>{date.day}</strong>
          <span>
            {date.weekday} · 第 {dayIndex + 1} 天
          </span>
        </div>
        <p>
          住宿锚点 · {locationName(locations, day.accommodation_location_id)}
        </p>
        {replanEnabled && (
          <button
            className="day-replan-trigger"
            type="button"
            onClick={(event) =>
              onEdit(
                { operation: "reorder_activities", day },
                event.currentTarget,
              )
            }
          >
            调整当天顺序
          </button>
        )}
      </header>

      <div
        className={`weather-card${day.weather ? "" : " weather-card--missing"}`}
      >
        <span className="weather-mark" aria-hidden="true">
          {day.weather ? "气" : "?"}
        </span>
        {day.weather ? (
          <div>
            <strong>
              {day.weather.condition_day} ·{" "}
              {day.weather.temperature_min_celsius}—
              {day.weather.temperature_max_celsius}℃
            </strong>
            <small>夜间 {day.weather.condition_night} · 逐日预报已获取</small>
            {day.weather.alerts.map((alert) => (
              <p className="weather-alert" key={alert.alert_id}>
                当前预警：{alert.title}
              </p>
            ))}
          </div>
        ) : (
          <div>
            <strong>天气数据缺失</strong>
            <small>不推测当天温度或天气情况</small>
          </div>
        )}
      </div>

      <ol className="activity-list" aria-label={`${day.local_date}活动`}>
        {day.activities.map((activity) => (
          <li key={activity.item_id}>
            <time>{formatTime(activity.start_time)}</time>
            <span className="activity-pin" aria-hidden="true" />
            <div className="activity-copy">
              <strong>{activity.title}</strong>
              <small>
                {locationName(locations, activity.location_id)} · 至{" "}
                {formatTime(activity.end_time)}
              </small>
              {replanEnabled && (
                <div className="activity-replan-actions">
                  <button
                    type="button"
                    onClick={(event) =>
                      onEdit(
                        { operation: "replace_activity", activity },
                        event.currentTarget,
                      )
                    }
                  >
                    替换活动
                  </button>
                  <button
                    type="button"
                    onClick={(event) =>
                      onEdit(
                        { operation: "delete_activity", activity },
                        event.currentTarget,
                      )
                    }
                  >
                    删除活动
                  </button>
                  <button
                    type="button"
                    onClick={(event) =>
                      onEdit(
                        { operation: "adjust_activity_time", activity },
                        event.currentTarget,
                      )
                    }
                  >
                    调整时间
                  </button>
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>

      <div className="route-list" aria-label={`${day.local_date}路线摘要`}>
        <div className="subsection-heading">
          <strong>路线摘要</strong>
          <span>
            {day.routes.length > 0 ? `${day.routes.length} 段` : "未验证"}
          </span>
        </div>
        {day.routes.length > 0 ? (
          day.routes.map((route) => (
            <div className="route-row" key={route.route_id}>
              <span className="route-mode">
                {ROUTE_MODE_LABELS[route.mode]}
              </span>
              <p>
                {locationName(locations, route.origin_location_id)}
                <span aria-hidden="true"> → </span>
                <span className="sr-only">到</span>
                {locationName(locations, route.destination_location_id)}
              </p>
              <strong>{route.duration_minutes} 分钟</strong>
              <small>{route.distance_meters} 米 · 服务端已校验</small>
            </div>
          ))
        ) : (
          <p className="missing-fact">路线数据缺失，交通时间尚未验证。</p>
        )}
      </div>
    </article>
  );
}

function ReplanComposer({
  target,
  onCancel,
  onReady,
}: {
  target: EditTarget;
  onCancel: () => void;
  onReady: (command: ReplanCommand, label: string) => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const activity = "activity" in target ? target.activity : null;
  const [startTime, setStartTime] = useState(
    activity?.start_time.slice(0, 5) ?? "09:00",
  );
  const [endTime, setEndTime] = useState(
    activity?.end_time.slice(0, 5) ?? "10:00",
  );
  const [categories, setCategories] = useState<string[]>(["culture"]);
  const [order, setOrder] = useState(
    target.operation === "reorder_activities"
      ? target.day.activities.map((item) => item.item_id)
      : [],
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    heading.current?.focus();
  }, []);

  const label =
    target.operation === "reorder_activities"
      ? `调整 ${target.day.local_date} 活动顺序`
      : `${
          target.operation === "replace_activity"
            ? "替换"
            : target.operation === "delete_activity"
              ? "删除"
              : "调整时间"
        } · ${activity?.title}`;

  const submit = () => {
    if (target.operation === "replace_activity") {
      if (categories.length < 1 || categories.length > 3) {
        setError("请选择 1–3 个替换类别。");
        return;
      }
      onReady(
        {
          operation: target.operation,
          target_activity_id: target.activity.item_id,
          replacement_categories: categories,
        },
        label,
      );
    } else if (target.operation === "delete_activity") {
      onReady(
        {
          operation: target.operation,
          target_activity_id: target.activity.item_id,
        },
        label,
      );
    } else if (target.operation === "adjust_activity_time") {
      if (!startTime || !endTime || endTime <= startTime) {
        setError("结束时间必须晚于开始时间，且不能改变活动日期。");
        return;
      }
      onReady(
        {
          operation: target.operation,
          target_activity_id: target.activity.item_id,
          start_time: `${startTime}:00`,
          end_time: `${endTime}:00`,
        },
        label,
      );
    } else if (target.operation === "reorder_activities") {
      onReady(
        {
          operation: target.operation,
          local_date: target.day.local_date,
          ordered_activity_ids: order,
        },
        label,
      );
    }
  };

  const move = (index: number, delta: number) =>
    setOrder((current) => {
      const next = [...current];
      const destination = index + delta;
      if (destination < 0 || destination >= next.length) return current;
      [next[index], next[destination]] = [next[destination], next[index]];
      return next;
    });

  return (
    <section
      className="replan-composer"
      aria-labelledby="replan-composer-title"
    >
      <p>STRUCTURED CHANGE / 不发送完整 Prompt</p>
      <h3 id="replan-composer-title" ref={heading} tabIndex={-1}>
        {label}
      </h3>
      {target.operation === "replace_activity" && (
        <fieldset>
          <legend>替换类别（1–3 项）</legend>
          {[
            ["culture", "文化"],
            ["nature", "自然"],
            ["food", "餐饮"],
          ].map(([value, text]) => (
            <label key={value}>
              <input
                type="checkbox"
                checked={categories.includes(value)}
                onChange={(event) =>
                  setCategories((current) =>
                    event.target.checked
                      ? [...current, value]
                      : current.filter((item) => item !== value),
                  )
                }
              />
              {text}
            </label>
          ))}
        </fieldset>
      )}
      {target.operation === "delete_activity" && (
        <p>
          将分析删除“{target.activity.title}
          ”对路线、时间、预算和来源的影响；此时不会改变原计划。
        </p>
      )}
      {target.operation === "adjust_activity_time" && (
        <div className="replan-time-fields">
          <label>
            开始时间
            <input
              aria-label="新的开始时间"
              type="time"
              value={startTime}
              onChange={(event) => setStartTime(event.target.value)}
            />
          </label>
          <label>
            结束时间
            <input
              aria-label="新的结束时间"
              type="time"
              value={endTime}
              onChange={(event) => setEndTime(event.target.value)}
            />
          </label>
        </div>
      )}
      {target.operation === "reorder_activities" && (
        <ol className="reorder-list">
          {order.map((id, index) => {
            const item = target.day.activities.find(
              (activityItem) => activityItem.item_id === id,
            );
            return (
              <li key={id}>
                <span>{item?.title}</span>
                <button
                  type="button"
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                >
                  上移
                </button>
                <button
                  type="button"
                  disabled={index === order.length - 1}
                  onClick={() => move(index, 1)}
                >
                  下移
                </button>
              </li>
            );
          })}
        </ol>
      )}
      {error && (
        <p className="replan-form-error" role="alert">
          {error}
        </p>
      )}
      <div className="replan-composer__actions">
        <button type="button" onClick={onCancel}>
          取消
        </button>
        <button type="button" onClick={submit}>
          准备影响分析
        </button>
      </div>
    </section>
  );
}

function SingleCityTripPlanResult({
  response,
  onRetry,
  onReset,
  replanApi,
}: SingleCityTripPlanResultProps) {
  const [completedOverride, setCompletedOverride] = useState<{
    baselinePlanId: string;
    response: typeof response;
  } | null>(null);
  const [editTarget, setEditTarget] = useState<EditTarget | null>(null);
  const [prepared, setPrepared] = useState<{
    command: ReplanCommand;
    label: string;
  } | null>(null);
  const [baseline, setBaseline] = useState(response);
  const [activeDate, setActiveDate] = useState(response.plan.start_date);
  const trigger = useRef<HTMLButtonElement | null>(null);

  const closeReplan = () => {
    setEditTarget(null);
    setPrepared(null);
    window.setTimeout(() => trigger.current?.focus(), 0);
  };
  const active =
    completedOverride?.baselinePlanId === response.plan.plan_id
      ? completedOverride.response
      : response;
  const { plan } = active;
  const currentDate = plan.days.some((day) => day.local_date === activeDate)
    ? activeDate
    : plan.start_date;
  const locations = new Map(
    plan.locations.map((location) => [location.location_id, location]),
  );
  const isPartial = active.status === "partial";
  const isConflict = active.status === "conflict";
  const canRetry =
    isPartial && active.retryable && active.attempt < 3 && Boolean(onRetry);
  const hasItineraryContent = plan.days.some(
    (day) =>
      day.activities.length > 0 ||
      day.routes.length > 0 ||
      day.weather !== null,
  );
  const verdict = isConflict
    ? (active.violations[0]?.message ??
      active.errors[0]?.message ??
      "计划没有通过确定性约束校验。")
    : isPartial
      ? `${active.uncertainties.length} 项数据尚未完成，以下计划不是完整验证结果。`
      : "日期、路线、时间和预算均已通过服务端确定性校验。";

  return (
    <div className="plan-result">
      <header className="result-heading">
        <div>
          <p className="tracking-kicker">
            {isConflict
              ? "存在硬冲突 · 需要调整约束"
              : isPartial
                ? "部分数据缺失 · 可查看已有计划"
                : "代码校验通过 · 可用于决策"}
          </p>
          <h2 id="plan-stage-title">
            {active.resolved_destination?.city_name ??
              active.request_summary.city}
            <span>{plan.days.length}日旅笺</span>
          </h2>
          <p className="tracking-summary">
            {plan.start_date}—{plan.end_date} ·{" "}
            {active.request_summary.travelers} 人 · 尝试 {active.attempt}/3
          </p>
        </div>
        <div className={`result-stamp result-stamp--${active.status}`}>
          {isConflict ? "约束\n冲突" : isPartial ? "部分\n可用" : "完整\n可用"}
        </div>
      </header>

      <div
        className={`result-verdict result-verdict--${active.status}`}
        role="status"
      >
        <strong>{isConflict ? "×" : isPartial ? "!" : "✓"}</strong>
        <p>{verdict}</p>
      </div>

      <section className="result-section" aria-labelledby="plan-summary-title">
        <h3 id="plan-summary-title">计划摘要</h3>
        <div className="summary-grid">
          <div>
            <span>行程跨度</span>
            <strong>{plan.days.length} 天</strong>
            <small>
              {plan.start_date}—{plan.end_date}
            </small>
          </div>
          <div>
            <span>已知费用</span>
            <strong>{formatMoney(plan.budget_summary.known_total)}</strong>
            <small>服务端提供的已知合计</small>
          </div>
          <div>
            <span>未知费用</span>
            <strong>{plan.budget_summary.unknown_count} 项</strong>
            <small>缺失金额没有按 0 处理</small>
          </div>
          <div>
            <span>预算判断</span>
            <strong className="summary-assessment">
              {ASSESSMENT_LABELS[plan.budget_summary.assessment]}
            </strong>
            <small>总预算 {formatMoney(plan.budget_summary.budget)}</small>
          </div>
        </div>
      </section>

      <ResultDiagnostics response={active} />

      {hasItineraryContent ? (
        <section className="result-section" aria-labelledby="days-title">
          <h3 id="days-title">逐日安排</h3>
          <TripDayNavigation
            days={plan.days}
            activeDate={currentDate}
            onSelect={(localDate) => {
              setActiveDate(localDate);
              const index = plan.days.findIndex(
                (day) => day.local_date === localDate,
              );
              window.setTimeout(
                () => document.getElementById(`trip-day-${index + 1}`)?.focus(),
                0,
              );
            }}
          />
          {plan.days.length > 2 && (
            <p className="multiday-replan-boundary" role="note">
              当前仅支持双日计划局部调整；此计划仍可完整查看、重试或返回修改。
            </p>
          )}
          <div className="day-list">
            {plan.days.map((day, index) => (
              <DayCard
                day={day}
                dayIndex={index}
                locations={locations}
                key={day.local_date}
                onEdit={(target, button) => {
                  trigger.current = button;
                  setBaseline(active);
                  setPrepared(null);
                  setEditTarget(target);
                }}
                replanEnabled={
                  plan.days.length === 2 &&
                  (active.status === "ready" || active.status === "partial")
                }
                current={day.local_date === currentDate}
              />
            ))}
          </div>
        </section>
      ) : (
        <p className="conflict-candidate-note">
          候选安排没有通过确定性校验，因此不展示为可执行的逐日行程。
        </p>
      )}

      <section className="result-section" aria-labelledby="budget-title">
        <h3 id="budget-title">预算可信度</h3>
        <div className="budget-panel">
          <div className="budget-total">
            <span>已知合计 / 总预算</span>
            <strong>
              {formatMoney(plan.budget_summary.known_total)}
              <small> / {formatMoney(plan.budget_summary.budget)}</small>
            </strong>
            <p>
              {plan.budget_summary.assessment === "budget_indeterminate"
                ? "仍有未知费用，不能称为最终余额或预算充足。"
                : "该判断来自服务端预算规则，前端不重新计算。"}
            </p>
          </div>
          <ul className="cost-list" aria-label="费用明细">
            {plan.budget_summary.cost_items.map((item) => (
              <li key={item.cost_id}>
                <div>
                  <strong>{CATEGORY_LABELS[item.category]}</strong>
                  <small>{item.description}</small>
                </div>
                <span className={`confidence confidence--${item.confidence}`}>
                  {CONFIDENCE_LABELS[item.confidence]}
                </span>
                <strong className="cost-amount">
                  {item.amount === null ? "未知" : formatMoney(item.amount)}
                </strong>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <SourceEvidence sources={active.sources} />

      {editTarget && !prepared && (
        <ReplanComposer
          target={editTarget}
          onCancel={closeReplan}
          onReady={(command, label) => setPrepared({ command, label })}
        />
      )}
      {editTarget && prepared && (
        <ReplanPanel
          api={replanApi}
          baseline={baseline}
          command={prepared.command}
          commandLabel={prepared.label}
          onClose={closeReplan}
          onCompleted={(result) => {
            if (
              result.plan &&
              (!("plan_format_version" in result.plan) ||
                result.plan.plan_format_version === "2")
            ) {
              setCompletedOverride({
                baselinePlanId: baseline.plan.plan_id,
                response: {
                  ...(result as
                    LegacyTripPlanResponseDto | TripPlanResponseV2Dto),
                  plan: result.plan,
                } as SingleCityTripPlanResultProps["response"],
              });
            }
          }}
        />
      )}

      {(isPartial || isConflict) && (canRetry || onReset) && (
        <div className="outcome-actions result-actions">
          {canRetry && (
            <button type="button" onClick={() => onRetry?.()}>
              {active.errors.some((error) => error.code === "data_stale")
                ? "重新获取数据"
                : "重试缺失数据"}
            </button>
          )}
          {onReset && (
            <button type="button" onClick={() => onReset()}>
              返回修改需求
            </button>
          )}
        </div>
      )}
      {isPartial && active.retryable && active.attempt >= 3 && (
        <p className="outcome-action-note">
          本任务已达到 3 次尝试上限，请返回修改需求后创建新任务。
        </p>
      )}
    </div>
  );
}

export function TripPlanResult(props: TripPlanResultProps) {
  if (props.response.plan === null) return null;
  if (
    "response_version" in props.response &&
    (props.response.response_version === "3" ||
      props.response.response_version === "4") &&
    "plan_format_version" in props.response.plan &&
    (props.response.plan.plan_format_version === "3" ||
      props.response.plan.plan_format_version === "4")
  ) {
    if (props.response.response_version === "4") {
      return (
        <MulticityTripPlanResult
          response={
            props.response as TripPlanResponseV4Dto & { plan: TripPlanV4Dto }
          }
          onRetry={props.onRetry}
          onReset={props.onReset}
        />
      );
    }
    return (
      <MulticityTripPlanResult
        response={
          props.response as TripPlanResponseV3Dto & { plan: TripPlanV3Dto }
        }
        onRetry={props.onRetry}
        onReset={props.onReset}
      />
    );
  }
  return (
    <SingleCityTripPlanResult {...(props as SingleCityTripPlanResultProps)} />
  );
}
