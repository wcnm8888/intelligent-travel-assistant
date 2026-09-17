import type { PoiOptionDto } from "./f009Api";

export interface MapFocusRequest {
  locationId: string;
  sequence: number;
}

export interface VisitCollection {
  visible: PoiOptionDto[];
  catalog: PoiOptionDto[];
}

type VisitUpdate =
  | PoiOptionDto[]
  | ((current: PoiOptionDto[]) => PoiOptionDto[])
  | { reset: true };

// Remember discovery order for the whole session, independent of search order.
export function visitCollectionReducer(
  state: VisitCollection,
  update: VisitUpdate,
): VisitCollection {
  if (typeof update === "object" && "reset" in update) {
    return { visible: [], catalog: [] };
  }
  const visible = typeof update === "function" ? update(state.visible) : update;
  const catalog = new Map(
    state.catalog.map((item) => [item.location_id, item]),
  );
  for (const item of visible) catalog.set(item.location_id, item);
  return { visible, catalog: [...catalog.values()] };
}

export function advisorPreferenceLabels(preferences: {
  walking_tolerance: "low" | "medium" | "high" | null;
  crowd_tolerance: "low" | "medium" | "high" | null;
  day_start: string | null;
  food_preferences: string[];
  budget_flexibility: "fixed" | "small" | "flexible" | null;
  party_notes: string[];
}): string[] {
  const tolerance = { low: "低", medium: "中", high: "高" };
  const budget = {
    fixed: "预算固定",
    small: "预算可小幅调整",
    flexible: "预算较灵活",
  };
  return [
    preferences.walking_tolerance
      ? `步行承受度：${tolerance[preferences.walking_tolerance]}`
      : null,
    preferences.crowd_tolerance
      ? `拥挤承受度：${tolerance[preferences.crowd_tolerance]}`
      : null,
    preferences.day_start
      ? `${preferences.day_start.slice(0, 5)} 后出发`
      : null,
    preferences.budget_flexibility
      ? budget[preferences.budget_flexibility]
      : null,
    ...preferences.food_preferences.map((item) => `饮食：${item}`),
    ...preferences.party_notes.map((item) => `同行：${item}`),
  ].filter((value): value is string => value !== null);
}
