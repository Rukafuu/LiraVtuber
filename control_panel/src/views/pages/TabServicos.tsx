import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiController } from "../../controllers/api";
import type { ServiceRunState, ServiceStatus } from "../../models/types";
import { AlertCircle, Loader2, Play, Power, RefreshCw, Square } from "lucide-react";
import { WhatsAppSessionPanel } from "../components/WhatsAppSessionPanel";

const STATE_STYLES: Record<
  ServiceRunState,
  { dot: string; labelKey: string; border: string }
> = {
  stopped: {
    dot: "bg-gray-500",
    labelKey: "servicos.state_stopped",
    border: "border-gray-600/40",
  },
  starting: {
    dot: "bg-yellow-400 animate-pulse",
    labelKey: "servicos.state_starting",
    border: "border-yellow-500/40",
  },
  running: {
    dot: "bg-green-500 shadow-[0_0_8px_#22c55e]",
    labelKey: "servicos.state_running",
    border: "border-green-500/40",
  },
  degraded: {
    dot: "bg-amber-400 animate-pulse",
    labelKey: "servicos.state_degraded",
    border: "border-amber-500/40",
  },
  error: {
    dot: "bg-red-500 shadow-[0_0_8px_#ef4444]",
    labelKey: "servicos.state_error",
    border: "border-red-500/40",
  },
};

const SERVICE_ICONS: Record<string, string> = {
  discord: "🎮",
  whatsapp_api: "🐍",
  whatsapp_bridge: "💬",
  mcp_gateway: "🔌",
};

function formatUptime(sec: number | null): string {
  if (sec == null) return "—";
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  if (m < 60) return `${m}m ${s}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function connectionHint(
  svc: ServiceStatus,
  t: (k: string) => string
): string | null {
  if (!svc.connection) return null;
  const map: Record<string, string> = {
    connected: t("servicos.conn_connected"),
    awaiting_qr: t("servicos.conn_qr"),
    awaiting_pairing: t("servicos.conn_pairing"),
    connecting: t("servicos.conn_connecting"),
    starting: t("servicos.conn_starting"),
  };
  return map[svc.connection] ?? svc.connection;
}

export function TabServicos() {
  const { t } = useTranslation();
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const bridgeSvc = services.find((s) => s.id === "whatsapp_bridge");

  const refresh = useCallback(async () => {
    const data = await ApiController.getServices();
    setServices(data.services);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [refresh]);

  const runAction = async (id: string, action: "start" | "stop") => {
    setActionId(id);
    setFlash(null);
    const res =
      action === "start"
        ? await ApiController.startService(id)
        : await ApiController.stopService(id);
    if (res.status !== "ok") {
      setFlash(res.message || t("servicos.action_failed"));
    }
    await refresh();
    setActionId(null);
  };

  const startAllWhatsApp = async () => {
    setActionId("whatsapp_bundle");
    await ApiController.startService("whatsapp_api");
    await new Promise((r) => setTimeout(r, 800));
    await ApiController.startService("whatsapp_bridge");
    await refresh();
    setActionId(null);
  };

  const stopAllWhatsApp = async () => {
    setActionId("whatsapp_bundle");
    await ApiController.stopService("whatsapp_bridge");
    await ApiController.stopService("whatsapp_api");
    await refresh();
    setActionId(null);
  };

  const resetWhatsAppSession = async () => {
    setActionId("whatsapp_reset");
    setFlash(null);
    const res = await ApiController.resetWhatsAppSession();
    if (res.status !== "ok") {
      setFlash(res.message || t("servicos.action_failed"));
    } else {
      setFlash(res.message || t("servicos.wa_reset_ok"));
    }
    await refresh();
    setActionId(null);
  };

  return (
    <div className="flex flex-col gap-6 h-full overflow-y-auto custom-scrollbar pr-2 pb-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-wide">
            {t("servicos.titulo")}
          </h2>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            {t("servicos.subtitulo")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => refresh()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border-strong)] text-sm text-[var(--text-secondary)] hover:text-white hover:border-[var(--purple-neon)] transition-colors"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            {t("servicos.refresh")}
          </button>
          <button
            type="button"
            disabled={!!actionId}
            onClick={startAllWhatsApp}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[rgba(34,197,94,0.15)] border border-green-500/40 text-green-300 text-sm font-bold hover:bg-[rgba(34,197,94,0.25)] disabled:opacity-50"
          >
            <Play size={16} />
            {t("servicos.whatsapp_start_all")}
          </button>
          <button
            type="button"
            disabled={!!actionId}
            onClick={stopAllWhatsApp}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[rgba(239,68,68,0.1)] border border-red-500/40 text-red-300 text-sm hover:bg-[rgba(239,68,68,0.2)] disabled:opacity-50"
          >
            <Square size={16} />
            {t("servicos.whatsapp_stop_all")}
          </button>
          <button
            type="button"
            disabled={!!actionId}
            onClick={resetWhatsAppSession}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-amber-500/40 text-amber-200 text-sm hover:bg-amber-500/10 disabled:opacity-50"
            title={t("servicos.wa_reset_hint")}
          >
            <Power size={16} />
            {t("servicos.wa_reset")}
          </button>
        </div>
      </div>

      {flash && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 text-sm">
          <AlertCircle size={18} />
          {flash}
        </div>
      )}

      <WhatsAppSessionPanel bridge={bridgeSvc} />

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {services.map((svc) => {
          const style = STATE_STYLES[svc.state] ?? STATE_STYLES.stopped;
          const busy = actionId === svc.id || actionId === "whatsapp_bundle";
          const conn = connectionHint(svc, t);
          const isRunning = svc.state === "running" || svc.state === "degraded" || svc.state === "starting";

          return (
            <div
              key={svc.id}
              className={`glass-panel rounded-2xl p-5 border ${style.border} flex flex-col gap-4`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="text-3xl">{SERVICE_ICONS[svc.id] ?? "⚙️"}</span>
                  <div>
                    <h3 className="text-lg font-bold text-white">{svc.label}</h3>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className={`w-2 h-2 rounded-full ${style.dot}`} />
                      <span className="text-xs font-mono uppercase tracking-wider text-[var(--text-secondary)]">
                        {t(style.labelKey)}
                      </span>
                      {svc.managed && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-[var(--purple-dark)] text-[var(--purple-neon)] border border-[var(--purple-neon)]/30">
                          {t("servicos.managed")}
                        </span>
                      )}
                      {svc.external && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">
                          {t("servicos.external")}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  {!isRunning ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => runAction(svc.id, "start")}
                      className="p-2.5 rounded-lg bg-green-500/20 border border-green-500/50 text-green-300 hover:bg-green-500/30 disabled:opacity-40"
                      title={t("servicos.start")}
                    >
                      {busy ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => runAction(svc.id, "stop")}
                      className="p-2.5 rounded-lg bg-red-500/15 border border-red-500/40 text-red-300 hover:bg-red-500/25 disabled:opacity-40"
                      title={t("servicos.stop")}
                    >
                      {busy ? <Loader2 size={18} className="animate-spin" /> : <Power size={18} />}
                    </button>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                <div className="bg-black/30 rounded-lg px-3 py-2 border border-white/5">
                  <span className="text-[var(--text-muted)] block">{t("servicos.pid")}</span>
                  <span className="text-white">{svc.pid ?? "—"}</span>
                </div>
                <div className="bg-black/30 rounded-lg px-3 py-2 border border-white/5">
                  <span className="text-[var(--text-muted)] block">{t("servicos.uptime")}</span>
                  <span className="text-white">{formatUptime(svc.uptime_sec)}</span>
                </div>
                <div className="bg-black/30 rounded-lg px-3 py-2 border border-white/5">
                  <span className="text-[var(--text-muted)] block">{t("servicos.http")}</span>
                  <span className="text-white">
                    {svc.health_http == null ? "—" : svc.health_http ? "OK" : t("servicos.off")}
                  </span>
                </div>
                <div className="bg-black/30 rounded-lg px-3 py-2 border border-white/5">
                  <span className="text-[var(--text-muted)] block">{t("servicos.session")}</span>
                  <span className="text-white truncate">{conn ?? "—"}</span>
                </div>
              </div>

              {svc.last_error && (
                <div className="flex gap-2 items-start px-3 py-2 rounded-lg bg-red-950/40 border border-red-500/25 text-red-200 text-xs font-mono">
                  <AlertCircle size={14} className="shrink-0 mt-0.5" />
                  <span className="break-all">{svc.last_error}</span>
                </div>
              )}

              <div className="flex-1 min-h-[120px] max-h-[180px] overflow-y-auto custom-scrollbar rounded-lg bg-black/40 border border-white/5 p-3 font-mono text-[11px] leading-relaxed">
                {svc.log_tail.length === 0 ? (
                  <span className="text-[var(--text-muted)]">{t("servicos.no_logs")}</span>
                ) : (
                  svc.log_tail.map((line, i) => (
                    <div
                      key={`${line.ts}-${i}`}
                      className={
                        line.stream === "stderr"
                          ? "text-red-300/90"
                          : line.stream === "system"
                            ? "text-[var(--cyan-neon)]/80"
                            : "text-gray-400"
                      }
                    >
                      <span className="text-[var(--text-muted)] mr-2">[{line.ts}]</span>
                      {line.line}
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {services.length === 0 && !loading && (
        <p className="text-center text-[var(--text-muted)] py-12">
          {t("servicos.api_offline")}
        </p>
      )}
    </div>
  );
}