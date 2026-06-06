/** Chamadas seguras para o painel MCP → POST /api/mcp/call */
export type McpTestPreset = {
  id: string;
  server: string;
  tool: string;
  arguments: Record<string, unknown>;
  labelKey: string;
  /** Primeira subida do subprocesso pode demorar */
  slow?: boolean;
};

export const MCP_TEST_PRESETS: McpTestPreset[] = [
  {
    id: "tavily",
    server: "tavily",
    tool: "tavily_search",
    arguments: { query: "Lira VTuber noticias hoje" },
    labelKey: "mcp.test_tavily",
  },
  {
    id: "github",
    server: "github",
    tool: "search_repositories",
    arguments: { query: "vtuber assistant language:python" },
    labelKey: "mcp.test_github",
  },
  {
    id: "filesystem",
    server: "filesystem",
    tool: "read_text_file",
    arguments: { path: "data/mcp_allowlist.json" },
    labelKey: "mcp.test_filesystem",
  },
  {
    id: "memory",
    server: "memory",
    tool: "read_graph",
    arguments: {},
    labelKey: "mcp.test_memory",
  },
  {
    id: "puppeteer",
    server: "puppeteer",
    tool: "puppeteer_navigate",
    arguments: { url: "https://example.com" },
    labelKey: "mcp.test_puppeteer",
    slow: true,
  },
];