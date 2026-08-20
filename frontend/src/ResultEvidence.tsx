import type { TripPlanResponseDto } from "./tripPlanningApi";
import type {
  DataFreshness,
  ProviderName,
  SourceRecordDto,
} from "./tripPlanModels";

const PROVIDER_LABELS: Record<ProviderName, string> = {
  deepseek: "DeepSeek",
  amap: "高德开放平台",
  qweather: "和风天气",
  user: "用户输入",
  system: "系统规则",
};

const FRESHNESS_LABELS: Record<DataFreshness, string> = {
  fresh: "当前有效",
  stale: "已过期",
  unknown_validity: "有效期未知",
};

function formatTimestamp(value: string): string {
  return `${value.slice(0, 10)} ${value.slice(11, 16)}`;
}

function SourceRow({ source }: { source: SourceRecordDto }) {
  return (
    <article className="source-row">
      <div className="source-provider">
        <strong>{PROVIDER_LABELS[source.provider]}</strong>
        <span>{source.source_type.replaceAll("_", " · ")}</span>
      </div>
      <div className="source-time">
        <span>获取于 {formatTimestamp(source.fetched_at)}</span>
        <small>
          {source.valid_until
            ? `有效至 ${formatTimestamp(source.valid_until)}`
            : "未提供有效截止时间"}
        </small>
      </div>
      <span className={`freshness freshness--${source.freshness}`}>
        {FRESHNESS_LABELS[source.freshness]}
      </span>
      {(source.attributions.length > 0 || source.warnings.length > 0) && (
        <ul className="source-notes" aria-label="来源说明">
          {source.attributions.map((attribution, index) => (
            <li key={`attribution-${index}`}>{attribution}</li>
          ))}
          {source.warnings.map((warning, index) => (
            <li key={`warning-${index}`}>{warning}</li>
          ))}
        </ul>
      )}
      {source.reference_url && (
        <a
          className="source-link"
          href={source.reference_url}
          rel="noreferrer"
          target="_blank"
        >
          查看提供方记录
        </a>
      )}
    </article>
  );
}

export function SourceEvidence({
  sources,
}: {
  sources: TripPlanResponseDto["sources"];
}) {
  const includesQWeather = sources.some(
    (source) => source.provider === "qweather",
  );
  const includesAmap = sources.some((source) => source.provider === "amap");
  const includesDeepSeek = sources.some(
    (source) => source.provider === "deepseek",
  );
  return (
    <section className="result-section" aria-labelledby="sources-title">
      <h3 id="sources-title">来源与时效</h3>
      {(includesAmap || includesQWeather || includesDeepSeek) && (
        <div className="provider-disclosures" aria-label="服务归因与 AI 披露">
          {includesAmap && (
            <p>
              地理位置、POI 和路线数据来源：
              <a href="https://www.amap.com/" rel="noreferrer" target="_blank">
                高德地图
              </a>
            </p>
          )}
          {includesQWeather && (
            <p>
              天气服务由
              <a
                href="https://www.qweather.com"
                rel="noreferrer"
                target="_blank"
              >
                和风天气
              </a>
              驱动
            </p>
          )}
          {includesDeepSeek && (
            <p>
              本计划包含 DeepSeek AI
              生成内容，已通过确定性规则校验，但仍可能不准确。
            </p>
          )}
        </div>
      )}
      {sources.length > 0 ? (
        <div className="sources-panel">
          {sources.map((source) => (
            <SourceRow key={source.source_id} source={source} />
          ))}
        </div>
      ) : (
        <p className="evidence-empty">本次结果没有可引用的外部事实来源。</p>
      )}
    </section>
  );
}

export function ResultDiagnostics({
  response,
}: {
  response: TripPlanResponseDto;
}) {
  const hasDiagnostics =
    response.violations.length > 0 ||
    response.warnings.length > 0 ||
    response.uncertainties.length > 0 ||
    response.errors.length > 0;
  if (!hasDiagnostics) return null;

  return (
    <section className="result-section" aria-labelledby="diagnostics-title">
      <h3 id="diagnostics-title">数据与校验说明</h3>
      <div className="diagnostic-list">
        {response.violations.map((violation, index) => (
          <article
            className={`diagnostic-card diagnostic-card--${violation.severity}`}
            key={`violation-${violation.code}-${index}`}
          >
            <span>确定性冲突</span>
            <strong>{violation.message}</strong>
            <small>
              {violation.code} · 影响 {violation.affected_refs.length} 项引用
            </small>
          </article>
        ))}
        {response.uncertainties.map((uncertainty, index) => (
          <article
            className="diagnostic-card diagnostic-card--uncertain"
            key={`uncertainty-${uncertainty.code}-${index}`}
          >
            <span>数据不确定</span>
            <strong>{uncertainty.message}</strong>
            <small>
              {uncertainty.code} · {uncertainty.source_ids.length} 个来源引用
            </small>
          </article>
        ))}
        {response.errors.map((error, index) => (
          <article
            className="diagnostic-card diagnostic-card--error"
            key={`error-${error.code}-${index}`}
          >
            <span>{error.retryable ? "可安全重试" : "需要调整或确认"}</span>
            <strong>{error.message}</strong>
            <small>
              {error.code} ·{" "}
              {error.provider
                ? (PROVIDER_LABELS[error.provider as ProviderName] ??
                  "相关服务")
                : "系统校验"}
              {error.field ? ` · 字段 ${error.field}` : ""}
            </small>
          </article>
        ))}
        {response.warnings.map((warning, index) => (
          <article
            className="diagnostic-card diagnostic-card--warning"
            key={`warning-${index}`}
          >
            <span>结果提示</span>
            <strong>{warning}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}

const TERMINAL_COPY = {
  needs_input: {
    kicker: "需要你的决定 · 未继续外部调用",
    heading: "需要补充旅行信息",
    symbol: "？",
    lead: "系统没有猜测缺失条件，也没有用默认值替你做决定。",
  },
  failed: {
    kicker: "规划未完成 · 已停止后续调用",
    heading: "暂时无法形成安全计划",
    symbol: "×",
    lead: "已保留可验证事实，但不会用模板或未批准数据冒充完整计划。",
  },
  conflict: {
    kicker: "确定性校验未通过 · 需要调整约束",
    heading: "旅行约束无法同时满足",
    symbol: "×",
    lead: "系统没有自动放宽预算、时间或路线约束。",
  },
} as const;

export function TerminalOutcome({
  response,
  onRetry,
  onReset,
}: {
  response: TripPlanResponseDto;
  onRetry: () => void;
  onReset: (field?: string | null) => void;
}) {
  if (
    response.status !== "needs_input" &&
    response.status !== "failed" &&
    response.status !== "conflict"
  )
    return null;
  const copy = TERMINAL_COPY[response.status];
  const canRetry =
    response.status === "failed" && response.retryable && response.attempt < 3;
  const editField =
    response.status === "needs_input"
      ? (response.errors.find((error) => error.field)?.field ?? null)
      : null;

  return (
    <div
      className={`terminal-outcome terminal-outcome--${response.status}`}
      role={response.status === "failed" ? "alert" : "status"}
      aria-live="polite"
    >
      <header className="outcome-heading">
        <span className="outcome-symbol" aria-hidden="true">
          {copy.symbol}
        </span>
        <div>
          <p className="tracking-kicker">{copy.kicker}</p>
          <h2 id="plan-stage-title">{copy.heading}</h2>
          <p>{copy.lead}</p>
        </div>
      </header>

      <p className="tracking-summary">
        <strong>
          {"response_version" in response && response.response_version === "3"
            ? response.request_summary.city_stays
                .map((stay) => stay.city)
                .join(" → ")
            : response.request_summary.city}
        </strong>{" "}
        · {response.request_summary.start_date}起 ·{" "}
        {response.request_summary.travelers} 人 · 尝试 {response.attempt}/3
      </p>

      <ResultDiagnostics response={response} />
      <SourceEvidence sources={response.sources} />

      <div className="outcome-actions">
        {canRetry && (
          <button type="button" onClick={onRetry}>
            重试本次任务
          </button>
        )}
        <button type="button" onClick={() => onReset(editField)}>
          {response.status === "needs_input" ? "补充旅行信息" : "返回修改需求"}
        </button>
      </div>
      {canRetry && (
        <p className="outcome-action-note">
          服务端允许安全重试；系统会复用当前任务，不会创建重复计划。
        </p>
      )}
      {response.retryable && response.attempt >= 3 && (
        <p className="outcome-action-note">
          本任务已达到 3 次尝试上限，请返回修改需求后创建新任务。
        </p>
      )}
    </div>
  );
}
