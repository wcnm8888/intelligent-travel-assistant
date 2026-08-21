import { TripDayNavigation } from "./TripDayNavigation";
import { ResultDiagnostics, SourceEvidence } from "./ResultEvidence";
import type { TripPlanResponseV3Dto } from "./tripPlanningApi";
import type { MoneyDto } from "./tripRequest";
import type {
  CostCategory,
  CostConfidence,
  LocationRefDto,
  PlanDayV3Dto,
  TripPlanV3Dto,
} from "./tripPlanModels";
import { useState } from "react";
interface Props {
  response: TripPlanResponseV3Dto & { plan: TripPlanV3Dto };
  onRetry?: () => void;
  onReset?: (field?: string | null) => void;
}
const MODE_LABELS = { rail: "铁路", air: "航空", coach: "长途客运" } as const;
const BUFFERS = {
  rail: "出发前 60 分钟 / 到达后 30 分钟",
  air: "出发前 120 分钟 / 到达后 60 分钟",
  coach: "出发前 45 分钟 / 到达后 30 分钟",
} as const;
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
  user_provided: "用户提供，未核验",
  unknown: "金额未知",
};
function formatMoney(money: MoneyDto): string {
  const [whole, decimal = ""] = money.amount.split(".");
  return `¥${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${decimal ? `.${decimal}` : ""}`;
}
function locationName(
  locations: ReadonlyMap<string, LocationRefDto>,
  locationId: string,
): string {
  return locations.get(locationId)?.name ?? "未识别地点";
}
function cityName(response: Props["response"], index: number): string {
  return (
    response.resolved_destinations[index]?.city_name ??
    response.request_summary.city_stays[index]?.city ??
    `第 ${index + 1} 城`
  );
}
function MulticityDayCard({
  day,
  index,
  response,
  locations,
  current,
}: {
  day: PlanDayV3Dto;
  index: number;
  response: Props["response"];
  locations: ReadonlyMap<string, LocationRefDto>;
  current: boolean;
}) {
  const segment = day.intercity_segment_id
    ? response.plan.intercity_segments.find(
        (item) => item.segment_id === day.intercity_segment_id,
      )
    : undefined;
  return (
    <article
      className={`itinerary-day multicity-day${current ? " itinerary-day--current" : ""}`}
      id={`trip-day-${index + 1}`}
      tabIndex={-1}
      aria-label={`第 ${index + 1} 天，${day.local_date} 行程`}
    >
      <header className="day-heading">
        <div className="day-date">
          <strong>{day.local_date.slice(-2)}</strong>
          <span>第 {index + 1} 天</span>
        </div>
        <p>
          {day.departure_city_index === day.arrival_city_index
            ? `${cityName(response, day.overnight_city_index)} · 当晚住宿`
            : `${cityName(response, day.departure_city_index)} → ${cityName(response, day.arrival_city_index)} · 当晚 ${cityName(response, day.overnight_city_index)}`}
        </p>
      </header>
      {segment && (
        <section
          className="intercity-result-card"
          aria-label="用户提供的城际段"
        >
          <div className="subsection-heading">
            <strong>
              {MODE_LABELS[segment.mode]} · <span>用户提供，未核验</span>
            </strong>
            <span>
              {segment.departure_at.slice(11, 16)}—
              {segment.arrival_at.slice(11, 16)}
            </span>
          </div>
          <p>
            {locationName(locations, segment.departure_station_location_id)} →{" "}
            {locationName(locations, segment.arrival_station_location_id)}
          </p>
          <small>{BUFFERS[segment.mode]} · 上海时区 UTC+08:00</small>
          <strong className="intercity-fare">
            {segment.fare.amount === null
              ? "金额未知"
              : `${formatMoney(segment.fare.amount)} · 用户提供`}
          </strong>
        </section>
      )}
      <div
        className={`weather-card${day.weather ? "" : " weather-card--missing"}`}
      >
        <span className="weather-mark" aria-hidden="true">
          {day.weather ? "气" : "?"}
        </span>
        <div>
          <strong>
            {day.weather
              ? `${day.weather.condition_day} · ${day.weather.temperature_min_celsius}—${day.weather.temperature_max_celsius}℃`
              : "天气数据缺失"}
          </strong>
          <small>
            {day.weather
              ? `夜间 ${day.weather.condition_night}`
              : "不推测当天温度或天气情况"}
          </small>
        </div>
      </div>
      <ol className="activity-list" aria-label={`${day.local_date}活动`}>
        {day.activities.map((activity) => (
          <li key={activity.item_id}>
            <time>{activity.start_time.slice(0, 5)}</time>
            <span className="activity-pin" aria-hidden="true" />
            <div className="activity-copy">
              <strong>{activity.title}</strong>
              <small>
                {locationName(locations, activity.location_id)} · 至{" "}
                {activity.end_time.slice(0, 5)}
              </small>
            </div>
          </li>
        ))}
        {day.activities.length === 0 && (
          <li className="missing-fact">转移日未安排额外活动。</li>
        )}
      </ol>
      <div className="route-list" aria-label={`${day.local_date}市内路线摘要`}>
        <div className="subsection-heading">
          <strong>市内路线</strong>
          <span>
            {day.routes.length ? `${day.routes.length} 段` : "未验证"}
          </span>
        </div>
        {day.routes.length === 0 && (
          <p className="missing-fact">市内路线数据缺失，未与城际段混合展示。</p>
        )}
      </div>
    </article>
  );
}
export function MulticityTripPlanResult({ response, onRetry, onReset }: Props) {
  const { plan } = response;
  const [activeDate, setActiveDate] = useState(plan.start_date);
  const locations = new Map(
    plan.locations.map((item) => [item.location_id, item]),
  );
  const isPartial = response.status === "partial";
  const route = response.request_summary.city_stays
    .map((stay) => stay.city)
    .join(" → ");
  const explicitGapCount = Math.max(
    response.uncertainties.length + response.errors.length,
    plan.budget_summary.unknown_count,
  );
  const verdict = isPartial
    ? `${explicitGapCount} 项缺口仍需核对；此计划不是完整验证结果。`
    : "城市顺序、转移日和预算已通过服务端确定性校验。";
  return (
    <div className="plan-result multicity-result">
      <header className="result-heading">
        <div>
          <p className="tracking-kicker">
            {isPartial
              ? "部分数据缺失 · 多城市计划"
              : "代码校验通过 · 多城市计划"}
          </p>
          <h2 id="plan-stage-title">
            {route}
            <span>{plan.days.length}日旅笺</span>
          </h2>
          <p className="tracking-summary">
            {plan.start_date}—{plan.end_date} ·{" "}
            {response.request_summary.travelers} 人 · {plan.days.length - 1} 晚
          </p>
        </div>
        <div className={`result-stamp result-stamp--${response.status}`}>
          {isPartial ? "部分\n可用" : "完整\n可用"}
        </div>
      </header>
      <div
        className={`result-verdict result-verdict--${response.status}`}
        role="status"
      >
        <strong>{isPartial ? "!" : "✓"}</strong>
        <p>{verdict}</p>
      </div>
      <section
        className="result-section"
        aria-labelledby="multicity-summary-title"
      >
        <h3 id="multicity-summary-title">路线与停留</h3>
        <p className="intercity-disclosure">
          城际段由用户提供、未核验；系统没有查询班次、票价、余票或库存。
        </p>
        <ol className="stay-summary-list">
          {response.request_summary.city_stays.map((stay, index) => {
            const accommodation = plan.locations.find(
              (item) =>
                item.city_adcode === plan.city_adcodes[index] &&
                item.category === "accommodation_anchor",
            );
            return (
              <li key={`${stay.city}-${index}`}>
                <span>0{index + 1}</span>
                <div>
                  <strong>{stay.city}</strong>
                  <small>
                    {accommodation?.name ?? "住宿锚点缺失"} · {stay.nights} 晚
                  </small>
                </div>
              </li>
            );
          })}
        </ol>
      </section>
      <ResultDiagnostics response={response} />
      <section className="result-section" aria-labelledby="days-title">
        <h3 id="days-title">逐日安排</h3>
        <TripDayNavigation
          days={plan.days}
          activeDate={activeDate}
          onSelect={(date) => {
            setActiveDate(date);
            const index = plan.days.findIndex((day) => day.local_date === date);
            window.setTimeout(
              () => document.getElementById(`trip-day-${index + 1}`)?.focus(),
              0,
            );
          }}
        />
        <p className="multiday-replan-boundary" role="note">
          当前多城市计划不支持局部调整；修改需返回表单创建新任务。
        </p>
        <div className="day-list">
          {plan.days.map((day, index) => (
            <MulticityDayCard
              key={day.local_date}
              day={day}
              index={index}
              response={response}
              locations={locations}
              current={day.local_date === activeDate}
            />
          ))}
        </div>
      </section>
      <section className="result-section" aria-labelledby="budget-title">
        <h3 id="budget-title">预算可信度</h3>
        <div className="budget-panel">
          <div className="budget-total">
            <span>已知合计 / 总预算</span>
            <strong>
              {formatMoney(plan.budget_summary.known_total)}
              <small> / {formatMoney(plan.budget_summary.budget)}</small>
            </strong>
            <p>{plan.budget_summary.unknown_count} 项未知费用没有按 0 处理。</p>
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
      <SourceEvidence sources={response.sources} />
      {(onReset ||
        (isPartial &&
          response.retryable &&
          response.attempt < 3 &&
          onRetry)) && (
        <div className="outcome-actions result-actions">
          {isPartial &&
            response.retryable &&
            response.attempt < 3 &&
            onRetry && (
              <button type="button" onClick={onRetry}>
                {response.errors.some((error) => error.code === "data_stale")
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
    </div>
  );
}
