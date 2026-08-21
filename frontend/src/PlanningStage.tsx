import type { PlanningStatus, TripPlanResponseDto } from "./tripPlanningApi";
import type { ReplanningApi } from "./replanningApi";
import { TerminalOutcome } from "./ResultEvidence";
import { TripPlanResult } from "./TripPlanResult";
import { tripDayCount } from "./tripRequest";
import { TerminalTaskActions } from "./TerminalTaskActions";
import type { TripPlanningViewState } from "./useTripPlanningJob";

interface PlanningStageProps {
  state: TripPlanningViewState;
  onResume: () => void;
  onRetry: () => void;
  onRestore?: () => void;
  onDelete?: () => Promise<void>;
  onReset: (field?: string | null) => void;
  replanApi?: ReplanningApi;
}

const TRACKING_STAGES: ReadonlyArray<{
  status: Exclude<
    PlanningStatus,
    "needs_input" | "ready" | "partial" | "conflict" | "failed"
  >;
  label: string;
  description: string;
}> = [
  { status: "draft", label: "任务登记", description: "本机后端已接受请求" },
  {
    status: "normalizing",
    label: "需求规范化",
    description: "检查城市、日期与约束",
  },
  {
    status: "collecting",
    label: "收集旅行事实",
    description: "获取地点、天气与候选信息",
  },
  {
    status: "planning",
    label: "生成结构计划",
    description: "模型只提出候选计划",
  },
  {
    status: "enriching_routes",
    label: "补全路线",
    description: "补齐住宿往返交通段",
  },
  {
    status: "validating",
    label: "确定性校验",
    description: "代码校验时间、路线与预算",
  },
];

const TERMINAL_LABELS: Record<
  "needs_input" | "ready" | "partial" | "conflict" | "failed",
  string
> = {
  needs_input: "需要补充输入",
  ready: "计划已通过校验",
  partial: "计划部分可用",
  conflict: "计划存在硬冲突",
  failed: "计划未能完成",
};

function RequestSummary({ response }: { response: TripPlanResponseDto }) {
  const dayCount = tripDayCount(
    response.request_summary.start_date,
    response.request_summary.end_date,
  );
  return (
    <p className="tracking-summary">
      <strong>
        {"response_version" in response &&
        (response.response_version === "3" || response.response_version === "4")
          ? response.request_summary.city_stays
              .map((stay) => stay.city)
              .join(" → ")
          : response.request_summary.city}
      </strong>{" "}
      · {response.request_summary.start_date}—
      {response.request_summary.end_date} · {dayCount ?? "?"} 日 ·{" "}
      {response.request_summary.travelers} 人 · 任务尝试 {response.attempt}/3
    </p>
  );
}

function ProgressTrack({ response }: { response: TripPlanResponseDto }) {
  const activeIndex = TRACKING_STAGES.findIndex(
    (stage) => stage.status === response.status,
  );
  return (
    <ol className="progress-track" aria-label="旅行计划处理阶段">
      {TRACKING_STAGES.map((stage, index) => {
        const state =
          index < activeIndex
            ? "complete"
            : index === activeIndex
              ? "active"
              : "pending";
        return (
          <li
            className={`progress-step progress-step--${state}`}
            key={stage.status}
          >
            <span className="progress-mark" aria-hidden="true">
              {state === "complete" ? "✓" : String(index + 1).padStart(2, "0")}
            </span>
            <div>
              <strong>{stage.label}</strong>
              <small>{stage.description}</small>
            </div>
            <span className="progress-state">
              {state === "active"
                ? "进行中"
                : state === "complete"
                  ? "完成"
                  : "等待"}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function PlanningStage({
  state,
  onResume,
  onRetry,
  onRestore,
  onDelete,
  onReset,
  replanApi,
}: PlanningStageProps) {
  const response =
    state.phase === "tracking" ||
    state.phase === "paused" ||
    state.phase === "terminal"
      ? state.response
      : null;
  const hasPlanResult =
    state.phase === "terminal" &&
    response !== null &&
    response.plan !== null &&
    (response.status === "ready" ||
      response.status === "partial" ||
      response.status === "conflict");
  const hasTerminalOutcome =
    state.phase === "terminal" &&
    response !== null &&
    !hasPlanResult &&
    (response.status === "needs_input" ||
      response.status === "failed" ||
      response.status === "conflict");
  const hasRichTerminal = hasPlanResult || hasTerminalOutcome;

  return (
    <aside
      className={`plan-stage${hasRichTerminal ? " plan-stage--result" : ""}`}
      aria-labelledby="plan-stage-title"
    >
      <div className="stage-number" aria-hidden="true">
        02
      </div>
      <p className="section-kicker">PLAN WORKSPACE / 02</p>

      {state.phase === "idle" && (
        <>
          <h2 id="plan-stage-title" tabIndex={-1}>
            计划将在这里展开
          </h2>
          {state.notice && (
            <p className="tracking-notice" role="status">
              {state.notice}
            </p>
          )}
          <div className="empty-stage">
            <span aria-hidden="true">旅</span>
            <p>
              先在左侧写下城市、日期、预算和旅行偏好。未知住宿费用可以留空，系统不会将它按
              0 计算。
            </p>
          </div>
        </>
      )}

      {state.phase === "submitting" && (
        <div className="tracking-view" role="status" aria-live="polite">
          <p className="tracking-kicker">
            {state.action === "restore"
              ? "正在读取本机任务"
              : "正在连接本机计划服务"}
          </p>
          <h2 id="plan-stage-title" tabIndex={-1}>
            {state.action === "restore"
              ? "正在恢复上次本机任务"
              : "登记旅行任务"}
          </h2>
          <p className="stage-note">
            请求仅发送到同源 `/api`，提交期间不会重复创建任务。
          </p>
        </div>
      )}

      {state.phase === "retrying" && (
        <div className="tracking-view" role="status" aria-live="polite">
          <p className="tracking-kicker">正在启动安全重试</p>
          <h2 id="plan-stage-title" tabIndex={-1}>
            重新核验缺失数据
          </h2>
          <p className="stage-note">
            正在复用原任务并创建第 {state.nextAttempt}/3
            次尝试。旧结果已从页面移除，避免与新快照混淆。
          </p>
        </div>
      )}

      {(state.phase === "tracking" || state.phase === "paused") && response && (
        <div className="tracking-view" role="status" aria-live="polite">
          <p className="tracking-kicker">
            服务端状态 · {response.status.replaceAll("_", " ")}
          </p>
          <h2 id="plan-stage-title" tabIndex={-1}>
            {state.phase === "paused"
              ? "任务仍在等待"
              : `正在形成${tripDayCount(response.request_summary.start_date, response.request_summary.end_date) ?? "多"}日计划`}
          </h2>
          <RequestSummary response={response} />
          <ProgressTrack response={response} />
          {state.phase === "paused" && (
            <div className="tracking-notice">
              <p>
                任务仍停留在当前服务端状态。为避免无限请求，自动刷新已经暂停。
              </p>
              <button type="button" onClick={onResume}>
                继续刷新
              </button>
            </div>
          )}
        </div>
      )}

      {hasPlanResult && response?.plan && (
        <TripPlanResult
          response={{ ...response, plan: response.plan }}
          onRetry={onRetry}
          onReset={onReset}
          replanApi={replanApi}
        />
      )}

      {hasTerminalOutcome && response && (
        <TerminalOutcome
          response={response}
          onRetry={onRetry}
          onReset={onReset}
        />
      )}

      {state.phase === "terminal" && response && !hasRichTerminal && (
        <div
          className="tracking-view terminal-view"
          role="status"
          aria-live="polite"
        >
          <p className="tracking-kicker">任务已停止轮询 · {response.status}</p>
          <h2 id="plan-stage-title" tabIndex={-1}>
            {TERMINAL_LABELS[response.status as keyof typeof TERMINAL_LABELS] ??
              "计划任务已结束"}
          </h2>
          <RequestSummary response={response} />
          <p className="stage-note">
            结果载荷不可用。页面不会推测缺失计划、来源或恢复动作，请返回修改需求。
          </p>
          <button
            className="stage-action"
            type="button"
            onClick={() => onReset()}
          >
            返回修改需求
          </button>
        </div>
      )}

      {state.phase === "terminal" && onDelete && (
        <TerminalTaskActions onDelete={onDelete} />
      )}

      {state.phase === "error" && (
        <div className="tracking-view error-view" role="alert">
          <p className="tracking-kicker">任务连接失败 · {state.code}</p>
          <h2 id="plan-stage-title" tabIndex={-1}>
            暂时无法继续
          </h2>
          <p className="stage-note">{state.message}</p>
          {state.recoveryAvailable && onRestore && (
            <button className="stage-action" type="button" onClick={onRestore}>
              稍后重试恢复
            </button>
          )}
          <button
            className="stage-action"
            type="button"
            onClick={() => onReset()}
          >
            返回修改需求
          </button>
        </div>
      )}

      <div className="scope-strip">
        <span>NO BOOKING</span>
        <span>NO PAYMENT</span>
        <span>LOCAL API ONLY</span>
      </div>
    </aside>
  );
}
