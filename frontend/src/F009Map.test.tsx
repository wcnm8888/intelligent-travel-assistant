import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { F009Map } from "./F009Map";
import type { MapPlanDto, PoiOptionDto } from "./f009Api";
import type {
  AMapInstance,
  AMapNamespace,
  F009MapLoader,
} from "./f009MapLoader";

describe("F009Map governed viewport search", () => {
  it("renders distinct accommodation, visit and selected marker semantics", async () => {
    const markerOptions: Array<Record<string, unknown>> = [];
    class FakeMap implements AMapInstance {
      destroy() {}
      add() {}
      setFitView() {}
      on() {}
      getCenter() {
        return { getLng: () => 120.17, getLat: () => 30.26 };
      }
    }
    const namespace = {
      Map: FakeMap,
      Marker: class {
        constructor(options: Record<string, unknown>) {
          markerOptions.push(options);
        }
        on() {}
      },
      Polyline: class {},
      InfoWindow: class {
        open() {}
      },
    } as unknown as AMapNamespace;
    const accommodation = {
      location_id: "lodging-id",
      provider: "amap",
      provider_place_id: "provider-lodging",
      name: "湖滨酒店",
      address: "杭州",
      city_adcode: "330100",
      district_adcode: "330102",
      category_code: "hotel",
      category_label: "住宿服务",
      coordinate_gcj02: { longitude: 120.16, latitude: 30.25 },
      purpose: "accommodation",
      scope_kind: "point",
      confirmation_status: "verified",
    } satisfies PoiOptionDto;
    const visit = {
      ...accommodation,
      location_id: "visit-id",
      provider_place_id: "provider-visit",
      name: "西湖",
      category_code: "scenic_area",
      category_label: "风景名胜",
      purpose: "visit",
      coordinate_gcj02: { longitude: 120.17, latitude: 30.26 },
    } satisfies PoiOptionDto;

    render(
      <F009Map
        options={[accommodation, visit]}
        optionRoles={
          new Map([
            [accommodation.location_id, "accommodation"],
            [visit.location_id, "visit"],
          ])
        }
        selectedLocationIds={new Set([visit.location_id])}
        mapPlan={null}
        onSelect={vi.fn()}
        loader={async () => namespace}
      />,
    );

    await waitFor(() => expect(markerOptions).toHaveLength(2));
    expect(String(markerOptions[0].content)).toContain(
      "f012-map-marker--accommodation",
    );
    expect(String(markerOptions[0].content)).toContain(">住<");
    expect(String(markerOptions[1].content)).toContain(
      "f012-map-marker--visit",
    );
    expect(String(markerOptions[1].content)).toContain(">游<");
    expect(String(markerOptions[1].content)).toContain(
      "f012-map-marker--selected",
    );
    expect(String(markerOptions[1].content)).toContain("✓");
    const legend = screen.getByLabelText("地图标记图例");
    expect(legend).toHaveTextContent("住宿");
    expect(legend).toHaveTextContent("景点");
    expect(legend).toHaveTextContent("已选中");
  });

  it("explains the exact local configuration boundary", async () => {
    render(
      <F009Map
        options={[]}
        optionRoles={new Map()}
        selectedLocationIds={new Set()}
        mapPlan={null}
        onSelect={vi.fn()}
        loader={() =>
          Promise.reject(new Error("amap_js_configuration_missing"))
        }
      />,
    );

    expect(await screen.findByText(/frontend\/.env\.local/)).toHaveTextContent(
      "VITE_AMAP_JS_KEY",
    );
    expect(screen.getByText(/AMAP_API_KEY 不能代替/)).toBeInTheDocument();
    expect(screen.getByText(/列表仍可完成地点选择/)).toBeInTheDocument();
  });

  it("waits for a stable viewport and only searches after explicit user action", async () => {
    let moveEnd: (() => void) | undefined;
    class FakeMap implements AMapInstance {
      destroy() {}
      add() {}
      setFitView() {}
      on(event: string, listener: () => void) {
        if (event === "moveend") moveEnd = listener;
      }
      getCenter() {
        return { getLng: () => 120.17, getLat: () => 30.26 };
      }
    }
    const namespace = {
      Map: FakeMap,
      Marker: class {
        on() {}
      },
      Polyline: class {},
      InfoWindow: class {
        open() {}
      },
    } as unknown as AMapNamespace;
    const loader: F009MapLoader = async () => namespace;
    const onSearchArea = vi.fn();
    render(
      <F009Map
        options={[]}
        optionRoles={new Map()}
        selectedLocationIds={new Set()}
        mapPlan={null}
        onSelect={vi.fn()}
        onSearchArea={onSearchArea}
        loader={loader}
      />,
    );
    await waitFor(() => expect(moveEnd).toBeTypeOf("function"));

    act(() => moveEnd?.());
    expect(
      screen.queryByRole("button", { name: "在此区域搜索" }),
    ).not.toBeInTheDocument();
    const button = await screen.findByRole(
      "button",
      { name: "在此区域搜索" },
      { timeout: 1_000 },
    );
    expect(onSearchArea).not.toHaveBeenCalled();

    await userEvent.click(button);
    expect(onSearchArea).toHaveBeenCalledWith({
      longitude: 120.17,
      latitude: 30.26,
    });
  });

  it("binds marker identity, InfoWindow and final polyline to the same map plan", async () => {
    const markerCallbacks = new Map<string, () => void>();
    const polylines: Array<Record<string, unknown>> = [];
    const onSelect = vi.fn();
    const infoOpen = vi.fn();
    class FakeMap implements AMapInstance {
      destroy() {}
      add() {}
      setFitView() {}
      on() {}
      getCenter() {
        return { getLng: () => 120.17, getLat: () => 30.26 };
      }
    }
    class FakeMarker {
      title: string;
      constructor(options: Record<string, unknown>) {
        this.title = String(options.title);
      }
      on(event: string, listener: () => void) {
        if (event === "click") markerCallbacks.set(this.title, listener);
      }
    }
    const namespace = {
      Map: FakeMap,
      Marker: FakeMarker,
      Polyline: class {
        constructor(options: Record<string, unknown>) {
          polylines.push(options);
        }
      },
      InfoWindow: class {
        open(map: AMapInstance, position: [number, number]) {
          infoOpen(map, position);
        }
      },
    } as unknown as AMapNamespace;
    const locationId = "70000000-0000-4000-8000-000000000004";
    const lodgingId = "70000000-0000-4000-8000-000000000003";
    const point = { longitude: 120.16, latitude: 30.25 };
    const mapPlan: MapPlanDto = {
      map_version: "1",
      job_id: "70000000-0000-4000-8000-000000000001",
      plan_id: "70000000-0000-4000-8000-000000000002",
      coordinate_system: "gcj02",
      accommodation: {
        location_id: lodgingId,
        name: "住宿",
        coordinate: point,
        visit_order: null,
      },
      days: [
        {
          local_date: "2026-10-01",
          color_token: "day-1",
          markers: [
            {
              location_id: locationId,
              name: "西湖",
              coordinate: { longitude: 120.17, latitude: 30.26 },
              visit_order: 1,
            },
          ],
          routes: [
            {
              route_id: "70000000-0000-4000-8000-000000000005",
              origin_location_id: lodgingId,
              destination_location_id: locationId,
              mode: "walking",
              distance_meters: 1500,
              duration_minutes: 20,
              points: [point, { longitude: 120.17, latitude: 30.26 }],
            },
          ],
        },
      ],
      warnings: [],
    };
    const options: PoiOptionDto[] = [];

    render(
      <F009Map
        options={options}
        optionRoles={new Map()}
        selectedLocationIds={new Set([locationId])}
        mapPlan={mapPlan}
        onSelect={onSelect}
        loader={async () => namespace}
      />,
    );

    await waitFor(() =>
      expect(markerCallbacks.get("西湖")).toBeTypeOf("function"),
    );
    act(() => markerCallbacks.get("西湖")?.());
    expect(onSelect).toHaveBeenCalledWith(locationId);
    expect(infoOpen).toHaveBeenCalled();
    expect(polylines[0]).toMatchObject({
      strokeStyle: "dashed",
      showDir: true,
    });
    expect(
      screen.getByRole("button", { name: /第 1 日 · 2026-10-01 · 虚线/ }),
    ).toBeInTheDocument();
  });

  it("keeps one map instance and replaces overlays when the active day changes", async () => {
    const mapConstructed = vi.fn();
    const removed: unknown[][] = [];
    const markerTitles: string[] = [];
    const polylineColors: string[] = [];
    class FakeMap implements AMapInstance {
      constructor() {
        mapConstructed();
      }
      destroy() {}
      add() {}
      remove(value: unknown | unknown[]) {
        removed.push(Array.isArray(value) ? value : [value]);
      }
      setFitView() {}
      on() {}
      getCenter() {
        return { getLng: () => 120.17, getLat: () => 30.26 };
      }
    }
    const namespace = {
      Map: FakeMap,
      Marker: class {
        constructor(options: Record<string, unknown>) {
          markerTitles.push(String(options.title));
        }
        on() {}
      },
      Polyline: class {
        constructor(options: Record<string, unknown>) {
          polylineColors.push(String(options.strokeColor));
        }
      },
      InfoWindow: class {
        open() {}
      },
    } as unknown as AMapNamespace;
    const lodgingId = "70000000-0000-4000-8000-000000000031";
    const dayOneId = "70000000-0000-4000-8000-000000000032";
    const dayTwoId = "70000000-0000-4000-8000-000000000033";
    const point = { longitude: 120.16, latitude: 30.25 };
    const route = (routeId: string, origin: string, destination: string) => ({
      route_id: routeId,
      origin_location_id: origin,
      destination_location_id: destination,
      mode: "walking" as const,
      distance_meters: 600,
      duration_minutes: 9,
      points: [point, { longitude: 120.17, latitude: 30.26 }],
    });
    const mapPlan: MapPlanDto = {
      map_version: "1",
      job_id: "70000000-0000-4000-8000-000000000034",
      plan_id: "70000000-0000-4000-8000-000000000035",
      coordinate_system: "gcj02",
      accommodation: {
        location_id: lodgingId,
        name: "住宿",
        coordinate: point,
        visit_order: null,
      },
      days: [
        {
          local_date: "2026-10-01",
          color_token: "day-1",
          markers: [
            {
              location_id: dayOneId,
              name: "第一天景点",
              coordinate: point,
              visit_order: 1,
            },
          ],
          routes: [
            route("70000000-0000-4000-8000-000000000036", lodgingId, dayOneId),
          ],
        },
        {
          local_date: "2026-10-02",
          color_token: "day-2",
          markers: [
            {
              location_id: dayTwoId,
              name: "第二天景点",
              coordinate: point,
              visit_order: 1,
            },
          ],
          routes: [
            route("70000000-0000-4000-8000-000000000037", lodgingId, dayTwoId),
          ],
        },
      ],
      warnings: [],
    };

    render(
      <F009Map
        options={[]}
        optionRoles={new Map()}
        selectedLocationIds={new Set()}
        mapPlan={mapPlan}
        onSelect={vi.fn()}
        loader={async () => namespace}
      />,
    );

    await waitFor(() => expect(markerTitles).toContain("第一天景点"));
    await userEvent.click(
      screen.getByRole("button", { name: /第 2 日 · 2026-10-02/ }),
    );
    await waitFor(() => expect(markerTitles).toContain("第二天景点"));
    expect(mapConstructed).toHaveBeenCalledTimes(1);
    expect(removed.length).toBeGreaterThan(0);
    expect(polylineColors).toEqual(["#bd3a2b", "#157565"]);
    expect(markerTitles.slice(-2)).toEqual(["住宿", "第二天景点"]);
  });
});
