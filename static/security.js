(() => {
  const SECURITY_VIEW_ID = "stu-security-view";

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

  function securityViewHtml() {
    return `
      <header class="pane-header">
        <button type="button" class="icon-button mobile-nav-toggle" @click="$store.stu.openMobileNav()" aria-label="Open navigation">≡</button>
        <div class="pane-title">
          <h1>Security</h1>
          <p class="pane-subtitle">Guardrails, sanitizer, egress, and security events.</p>
        </div>
        <div class="pane-actions">
          <button type="button" class="btn" @click="$store.stu.fetchSecurity()">Refresh</button>
        </div>
      </header>

      <div class="security-toolbar">
        <span class="health-pill" :class="$store.stu.healthDotClass()" x-text="$store.stu.healthLabel()"></span>
      </div>

      <template x-if="$store.stu.security.loading">
        <div class="security-grid">
          <div class="card card--primary"><p>Loading security data...</p></div>
        </div>
      </template>

      <template x-if="!$store.stu.security.loading && $store.stu.security.status">
        <div class="security-grid">
          <article class="card card--primary">
            <header class="card-header">
              <h3>Guardrails</h3>
              <span class="card-badge" x-text="$store.stu.security.status.guardrails_enabled ? 'enabled' : 'disabled'"></span>
            </header>
            <p>Central pre-loop, pre-tool, and post-tool enforcement.</p>
          </article>

          <article class="card card--safe">
            <header class="card-header">
              <h3>Sanitizer</h3>
              <span class="card-badge" x-text="$store.stu.security.status.sanitizer_enabled ? 'enabled' : 'disabled'"></span>
            </header>
            <p>Regex and heuristic scanning for forbidden patterns.</p>
          </article>

          <article class="card" :class="$store.stu.security.status.network_enabled ? 'card--warning' : 'card--safe'">
            <header class="card-header">
              <h3>Egress</h3>
              <span class="card-badge" x-text="$store.stu.security.status.network_enabled ? 'enabled' : 'deny-by-default'"></span>
            </header>
            <p>Network egress is controlled by allowlist.</p>
          </article>

          <article class="card card--primary">
            <header class="card-header">
              <h3>Events</h3>
              <span class="card-badge" x-text="$store.stu.security.status.total_events"></span>
            </header>
            <p>
              Deny: <span x-text="$store.stu.security.status.deny_count"></span>
              Review: <span x-text="$store.stu.security.status.review_count"></span>
            </p>
          </article>
        </div>
      </template>

      <section class="security-events">
        <template x-if="!$store.stu.security.loading && $store.stu.security.events.length === 0">
          <div class="card card--muted"><p>No security events recorded.</p></div>
        </template>

        <template x-for="event in $store.stu.security.events" :key="event.id">
          <article class="security-event">
            <div class="security-event-top">
              <span class="security-badge" :class="'security-decision--' + event.decision" x-text="event.decision"></span>
              <span class="security-badge" :class="'security-severity--' + event.severity" x-text="event.severity"></span>
            </div>
            <p x-text="event.reason"></p>
            <div class="security-event-meta">
              <span x-text="event.source"></span>
              ·
              <span x-text="new Date(event.timestamp).toLocaleString()"></span>
              ·
              <span x-text="event.project_id || 'global'"></span>
            </div>
          </article>
        </template>
      </section>
    `;
  }

  function injectSecurityView() {
    const main = document.getElementById("chat-pane");
    if (!main || document.getElementById(SECURITY_VIEW_ID)) {
      return;
    }

    const view = document.createElement("div");
    view.id = SECURITY_VIEW_ID;
    view.className = "view-container";
    view.setAttribute("x-show", "$store.stu.activeView === 'security'");
    view.setAttribute("x-cloak", "");
    view.innerHTML = securityViewHtml();

    main.appendChild(view);
  }

  function extendStore() {
    if (!window.Alpine) {
      return;
    }

    const store = window.Alpine.store("stu");
    if (!store || store.security) {
      return;
    }

    store.security = {
      loading: false,
      status: null,
      events: [],
    };

    store.fetchSecurity = async function () {
      this.security.loading = true;
      try {
        const [status, events] = await Promise.all([
          fetchJson(`${this.apiPrefix}/security/status`),
          fetchJson(`${this.apiPrefix}/security/events?limit=50`),
        ]);

        this.security.status = status;
        this.security.events = events;
      } catch (e) {
        this.pushToast("Failed to load security data.", "error");
      } finally {
        this.security.loading = false;
      }
    };

    const originalSetActiveView = store.setActiveView;
    store.setActiveView = function (view) {
      originalSetActiveView.call(this, view);
      if (view === "security") {
        this.fetchSecurity();
      }
    };

    if (store.activeView === "security") {
      store.fetchSecurity();
    }
  }

  injectSecurityView();

  document.addEventListener("alpine:init", () => {
    injectSecurityView();
    extendStore();
  });
})();
