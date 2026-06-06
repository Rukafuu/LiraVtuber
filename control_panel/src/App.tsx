import { useEffect } from "react";
import "./App.css";
import { MainLayout } from "./views/layouts/MainLayout";

function App() {
  useEffect(() => {
    // Aplica o tema salvo assim que o App inicializa
    const savedColor = localStorage.getItem("lira_accent_color") || "#a855f7";
  let savedOpacity = parseFloat(localStorage.getItem("lira_bg_opacity") || "1");
  if (!Number.isFinite(savedOpacity) || savedOpacity < 0.35) {
    savedOpacity = 1;
    localStorage.setItem("lira_bg_opacity", "1");
  }

  document.documentElement.style.setProperty('--purple-neon', savedColor);
  document.documentElement.style.setProperty('--purple-glow', savedColor);
  document.documentElement.style.setProperty('--purple-dark', `${savedColor}40`);
  document.documentElement.style.setProperty('--bg-opacity', String(savedOpacity));
  }, []);

  return <MainLayout />;
}

export default App;
