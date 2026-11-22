/**
 * Credit Card Fraud Detection Portal - Real-Time Frontend Orchestration
 */

const state = {
  theme: localStorage.getItem("fraud_portal_theme") || "dark",
  charts: {},
  sseSource: null,
  streamRunning: false,
  streamInterval: 1.0,
  processedCount: 0,
  fraudCount: 0,
  blockedAmount: 0.0,
  rollingPoints: [],
  bestModelName: "Random Forest"
};

// Utilities
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

async function apiFetch(endpoint, options = {}) {
  try {
    const res = await fetch(endpoint, options);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.error(`API Error on ${endpoint}:`, err);
    throw err;
  }
}

// -----------------------------------------------------------------------------
// Theme Management
// -----------------------------------------------------------------------------
function applyTheme(theme) {
  state.theme = theme;
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("fraud_portal_theme", theme);
  const icon = $("#themeIcon");
  if (icon) {
    icon.textContent = theme === "dark" ? "☀️" : "🌙";
    $("#themeToggle").innerHTML = `<span id="themeIcon">${theme === "dark" ? "☀️" : "🌙"}</span> ${theme === "dark" ? "Light" : "Dark"}`;
  }
  updateChartColors();
}

function updateChartColors() {
  const isDark = state.theme === "dark";
  Chart.defaults.color = isDark ? "#94a3b8" : "#475569";
  Chart.defaults.borderColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";
  Object.values(state.charts).forEach(c => c && c.update && c.update());
}

// -----------------------------------------------------------------------------
// Navigation Tabs
// -----------------------------------------------------------------------------
function setupNavigation() {
  $$(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      $$(".nav-tab").forEach(t => t.classList.remove("active"));
      $$(".tab-pane").forEach(p => p.classList.remove("active"));

      tab.classList.add("active");
      const target = $(`#${tab.dataset.target}`);
      if (target) target.classList.add("active");

      handleTabActivation(tab.dataset.target);
    });
  });
}

function handleTabActivation(tabId) {
  if (tabId === "overviewPane") loadOverview();
  else if (tabId === "reviewPane") loadReviewQueue();
}

// -----------------------------------------------------------------------------
// Page 1: Real-Time Live Tracking (SSE)
// -----------------------------------------------------------------------------
function initRollingChart() {
  const ctx = $("#rollingRateChart");
  if (!ctx) return;

  state.charts.rolling = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Real-Time Fraud Probability",
          data: [],
          borderColor: "#ef4444",
          backgroundColor: "rgba(239, 68, 68, 0.12)",
          fill: true,
          tension: 0.25,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: "#ef4444"
        }
      ]
    },
    options: {
      responsive: true,
      animation: { duration: 300 },
      scales: {
        y: { 
          min: 0, 
          max: 1.0, 
          title: { display: true, text: "Fraud Risk (0.0 to 1.0)" },
          ticks: {
            callback: (v) => `${(v * 100).toFixed(0)}%`
          }
        },
        x: {
          title: { display: true, text: "Event Timestamp (HH:MM:SS)" }
        }
      }
    }
  });
}

async function startStream() {
  const interval = parseFloat($("#streamIntervalSelect").value) || 1.0;
  state.streamInterval = interval;
  try {
    await apiFetch(`/api/simulator/start?interval=${interval}`, { method: "POST" });
    startSseListener();
    state.streamRunning = true;
    
    const btn = $("#toggleStreamBtn");
    btn.textContent = "⏸️ Pause Stream";
    btn.className = "btn danger";

    $("#streamBadge").className = "badge live";
    $("#streamStatusText").textContent = `Streaming Live (${interval}s)`;
    $("#liveTps").textContent = `Throughput: ~${(1 / interval).toFixed(1)} txns/sec`;
  } catch (err) {
    console.error("Failed to start simulator:", err);
  }
}

async function stopStream() {
  try {
    await apiFetch("/api/simulator/stop", { method: "POST" });
    stopSseListener();
    state.streamRunning = false;

    const btn = $("#toggleStreamBtn");
    btn.textContent = "▶️ Resume Live Stream";
    btn.className = "btn success";

    $("#streamBadge").className = "badge";
    $("#streamStatusText").textContent = "Stream Paused";
    $("#liveTps").textContent = "Throughput: 0 txns/sec (Paused)";
  } catch (err) {
    console.error("Failed to stop simulator:", err);
  }
}

function startSseListener() {
  if (state.sseSource) state.sseSource.close();
  state.sseSource = new EventSource("/api/stream");

  state.sseSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleIncomingStreamEvent(data);
    } catch (err) {
      // Heartbeat or ping
    }
  };

  state.sseSource.onerror = () => {
    console.warn("SSE connection interrupted, retrying...");
  };
}

function stopSseListener() {
  if (state.sseSource) {
    state.sseSource.close();
    state.sseSource = null;
  }
}

function handleIncomingStreamEvent(event) {
  state.processedCount++;
  const isHighRisk = event.probability >= 0.50;

  if (isHighRisk) {
    state.fraudCount++;
    state.blockedAmount += event.amount;
  }

  // Update Real-Time Metrics Bar
  $("#liveProcessedCount").textContent = state.processedCount.toLocaleString();
  $("#liveFraudCount").textContent = state.fraudCount.toLocaleString();
  const rate = state.processedCount > 0 ? (100.0 * state.fraudCount / state.processedCount).toFixed(2) : "0.00";
  $("#liveFraudRate").textContent = `Session Fraud Rate: ${rate}%`;
  $("#liveBlockedAmount").textContent = `$${state.blockedAmount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  $("#liveEventCount").textContent = `${state.processedCount} events processed`;

  // Update Rolling Chart
  if (state.charts.rolling) {
    const chart = state.charts.rolling;
    chart.data.labels.push(event.timestamp);
    chart.data.datasets[0].data.push(event.probability);
    if (chart.data.labels.length > 30) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
    }
    chart.update("none");
  }

  // Prepend to Live Stream Box
  const feed = $("#liveStreamFeed");
  // Remove placeholder if present
  if (feed.firstElementChild && feed.firstElementChild.textContent.includes("Connecting")) {
    feed.innerHTML = "";
  }

  const item = document.createElement("div");
  item.className = `stream-item ${isHighRisk ? 'fraud-alert' : ''}`;
  item.style.animation = "fadeIn 0.25s ease";
  item.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:2px;">
      <div style="font-weight:600;">
        <strong>Txn #${event.txn_id}</strong> &bull; $${event.amount.toFixed(2)} &bull; 
        <span style="color:var(--text-muted); font-size:12px;">${event.timestamp}</span>
      </div>
      <div style="font-size:11px; color:var(--text-dim);">
        ${event.merchant || 'Retail'} &bull; ${event.card || 'Card'}
      </div>
    </div>
    <div style="display:flex; align-items:center; gap:10px;">
      <div style="text-align:right;">
        <span style="font-family:var(--font-mono); font-weight:700; color:${isHighRisk ? 'var(--accent-fraud)' : 'var(--accent-success)'};">
          ${(event.probability * 100).toFixed(1)}%
        </span>
        <div style="font-size:10px; color:var(--text-muted); text-transform:uppercase;">${event.risk_tier}</div>
      </div>
      <span class="badge ${isHighRisk ? 'fraud' : 'live'}">${event.prediction}</span>
      <button class="btn secondary" style="padding:4px 8px; font-size:11px;" onclick="openReviewModal(${event.txn_id}, ${event.amount}, '${isHighRisk ? 'CONFIRMED_FRAUD' : 'FALSE_ALARM'}')">
        Triage
      </button>
    </div>
  `;
  feed.prepend(item);
  if (feed.children.length > 50) feed.removeChild(feed.lastChild);

  // If High Risk, add to alert feed
  if (isHighRisk) {
    $("#alertCountBadge").textContent = `${state.fraudCount} Alerts`;

    const alertFeed = $("#liveAlertsFeed");
    if (alertFeed.firstElementChild && alertFeed.firstElementChild.textContent.includes("Monitoring")) {
      alertFeed.innerHTML = "";
    }

    const alertItem = document.createElement("div");
    alertItem.className = "stream-item fraud-alert";
    alertItem.style.animation = "fadeIn 0.3s ease";
    
    const shapText = (event.top_shap_features || []).map(f => 
      `<span style="background:rgba(239,68,68,0.2); padding:2px 5px; border-radius:4px; margin-right:4px;">${f.feature}: ${f.contribution > 0 ? '+' : ''}${f.contribution.toFixed(2)}</span>`
    ).join("");

    alertItem.innerHTML = `
      <div>
        <div style="font-weight:700; color:var(--accent-fraud); display:flex; align-items:center; gap:6px;">
          <span>🚨 ALERT: Txn #${event.txn_id}</span>
          <span style="color:var(--text-main); font-weight:600;">$${event.amount.toFixed(2)}</span>
          <span style="font-size:11px; color:var(--text-muted);">(${event.timestamp})</span>
        </div>
        <div style="font-size:12px; margin-top:4px;">
          ${event.merchant || 'Store'} &bull; ${event.card || 'Card'}
        </div>
        <div style="font-size:11px; margin-top:6px;">
          ${shapText}
        </div>
      </div>
      <div>
        <button class="btn danger" style="padding:6px 12px; font-size:12px; white-space:nowrap;" onclick="openReviewModal(${event.txn_id}, ${event.amount}, 'CONFIRMED_FRAUD')">
          🚨 Confirm Fraud
        </button>
      </div>
    `;
    alertFeed.prepend(alertItem);
    if (alertFeed.children.length > 30) alertFeed.removeChild(alertFeed.lastChild);
  }
}

function setupStreamControls() {
  const toggleBtn = $("#toggleStreamBtn");
  const intervalSel = $("#streamIntervalSelect");
  const clearBtn = $("#clearStreamBtn");

  toggleBtn.addEventListener("click", () => {
    if (state.streamRunning) {
      stopStream();
    } else {
      startStream();
    }
  });

  intervalSel.addEventListener("change", () => {
    if (state.streamRunning) {
      stopStream().then(() => startStream());
    }
  });

  clearBtn.addEventListener("click", () => {
    $("#liveStreamFeed").innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center;">Feed cleared. New transactions will appear as they arrive.</div>';
    $("#liveAlertsFeed").innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center;">Alerts cleared. High-risk transactions will appear here.</div>';
    state.processedCount = 0;
    state.fraudCount = 0;
    state.blockedAmount = 0.0;
    $("#liveProcessedCount").textContent = "0";
    $("#liveFraudCount").textContent = "0";
    $("#liveFraudRate").textContent = "Session Fraud Rate: 0.0%";
    $("#liveBlockedAmount").textContent = "$0.00";
    $("#alertCountBadge").textContent = "0 Alerts";
  });

  initRollingChart();

  // Auto-start live stream on page load!
  startStream();
}

// -----------------------------------------------------------------------------
// Page 2: Portfolio Overview & KPIs
// -----------------------------------------------------------------------------
async function loadOverview() {
  try {
    const data = await apiFetch("/api/kpis");
    const kpis = data.kpis;

    $("#kpiTotalTxns").textContent = (kpis.total_transactions || 0).toLocaleString();
    $("#kpiFraudTxns").textContent = (kpis.fraud_transactions || 0).toLocaleString();
    $("#kpiFraudRate").textContent = `Rate: ${(kpis.fraud_rate_pct || 0).toFixed(3)}%`;
    $("#kpiAmountAtRisk").textContent = `$${(kpis.amount_at_risk || 0).toLocaleString()}`;
    $("#kpiTotalAmount").textContent = `Total Volume: $${(kpis.total_amount || 0).toLocaleString()}`;
    $("#kpiAvgAmount").textContent = `$${(kpis.avg_amount || 0).toFixed(2)}`;
    $("#kpiMaxAmount").textContent = `Max: $${(kpis.max_amount || 0).toLocaleString()}`;

    renderPeriodChart(data.by_period || []);
    renderHourlyChart(data.by_hour || []);
    loadEtlRuns();
  } catch (err) {
    console.error("Failed to load overview data:", err);
  }
}

function renderPeriodChart(periods) {
  const ctx = $("#periodChart");
  if (!ctx) return;
  if (state.charts.period) state.charts.period.destroy();

  state.charts.period = new Chart(ctx, {
    type: "bar",
    data: {
      labels: periods.map(p => p.period),
      datasets: [
        {
          label: "Fraud Rate (%)",
          data: periods.map(p => p.fraud_rate),
          backgroundColor: "#ef4444",
          borderRadius: 6,
          yAxisID: "yRate"
        },
        {
          label: "Transaction Count",
          data: periods.map(p => p.txns),
          backgroundColor: "#3b82f6",
          borderRadius: 6,
          yAxisID: "yCount"
        }
      ]
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: {
        yRate: { type: "linear", position: "left", title: { display: true, text: "Fraud Rate (%)" } },
        yCount: { type: "linear", position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "Volume" } }
      }
    }
  });
}

function renderHourlyChart(hourly) {
  const ctx = $("#hourlyChart");
  if (!ctx) return;
  if (state.charts.hourly) state.charts.hourly.destroy();

  state.charts.hourly = new Chart(ctx, {
    type: "line",
    data: {
      labels: hourly.map(h => `${h.hour}:00`),
      datasets: [
        {
          label: "Hourly Fraud Incidents",
          data: hourly.map(h => h.fraud_count),
          borderColor: "#ef4444",
          backgroundColor: "rgba(239, 68, 68, 0.15)",
          fill: true,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: true } }
    }
  });
}

async function loadEtlRuns() {
  try {
    const data = await apiFetch("/api/etl-runs");
    const tbody = $("#etlHistoryTable tbody");
    if (!tbody) return;

    if (!data.history || data.history.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;">No ETL runs recorded.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.history.map(r => `
      <tr>
        <td><strong>#${r.run_id}</strong></td>
        <td>${r.run_timestamp}</td>
        <td><span class="badge ${r.status === 'SUCCESS' ? 'live' : 'fraud'}">${r.status}</span></td>
        <td>${(r.rows_extracted || 0).toLocaleString()}</td>
        <td>${(r.rows_loaded || 0).toLocaleString()}</td>
        <td>${(r.rows_rejected || 0).toLocaleString()}</td>
        <td><strong>${(r.fraud_rows || 0).toLocaleString()}</strong></td>
        <td>${r.duration_seconds}s</td>
        <td>${r.data_quality_passed ? '✅ Passed' : '❌ Failed'}</td>
        <td style="font-size:11px; max-width:200px; overflow:hidden; text-overflow:ellipsis;">${r.notes || '-'}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Failed to load ETL runs:", err);
  }
}

// -----------------------------------------------------------------------------
// Page 3: Check a Transaction (Inference & SHAP)
// -----------------------------------------------------------------------------
function buildPcaFormInputs() {
  const grid = $("#pcaInputsGrid");
  if (!grid) return;

  grid.innerHTML = Array.from({ length: 28 }, (_, i) => i + 1).map(n => `
    <div class="form-group">
      <label for="feat_V${n}">V${n}</label>
      <input type="number" id="feat_V${n}" step="0.0001" value="0.0" />
    </div>
  `).join("");
}

async function loadSample(cls) {
  try {
    const data = await apiFetch(`/api/sample?cls=${cls}`);
    $("#txnAmount").value = data.amount || 0;
    for (let i = 1; i <= 28; i++) {
      const el = $(`#feat_V${i}`);
      if (el) el.value = data[`V${i}`] !== undefined ? data[`V${i}`] : 0.0;
    }
  } catch (err) {
    console.error("Failed to load sample transaction:", err);
  }
}

async function handlePredictSubmit(e) {
  e.preventDefault();
  const payload = {
    amount: parseFloat($("#txnAmount").value) || 0.0,
    threshold: parseFloat($("#predictThreshold").value) || 0.50,
  };
  for (let i = 1; i <= 28; i++) {
    payload[`V${i}`] = parseFloat($(`#feat_V${i}`).value) || 0.0;
  }

  try {
    const result = await apiFetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    displayPredictionResult(result);
  } catch (err) {
    alert("Inference error: " + err.message);
  }
}

function displayPredictionResult(res) {
  const panel = $("#predictionResultPanel");
  panel.style.display = "block";

  const isFraud = res.is_fraud_predicted;
  $("#riskTierBadge").textContent = `TIER: ${res.risk_tier}`;
  $("#riskTierBadge").className = `badge ${isFraud ? 'fraud' : 'live'}`;

  const verdictCard = $("#verdictCard");
  verdictCard.className = `kpi-card ${isFraud ? 'fraud' : 'success'}`;
  $("#verdictLabel").textContent = res.prediction_label;
  $("#verdictSub").textContent = `Scored by ${res.model_name}`;

  $("#verdictProb").textContent = `${(res.probability * 100).toFixed(2)}%`;
  $("#verdictThreshold").textContent = `Decision Cutoff: ${res.threshold}`;
  $("#verdictAmount").textContent = `$${res.input_amount.toFixed(2)}`;

  // Render SHAP Bar Chart
  const shapBox = $("#shapBarContainer");
  const maxAbs = Math.max(...res.top_shap_features.map(f => Math.abs(f.contribution)), 0.001);

  shapBox.innerHTML = res.top_shap_features.map(f => {
    const pct = Math.min(100, Math.round((Math.abs(f.contribution) / maxAbs) * 100));
    const isRiskInc = f.direction === "RISK_INCREASING";
    return `
      <div class="shap-row">
        <span class="shap-label">${f.feature}</span>
        <div class="shap-track">
          <div class="shap-fill ${isRiskInc ? 'risk-inc' : 'risk-dec'}" style="width: ${pct}%;"></div>
        </div>
        <span style="font-family:var(--font-mono); font-weight:600; text-align:right; color:${isRiskInc ? 'var(--accent-fraud)' : 'var(--accent-success)'};">
          ${f.contribution > 0 ? '+' : ''}${f.contribution.toFixed(3)}
        </span>
      </div>
    `;
  }).join("");

  panel.scrollIntoView({ behavior: "smooth" });
}

// -----------------------------------------------------------------------------
// Page 4: Analyst Review Queue
// -----------------------------------------------------------------------------
async function loadReviewQueue() {
  try {
    const pending = await apiFetch("/api/reviews/pending");
    const reviews = await apiFetch("/api/reviews");

    // Pending Table
    const pBody = $("#pendingQueueTable tbody");
    if (pBody) {
      if (!pending.pending_queue || pending.pending_queue.length === 0) {
        pBody.innerHTML = `<tr><td colspan="6" style="text-align:center;">Queue is empty.</td></tr>`;
      } else {
        $("#pendingQueueCount").textContent = `${pending.pending_queue.length} Pending`;
        pBody.innerHTML = pending.pending_queue.map(item => `
          <tr>
            <td><strong>#${item.txn_id}</strong></td>
            <td>$${item.amount.toFixed(2)}</td>
            <td>${item.merchant}</td>
            <td>${item.card}</td>
            <td>${item.period}</td>
            <td>
              <button class="btn danger" style="padding:4px 8px; font-size:12px;" onclick="openReviewModal(${item.txn_id}, ${item.amount}, 'CONFIRMED_FRAUD')">
                🚨 Confirm Fraud
              </button>
              <button class="btn secondary" style="padding:4px 8px; font-size:12px; margin-left:6px;" onclick="openReviewModal(${item.txn_id}, ${item.amount}, 'FALSE_ALARM')">
                ✅ False Alarm
              </button>
            </td>
          </tr>
        `).join("");
      }
    }

    // Historical Table
    const rBody = $("#resolvedReviewsTable tbody");
    if (rBody) {
      if (!reviews.reviews || reviews.reviews.length === 0) {
        rBody.innerHTML = `<tr><td colspan="7" style="text-align:center;">No investigations logged yet.</td></tr>`;
      } else {
        rBody.innerHTML = reviews.reviews.map(r => `
          <tr>
            <td>#${r.review_id}</td>
            <td><strong>#${r.txn_id}</strong></td>
            <td>$${parseFloat(r.amount || 0).toFixed(2)}</td>
            <td><span class="badge ${r.decision === 'CONFIRMED_FRAUD' ? 'fraud' : 'live'}">${r.decision}</span></td>
            <td>${r.reviewer}</td>
            <td style="font-size:12px;">${r.notes || '-'}</td>
            <td>${r.reviewed_at}</td>
          </tr>
        `).join("");
      }
    }
  } catch (err) {
    console.error("Failed to load review queue:", err);
  }
}

window.openReviewModal = function(txnId, amount, decision = "CONFIRMED_FRAUD") {
  $("#revTxnId").value = txnId;
  $("#revAmount").value = amount;
  $("#revDecision").value = decision;
  $("#reviewModalTitle").textContent = decision === "CONFIRMED_FRAUD" ? "🚨 Confirm Fraud Incident" : "✅ Mark as False Alarm";
  $("#reviewModalDesc").textContent = `Recording disposition for Transaction #${txnId} ($${parseFloat(amount).toFixed(2)}).`;
  $("#reviewModal").classList.add("active");
};

// -----------------------------------------------------------------------------
// App Initialization
// -----------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  // 1. Initialize Theme
  applyTheme(state.theme);
  $("#themeToggle").addEventListener("click", () => {
    applyTheme(state.theme === "dark" ? "light" : "dark");
  });

  // 2. Setup Navigation
  setupNavigation();

  // 3. Setup Modals
  const reviewCloseBtn = $("#closeReviewModalBtn");
  if (reviewCloseBtn) {
    reviewCloseBtn.addEventListener("click", () => $("#reviewModal").classList.remove("active"));
  }

  // 4. Initialize Transaction Screening Inputs
  buildPcaFormInputs();

  // 5. Wire Events
  $("#refreshKpiBtn").addEventListener("click", loadOverview);
  $("#triggerEtlBtn").addEventListener("click", async () => {
    await apiFetch("/api/etl/trigger", { method: "POST" });
    alert("ETL pipeline scheduled in background! Updating logs in a moment...");
    setTimeout(loadEtlRuns, 3000);
  });

  $("#predictThreshold").addEventListener("input", (e) => {
    $("#cutoffValueDisplay").textContent = parseFloat(e.target.value).toFixed(2);
  });

  $("#loadLegitSampleBtn").addEventListener("click", () => loadSample(0));
  $("#loadFraudSampleBtn").addEventListener("click", () => loadSample(1));
  $("#predictForm").addEventListener("submit", handlePredictSubmit);

  $("#refreshQueueBtn").addEventListener("click", loadReviewQueue);

  $("#reviewActionForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      txn_id: parseInt($("#revTxnId").value),
      amount: parseFloat($("#revAmount").value),
      probability: 0.95,
      decision: $("#revDecision").value,
      reviewer: "Fraud Risk Analyst",
      notes: $("#revNotes").value
    };

    try {
      await apiFetch("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      $("#reviewModal").classList.remove("active");
      $("#revNotes").value = "";
      alert(`Disposition logged: Transaction #${payload.txn_id} saved as ${payload.decision}.`);
      loadReviewQueue();
    } catch (err) {
      alert("Failed to submit review: " + err.message);
    }
  });

  // 6. Setup and Auto-Start Live Stream Tracking
  setupStreamControls();
});
