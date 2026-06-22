import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiController } from "../../controllers/api";
import { Loader2, RefreshCw, Plug, Shield, Wrench, FlaskConical } from "lucide-react";
import { MCP_TEST_PRESETS, type McpTestPreset } from "./mcpTestPresets";

type McpServerRow = {
  id: string;
  label: string;
  enabled: boolean;
  planned?: boolean;
  running?: boolean;
};

type McpTool = {
  name: string;
  qualified: string;
  description?: string;
};

export function TabMCP({ active = true }: { active?: boolean }) {
  const { t } = useTranslation();
  const [servers, setServers] = useState<McpServerRow[]>([]);
  const [allowlist, setAllowlist] = useState<string[]>([]);
  const [tools, setTools] = useState<McpTool[]>([]);
  const [selectedServer, setSelectedServer] = useState<string>("tavily");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [gatewayOk, setGatewayOk] = useState<boolean | null>(null);
  const [newRule, setNewRule] = useState("");
  const [flash, setFlash] = useState<string | null>(null);
  const [testRunning, setTestRunning] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{
    presetId: string;
    ok: boolean;
    ms: number;
    text: string;
  } | null>(null);

  const refresh = useCallback(async () => {
    const [st, srv, al] = await Promise.all([
      ApiController.getMcpStatus(),
      ApiController.getMcpServers(),
      ApiController.getMcpAllowlist(),
    ]);
    setGatewayOk(!st?.status || st.status !== "error");
    setServers(srv?.servers ?? []);
    setAllowlist(al?.allowed ?? []);
    setLoading(false);
  }, []);

  const loadTools = useCallback(async (serverId: string, forceRefresh = false) => {
    setBusy(true);
    const data = await ApiController.getMcpTools(serverId, forceRefresh);
    setTools(data?.tools ?? []);
    setBusy(false);
  }, []);

  useEffect(() => {
    if (!active) return;
    refresh();
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, [refresh, active]);

  useEffect(() => {
    if (!active || !selectedServer) return;
    loadTools(selectedServer, false);
  }, [selectedServer, loadTools, active]);

  const toggleServer = async (id: string, enabled: boolean) => {
    setBusy(true);
    await ApiController.setMcpServerEnabled(id, enabled);
    await refresh();
    if (enabled) await loadTools(id, true);
    setBusy(false);
  };

  const saveAllowlist = async (next: string[]) => {
    setBusy(true);
    await ApiController.setMcpAllowlist(next);
    setAllowlist(next);
    setBusy(false);
    setFlash(t("mcp.allowlist_saved"));
    setTimeout(() => setFlash(null), 2000);
  };

  const addRule = () => {
    const rule = newRule.trim();
    if (!rule || allowlist.includes(rule)) return;
    saveAllowlist([...allowlist, rule]);
    setNewRule("");
  };

  const removeRule = (rule: string) => {
    saveAllowlist(allowlist.filter((r) => r !== rule));
  };

  const toggleToolInAllowlist = (qualified: string) => {
    if (allowlist.includes(qualified)) {
      removeRule(qualified);
      return;
    }
    const server = qualified.split("/")[0];
    saveAllowlist([...allowlist.filter((r) => r !== `${server}/*`), qualified]);
  };

  const isToolAllowed = (qualified: string) => {
    const [server] = qualified.split("/");
    if (allowlist.includes(qualified)) return true;
    return allowlist.includes(`${server}/*`);
  };

  const isServerEnabled = (serverId: string) =>
    servers.some((s) => s.id === serverId && s.enabled);

  const runMcpTest = async (preset: McpTestPreset) => {
    if (!gatewayOk || !isServerEnabled(preset.server)) return;
    setTestRunning(preset.id);
    setTestResult(null);
    const t0 = performance.now();
    const data = await ApiController.callMcp(preset.server, preset.tool, preset.arguments);
    const ms = Math.round(performance.now() - t0);
    let text: string;
    if (data.ok && data.result != null) {
      text = String(data.result).slice(0, 1200);
    } else {
      text = data.error || JSON.stringify(data.detail ?? data, null, 2);
    }
    setTestResult({ presetId: preset.id, ok: data.ok, ms, text });
    setTestRunning(null);
  };

  return (
    <div className="w-full h-full flex flex-col gap-4 overflow-y-auto pr-2">
      <div>
        <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-[var(--purple-neon)] to-[var(--cyan-neon)]">
          {t("mcp.titulo")}
        </h2>
        <p className="text-sm text-[var(--text-secondary)] mt-1">{t("mcp.subtitulo")}</p>
      </div>

      {flash && (
        <div className="text-sm text-green-400 border border-green-500/30 rounded-lg px-3 py-2">{flash}</div>
      )}

      <div className="flex items-center gap-3 text-sm">
        <Plug size={16} className={gatewayOk ? "text-green-400" : "text-red-400"} />
        <span>
          {gatewayOk === null
            ? "…"
            : gatewayOk
              ? t("mcp.gateway_online")
              : t("mcp.gateway_offline")}
        </span>
        <button
          type="button"
          onClick={() => {
            refresh();
            if (selectedServer) loadTools(selectedServer, true);
          }}
          className="ml-auto flex items-center gap-1 text-xs opacity-80 hover:opacity-100"
        >
          <RefreshCw size={14} /> {t("mcp.refresh")}
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="animate-spin text-[var(--purple-neon)]" />
        </div>
      ) : (
        <>
          <section className="grid gap-3 md:grid-cols-2">
            {servers.map((srv) => (
              <div
                key={srv.id}
                className={`rounded-xl border p-4 backdrop-blur-md ${
                  srv.enabled ? "border-[var(--purple-neon)]/40" : "border-[var(--border-strong)]"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold">{srv.label}</p>
                    <p className="text-xs text-[var(--text-secondary)] font-mono">{srv.id}</p>
                  </div>
                  <label className="flex items-center gap-2 text-xs cursor-pointer">
                    <input
                      type="checkbox"
                      checked={srv.enabled}
                      disabled={busy || srv.planned}
                      onChange={(e) => toggleServer(srv.id, e.target.checked)}
                    />
                    {srv.enabled ? "ON" : "OFF"}
                  </label>
                </div>
                <p className="text-xs mt-2 text-[var(--text-secondary)]">
                  {srv.planned && !srv.enabled
                    ? t("mcp.planned")
                    : srv.running
                      ? t("mcp.running")
                      : srv.enabled
                        ? t("mcp.stopped")
                        : "—"}
                </p>
              </div>
            ))}
          </section>

          <section className="rounded-xl border border-[var(--border-strong)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <Wrench size={16} />
              <h3 className="font-semibold">{t("mcp.tools_title")}</h3>
              <select
                value={selectedServer}
                onChange={(e) => setSelectedServer(e.target.value)}
                className="ml-auto text-sm bg-black/30 border border-[var(--border-strong)] rounded px-2 py-1"
              >
                {servers.filter((s) => s.enabled).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            {busy && <Loader2 className="animate-spin w-5 h-5 mb-2" />}
            <ul className="space-y-2 max-h-48 overflow-y-auto text-sm">
              {tools.length === 0 && <li className="text-[var(--text-secondary)]">{t("mcp.no_tools")}</li>}
              {tools.map((tool) => (
                <li
                  key={tool.qualified}
                  className="flex items-start gap-2 border-b border-white/5 pb-2"
                >
                  <input
                    type="checkbox"
                    checked={isToolAllowed(tool.qualified)}
                    onChange={() => toggleToolInAllowlist(tool.qualified)}
                  />
                  <div>
                    <span className="font-mono text-[var(--cyan-neon)]">{tool.qualified}</span>
                    {tool.description && (
                      <p className="text-xs text-[var(--text-secondary)] line-clamp-2">{tool.description}</p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-[var(--border-strong)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <Shield size={16} />
              <h3 className="font-semibold">{t("mcp.allowlist_title")}</h3>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mb-2">{t("mcp.allowlist_hint")}</p>
            <div className="flex flex-wrap gap-2 mb-3">
              {allowlist.map((rule) => (
                <span
                  key={rule}
                  className="text-xs font-mono bg-[var(--purple-neon)]/20 px-2 py-1 rounded flex items-center gap-1"
                >
                  {rule}
                  <button type="button" onClick={() => removeRule(rule)} className="opacity-70 hover:opacity-100">
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                value={newRule}
                onChange={(e) => setNewRule(e.target.value)}
                placeholder="tavily/* ou github/get_issue"
                className="flex-1 text-sm bg-black/30 border border-[var(--border-strong)] rounded px-2 py-1 font-mono"
              />
              <button
                type="button"
                onClick={addRule}
                className="text-sm px-3 py-1 rounded bg-[var(--purple-neon)]/30 hover:bg-[var(--purple-neon)]/50"
              >
                {t("mcp.add_rule")}
              </button>
            </div>
          </section>

          <section className="rounded-xl border border-[var(--border-strong)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <FlaskConical size={16} />
              <h3 className="font-semibold">{t("mcp.test_title")}</h3>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mb-3">{t("mcp.test_hint")}</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {MCP_TEST_PRESETS.map((preset) => {
                const enabled = isServerEnabled(preset.server);
                const running = testRunning === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    disabled={busy || !!testRunning || !gatewayOk || !enabled}
                    title={!enabled ? t("mcp.test_server_off") : preset.slow ? t("mcp.test_slow") : undefined}
                    onClick={() => runMcpTest(preset)}
                    className={`text-left text-sm px-3 py-2 rounded border transition-colors disabled:opacity-40 ${
                      running
                        ? "border-[var(--cyan-neon)]/60 bg-[var(--cyan-neon)]/15"
                        : "border-[var(--border-strong)] bg-black/20 hover:bg-[var(--purple-neon)]/15"
                    }`}
                  >
                    <span className="font-medium block">{t(preset.labelKey)}</span>
                    <span className="text-xs font-mono text-[var(--text-secondary)]">
                      {preset.server}/{preset.tool}
                    </span>
                  </button>
                );
              })}
            </div>
            {testResult && (
              <div
                className={`mt-3 rounded-lg border px-3 py-2 text-xs ${
                  testResult.ok
                    ? "border-green-500/30 bg-green-500/5"
                    : "border-red-500/30 bg-red-500/5"
                }`}
              >
                <p className="font-mono mb-1 text-[var(--text-secondary)]">
                  {testResult.ok ? "✓" : "✗"} {testResult.presetId} · {testResult.ms} ms
                </p>
                <pre className="whitespace-pre-wrap max-h-48 overflow-y-auto text-[var(--text-secondary)]">
                  {testResult.text}
                </pre>
              </div>
            )}
          </section>

          <p className="text-xs text-[var(--text-secondary)] font-mono border border-dashed border-white/10 rounded p-3">
            {t("mcp.tag_hint")}
          </p>
        </>
      )}
    </div>
  );
}