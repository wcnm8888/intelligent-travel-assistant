import type {
  AMapInstance,
  AMapNamespace,
  F009MapLoader,
} from "./f009MapLoader";

class SyntheticMarker {
  readonly options: Record<string, unknown>;
  click: (() => void) | null = null;

  constructor(options: Record<string, unknown>) {
    this.options = options;
  }

  on(event: string, listener: () => void) {
    if (event === "click") this.click = listener;
  }
}

class SyntheticPolyline {
  readonly options: Record<string, unknown>;

  constructor(options: Record<string, unknown>) {
    this.options = options;
  }
}

class SyntheticMap implements AMapInstance {
  private readonly overlayElements = new Map<unknown, HTMLElement>();

  constructor(private readonly element: HTMLElement) {
    element.dataset.syntheticMap = "ready";
  }

  destroy() {
    this.element.replaceChildren();
    delete this.element.dataset.syntheticMap;
  }

  add(value: unknown) {
    if (value instanceof SyntheticMarker) {
      const marker = document.createElement("button");
      marker.type = "button";
      marker.className = "f010-synthetic-marker";
      marker.textContent = String(value.options.title ?? "地点");
      marker.setAttribute("aria-label", `地图标记：${marker.textContent}`);
      marker.addEventListener("click", () => value.click?.());
      this.element.append(marker);
      this.overlayElements.set(value, marker);
      return;
    }
    if (value instanceof SyntheticPolyline) {
      const route = document.createElement("span");
      route.className = "f010-synthetic-polyline";
      route.textContent =
        value.options.strokeStyle === "dashed"
          ? "步行虚线路线"
          : "公交实线路线";
      this.element.append(route);
      this.overlayElements.set(value, route);
    }
  }

  remove(value: unknown | unknown[]) {
    const values = Array.isArray(value) ? value : [value];
    for (const overlay of values) {
      this.overlayElements.get(overlay)?.remove();
      this.overlayElements.delete(overlay);
    }
  }

  setFitView() {}
  on() {}
  getCenter() {
    return { getLng: () => 120.16, getLat: () => 30.25 };
  }
}

const namespace = {
  Map: SyntheticMap,
  Marker: SyntheticMarker,
  Polyline: SyntheticPolyline,
  InfoWindow: class {
    private readonly content: string;

    constructor(options: Record<string, unknown>) {
      this.content = String(options.content ?? "地点");
    }

    open(map: SyntheticMap) {
      const status = document.createElement("span");
      status.className = "sr-only";
      status.setAttribute("role", "status");
      status.textContent = `已打开 ${this.content}`;
      (map as unknown as { element: HTMLElement }).element?.append(status);
    }
  },
} as unknown as AMapNamespace;

export const f010SyntheticMapLoader: F009MapLoader = async () => namespace;
