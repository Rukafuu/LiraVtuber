import { useEffect } from "react";
import "./App.css";
import { MainLayout } from "./views/layouts/MainLayout";

function App() {
  useEffect(() => {
    // Aplica o tema salvo assim que o App inicializa
    const savedColor = localStorage.getItem("lira_accent_color") || "#a855f7";
  const savedOpacity = localStorage.getItem("lira_bg_opacity") || "1.0";

  document.documentElement.style.setProperty('--purple-neon', savedColor);
  document.documentElement.style.setProperty('--purple-glow', savedColor);
  document.documentElement.style.setProperty('--purple-dark', `${savedColor}40`);
  document.documentElement.style.setProperty('--bg-opacity', savedOpacity);
  }, []);

  return <MainLayout />;
}

export default App;
