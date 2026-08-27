(() => {
  const TELEMETRY_VIEW_ID = "stu-telemetry-view";

  function telemetryViewHtml() {
    return `
      <header class="pane-header telemetry-header">
        <div class="pane-title">
          <h2>Telemetry</h2>
          <p class="pane-subtitle">Live system vitals and daemon status.</p>
        </div>

        <div class="pane-actions">
          <span class="telemetry-live-indicator">
            <span class="telemetry-live-dot" :class="{ disconnected: !$store.stu.telemetry.connected }"></span>
            <span x-text="$store.stu.telemetry.connected ? 'Live' : 'Disconnected'"></span>
          </span>
        </div>
      </header>

      <div class="telemetry-status-grid">
        <div class="telemetry-status-card">
          <h4>Loop Status</h4>
          <div class="telemetry-status-value" x-text="$store.stu.telemetry.data?.loop_state?.status || 'idle'"></div>
          <div class="telemetry-status-sub" x-text="'Phase: ' + ($store.stu.telemetry.data?.loop_state?.phase || '-')"></div>
        </div>

        <div class="telemetry-status-card">
          <h4>Tools</h4>
          <div class="telemetry-status-value" x-text="$store.stu.telemetry.data?.tool_stats?.total || 0"></div>
          <div class="telemetry-status-sub">
            <span x-text="($store.stu.telemetry.data?.tool_stats?.native || 0) + ' native'"></span> ·
            <span x-text="($store.stu.telemetry.data?.tool_stats?.mcp || 0) + ' MCP'"></span>
          </div>
        </div>

        <div class="telemetry-status-card">
          <h4>MCP Servers</h4>
          <div class="telemetry-status-value" x-text="($store.stu.telemetry.data?.mcp_stats?.servers_connected || 0) + '/' + ($store.stu.telemetry.data?.mcp_stats?.servers_total || 0)"></div>
          <div class="telemetry-status-sub" x-text="($store.stu.telemetry.data?.mcp_stats?.total_tools || 0) + ' tools'"></div>
        </div>

        <div class="telemetry-status-card">
          <h4>Memory</h4>
          <div class="telemetry-status-value" x-text="$store.stu.telemetry.data?.memory_stats?.entry_count || 0"></div>
          <div class="telemetry-status-sub">entries</div>
        </div>

        <div class="telemetry-status-card">
          <h4>WebSocket Clients</h4>
          <div class="telemetry-status-value" x-text="$store.stu.telemetry.data?.ws_clients || 0"></div>
          <div class="telemetry-status-sub" x-text="($store.stu.telemetry.data?.total_broadcasts || 0) + ' broadcasts'"></div>
        </div>
      </div>

      <div class="daemon-status-list">
        <template x-if="$store.stu.telemetry.data?.daemon_status">
          <div>
            <template x-for="daemon in $store.stu.telemetry.data.daemon_status" :key="daemon.name">
              <div class="daemon-status-item">
                <span class="name" x-text="daemon.name"></span>
                <span class="status" :class="{ running: daemon.running, stopped: !daemon.running && daemon.enabled, error: daemon.error_count > 0 }" x-text="daemon.error_count > 0 ? 'error (' + daemon.error_count + ')' : (daemon.running ? 'running' : (daemon.enabled ? 'stopped' : 'disabled'))"></span>
              </div>
            </template>
          </div>
        </template>
      </div>
    `;
  }

  function injectTelemetryView() {
    const main = document.getElementById("chat-pane");
    if (!main || document.getElementById(TELEMETRY_VIEW_ID)) {
      return;
    }

    const view = document.createElement("div");
    view.id = TELEMETRY_VIEW_ID;
    view.className = "view-container";
    view.setAttribute("x-show", "$store.stu.activeView === 'daemons'");
    view.setAttribute("x-cloak", "");
    view.innerHTML = telemetryViewHtml();

    main.appendChild(view);
  }

  function extendStore() {
    if (!window.Alpine) {
      return;
    }

    const store = window.Alpine.store("stu");
    if (!store || store.telemetry) {
      return;
    }

    store.telemetry = {
      connected: false,
      data: null,
      ws: null,
      reconnectAttempts: 0,
      maxReconnectAttempts: 10,
      reconnectDelay: 3000,
    };

    store.telemetryConnect = function () {
      if (store.telemetry.ws) {
        store.telemetry.ws.close();
      }

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}${store.apiPrefix}/telemetry/ws`;

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        store.telemetry.connected = true;
        store.telemetry.reconnectAttempts = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "telemetry_update") {
            store.telemetry.data = data;
          }
        } catch (e) {
          // ignore non-JSON messages (like "pong")
        }
      };

      ws.onclose = () => {
        store.telemetry.connected = false;
        store.telemetry.ws = null;

        if (store.telemetry.reconnectAttempts < store.telemetry.maxReconnectAttempts) {
          store.telemetry.reconnectAttempts++;
          setTimeout(() => store.telemetryConnect(), store.telemetry.reconnectDelay);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      store.telemetry.ws = ws;
    };

    store.telemetryDisconnect = function () {
      if (store.telemetry.ws) {
        store.telemetry.ws.close();
        store.telemetry.ws = null;
      }
      store.telemetry.connected = false;
    };

    store.telemetryConnect();
  }

  injectTelemetryView();

  document.addEventListener("alpine:init", () => {
    injectTelemetryView();
    extendStore();
  });
})();
