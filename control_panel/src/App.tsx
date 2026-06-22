import { useEffect } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import "./App.css";
import { MainLayout } from "./views/layouts/MainLayout";
import { RadialMenu } from "./radial/components/RadialMenu";
import { SettingsPanel } from "./radial/components/SettingsPanel";
import "./radial/RadialApp.css";

function getWindowLabel() {
  const previewLabel = new URLSearchParams(window.location.search).get("window");
  if (previewLabel) return previewLabel;

  try {
    return getCurrentWindow().label;
  } catch {
    return "main";
  }
}

function App() {
  const windowLabel = getWindowLabel();

  useEffect(() => {
    if (windowLabel !== "main") return;

    const savedColor = localStorage.getItem("lira_accent_color") || "#a855f7";
    let savedOpacity = parseFloat(localStorage.getItem("lira_bg_opacity") || "1");
    if (!Number.isFinite(savedOpacity) || savedOpacity < 0.35) {
      savedOpacity = 1;
      localStorage.setItem("lira_bg_opacity", "1");
    }

    document.documentElement.style.setProperty("--purple-neon", savedColor);
    document.documentElement.style.setProperty("--purple-glow", savedColor);
    document.documentElement.style.setProperty("--purple-dark", `${savedColor}40`);
    document.documentElement.style.setProperty("--bg-opacity", String(savedOpacity));
  }, [windowLabel]);

  if (windowLabel === "radial-settings") {
    return <SettingsPanel />;
  }

  if (windowLabel === "radial") {
    return (
      <div className="app-wrapper">
        <RadialMenu />
      </div>
    );
  }

  return <MainLayout />;
}

export default App;