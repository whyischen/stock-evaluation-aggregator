const form = document.querySelector("#evaluateForm");
const tickerInput = document.querySelector("#tickerInput");
const report = document.querySelector("#report");
const pluginStatus = document.querySelector("#pluginStatus");
const pluginPicker = document.querySelector("#pluginPicker");

const directionLabel = {
  BUY: "买入",
  HOLD: "持有",
  SELL: "卖出",
  UNKNOWN: "未知",
};

function scoreLabel(score) {
  if (score === null || score === undefined) return "--";
  const value = Math.round(score * 100);
  return value > 0 ? `+${value}` : String(value);
}

function directionClass(direction) {
  return {
    BUY: "buy",
    HOLD: "hold",
    SELL: "sell",
  }[direction] || "";
}

async function loadStatus() {
  const response = await fetch("/api/system/status");
  const data = await response.json();
  pluginStatus.innerHTML = data.plugins.map((plugin) => `
    <div class="status-item">
      <div class="status-name">
        <span>${plugin.name}</span>
        <span class="pill ${plugin.status}">${plugin.status}</span>
      </div>
      <div class="status-message">${plugin.message} · ${plugin.plugin_type}</div>
    </div>
  `).join("");

  pluginPicker.innerHTML = data.plugins.map((plugin) => `
    <label class="plugin-option">
      <input type="checkbox" name="plugin" value="${plugin.plugin_id}" checked>
      <span>${plugin.name}</span>
      <small>${plugin.markets.join(", ")}</small>
    </label>
  `).join("");
}

async function evaluateTicker(ticker) {
  report.className = "report";
  report.innerHTML = `<div class="empty-state">正在调用插件评估 ${ticker}...</div>`;

  const pluginIds = Array.from(document.querySelectorAll('input[name="plugin"]:checked'))
    .map((input) => input.value);

  const response = await fetch("/api/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, plugin_ids: pluginIds }),
  });

  if (!response.ok) {
    report.innerHTML = `<div class="empty-state error">评估请求失败：${response.status}</div>`;
    return;
  }

  const data = await response.json();
  renderReport(data);
}

function renderReport(data) {
  const date = data.eval_date;
  const score = scoreLabel(data.weighted_score);
  const scoreClass = data.weighted_score > 0.15 ? "buy" : data.weighted_score < -0.15 ? "sell" : "hold";

  report.innerHTML = `
    <div class="report-header">
      <div>
        <h2>${data.ticker} 评估报告</h2>
        <div class="meta">${date} · ${data.market} · ${data.success_count}/${data.results.length} 插件成功 · 共识 ${data.consensus_level}</div>
      </div>
      <div class="score ${scoreClass}">
        <strong>${score}</strong>
        <span>聚合展示分</span>
      </div>
    </div>
    <div class="result-grid">
      ${data.results.map(renderResult).join("")}
    </div>
  `;
}

function renderResult(result) {
  const ok = result.status === "success";
  const verdict = ok ? directionLabel[result.direction] : result.status;
  const verdictClass = ok ? directionClass(result.direction) : "error";
  const confidence = ok ? `${Math.round(result.confidence * 100)}%` : "--";
  const detail = JSON.stringify(result.detail || {}, null, 2);

  return `
    <article class="result-card">
      <div class="result-top">
        <div>
          <div class="plugin-name">${result.plugin_name}</div>
          <div class="meta">${result.plugin_id} · ${result.latency_ms}ms</div>
        </div>
        <span class="${verdictClass}">${verdict}</span>
        <span class="pill ${result.status}">${confidence}</span>
      </div>
      <div class="summary">${ok ? result.summary : result.error}</div>
      ${ok ? `<details class="detail"><summary>查看标准化 detail</summary>${detail}</details>` : ""}
    </article>
  `;
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const ticker = tickerInput.value.trim();
  if (ticker) evaluateTicker(ticker);
});

document.querySelectorAll("[data-ticker]").forEach((button) => {
  button.addEventListener("click", () => {
    tickerInput.value = button.dataset.ticker;
    evaluateTicker(button.dataset.ticker);
  });
});

loadStatus();
