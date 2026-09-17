import AMapLoader from "@amap/amap-jsapi-loader";

export interface AMapInstance {
  destroy(): void;
  add(value: unknown): void;
  remove?(value: unknown | unknown[]): void;
  setFitView(): void;
  setCenter?(position: [number, number]): void;
  setZoom?(zoom: number): void;
  on(event: string, listener: () => void): void;
  getCenter(): { getLng(): number; getLat(): number };
}

export interface AMapNamespace {
  Map: new (
    element: HTMLElement,
    options: Record<string, unknown>,
  ) => AMapInstance;
  Marker: new (options: Record<string, unknown>) => {
    on(event: string, listener: () => void): void;
  };
  Polyline: new (options: Record<string, unknown>) => unknown;
  InfoWindow: new (options: Record<string, unknown>) => {
    open(map: AMapInstance, position: [number, number]): void;
  };
}

export type F009MapLoader = () => Promise<AMapNamespace>;

declare global {
  interface Window {
    _AMapSecurityConfig?: { securityJsCode: string };
  }
}

export function officialF009MapLoader(): Promise<AMapNamespace> {
  const key = import.meta.env.VITE_AMAP_JS_KEY as string | undefined;
  const securityJsCode = import.meta.env.VITE_AMAP_JS_SECURITY_CODE as
    string | undefined;
  if (!key || !securityJsCode) {
    return Promise.reject(new Error("amap_js_configuration_missing"));
  }
  window._AMapSecurityConfig = { securityJsCode };
  return AMapLoader.load({
    key,
    version: "2.0",
    plugins: [],
  }) as Promise<AMapNamespace>;
}
