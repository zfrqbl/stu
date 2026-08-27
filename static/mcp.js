(() => {
  const MCP_VIEW_ID = "stu-mcp-view";

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }

    if (response.status === 204) {
      return null;
    }

    return response.json();
  }

  function mcpViewHtml() {
    return `
      <header class="pane-header">
        <button type="button" class="icon-button mobile-nav-toggle" @click="$store.stu.openMobileNav()" aria-label="Open navigation">≡</button>
        <div class="pane-title">
          <h1>MCP</h1>
          <p class="pane-subtitle">Model Context Protocol servers and tools.</p>
        </div>
        <div class="pane-actions">
          <button type="button" class="btn" @click="$store.stu.mcpRefresh()">Refresh</button>
        </div>
      </header>

      <div class="mcp-toolbar">
        <span class="health-pill" :class="$store.stu.healthDotClass()" x-text="$store.stu.healthLabel()"></span>
      </div>

      <template x-if="$store.stu.mcp.loading">
        <div class="mcp-grid">
          <div class="card card--primary"><p>Loading MCP servers...</p></div>
        </div>
      </template>

      <template x-if="!$store.stu.mcp.loading">
        <div class="mcp-grid">
          <template x-for="server in $store.stu.mcp.servers" :key="server.name">
            <article class="card" :class="{
              'card--safe': server.status === 'connected',
              'card--error': server.status === 'error',
              'card--muted': server.status === 'disconnected'
            }">
              <header class="card-header">
                <h3 x-text="server.name"></h3>
                <span class="mcp-status-badge" :class="'mcp-status--' + server.status" x-text="server.status"></span>
              </header>
              <p>Transport: <span x-text="server.transport"></span></p>
              <p>Tools: <span x-text="server.tools_count"></span></p>
              <template x-if="server.last_error">
                <p class="error-text" x-text="server.last_error"></p>
              </template>
            </article>
          </template>
        </div>
      </template>

      <template x-if="!$store.stu.mcp.loading && $store.stu.mcp.servers.length === 0">
        <div class="mcp-grid">
          <div class="card card--muted"><p>No MCP servers configured.</p></div>
        </div>
      </template>

      <section class="mcp-tools-section">
        <template x-for="server in $store.stu.mcp.servers" :key="'tools_' + server.name">
          <template x-if="server.status === 'connected' && server.tools_count > 0">
            <div>
              <h3 x-text="'Tools: ' + server.name" style="margin-bottom: 12px;"></h3>
              <template x-for="tool in $store.stu.mcp.tools.filter(t => t.server_name === server.name)" :key="tool.full_name">
                <div class="mcp-tool-item">
                  <div class="mcp-tool-header">
                    <span class="mcp-tool-name" x-text="tool.full_name"></span>
                    <span class="mcp-schema-badge" :class="tool.schema_valid ? 'mcp-schema-valid' : 'mcp-schema-invalid'" x-text="tool.schema_valid ? 'schema valid' : 'schema invalid'"></span>
                  </div>
                  <p class="mcp-tool-desc" x-text="tool.description"></p>
                  <template x-if="tool.schema_error">
                    <p class="error-text" x-text="tool.schema_error"></p>
                  </template>
                </div>
              </template>
            </div>
          </template>
        </template>
      </section>
    `;
  }

  function injectMcpView() {
    const main = document.getElementById("chat-pane");
    if (!main || document.getElementById(MCP_VIEW_ID)) {
      return;
    }

    const view = document.createElement("div");
    view.id = MCP_VIEW_ID;
    view.className = "view-container";
    view.setAttribute("x-show", "$store.stu.activeView === 'mcp'");
    view.setAttribute("x-cloak", "");
    view.innerHTML = mcpViewHtml();

    main.appendChild(view);
  }

  function extendStore() {
    if (!window.Alpine) {
      return;
    }

    const store = window.Alpine.store("stu");
    if (!store || store.mcp) {
      return;
    }

    store.mcp = {
      loading: false,
      servers: [],
      tools: [],
    };

    store.mcpRefresh = async function () {
      this.mcp.loading = true;
      try {
        const servers = await fetchJson(`${this.apiPrefix}/mcp/servers`);
        this.mcp.servers = servers;

        const allTools = [];
        for (const server of servers) {
          if (server.status === "connected" && server.tools_count > 0) {
            try {
              const tools = await fetchJson(`${this.apiPrefix}/mcp/servers/${server.name}/tools`);
              allTools.push(...tools);
            } catch (e) {
              // skip
            }
          }
        }
        this.mcp.tools = allTools;
      } catch (e) {
        this.pushToast("Failed to load MCP data.", "error");
      } finally {
        this.mcp.loading = false;
      }
    };

    const originalSetActiveView = store.setActiveView;
    store.setActiveView = function (view) {
      originalSetActiveView.call(this, view);
      if (view === "mcp") {
        this.mcpRefresh();
      }
    };

    if (store.activeView === "mcp") {
      store.mcpRefresh();
    }
  }

  injectMcpView();

  document.addEventListener("alpine:init", () => {
    injectMcpView();
    extendStore();
  });
})();
