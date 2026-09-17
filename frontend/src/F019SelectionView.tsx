import { useEffect, useRef, useState, type ReactNode } from "react";
import type { PoiOptionDto } from "./f009Api";
import type { MapFocusRequest } from "./f019Presentation";
import "./f019-selection.css";

interface Props {
  city: string;
  accommodation: { location_id: string; name: string } | null;
  visits: PoiOptionDto[];
  indices: ReadonlyMap<string, number>;
  selected: ReadonlySet<string>;
  selectedCount: number;
  pendingCount: number;
  busy: boolean;
  notice: string | null;
  listFocus: MapFocusRequest | null;
  editor: ReactNode;
  anchorTask: ReactNode;
  map: ReactNode;
  advisor: ReactNode;
  onChoose(option: PoiOptionDto): void;
  onRemove(locationId: string): void;
  onView(locationId: string): void;
  onDestination(): void;
  onContinue(): void;
  onSearch(query: string): void;
  anchorPending: boolean;
}

function InlineSelectionEditor({
  children,
  onClose,
}: {
  children: ReactNode;
  onClose(): void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current
      ?.querySelector<HTMLElement>("h3")
      ?.focus({ preventScroll: true });
    return () => {
      previous?.focus({ preventScroll: true });
    };
  }, []);
  return (
    <div
      ref={ref}
      className="f020-inline-editor"
      role="dialog"
      aria-modal="false"
      aria-label="编辑住宿与地点"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          onClose();
        }
      }}
    >
      <header>
        <h3 tabIndex={-1}>编辑住宿与地点</h3>
        <button
          type="button"
          className="f019-button f019-secondary"
          onClick={onClose}
        >
          返回选点
        </button>
      </header>
      <p className="f019-label">在左侧编辑，地图仍可查看和定位。</p>
      {children}
    </div>
  );
}

function SelectionDialog({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose(): void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current;
    if (dialog?.showModal) dialog.showModal();
    else dialog?.setAttribute("open", "");
    return () => {
      dialog?.close?.();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      className="f019-dialog"
      ref={ref}
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <header>
        <h3>{title}</h3>
        <button
          type="button"
          className="f019-button f019-secondary"
          onClick={onClose}
        >
          返回选点
        </button>
      </header>
      {children}
    </dialog>
  );
}

export function F019SelectionView({
  city,
  accommodation,
  visits,
  indices,
  selected,
  selectedCount,
  pendingCount,
  busy,
  notice,
  listFocus,
  editor,
  anchorTask,
  map,
  advisor,
  onChoose,
  onRemove,
  onView,
  onDestination,
  onContinue,
  onSearch,
  anchorPending,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [summary, setSummary] = useState(false);
  const [search, setSearch] = useState({
    query: "",
    filter: "",
    focusSequence: listFocus?.sequence,
  });
  const query =
    search.focusSequence === listFocus?.sequence ? search.query : "";
  const filter =
    search.focusSequence === listFocus?.sequence ? search.filter : "";
  const locations = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!anchorPending) return;
    const task = locations.current?.querySelector<HTMLElement>(
      '[aria-label="确认景区入口"]',
    );
    task?.scrollIntoView?.({ block: "nearest" });
    task?.focus({ preventScroll: true });
  }, [anchorPending]);
  useEffect(() => {
    if (!listFocus) return;
    const card = Array.from(
      locations.current?.querySelectorAll<HTMLElement>("[data-location-id]") ??
        [],
    ).find((item) => item.dataset.locationId === listFocus.locationId);
    card?.scrollIntoView?.({ block: "nearest" });
    card?.focus({ preventScroll: true });
  }, [listFocus]);
  const visible = visits.filter(
    (item) => !filter || item.name.includes(filter),
  );
  const openEditor = () => setEditing(true);
  return (
    <div className="f019-selection" data-step="selection">
      <header className="f019-header">
        <div className="f019-brand">
          <span className="f019-brand-mark">行</span>
          <strong>行旅</strong>
          <small>旅行顾问</small>
        </div>
        <nav className="f019-steps" aria-label="旅行进度">
          <button type="button" disabled={busy} onClick={onDestination}>
            ✓ 旅行需求
          </button>
          <span aria-current="step">02 选地点</span>
          <button
            type="button"
            aria-disabled={busy || selectedCount === 0}
            onClick={() => {
              if (!busy) onContinue();
            }}
          >
            03 比较方案
          </button>
        </nav>
        <button
          type="button"
          className="f019-button f019-ghost"
          onClick={() => setSummary(true)}
        >
          我的旅行
        </button>
      </header>
      <div className="f019-context">
        <div>
          <h2 id="f019-title" data-f010-step-heading tabIndex={-1}>
            {city}，先选出想去的地方
          </h2>
          <p>
            {accommodation
              ? "住宿已确认。看看顾问的建议，再决定要不要加入。"
              : "先确认住宿，再看看顾问的建议。"}
          </p>
        </div>
        <div className="f019-status">
          <span>{accommodation ? "✓  住宿已确认" : "住宿待确认"}</span>
          <span>已选景点 {selectedCount}</span>
          <span>{pendingCount} 条建议待确认</span>
        </div>
      </div>
      <nav className="f019-section-nav" aria-label="选点页分区">
        <a href="#f019-locations">地点清单</a>
        <a href="#f019-map-region">地点地图</a>
        <a href="#f014-advisor-title">旅行顾问</a>
      </nav>
      <div className="f019-workspace">
        <section
          id="f019-locations"
          ref={locations}
          tabIndex={-1}
          className="f019-locations f019-panel"
          aria-label="地点清单"
        >
          {editing && (
            <InlineSelectionEditor onClose={() => setEditing(false)}>
              {notice && (
                <p className="form-notice" role="alert">
                  {notice}
                </p>
              )}
              {editor}
            </InlineSelectionEditor>
          )}
          <div className="f020-list-body" hidden={editing}>
            {notice && !summary && (
              <p className="f020-list-feedback" role="alert">
                {notice}
              </p>
            )}
            <header>
              <h3>地点清单</h3>
              <small>{visits.length + (accommodation ? 1 : 0)} 个地点</small>
            </header>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                setSearch({
                  query,
                  filter: "",
                  focusSequence: listFocus?.sequence,
                });
                if (query.trim()) onSearch(query.trim());
              }}
            >
              <input
                aria-label="搜索景点；更换住宿请打开住宿编辑"
                placeholder="搜索景点"
                value={query}
                onChange={(event) => {
                  setSearch({
                    query: event.target.value,
                    filter: event.target.value.trim(),
                    focusSequence: listFocus?.sequence,
                  });
                }}
              />
            </form>
            <p className="f019-label">
              住宿 / {accommodation ? "1 已确认" : "待确认"}
            </p>
            {accommodation ? (
              <article
                className="f019-location f019-stay"
                data-location-id={accommodation.location_id}
                tabIndex={-1}
                aria-label={accommodation.name}
              >
                <h4>{accommodation.name}</h4>
                <small>住宿 · 已确认</small>
                <div className="f019-actions">
                  <button
                    className="f019-button f019-ghost"
                    type="button"
                    disabled={busy}
                    onClick={openEditor}
                  >
                    更换住宿
                  </button>
                  <button
                    className="f019-button f019-ghost"
                    type="button"
                    onClick={() => onView(accommodation.location_id)}
                  >
                    地图查看
                  </button>
                </div>
              </article>
            ) : (
              <button
                type="button"
                className="f019-button f019-secondary"
                onClick={openEditor}
              >
                选择住宿
              </button>
            )}
            <button
              type="button"
              className="f019-label f019-link f019-edit-choice"
              aria-label="编辑已选地点与关系"
              onClick={openEditor}
            >
              景点 / {selectedCount} 已选 ·{" "}
              {visits.filter((item) => !selected.has(item.location_id)).length}{" "}
              候选
            </button>
            {anchorTask}
            <div className="f019-location-list">
              {visible.length === 0 && (
                <p className="f019-empty" role="status">
                  {filter
                    ? "没有匹配的候选地点，试试其他关键词。"
                    : "还没有景点候选，可搜索地点或告诉顾问你的想法。"}
                </p>
              )}
              {visible.map((option) => (
                <article
                  className="f019-location"
                  key={option.location_id}
                  data-location-id={option.location_id}
                  data-selected={selected.has(option.location_id)}
                  tabIndex={-1}
                  aria-label={option.name}
                >
                  <h4>
                    {indices.get(option.location_id)} · {option.name}
                  </h4>
                  <small>
                    {option.category_label} ·{" "}
                    {option.confirmation_status === "verified"
                      ? "地点已核验"
                      : "需确认具体入口"}
                  </small>
                  <div className="f019-actions">
                    <button
                      type="button"
                      className="f019-button f019-secondary"
                      disabled={
                        busy ||
                        (anchorPending && !selected.has(option.location_id))
                      }
                      onClick={() => {
                        if (selected.has(option.location_id))
                          onRemove(option.location_id);
                        else onChoose(option);
                      }}
                    >
                      {selected.has(option.location_id) ? "移除" : "加入已选"}
                    </button>
                    <button
                      type="button"
                      className="f019-button f019-ghost"
                      onClick={() => onView(option.location_id)}
                    >
                      地图查看
                    </button>
                  </div>
                </article>
              ))}
            </div>
            <p className="f019-guidance">
              候选不会自动加入。先选地点，再比较可行的日期安排。
            </p>
          </div>
        </section>
        {map}
        {advisor}
      </div>
      {summary && (
        <SelectionDialog
          title="我的旅行 · 当前会话"
          onClose={() => setSummary(false)}
        >
          {notice && (
            <p className="form-notice" role="alert">
              {notice}
            </p>
          )}
          <p>{city}</p>
          <p>住宿：{accommodation?.name ?? "待确认"}</p>
          <p>已选景点 {selectedCount}</p>
          <ul>
            {visits
              .filter((item) => selected.has(item.location_id))
              .map((item) => (
                <li key={item.location_id}>{item.name}</li>
              ))}
          </ul>
          <button
            type="button"
            className="f019-button f019-secondary"
            onClick={() => {
              setSummary(false);
              setEditing(true);
            }}
          >
            编辑选择
          </button>
        </SelectionDialog>
      )}
    </div>
  );
}
