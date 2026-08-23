(() => {
  const STORAGE_KEY = "stu.ui.preferences.v1";

  const DEFAULT_PREFERENCES = {
    navCollapsed: false,
    activeView: "chat",
    telemetryVisible: true,
  };

  function makeId() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function hasStoredPreferences() {
    try {
      return localStorage.getItem(STORAGE_KEY) !== null;
    } catch {
      return false;
    }
  }

  function loadPreferences() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        return { ...DEFAULT_PREFERENCES };
      }
      return { ...DEFAULT_PREFERENCES, ...JSON.parse(raw) };
    } catch {
      return { ...DEFAULT_PREFERENCES };
    }
  }

  function savePreferences(prefs) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch {
      // Ignore storage failures.
    }
  }

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

  function createStuStore() {
    return {
      initialized: false,
      apiPrefix: document.body?.dataset?.apiPrefix || "/api/v1",

      health: null,
      publicConfig: null,

      navCollapsed: false,
      mobileNavOpen: false,
      telemetryVisible: true,
      activeView: "chat",
      currentProjectId: "default",

      projects: [],
      navItems: [
        { id: "chat", label: "Chat", icon: "💬" },
        { id: "workbench", label: "Workbench", icon: "🧰" },
        { id: "memory", label: "Memory", icon: "🧠" },
        { id: "tools", label: "Tools", icon: "🛠️" },
        { id: "mcp", label: "MCP", icon: "🔌" },
        { id: "daemons", label: "Daemons", icon: "📡" },
        { id: "security", label: "Security", icon: "🛡️" },
        { id: "settings", label: "Settings", icon: "⚙️" },
      ],

      telemetryCards: [
        {
          id: "loop",
          title: "Control Loop",
          tone: "primary",
          badge: "Idle",
          body: "7-phase agentic loop not started.",
        },
        {
          id: "daemons",
          title: "Daemons",
          tone: "safe",
          badge: "0 running",
          body: "Telemetry, maintenance, and reporting daemons are configured but disabled.",
        },
        {
          id: "tools",
          title: "Tools",
          tone: "warning",
          badge: "Standby",
          body: "Universal tool catalog will appear here.",
        },
        {
          id: "security",
          title: "Security",
          tone: "error",
          badge: "Pending",
          body: "Guardrails and sanitizer telemetry will appear here.",
        },
      ],

      chat: {
        draft: "",
        loading: false,
        messages: [],
      },

      toasts: [],
      showAddMemory: false,
      memory: {
        loading: false,
        entries: [],
        searchQuery: "",
        newEntry: { title: "", content: "", tagsStr: "" },
      },

      workbench: {
        goal: "",
        loading: false,
        state: null,
        polling: null,
      },

      init() {
        if (this.initialized) {
          return;
        }

        this.applyPreferences();
        this.fetchAll().then(() => {
          this.initialized = true;
          if (this.activeView === "memory") {
            this.fetchMemories();
          }
          if (this.activeView === "chat") {
            this.fetchChatHistory();
          }
          if (this.activeView === "workbench") {
            this.startWorkbenchPolling();
          }
        });
      },

      applyPreferences() {
        const prefs = loadPreferences();
        this.navCollapsed = Boolean(prefs.navCollapsed);
        this.activeView = prefs.activeView || "chat";
        this.telemetryVisible = Boolean(prefs.telemetryVisible);
      },

      persist() {
        savePreferences({
          navCollapsed: this.navCollapsed,
          activeView: this.activeView,
          telemetryVisible: this.telemetryVisible,
        });
      },

      async fetchAll() {
        await Promise.allSettled([this.fetchHealth(), this.fetchPublicConfig()]);

        if (!this.health || this.health.status === "error") {
          this.pushToast("Backend unreachable. Showing offline shell.", "error");
        }
      },

      async fetchHealth() {
        try {
          this.health = await fetchJson(`${this.apiPrefix}/health`);
        } catch {
          this.health = {
            status: "error",
            version: null,
            workspace_ready: false,
            timestamp: new Date().toISOString(),
          };
        }
      },

      async fetchPublicConfig() {
        try {
          const data = await fetchJson(`${this.apiPrefix}/config/public`);
          this.publicConfig = data;

          const defaultProjectId = data?.app?.default_project_id || "default";
          this.currentProjectId = defaultProjectId;
          this.projects = [
            {
              id: defaultProjectId,
              name: defaultProjectId,
            },
          ];

          if (!hasStoredPreferences() && data?.ui) {
            const smallViewport = window.matchMedia("(max-width: 1279px)").matches;

            this.activeView = data.ui.default_active_view || "chat";
            this.navCollapsed = Boolean(data.ui.default_nav_collapsed);
            this.telemetryVisible = smallViewport
              ? false
              : Boolean(data.ui.default_telemetry_visible);

            this.persist();
          }
        } catch {
          this.publicConfig = null;
          this.projects = [{ id: "default", name: "default" }];
          this.currentProjectId = "default";
        }
      },

      healthDotClass() {
        if (!this.health) return "status-dot--error";
        if (this.health.status === "ok") return "status-dot--safe";
        if (this.health.status === "degraded") return "status-dot--warning";
        return "status-dot--error";
      },

      healthLabel() {
        if (!this.health) return "Offline";
        if (this.health.status === "ok") return "Healthy";
        if (this.health.status === "degraded") return "Degraded";
        return "Error";
      },

      toggleNav() {
        this.navCollapsed = !this.navCollapsed;
        this.persist();
      },

      toggleTelemetry() {
        this.telemetryVisible = !this.telemetryVisible;
        this.persist();
      },

      openMobileNav() {
        this.mobileNavOpen = true;
      },

      closeMobileNav() {
        this.mobileNavOpen = false;
      },

      setActiveView(view) {
        this.activeView = view;
        this.closeMobileNav();
        this.persist();

        if (view === "memory") {
          this.fetchMemories();
        }
        if (view === "chat") {
          this.fetchChatHistory();
        }
        if (view === "workbench") {
          this.startWorkbenchPolling();
        } else {
          this.stopWorkbenchPolling();
        }
      },

      canSend() {
        return !this.chat.loading && this.chat.draft.trim().length > 0;
      },

      async fetchChatHistory() {
        try {
          const data = await fetchJson(
            `${this.apiPrefix}/projects/${this.currentProjectId}/chat/history`
          );
          this.chat.messages = data;
        } catch {
          this.chat.messages = [];
        }
      },

      async sendChat() {
        const message = this.chat.draft.trim();
        if (!message || this.chat.loading) return;

        this.chat.messages.push({
          id: makeId(),
          role: "user",
          content: message,
          timestamp: new Date().toISOString(),
        });

        this.chat.draft = "";
        this.chat.loading = true;

        try {
          const data = await fetchJson(
            `${this.apiPrefix}/projects/${this.currentProjectId}/chat`,
            {
              method: "POST",
              body: JSON.stringify({ message }),
            }
          );
          this.chat.messages.push(data.message);
        } catch (e) {
          this.pushToast("Failed to get LLM response.", "error");
          this.chat.messages.push({
            id: makeId(),
            role: "assistant",
            content: "Error: Failed to generate response.",
            timestamp: new Date().toISOString(),
          });
        } finally {
          this.chat.loading = false;
        }
      },

      sendDraft() {
        this.sendChat();
      },

      pushToast(message, tone = "primary") {
        const id = makeId();
        this.toasts.push({ id, message, tone });

        setTimeout(() => {
          this.toasts = this.toasts.filter((toast) => toast.id !== id);
        }, 5000);
      },

      async fetchMemories() {
        this.memory.loading = true;
        try {
          const params = this.memory.searchQuery
            ? `?query=${encodeURIComponent(this.memory.searchQuery)}`
            : "";
          const data = await fetchJson(
            `${this.apiPrefix}/projects/${this.currentProjectId}/memory${params}`
          );
          this.memory.entries = data;
        } catch (e) {
          this.pushToast("Failed to load memories.", "error");
        } finally {
          this.memory.loading = false;
        }
      },

      async createMemory() {
        const { title, content, tagsStr } = this.memory.newEntry;
        if (!title || !content) {
          this.pushToast("Title and content are required.", "warning");
          return;
        }
        const tags = tagsStr.split(",").map((t) => t.trim()).filter((t) => t);
        try {
          await fetchJson(
            `${this.apiPrefix}/projects/${this.currentProjectId}/memory`,
            {
              method: "POST",
              body: JSON.stringify({ title, content, tags }),
            }
          );
          this.showAddMemory = false;
          this.memory.newEntry = { title: "", content: "", tagsStr: "" };
          this.pushToast("Memory saved.", "safe");
          this.fetchMemories();
        } catch (e) {
          this.pushToast("Failed to save memory.", "error");
        }
      },

      async deleteMemory(id) {
        if (!confirm("Delete this memory?")) return;
        try {
          await fetchJson(
            `${this.apiPrefix}/projects/${this.currentProjectId}/memory/${id}`,
            { method: "DELETE" }
          );
          this.pushToast("Memory deleted.", "safe");
          this.fetchMemories();
        } catch (e) {
          this.pushToast("Failed to delete memory.", "error");
        }
      },

      // --- Workbench Methods ---

      startWorkbenchPolling() {
        this.stopWorkbenchPolling();
        this.fetchWorkbenchStatus();
        this.workbench.polling = setInterval(() => {
          this.fetchWorkbenchStatus();
        }, 2000);
      },

      stopWorkbenchPolling() {
        if (this.workbench.polling) {
          clearInterval(this.workbench.polling);
          this.workbench.polling = null;
        }
      },

      async fetchWorkbenchStatus() {
        try {
          const data = await fetchJson(
            `${this.apiPrefix}/projects/${this.currentProjectId}/execution/status`
          );
          this.workbench.state = data;
        } catch {
          // ignore
        }
      },

      async startExecution() {
        const goal = this.workbench.goal.trim();
        if (!goal || this.workbench.loading) return;
        this.workbench.loading = true;
        try {
          await fetchJson(
            `${this.apiPrefix}/projects/${this.currentProjectId}/execution/start`,
            {
              method: "POST",
              body: JSON.stringify({ goal }),
            }
          );
          this.workbench.goal = "";
          this.fetchWorkbenchStatus();
        } catch (e) {
          this.pushToast("Failed to start execution.", "error");
        } finally {
          this.workbench.loading = false;
        }
      },

      async approveExecution() {
        try {
          await fetchJson(
            `${this.apiPrefix}/projects/${this.currentProjectId}/execution/approve`,
            { method: "POST" }
          );
          this.fetchWorkbenchStatus();
        } catch (e) {
          this.pushToast("Failed to approve execution.", "error");
        }
      },

      async rejectExecution() {
        try {
          await fetchJson(
            `${this.apiPrefix}/projects/${this.currentProjectId}/execution/reject`,
            { method: "POST" }
          );
          this.fetchWorkbenchStatus();
        } catch (e) {
          this.pushToast("Failed to reject execution.", "error");
        }
      },
    };
  }

  function registerStore() {
    if (window.Alpine && !window.Alpine.__stuStoreRegistered) {
      window.Alpine.store("stu", createStuStore());
      window.Alpine.__stuStoreRegistered = true;
    }
  }

  document.addEventListener("alpine:init", registerStore);

  if (window.Alpine) {
    registerStore();
  }

  window.addEventListener("load", () => {
    if (!window.Alpine) {
      const warning = document.getElementById("alpine-missing-warning");
      if (warning) {
        warning.hidden = false;
      }
    }
  });
})();
