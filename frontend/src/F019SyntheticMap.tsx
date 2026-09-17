import { useEffect, useMemo, useRef, useState } from "react";
import type { PoiOptionDto } from "./f009Api";
import type { MapFocusRequest } from "./f019Presentation";
import background from "./assets/f019-map-background.svg";

interface Props {
  options: PoiOptionDto[];
  selectedLocationIds: ReadonlySet<string>;
  displayIndices?: ReadonlyMap<string, number>;
  focusRequest?: MapFocusRequest | null;
  city?: string;
  onSelect(locationId: string): void;
}

export function F019SyntheticMap({
  options,
  selectedLocationIds,
  displayIndices,
  focusRequest,
  city,
  onSelect,
}: Props) {
  const element = useRef<HTMLElement>(null);
  const handledFocus = useRef(0);
  const [size, setSize] = useState({ width: 664, height: 712 });
  useEffect(() => {
    if (!element.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      setSize({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      });
    });
    observer.observe(element.current);
    return () => observer.disconnect();
  }, []);
  const fit = Math.min(size.width / 664, size.height / 712);
  const offsetX = (size.width - 664 * fit) / 2;
  const offsetY = (size.height - 712 * fit) / 2;
  const [interaction, setInteraction] = useState({
    sequence: 0,
    view: { scale: 1, x: 0, y: 0 },
    focused: null as string | null,
  });
  const positions = useMemo(() => {
    const lngs = options.map((item) => item.coordinate_gcj02.longitude);
    const lats = options.map((item) => item.coordinate_gcj02.latitude);
    const west = Math.min(...lngs);
    const east = Math.max(...lngs);
    const south = Math.min(...lats);
    const north = Math.max(...lats);
    return options.map((item) => ({
      item,
      x:
        east === west
          ? 332
          : 86 +
            ((item.coordinate_gcj02.longitude - west) / (east - west)) * 438,
      y:
        north === south
          ? 356
          : 476 -
            ((item.coordinate_gcj02.latitude - south) / (north - south)) * 240,
      labelShift:
        item.purpose === "accommodation"
          ? -25
          : item.coordinate_gcj02.longitude === east
            ? 13
            : 2,
    }));
  }, [options]);
  const focusPoint =
    focusRequest &&
    positions.find(
      (point) => point.item.location_id === focusRequest.locationId,
    );
  const newFocus =
    !!focusPoint && interaction.sequence !== focusRequest?.sequence;
  const view = newFocus
    ? { scale: 1, x: 332 - focusPoint.x, y: 356 - focusPoint.y }
    : interaction.view;
  const focused = newFocus ? focusPoint.item.location_id : interaction.focused;
  const setView = (next: typeof view, nextFocus = focused) =>
    setInteraction({
      sequence: focusRequest?.sequence ?? 0,
      view: next,
      focused: nextFocus,
    });
  useEffect(() => {
    if (!focusRequest || handledFocus.current === focusRequest.sequence) return;
    const point = positions.find(
      (value) => value.item.location_id === focusRequest.locationId,
    );
    if (!point) return;
    handledFocus.current = focusRequest.sequence;
    if (window.innerWidth <= 1180)
      element.current?.scrollIntoView?.({ block: "center" });
    const buttons = element.current?.querySelectorAll<HTMLButtonElement>(
      "[data-map-location-id]",
    );
    Array.from(buttons ?? [])
      .find((button) => button.dataset.mapLocationId === point.item.location_id)
      ?.focus({ preventScroll: true });
  }, [focusRequest, positions]);
  const zoom = (factor: number) => {
    const scale = Math.min(3, Math.max(0.5, view.scale * factor));
    const ratio = scale / view.scale;
    setView({
      scale,
      x: 332 - (332 - view.x) * ratio,
      y: 356 - (356 - view.y) * ratio,
    });
  };
  return (
    <section
      className="f019-map"
      id="f019-map-region"
      tabIndex={-1}
      aria-label="地点地图"
      data-state="ready"
      data-map-kind="synthetic"
      data-focus-sequence={focusRequest?.sequence ?? 0}
      ref={element}
    >
      <img
        className="f019-map-background"
        src={background}
        alt=""
        width={664}
        height={712}
        style={{
          transform: `translate(${offsetX + view.x * fit}px, ${offsetY + view.y * fit}px) scale(${view.scale * fit})`,
        }}
      />
      <div className="f019-map-heading">
        <div>
          <h3>{city} · 地点分布</h3>
          <small>先理解位置，再决定想去哪里</small>
        </div>
        <button
          className="f019-button f019-secondary"
          type="button"
          onClick={() => {
            setView({ scale: 1, x: 0, y: 0 }, null);
          }}
        >
          查看全部
        </button>
      </div>
      <div className="f019-map-markers">
        {positions.map(({ item, x, y, labelShift }) => {
          const lodging = item.purpose === "accommodation";
          const left =
            offsetX +
            (x * view.scale + view.x) * fit -
            (lodging && fit < 0.75 ? 12 : 0);
          const top = offsetY + (y * view.scale + view.y) * fit;
          return (
            <div key={item.location_id}>
              <button
                type="button"
                className="f019-map-marker"
                data-map-location-id={item.location_id}
                data-role={item.purpose}
                data-selected={selectedLocationIds.has(item.location_id)}
                data-focused={focused === item.location_id}
                aria-label={`地图定位：${item.name}`}
                style={{ left: left - 22, top: top - 22 }}
                onClick={() => {
                  setView(view, item.location_id);
                  onSelect(item.location_id);
                }}
              >
                {lodging
                  ? "宿"
                  : (displayIndices?.get(item.location_id) ?? "·")}
              </button>
              <span
                className="f019-map-label"
                data-role={item.purpose}
                style={{
                  left: Math.max(
                    8,
                    Math.min(
                      size.width - (lodging ? 168 : 108) - 8,
                      left + labelShift * fit - (lodging ? 84 : 54),
                    ),
                  ),
                  top: top + (lodging ? -80 : 34),
                }}
              >
                {item.name}
              </span>
            </div>
          );
        })}
      </div>
      <div className="f019-map-zoom">
        <button
          type="button"
          className="f019-button f019-secondary"
          aria-label="放大地图"
          disabled={view.scale >= 3}
          onClick={() => zoom(1.25)}
        >
          +
        </button>
        <button
          type="button"
          className="f019-button f019-secondary"
          aria-label="缩小地图"
          disabled={view.scale <= 0.5}
          onClick={() => zoom(0.8)}
        >
          −
        </button>
      </div>
      <div className="f019-map-legend">
        <div>
          <span>■ 已确认住宿</span>
          <span>○ 候选景点</span>
          <span>尚未生成路线</span>
        </div>
        <small>地图为合成设计示意 · 地形非真实底图 · 不用于导航</small>
      </div>
    </section>
  );
}
