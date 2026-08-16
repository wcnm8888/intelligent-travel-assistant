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

export function ReplanPanel({
  api = createReplanningApi(),
  baseline,
  command,
  commandLabel,
  onClose,
  onCompleted,
  pollingPolicy = DEFAULT_POLLING,
}: ReplanPanelProps) {
  const titleId = useId();
  const title = useRef<HTMLHeadingElement>(null);
  const [snapshot, setSnapshot] = useState<ReplanResponseDto | null>(null);
  const [phase, setPhase] = useState<"editing" | "busy" | "paused" | "settled">(
    "editing",
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    title.current?.focus();
  }, []);

  const finish = (next: ReplanResponseDto) => {
    setSnapshot(next);
    if (next.status === "completed" && next.result && next.change_set)
      onCompleted(next.result, next.change_set);
    setPhase("settled");
  };

  const poll = async (initial: ReplanResponseDto) => {
    let current = initial;
    for (
      let count = 0;
      count < pollingPolicy.maxPolls &&
      ["analyzing", "replanning"].includes(current.status);
      count += 1
    ) {
      await pollingPolicy.wait();
      current = await api.read(current.job_id, current.replan_id);
      setSnapshot(current);
    }
    if (["analyzing", "replanning"].includes(current.status)) {
      setPhase("paused");
    } else {
      finish(current);
    }
  };

  const safely = async (action: () => Promise<ReplanResponseDto>) => {
    setError(null);
    setPhase("busy");
    try {
      const next = await action();
      setSnapshot(next);
      if (["analyzing", "replanning"].includes(next.status)) await poll(next);
      else finish(next);
    } catch (caught) {
      setError(
        caught instanceof ReplanningClientError
          ? caught.message
          : "局部调整未能安全完成，原计划保持不变。",
      );
      setPhase("settled");
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
    return safely(() =>
      api.decide(snapshot.job_id, snapshot.replan_id, choice),
    );
  };
  const busy = phase === "busy";
  const impact = snapshot?.impact;
  const terminalMessage: Partial<Record<ReplanResponseDto["status"], string>> =
    {
      cancelled: "已取消调整，原计划没有改变。",
      expired: "确认已失效，原计划没有改变；请重新分析影响。",
      needs_input: "还需要安全的结构化信息，原计划仍可继续使用。",
      conflict: "局部调整存在硬冲突，原计划仍可继续使用。",
      failed: "局部调整未能安全完成，原计划仍可继续使用。",
      rejected: "该修改超出当前范围，原计划仍可继续使用。",
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
              void poll(snapshot);
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

      {impact && (
        <section className="replan-impact" aria-label="修改影响">
          <div className="replan-section-heading">
            <span>01</span>
            <h4>将影响哪些内容</h4>
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
          {snapshot?.status === "awaiting_confirmation" && (
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
                  disabled={busy}
                >
                  取消并保留原计划
                </button>
                <button
                  type="button"
                  onClick={() => void decide("approve")}
                  disabled={busy}
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
            <h4 id={`${titleId}-changes`}>本次版本变化</h4>
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

      {(error || (snapshot && terminalMessage[snapshot.status])) && (
        <div className="replan-terminal" role="alert">
          <strong>没有替换当前计划</strong>
          <p>{error ?? terminalMessage[snapshot!.status]}</p>
        </div>
      )}
    </section>
  );
}
