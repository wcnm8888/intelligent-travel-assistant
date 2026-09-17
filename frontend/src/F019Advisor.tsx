import { useEffect, useRef, useState } from "react";
import type { AdvisorSnapshotDto, AdvisorSuggestionDto } from "./f009Api";
import { advisorPreferenceLabels } from "./f019Presentation";

interface Props {
  snapshot: AdvisorSnapshotDto;
  message: string;
  disabled: boolean;
  expanded: boolean;
  indices: ReadonlyMap<string, number>;
  selected: ReadonlySet<string>;
  onToggle(): void;
  onMessage(value: string): void;
  onSend(): void;
  onAction(suggestion: AdvisorSuggestionDto, action: "accept" | "ignore"): void;
  onView(locationId: string): void;
}

export function F019Advisor({
  snapshot,
  message,
  disabled,
  expanded,
  indices,
  selected,
  onToggle,
  onMessage,
  onSend,
  onAction,
  onView,
}: Props) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const composing = useRef(false);
  const composer = useRef<HTMLFormElement>(null);
  const restoreComposerFocus = useRef(false);
  useEffect(() => {
    if (disabled || !restoreComposerFocus.current) return;
    restoreComposerFocus.current = false;
    // Disabled controls can yield focus to body; respect navigation elsewhere.
    if (
      document.activeElement === document.body ||
      composer.current?.contains(document.activeElement)
    )
      composer.current
        ?.querySelector("textarea")
        ?.focus({ preventScroll: true });
  }, [disabled]);
  const preferenceLabels = advisorPreferenceLabels(
    snapshot.confirmed_preferences,
  );
  const conversation = snapshot.conversation.length
    ? snapshot.conversation
    : snapshot.question
      ? [{ role: "advisor", text: snapshot.question }]
      : [];
  const showHistory = historyOpen || snapshot.phase === "interview";
  const latestReply = conversation
    .filter((entry) => entry.role === "advisor")
    .at(-1);
  const latestRequest =
    snapshot.conversation.filter((entry) => entry.role === "user").at(-1)
      ?.text ?? "告诉顾问你的想法";
  // A brief display of the user's own words; never infer confirmed preferences.
  const requestLabel = latestRequest.replace(/^先推荐/, "");
  return (
    <aside
      className="f019-advisor f019-panel"
      aria-labelledby="f014-advisor-title"
      data-collapsed={!expanded}
    >
      <p
        className="sr-only"
        role="status"
        aria-label="顾问最新回复"
        aria-live="polite"
        aria-atomic="true"
        aria-busy={disabled}
      >
        <span key={`${conversation.length}-${latestReply?.text ?? ""}`}>
          {latestReply ? `旅行顾问：${latestReply.text} ` : ""}
          {snapshot.pending_suggestions.length} 条建议待确认。
        </span>
      </p>
      <header className="f019-advisor-heading">
        <h3 id="f014-advisor-title" tabIndex={-1}>
          旅行顾问
        </h3>
        <button
          type="button"
          className="f019-link f019-advisor-toggle"
          aria-label={expanded ? "收起" : "打开顾问"}
          aria-expanded={expanded}
          aria-controls="f019-advisor-body"
          onClick={onToggle}
        >
          {expanded ? "与你一起选" : "打开顾问"}
        </button>
      </header>
      {expanded && (
        <>
          <div id="f019-advisor-body" className="f019-advisor-scroll">
            <div className="f019-request">
              <small>本轮诉求</small>
              <p>{requestLabel}</p>
            </div>
            {snapshot.phase === "degraded" && (
              <p role="status">顾问暂不可用。{snapshot.safety_summary}</p>
            )}
            <h4 className="f019-suggestion-heading">
              {snapshot.pending_suggestions.length} 条建议，等你确认
            </h4>
            <div className="f019-suggestions">
              {snapshot.pending_suggestions.length === 0 &&
                snapshot.phase !== "interview" && (
                  <p className="f019-empty" role="status">
                    当前没有待确认建议。可以继续选点，或补充你的想法。
                  </p>
                )}
              {snapshot.pending_suggestions.map((suggestion) => {
                const index = suggestion.location_id
                  ? indices.get(suggestion.location_id)
                  : undefined;
                const alreadySelected =
                  !!suggestion.location_id &&
                  selected.has(suggestion.location_id);
                return (
                  <article
                    className="f019-suggestion"
                    key={suggestion.suggestion_id}
                    aria-label={suggestion.location_name || suggestion.title}
                    data-suggestion-id={suggestion.suggestion_id}
                  >
                    <small>
                      {alreadySelected ? "地点已选 · 建议待确认" : "待你确认"}
                    </small>
                    <h4>
                      {suggestion.kind === "poi"
                        ? `${index ? `${index} · ` : ""}${suggestion.location_name || suggestion.title}`
                        : suggestion.title}
                    </h4>
                    <p>{suggestion.reason}</p>
                    <div className="f019-actions">
                      <button
                        className="f019-button f019-primary"
                        type="button"
                        disabled={disabled}
                        onClick={() => onAction(suggestion, "accept")}
                      >
                        {suggestion.kind === "poi"
                          ? alreadySelected
                            ? "确认已选"
                            : "加入已选"
                          : "确认偏好"}
                      </button>
                      {suggestion.location_id && (
                        <button
                          className="f019-button f019-secondary"
                          type="button"
                          onClick={() => onView(suggestion.location_id!)}
                        >
                          地图查看
                        </button>
                      )}
                      <button
                        className="f019-button f019-ghost"
                        type="button"
                        disabled={disabled}
                        onClick={() => onAction(suggestion, "ignore")}
                      >
                        忽略
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
            <div className="f019-history-row">
              <button
                type="button"
                className="f019-link"
                aria-expanded={showHistory}
                aria-controls="f019-history"
                onClick={() => setHistoryOpen(!historyOpen)}
              >
                查看对话记录（{conversation.length}）
              </button>
              <small>已确认偏好 {preferenceLabels.length}</small>
            </div>
            {showHistory && (
              <section
                id="f019-history"
                className="f019-history"
                aria-label="对话与偏好"
              >
                <h4>最近对话</h4>
                <ol>
                  {conversation.map((entry, index) => (
                    <li key={`${entry.role}-${index}`}>
                      <small>{entry.role === "user" ? "你" : "旅行顾问"}</small>
                      <p>{entry.text}</p>
                    </li>
                  ))}
                </ol>
                <h4>已确认偏好</h4>
                {preferenceLabels.length ? (
                  <ul>
                    {preferenceLabels.map((label) => (
                      <li key={label}>{label}</li>
                    ))}
                  </ul>
                ) : (
                  <p>尚未确认偏好，顾问会先从你的回答中整理。</p>
                )}
                <button
                  type="button"
                  className="f019-link"
                  onClick={() => onMessage("我想调整已确认偏好：")}
                >
                  调整
                </button>
                <div className="f019-quick-replies" aria-label="快捷回答">
                  {[
                    "先推荐自然景点，其他都灵活",
                    "少走路",
                    "避开拥挤",
                    "上午 10 点后出发",
                    "第一次来，请帮我取舍",
                  ].map((reply) => (
                    <button
                      key={reply}
                      type="button"
                      className="f019-button f019-secondary"
                      disabled={disabled}
                      onClick={() => onMessage(reply)}
                    >
                      {reply}
                    </button>
                  ))}
                </div>
                <details>
                  <summary>顾问如何工作</summary>
                  <p>
                    顾问只提出偏好补丁和已验证地点建议；你确认后才会更新选择并使旧预检失效。路线、时间和可行性仍由确定性程序核验。
                  </p>
                </details>
              </section>
            )}
          </div>
          <form
            ref={composer}
            className="f019-composer"
            onSubmit={(event) => {
              event.preventDefault();
              if (
                !composing.current &&
                !disabled &&
                message.trim() &&
                message.length <= 500
              ) {
                restoreComposerFocus.current = event.currentTarget.contains(
                  document.activeElement,
                );
                onSend();
              }
            }}
          >
            <label className="sr-only" htmlFor="f019-message">
              你的补充
            </label>
            <textarea
              id="f019-message"
              disabled={disabled}
              rows={1}
              maxLength={500}
              value={message}
              placeholder="想补充什么？例如：更喜欢安静的地方"
              onChange={(event) => onMessage(event.target.value)}
              onCompositionStart={() => {
                composing.current = true;
              }}
              onCompositionEnd={() => {
                composing.current = false;
              }}
            />
            <div className="f019-composer-footer">
              <small aria-live="off">{message.length} / 500</small>
              <button
                className="f019-button f019-primary"
                type="submit"
                aria-label="发送给旅行顾问"
                disabled={disabled || !message.trim() || message.length > 500}
              >
                {disabled ? "发送中…" : "发送"}
              </button>
            </div>
          </form>
        </>
      )}
    </aside>
  );
}
