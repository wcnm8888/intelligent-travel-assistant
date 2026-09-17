import { createRoot } from "react-dom/client";

import { App } from "./App";
import { f010SyntheticMapLoader } from "./f010SyntheticMapLoader";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Frontend root element is missing");
}

const syntheticMap = import.meta.env.VITE_F010_SYNTHETIC_MAP === "1";

createRoot(rootElement).render(
  <App
    f009MapLoader={syntheticMap ? f010SyntheticMapLoader : undefined}
    syntheticSelectionMap={syntheticMap}
  />,
);
