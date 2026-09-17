import { useEffect, useRef, useState } from "react";

import type { MapPlanDto, PoiOptionDto } from "./f009Api";
import {
  officialF009MapLoader,
  type AMapInstance,
  type F009MapLoader,
  type AMapNamespace,
} from "./f009MapLoader";

interface F009MapProps {
  options: PoiOptionDto[];
  optionRoles: ReadonlyMap<string, "accommodation" | "visit">;
  selectedLocationIds: ReadonlySet<string>;
  mapPlan: MapPlanDto | null;
  onSelect(locationId: string): void;
  onSearchArea?(center: { longitude: number; latitude: number }): void;
  loader?: F009MapLoader;
}

export function F009Map({
  options,
  optionRoles,
  selectedLocationIds,
  mapPlan,
  onSelect,
  onSearchArea,
  loader = officialF009MapLoader,
}: F009MapProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<AMapInstance | null>(null);
  const namespaceRef = useRef<AMapNamespace | null>(null);
  const overlaysRef = useRef<unknown[]>([]);
  const [attempt, setAttempt] = useState(0);
  const [mapReadyVersion, setMapReadyVersion] = useState(0);
  const [activeDaySelection, setActiveDaySelection] = useState({
    planId: mapPlan?.plan_id ?? null,
    index: 0,
  });
  const activeDayIndex =
    activeDaySelection.planId === (mapPlan?.plan_id ?? null)
      ? activeDaySelection.index
      : 0;
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable">(
    "loading",
  );
  const [failureReason, setFailureReason] = useState<
    "configuration" | "load" | null
  >(null);
  const [searchCenter, setSearchCenter] = useState<{
    longitude: number;
    latitude: number;
  } | null>(null);

  useEffect(() => {
    let active = true;
    let map: AMapInstance | null = null;
    const element = container.current;
    if (!element) return;
    setStatus("loading");
    setFailureReason(null);
    void loader()
      .then((AMap) => {
        if (!active) return;
        map = new AMap.Map(element, { zoom: 12, resizeEnable: true });
        mapRef.current = map;
        namespaceRef.current = AMap;
        let moveTimer: ReturnType<typeof setTimeout> | undefined;
        map.on("moveend", () => {
          clearTimeout(moveTimer);
          moveTimer = setTimeout(() => {
            if (!active || !map) return;
            const center = map.getCenter();
            setSearchCenter({
              longitude: center.getLng(),
              latitude: center.getLat(),
            });
          }, 600);
        });
        setStatus("ready");
        setMapReadyVersion((value) => value + 1);
      })
      .catch((error: unknown) => {
        if (active) {
          setFailureReason(
            error instanceof Error &&
              error.message === "amap_js_configuration_missing"
              ? "configuration"
              : "load",
          );
          setStatus("unavailable");
        }
      });
    return () => {
      active = false;
      setSearchCenter(null);
      overlaysRef.current = [];
      mapRef.current = null;
      namespaceRef.current = null;
      map?.destroy();
    };
  }, [attempt, loader]);

  useEffect(() => {
    const map = mapRef.current;
    const AMap = namespaceRef.current;
    if (!map || !AMap || status !== "ready") return;
    if (overlaysRef.current.length > 0) {
      map.remove?.(overlaysRef.current);
      overlaysRef.current = [];
    }
    const activeDay = mapPlan?.days[activeDayIndex] ?? mapPlan?.days[0];
    const markers = mapPlan
      ? [
          { ...mapPlan.accommodation, role: "accommodation" as const },
          ...(activeDay?.markers ?? []).map((marker) => ({
            ...marker,
            role: "visit" as const,
          })),
        ]
      : options.map((option) => ({
          location_id: option.location_id,
          name: option.name,
          coordinate: option.coordinate_gcj02,
          visit_order: null,
          role: optionRoles.get(option.location_id) ?? option.purpose,
        }));
    for (const marker of markers) {
      const position: [number, number] = [
        marker.coordinate.longitude,
        marker.coordinate.latitude,
      ];
      const selected = selectedLocationIds.has(marker.location_id);
      const markerText =
        marker.role === "accommodation"
          ? "住"
          : marker.visit_order
            ? String(marker.visit_order)
            : "游";
      const instance = new AMap.Marker({
        position,
        title: marker.name,
        content: markerContent(marker.role, markerText, selected),
        anchor: "bottom-center",
        zIndex: selected ? 130 : 100,
      });
      instance.on("click", () => {
        onSelect(marker.location_id);
        new AMap.InfoWindow({
          content: marker.name,
          offset: [0, -28],
        }).open(map, position);
      });
      map.add(instance);
      overlaysRef.current.push(instance);
    }
    if (activeDay) {
      for (const route of activeDay.routes) {
        const polyline = new AMap.Polyline({
          path: route.points.map(
            (point) => [point.longitude, point.latitude] as [number, number],
          ),
          strokeColor: colorFor(activeDay.color_token),
          strokeWeight: 6,
          strokeStyle: route.mode === "walking" ? "dashed" : "solid",
          showDir: true,
        });
        map.add(polyline);
        overlaysRef.current.push(polyline);
      }
    }
    map.setFitView();
  }, [
    activeDayIndex,
    mapPlan,
    mapReadyVersion,
    onSelect,
    optionRoles,
    options,
    selectedLocationIds,
    status,
  ]);

  return (
    <section
      className="f009-map-shell"
      aria-label="地点地图"
      data-state={status}
    >
      {mapPlan && (
        <div className="f009-map-days" aria-label="地图日期图层">
          {mapPlan.days.map((day, index) => (
            <button
              type="button"
              key={day.local_date}
              aria-pressed={index === activeDayIndex}
              onClick={() =>
                setActiveDaySelection({ planId: mapPlan.plan_id, index })
              }
            >
              第 {index + 1} 日 · {day.local_date} ·{" "}
              {day.routes[0]?.mode === "walking" ? "虚线" : "实线"}
            </button>
          ))}
        </div>
      )}
      <div className="f012-map-legend" aria-label="地图标记图例">
        <span>
          <i className="f012-map-marker f012-map-marker--accommodation">住</i>
          住宿
        </span>
        <span>
          <i className="f012-map-marker f012-map-marker--visit">游</i>
          景点
        </span>
        <span>
          <i className="f012-map-marker f012-map-marker--visit f012-map-marker--selected">
            游<b>✓</b>
          </i>
          已选中
        </span>
      </div>
      <div
        ref={container}
        className="f009-map-canvas"
        aria-hidden={status !== "ready"}
      />
      {status === "ready" && searchCenter && onSearchArea && (
        <button
          type="button"
          className="f009-search-area"
          onClick={() => {
            onSearchArea(searchCenter);
            setSearchCenter(null);
          }}
        >
          在此区域搜索
        </button>
      )}
      {status !== "ready" && (
        <div className="f009-map-fallback" role="status">
          <strong>
            {status === "loading" ? "地图加载中" : "地图当前不可用"}
          </strong>
          <p>
            {failureReason === "configuration"
              ? "缺少 frontend/.env.local 中的 VITE_AMAP_JS_KEY 与 VITE_AMAP_JS_SECURITY_CODE；后端 AMAP_API_KEY 不能代替。"
              : "地图脚本未能加载或渲染。"}
          </p>
          <p>列表仍可完成地点选择、预检、冲突处理和计划阅读。</p>
          {status === "unavailable" && (
            <button
              type="button"
              onClick={() => setAttempt((value) => value + 1)}
            >
              重试加载地图
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function markerContent(
  role: "accommodation" | "visit",
  text: string,
  selected: boolean,
): string {
  const classes = [
    "f012-map-marker",
    `f012-map-marker--${role}`,
    selected ? "f012-map-marker--selected" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return `<span class="${classes}" data-marker-role="${role}" data-selected="${selected}"><span>${text}</span>${selected ? '<b aria-hidden="true">✓</b>' : ""}</span>`;
}

function colorFor(token: string): string {
  return (
    {
      "day-1": "#bd3a2b",
      "day-2": "#157565",
      "day-3": "#126f94",
      "day-4": "#9b6716",
      "day-5": "#684a91",
      "day-6": "#9a4e78",
      "day-7": "#3f5d33",
    }[token] ?? "#132c33"
  );
}
