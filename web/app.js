(() => {
  const $ = (id) => document.getElementById(id);
  const TOKEN_KEY = "tradingbot.auth";

  function getToken() {
    let t = localStorage.getItem(TOKEN_KEY);
    if (t === null) {
      t = window.prompt(
        "Enter X-Auth-Token (printed in the bot's startup log).\nLeave empty if running on localhost without WEB_AUTH_TOKEN."
      ) ?? "";
      localStorage.setItem(TOKEN_KEY, t);
    }
    return t;
  }

  async function api(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    const t = getToken();
    if (t) headers["X-Auth-Token"] = t;
    const res = await fetch(path, { ...options, headers });
    if (res.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      throw new Error("unauthorized — refresh the page to re-enter token");
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status}: ${text}`);
    }
    const ct = res.headers.get("content-type") || "";
    return ct.includes("application/json") ? res.json() : res.text();
  }

  const fmt = {
    money: (n) => (n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`),
    pct: (n) => (n == null ? "—" : `${(Number(n) * 100).toFixed(2)}%`),
    time: (ts) => {
      if (!ts) return "—";
      const d = new Date(ts * 1000);
      return d.toLocaleTimeString();
    },
  };

  // Tabs
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".pane").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $(`tab-${btn.dataset.tab}`).classList.add("active");
      if (btn.dataset.tab === "logs") refreshLogs();
      if (btn.dataset.tab === "tutorial") loadTutorial();
    });
  });

  // Status polling
  async function refreshStatus() {
    try {
      const s = await api("/api/status");
      $("equity").textContent = fmt.money(s.equity);
      const pnlEl = $("pnl");
      pnlEl.textContent = fmt.money(s.day_pnl);
      pnlEl.className = s.day_pnl > 0 ? "pos" : s.day_pnl < 0 ? "neg" : "";
      $("mode").textContent = s.execution_mode;
      $("market").textContent = s.market_open ? "open" : "closed";
      $("halted").textContent = s.halted ? "yes" : "no";
      $("halted").className = s.halted ? "neg" : "pos";
      $("last-scan").textContent = fmt.time(s.last_scan_ts);
      const badge = $("paper-badge");
      badge.textContent = s.is_paper ? "paper" : "live";
      badge.classList.toggle("live", !s.is_paper);

      const tbody = document.querySelector("#positions tbody");
      if (!s.positions.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty">No open positions</td></tr>`;
      } else {
        tbody.innerHTML = s.positions.map((p) => `
          <tr>
            <td>${p.symbol}</td>
            <td>${p.qty}</td>
            <td>${fmt.money(p.avg_entry)}</td>
            <td>${fmt.money(p.current_price)}</td>
            <td class="${p.unrealized_pl >= 0 ? "pos" : "neg"}">${fmt.money(p.unrealized_pl)}</td>
            <td class="${p.unrealized_plpc >= 0 ? "pos" : "neg"}">${fmt.pct(p.unrealized_plpc)}</td>
          </tr>
        `).join("");
      }
    } catch (e) {
      console.error("status:", e.message);
    }
  }

  async function refreshSignals() {
    try {
      const sigs = await api("/api/signals");
      const tbody = document.querySelector("#signals tbody");
      if (!sigs.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="empty">No signals yet</td></tr>`;
        return;
      }
      tbody.innerHTML = sigs.map((s) => `
        <tr>
          <td>${fmt.time(s.ts)}</td>
          <td>${s.symbol}</td>
          <td>${s.side.toUpperCase()}</td>
          <td>${fmt.money(s.entry)}</td>
          <td>${fmt.money(s.stop)}</td>
          <td>${fmt.money(s.take_profit)}</td>
          <td>${s.rr.toFixed(2)}</td>
          <td>${s.qty}</td>
          <td><span class="status-pill ${s.status}">${s.status}</span></td>
        </tr>
      `).join("");
    } catch (e) { console.error("signals:", e.message); }
  }

  // Settings
  async function loadSettings() {
    try {
      const s = await api("/api/settings");
      $("risk_per_trade").value = s.risk_per_trade;
      $("risk_per_trade_out").textContent = (s.risk_per_trade * 100).toFixed(2) + "%";
      $("max_daily_loss").value = s.max_daily_loss;
      $("max_daily_loss_out").textContent = (s.max_daily_loss * 100).toFixed(1) + "%";
      $("max_open_positions").value = s.max_open_positions;
      $("rr_target").value = s.rr_target;
      $("timeframe").value = s.timeframe;
      $("execution_mode").value = s.execution_mode;
      $("strategy").value = s.strategy;
      $("watchlist").value = s.watchlist.join(", ");
    } catch (e) { console.error("settings load:", e.message); }
  }

  $("risk_per_trade").addEventListener("input", (e) => {
    $("risk_per_trade_out").textContent = (parseFloat(e.target.value) * 100).toFixed(2) + "%";
  });
  $("max_daily_loss").addEventListener("input", (e) => {
    $("max_daily_loss_out").textContent = (parseFloat(e.target.value) * 100).toFixed(1) + "%";
  });

  $("settings-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = $("settings-msg");
    msg.textContent = "saving…";
    msg.className = "";
    const payload = {
      risk_per_trade: parseFloat($("risk_per_trade").value),
      max_daily_loss: parseFloat($("max_daily_loss").value),
      max_open_positions: parseInt($("max_open_positions").value, 10),
      rr_target: parseFloat($("rr_target").value),
      timeframe: $("timeframe").value,
      execution_mode: $("execution_mode").value,
      strategy: $("strategy").value,
      watchlist: $("watchlist").value,
    };
    try {
      await api("/api/settings", { method: "PUT", body: JSON.stringify(payload) });
      msg.textContent = "Saved.";
      msg.className = "ok";
    } catch (e) {
      msg.textContent = e.message;
      msg.className = "err";
    }
  });

  // Action buttons
  async function postAction(path, confirmMsg) {
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    try {
      const r = await api(path, { method: "POST" });
      alert(r.message || "ok");
      refreshStatus();
    } catch (e) {
      alert(e.message);
    }
  }
  $("halt-btn").addEventListener("click", () => postAction("/api/halt"));
  $("resume-btn").addEventListener("click", () => postAction("/api/resume"));
  $("closeall-btn").addEventListener("click", () =>
    postAction("/api/closeall", "Close ALL open positions immediately?")
  );

  // Tutorial
  let tutorialLoaded = false;
  async function loadTutorial() {
    if (tutorialLoaded) return;
    try {
      const md = await api("/api/tutorial");
      $("tutorial-content").innerHTML = window.marked ? marked.parse(md) : `<pre>${md}</pre>`;
      tutorialLoaded = true;
    } catch (e) {
      $("tutorial-content").textContent = "Failed to load tutorial: " + e.message;
    }
  }

  // Logs
  async function refreshLogs() {
    try {
      $("log-output").textContent = await api("/api/logs");
    } catch (e) {
      $("log-output").textContent = "Failed: " + e.message;
    }
  }
  $("refresh-logs").addEventListener("click", refreshLogs);

  // Boot
  loadSettings();
  refreshStatus();
  refreshSignals();
  setInterval(refreshStatus, 5000);
  setInterval(refreshSignals, 10000);
})();
