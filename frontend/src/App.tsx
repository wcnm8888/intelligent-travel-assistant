import { useRef, useState } from "react";

import { PlanningStage } from "./PlanningStage";
import { TripRequestForm } from "./TripRequestForm";
import type { TripPlanningApi } from "./tripPlanningApi";
import type { ReplanningApi } from "./replanningApi";
import {
  DEFAULT_POLLING_POLICY,
  useTripPlanningJob,
  type PollingPolicy,
} from "./useTripPlanningJob";
import "./styles.css";

interface AppProps {
  createClientRequestId?: () => string;
  tripPlanApi?: TripPlanningApi;
  pollingPolicy?: PollingPolicy;
  replanApi?: ReplanningApi;
}

export function App({
  createClientRequestId,
  tripPlanApi,
  pollingPolicy = DEFAULT_POLLING_POLICY,
  replanApi,
}: AppProps) {
  const { state, start, resume, retry, reset } = useTripPlanningJob(
    tripPlanApi,
    pollingPolicy,
  );
  const [requestExpanded, setRequestExpanded] = useState(false);
  const requestPanel = useRef<HTMLElement>(null);
  const busy =
    state.phase === "submitting" ||
    state.phase === "retrying" ||
    state.phase === "tracking";
  const resultFirst = state.phase !== "idle";
  const requestCollapsed = resultFirst && !requestExpanded;

  const returnToRequest = (field: string | null = null) => {
    reset();
    setRequestExpanded(true);
    const target = (() => {
      if (field === "accommodation.area_or_poi") return "accommodation";
      if (field === "start_date") return "startDate";
      if (field === "end_date" || field === "day_windows") return "endDate";
      const windowField = /^day_windows\.(\d+)\.(start_time|end_time)$/.exec(
        field ?? "",
      );
      if (windowField) {
        const [, index, timeField] = windowField;
        return `dayWindows.${index}.${timeField === "start_time" ? "startTime" : "endTime"}`;
      }
      const cityStayField =
        /^city_stays\.(\d+)\.(city|nights|accommodation\.area_or_poi|accommodation\.one_night_cost)$/.exec(
          field ?? "",
        );
      if (cityStayField) {
        const [, index, nested] = cityStayField;
        const key =
          nested === "accommodation.area_or_poi"
            ? "accommodation"
            : nested === "accommodation.one_night_cost"
              ? "oneNightCost"
              : nested;
        return `cityStays.${index}.${key}`;
      }
      const segmentField =
        /^intercity_segments\.(\d+)\.(mode|service_number|departure_station|arrival_station|departure_at|arrival_at|fare)$/.exec(
          field ?? "",
        );
      if (segmentField) {
        const [, index, nested] = segmentField;
        const key = {
          mode: "mode",
          service_number: "serviceNumber",
          departure_station: "departureStation",
          arrival_station: "arrivalStation",
          departure_at: "departureTime",
          arrival_at: "arrivalTime",
          fare: "fare",
        }[nested];
        return `intercitySegments.${index}.${key}`;
      }
      return field;
    })();
    window.setTimeout(() => {
      const permitted = new Set([
        "city",
        "startDate",
        "endDate",
        "travelers",
        "totalBudget",
        "transportModes",
        "accommodation",
        "oneNightCost",
        "mealBudgetPerPersonPerDay",
        "freeText",
      ]);
      const isPermittedTarget =
        target &&
        (permitted.has(target) ||
          /^dayWindows\.\d+\.(startTime|endTime)$/.test(target) ||
          /^cityStays\.\d+\.(city|nights|accommodation|oneNightCost)$/.test(
            target ?? "",
          ) ||
          /^intercitySegments\.\d+\.(mode|serviceNumber|departureStation|arrivalStation|departureTime|arrivalTime|fare)$/.test(
            target ?? "",
          ));
      const safeTarget = isPermittedTarget ? target : "city";
      requestPanel.current
        ?.querySelector<HTMLElement>(`[data-field="${safeTarget}"]`)
        ?.focus();
    }, 0);
  };

  return (
    <div className="product-shell">
      <a
        className="skip-link"
        href="#trip-request-form"
        onClick={() => setRequestExpanded(true)}
      >
        跳到旅行需求表单
      </a>

      <header className="product-header">
        <div className="product-wordmark">
          <p>LOCAL TRAVEL DECISION DESK</p>
          <h1>
            旅笺 <span>Intelligent Travel Assistant</span>
          </h1>
        </div>
        <dl className="runtime-facts">
          <div>
            <dt>运行方式</dt>
            <dd>仅本机</dd>
          </div>
          <div>
            <dt>当前范围</dt>
            <dd>单城 / 2—3 城 · 2—7 日</dd>
          </div>
          <div>
            <dt>币种</dt>
            <dd>CNY</dd>
          </div>
        </dl>
      </header>

      <main
        className={`planning-workspace${
          resultFirst ? " planning-workspace--result" : ""
        }`}
      >
        <section
          className="request-panel"
          data-collapsed={requestCollapsed}
          id="trip-request-form"
          aria-label="旅行需求"
          ref={requestPanel}
          tabIndex={-1}
        >
          <button
            className="request-panel-toggle"
            type="button"
            aria-controls="trip-request-fields"
            aria-expanded={!requestCollapsed}
            onClick={() => setRequestExpanded((current) => !current)}
          >
            <span>{requestCollapsed ? "查看旅行需求" : "收起旅行需求"}</span>
            <span aria-hidden="true">{requestCollapsed ? "+" : "−"}</span>
          </button>
          <div className="request-panel-body" id="trip-request-fields">
            <TripRequestForm
              onSubmit={(request) => {
                setRequestExpanded(false);
                void start(request);
              }}
              createClientRequestId={createClientRequestId}
              submitting={busy}
            />
          </div>
        </section>

        <PlanningStage
          state={state}
          onResume={() => void resume()}
          onRetry={() => {
            setRequestExpanded(false);
            void retry();
          }}
          onReset={returnToRequest}
          replanApi={replanApi}
        />
      </main>

      <footer className="product-footer">
        <span>F-004C · 单城市、多城市与用户已购铁路段</span>
        <span>计划、来源、时效与冲突均来自服务端终态 · 不推测缺失事实</span>
      </footer>
    </div>
  );
}
