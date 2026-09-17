import { useEffect, useId, useRef, useState } from "react";

import {
  createReplanningApi,
  ReplanningClientError,
  type ReplanChangeSetDto,
  type ReplanCommand,
  type ReplanningApi,
  type ReplanResponseDto,
} from "./replanningApi";
import type { TripPlanResponseDto } from "./tripPlanningApi";
import type { TripPlanDto } from "./tripPlanModels";

type Baseline = TripPlanResponseDto & { plan: TripPlanDto };
export interface ReplanPollingPolicy {
  maxPolls: number;
  wait: () => Promise<void>;
}
const DEFAULT_POLLING: ReplanPollingPolicy = {
  maxPolls: 20,
  wait: () => new Promise((resolve) => window.setTimeout(resolve, 500)),
};

interface ReplanPanelProps {
  api?: ReplanningApi;
  baseline: Baseline;
  command: ReplanCommand;
  commandLabel: string;
  onClose: () => void;
  onModify?: () => void;
  onRefresh?: () => Promise<void>;
  onCompleted: (
    result: TripPlanResponseDto,
    changeSet: ReplanChangeSetDto,
  ) => void;
  pollingPolicy?: ReplanPollingPolicy;
}

const IMPACT_LABELS: Record<string, string> = {
  same_day_low: "同日低影响",
  adjacent_day: "相邻日期受影响",
  cross_day: "跨日依赖",
  accommodation_effect: "住宿锚点影响",
  budget_risk: "预算风险",
  source_refresh: "来源需刷新",
  cross_city: "跨城市（不支持）",
  unknown_impact: "影响尚不能判定",
};
const SOURCE_LABELS = {
  reuse: "继续使用",
  refresh: "重新获取",
  drop: "不再采用",
} as const;
const CHANGE_LABELS: Record<string, string> = {
  activity_added: "新增活动",
  activity_removed: "删除活动",
  activity_changed: "活动内容变化",
  route_changed: "路线变化",
  schedule_changed: "时间变化",
  cost_changed: "费用变化",
  source_changed: "来源变化",
};

type RecoveryAction = "retry" | "modify" | "refresh" | "stop";
function recoveryFor(
  status: ReplanResponseDto["status"],
  errors: ReplanResponseDto["errors"],
): RecoveryAction | null {
  if (status === "cancelled") return "retry";
  if (["conflict", "expired"].includes(status)) return "refresh";
  if (status === "needs_input") return "modify";
  if (status === "rejected") return "stop";
  if (status !== "failed") return null;
  const first = errors[0];
  if (
    [
      "version_conflict",
      "confirmation_expired",
      "constraint_conflict",
    ].includes(first?.code)
  )
    return "refresh";
  if (
    ["input_invalid", "data_missing", "budget_incomplete"].includes(first?.code)
  )
    return "modify";
  if (
    first?.retryable &&
    ([
      "provider_timeout",
      "provider_unavailable",
      "provider_rate_limited",
      "data_stale",
    ].includes(first.code) ||
      (first.code === "internal_error" &&
        ["replan_analysis_cancelled", "replan_execution_cancelled"].includes(
          first.diagnostic_code ?? "",
        )))
  )
    return "retry";
  return "stop";
}

export function ReplanPanel({
  api = createReplanningApi(),
  baseline,
  command,
  commandLabel,
  onClose,
  onModify = onClose,
  onRefresh,
  onCompleted,
  pollingPolicy = DEFAULT_POLLING,
}: ReplanPanelProps) {
  const titleId = useId();
  const title = useRef<HTMLHeadingElement>(null);
  const impactTitle = useRef<HTMLHeadingElement>(null);
  const changesTitle = useRef<HTMLHeadingElement>(null);
  const errorTitle = useRef<HTMLElement>(null);
  const [snapshot, setSnapshot] = useState<ReplanResponseDto | null>(null);
  const [phase, setPhase] = useState<"editing" | "busy" | "paused" | "settled">(
    "editing",
  );
  const [error, setError] = useState<string | null>(null);
  const [outcomeUncertain, setOutcomeUncertain] = useState(false);
  const [clientRecovery, setClientRecovery] = useState<RecoveryAction | null>(
    null,
  );

  useEffect(() => {
    title.current?.focus();
  }, []);

  useEffect(() => {
    if (snapshot?.status === "awaiting_confirmation")
      impactTitle.current?.focus();
    if (snapshot?.status === "completed") changesTitle.current?.focus();
  }, [snapshot?.status]);

  useEffect(() => {
    if (
      error ||
      [
        "cancelled",
        "expired",
        "needs_input",
        "conflict",
        "failed",
        "rejected",
      ].includes(snapshot?.status ?? "")
    )
      errorTitle.current?.focus();
  }, [error, snapshot?.status]);

  const finish = (next: ReplanResponseDto) => {
    setSnapshot(next);
    if (next.status === "completed" && next.result && next.change_set)
      onCompleted(next.result, next.change_set);
    setPhase("settled");
  };

  const poll = async (initial: ReplanResponseDto, forceFirstRead = false) => {
    let current = initial;
    for (
      let count = 0;
      count < pollingPolicy.maxPolls &&
      (forceFirstRead && count === 0
        ? true
        : ["analyzing", "replanning"].includes(current.status));
      count += 1
    ) {
      await pollingPolicy.wait();
      try {
        current = await api.read(current.job_id, current.replan_id);
      } catch (caught) {
        setError(
          caught instanceof ReplanningClientError
            ? `${caught.message} 后台可能仍在执行，请继续刷新确认最终状态。`
            : "自动刷新暂时失败；后台可能仍在执行，请继续刷新确认最终状态。",
        );
        setPhase("paused");
        return;
      }
      setSnapshot(current);
    }
    if (["analyzing", "replanning"].includes(current.status)) {
      setPhase("paused");
    } else {
      finish(current);
    }
  };

  const safely = async (
    action: () => Promise<ReplanResponseDto>,
    recoverableResponseLoss = false,
  ) => {
    setError(null);
    setOutcomeUncertain(false);
    setClientRecovery(null);
    setPhase("busy");
    try {
      const next = await action();
      setSnapshot(next);
      if (["analyzing", "replanning"].includes(next.status)) await poll(next);
      else finish(next);
    } catch (caught) {
      const responseUncertain =
        !(caught instanceof ReplanningClientError) ||
        [
          "network_unavailable",
          "response_invalid",
          "http_error",
          "internal_error",
        ].includes(caught.code);
      const shouldRecover =
        recoverableResponseLoss &&
        (responseUncertain ||
          (caught instanceof ReplanningClientError && caught.retryable));
      setOutcomeUncertain(responseUncertain);
      setError(
        shouldRecover
          ? "确认响应未能核实；后台可能仍在执行，请继续刷新确认最终状态。"
          : responseUncertain
            ? "提交响应未能核实；后台可能仍在执行，请刷新当前计划确认，勿重复提交调整。"
            : caught instanceof ReplanningClientError
              ? caught.message
              : "局部调整未能安全完成，原计划保持不变。",
      );
      setPhase(shouldRecover ? "paused" : "settled");
      setClientRecovery(
        shouldRecover
          ? null
          : responseUncertain
            ? "refresh"
            : recoveryFor("failed", [
                {
                  code:
                    caught instanceof ReplanningClientError
                      ? caught.code
                      : "internal_error",
                  retryable:
                    caught instanceof ReplanningClientError && caught.retryable,
                  message: "",
                  field: null,
                  provider: null,
                  diagnostic_code: null,
                },
              ]),
      );
    }
  };

  const analyze = () =>
    safely(() =>
      api.create(baseline.job_id, {
        replan_request_id: crypto.randomUUID(),
        baseline_plan_id: baseline.plan.plan_id,
        command,
      }),
    );
  const decide = (choice: "approve" | "cancel") => {
    if (!snapshot) return Promise.resolve();
    return safely(
      () => api.decide(snapshot.job_id, snapshot.replan_id, choice),
      true,
    );
  };
  const busy = phase === "busy";
  const impact = snapshot?.impact;
  const terminalMessage: Partial<Record<ReplanResponseDto["status"], string>> =
    {
      cancelled: "已取消调整，原计划未改变。",
      expired: "确认已失效，原计划未改变；请刷新当前计划。",
      needs_input: "还需要安全的结构化信息，原计划未改变。",
      conflict: "局部调整存在硬冲突，原计划未改变。",
      failed: "局部调整未能安全完成，原计划未改变。",
      rejected: "该修改超出当前范围，原计划未改变。",
    };
  const recoveryAction =
    phase === "paused"
      ? null
      : error
        ? clientRecovery
        : snapshot
          ? recoveryFor(snapshot.status, snapshot.errors)
          : null;
  const recover = async () => {
    if (busy) return;
    if (recoveryAction === "retry") {
      await analyze();
      return;
    }
    if (recoveryAction === "modify") {
      onModify();
      return;
    }
    if (recoveryAction !== "refresh") {
      onClose();
      return;
    }
    setPhase("busy");
    try {
      if (!onRefresh) throw new Error("current_plan_refresh_unavailable");
      await onRefresh();
    } catch {
      setError(
        "当前计划读取未成功，仍保留原计划；请稍后刷新，不会重新提交调整。",
      );
      setClientRecovery("refresh");
    } finally {
      setPhase("settled");
    }
  };

  return (
    <section className="replan-panel" aria-labelledby={titleId}>
      <header className="replan-panel__header">
        <div>
          <p>LOCAL CHANGE DESK / 当前计划保持可见</p>
          <h3 id={titleId} ref={title} tabIndex={-1}>
            {commandLabel}
          </h3>
        </div>
        <button type="button" onClick={onClose} disabled={busy}>
          关闭局部调整
        </button>
      </header>

      <div className="replan-live" role="status" aria-live="polite">
        {busy
          ? snapshot?.status === "replanning"
            ? "正在重新校验并生成新版本"
            : "正在分析修改影响"
          : outcomeUncertain
            ? "本次调整结果尚待确认。"
            : phase === "paused"
              ? "自动刷新已暂停；原计划仍可继续阅读。"
              : snapshot
                ? `局部调整状态：${snapshot.status}`
                : "修改尚未发送；原计划不会在分析前改变。"}
      </div>

      {phase === "paused" && snapshot && (
        <div className="replan-intent">
          <p>为避免无限轮询，页面已暂停自动刷新。</p>
          <button
            type="button"
            onClick={() => {
              setPhase("busy");
              setError(null);
              void poll(snapshot, true);
            }}
          >
            继续刷新局部调整
          </button>
        </div>
      )}

      {!snapshot && !error && (
        <div className="replan-intent">
          <p>
            系统只提交上方结构化修改，不发送完整 Prompt。分析阶段不会调用
            Provider。
          </p>
          <button type="button" onClick={() => void analyze()} disabled={busy}>
            分析影响
          </button>
        </div>
      )}

      {(error || (snapshot && terminalMessage[snapshot.status])) && (
        <div className="replan-terminal" role="alert">
          <strong ref={errorTitle} tabIndex={-1}>
            {phase === "paused" || outcomeUncertain
              ? "最终状态尚待确认"
              : "没有替换当前计划"}
          </strong>
          <p>{error ?? terminalMessage[snapshot!.status]}</p>
          {recoveryAction && (
            <button
              type="button"
              onClick={() => void recover()}
              disabled={busy}
            >
              {recoveryAction === "retry"
                ? "重新发起调整"
                : recoveryAction === "modify"
                  ? "修改调整内容"
                  : recoveryAction === "refresh"
                    ? "刷新当前计划"
                    : "停止并保留原计划"}
            </button>
          )}
        </div>
      )}

      {impact && (
        <section className="replan-impact" aria-label="修改影响">
          <div className="replan-section-heading">
            <span>01</span>
            <h4 ref={impactTitle} tabIndex={-1}>
              将影响哪些内容
            </h4>
          </div>
          <ul className="impact-tags">
            {impact.categories.map((category) => (
              <li key={category}>{IMPACT_LABELS[category] ?? category}</li>
            ))}
          </ul>
          <dl className="impact-grid">
            <div>
              <dt>受影响日期</dt>
              <dd>{impact.affected_dates.join("、") || "仅当前活动"}</dd>
            </div>
            <div>
              <dt>路线</dt>
              <dd>{impact.route_refs.length} 段需要复核</dd>
            </div>
            <div>
              <dt>直接 / 传递对象</dt>
              <dd>
                {impact.direct_refs.length} / {impact.transitive_refs.length}
              </dd>
            </div>
            <div>
              <dt>预算</dt>
              <dd>
                {impact.budget_effect
                  ? `已知合计变化 ${impact.budget_effect.known_total_delta}；未知项变化 ${impact.budget_effect.unknown_count_delta}`
                  : "金额未知时不会按 0 计算"}
              </dd>
            </div>
          </dl>
          <div className="source-actions">
            <h5>来源处理</h5>
            {impact.source_actions.length === 0 ? (
              <p>没有需要改变的来源记录。</p>
            ) : (
              <ul>
                {impact.source_actions.map((source) => (
                  <li key={source.source_id}>
                    <strong>{SOURCE_LABELS[source.action]}</strong>
                    <span>
                      {source.freshness === "unknown_validity"
                        ? "有效期未知"
                        : source.freshness}
                    </span>
                    <code>{source.source_id.slice(0, 8)}</code>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {snapshot?.status === "awaiting_confirmation" && !error && (
            <div className="confirmation-box">
              <p>
                <strong>确认前请检查：</strong>
                将保留未列出的计划内容；取消后原计划不变。确认有效至{" "}
                <time>
                  {new Date(snapshot.confirmation_expires_at).toLocaleString(
                    "zh-CN",
                    { hour12: false },
                  )}
                </time>
                。
              </p>
              <div>
                <button
                  type="button"
                  onClick={() => void decide("cancel")}
                  disabled={busy || Boolean(error)}
                >
                  取消并保留原计划
                </button>
                <button
                  type="button"
                  onClick={() => void decide("approve")}
                  disabled={busy || Boolean(error)}
                >
                  确认并生成新版本
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {snapshot?.status === "completed" && snapshot.change_set && (
        <section
          className="replan-change-set"
          aria-labelledby={`${titleId}-changes`}
        >
          <div className="replan-section-heading">
            <span>02</span>
            <h4 id={`${titleId}-changes`} ref={changesTitle} tabIndex={-1}>
              本次版本变化
            </h4>
          </div>
          <p>仅比较本次 baseline → result，不提供任意历史版本比较或恢复。</p>
          <ul>
            {snapshot.change_set.change_codes.map((code) => (
              <li key={code}>{CHANGE_LABELS[code] ?? code}</li>
            ))}
          </ul>
          <dl>
            <div>
              <dt>新增</dt>
              <dd>{snapshot.change_set.added_refs.length}</dd>
            </div>
            <div>
              <dt>删除</dt>
              <dd>{snapshot.change_set.removed_refs.length}</dd>
            </div>
            <div>
              <dt>变更</dt>
              <dd>{snapshot.change_set.changed_refs.length}</dd>
            </div>
          </dl>
          <ul className="replan-change-refs">
            {snapshot.change_set.added_refs.map((reference) => (
              <li key={`added-${reference}`}>新增对象：{reference}</li>
            ))}
            {snapshot.change_set.removed_refs.map((reference) => (
              <li key={`removed-${reference}`}>删除对象：{reference}</li>
            ))}
            {snapshot.change_set.changed_refs.map((reference) => (
              <li key={`changed-${reference}`}>变更对象：{reference}</li>
            ))}
          </ul>
          {snapshot.result?.plan?.budget_summary.unknown_count ? (
            <p className="replan-budget-unknown">
              金额未知 · {snapshot.result.plan.budget_summary.unknown_count}{" "}
              项，未按 0 处理
            </p>
          ) : null}
          {snapshot.result?.status === "partial" && (
            <p className="replan-partial-note">
              新版本仍为部分可用；warning 与不确定性继续保留。
            </p>
          )}
        </section>
      )}
    </section>
  );
}
