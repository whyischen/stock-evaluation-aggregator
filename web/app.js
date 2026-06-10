const form = document.querySelector("#evaluateForm");
const tickerInput = document.querySelector("#tickerInput");
const report = document.querySelector("#report");
const pluginStatus = document.querySelector("#pluginStatus");
const pluginPicker = document.querySelector("#pluginPicker");
const watchlist = document.querySelector("#watchlist");
const historyList = document.querySelector("#historyList");
const refreshHistoryBtn = document.querySelector("#refreshHistoryBtn");

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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function loadStatus() {
  const response = await fetch("/api/system/status");
  const data = await response.json();
  pluginStatus.innerHTML = data.plugins.map((plugin) => `
    <div class="status-item">
      <div class="status-name">
        <span>${escapeHtml(plugin.name)}</span>
        <span class="pill ${escapeHtml(plugin.status)}">${escapeHtml(plugin.status)}</span>
      </div>
      <div class="status-message">${escapeHtml(plugin.message)} · ${escapeHtml(plugin.plugin_type)}</div>
    </div>
  `).join("");

  pluginPicker.innerHTML = data.plugins.map((plugin) => `
    <label class="plugin-option">
      <input type="checkbox" name="plugin" value="${escapeHtml(plugin.plugin_id)}" checked>
      <span>${escapeHtml(plugin.name)}</span>
      <small>${escapeHtml(plugin.markets.join(", "))}</small>
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
  loadHistory();
}

function renderReport(data) {
  const date = data.eval_date;
  const score = scoreLabel(data.weighted_score);
  const scoreClass = data.weighted_score > 0.15 ? "buy" : data.weighted_score < -0.15 ? "sell" : "hold";

  report.innerHTML = `
    <div class="report-header">
      <div>
        <h2>${escapeHtml(data.ticker)} 评估报告</h2>
        <div class="meta">${escapeHtml(date)} · ${escapeHtml(data.market)} · ${data.success_count}/${data.results.length} 插件成功 · 共识 ${escapeHtml(data.consensus_level)}</div>
      </div>
      <div class="score ${scoreClass}">
        <strong>${score}</strong>
        <span>聚合展示分</span>
      </div>
    </div>
    <div class="result-grid">
      ${data.results.map(renderResult).join("")}
    </div>
    <div class="report-actions">
      <button type="button" data-add-watch="${escapeHtml(data.ticker)}">加入关注</button>
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
          <div class="plugin-name">${escapeHtml(result.plugin_name)}</div>
          <div class="meta">${escapeHtml(result.plugin_id)} · ${result.latency_ms}ms</div>
        </div>
        <span class="${verdictClass}">${escapeHtml(verdict)}</span>
        <span class="pill ${escapeHtml(result.status)}">${escapeHtml(confidence)}</span>
      </div>
      <div class="summary">${escapeHtml(ok ? result.summary : result.error)}</div>
      ${ok ? `<details class="detail"><summary>查看标准化 detail</summary>${escapeHtml(detail)}</details>` : ""}
    </article>
  `;
}

async function loadWatchlist() {
  const response = await fetch("/api/watchlist");
  const items = await response.json();
  if (!items.length) {
    watchlist.innerHTML = `<div class="empty-small">暂无关注标的</div>`;
    return;
  }

  watchlist.innerHTML = items.map((item) => `
    <div class="watch-item">
      <div class="watch-top">
        <strong>${escapeHtml(item.ticker)}</strong>
        <button type="button" data-remove-watch="${escapeHtml(item.ticker)}">移除</button>
      </div>
      <div class="meta">${escapeHtml(item.name || item.market)}</div>
      <button type="button" data-evaluate-ticker="${escapeHtml(item.ticker)}">评估</button>
    </div>
  `).join("");
}

async function addWatch(ticker) {
  await fetch("/api/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker }),
  });
  loadWatchlist();
}

async function removeWatch(ticker) {
  await fetch(`/api/watchlist/${encodeURIComponent(ticker)}`, { method: "DELETE" });
  loadWatchlist();
}

function selectAndEvaluate(ticker) {
  tickerInput.value = ticker;
  evaluateTicker(ticker);
}

async function loadHistory() {
  const response = await fetch("/api/history?limit=8");
  const items = await response.json();
  if (!items.length) {
    historyList.innerHTML = `<div class="empty-small">暂无评估历史</div>`;
    return;
  }

  historyList.innerHTML = items.map((item) => `
    <div class="history-item">
      <div class="history-top">
        <strong>${escapeHtml(item.ticker)}</strong>
        <span class="${item.weighted_score > 0.15 ? "buy" : item.weighted_score < -0.15 ? "sell" : "hold"}">${scoreLabel(item.weighted_score)}</span>
      </div>
      <div class="meta">${escapeHtml(item.eval_date)} · ${escapeHtml(item.market)} · ${escapeHtml(item.consensus_level)} · ${item.success_count}/${item.success_count + item.failed_count} 成功</div>
      <button type="button" data-evaluate-ticker="${escapeHtml(item.ticker)}">重新评估</button>
    </div>
  `).join("");
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

refreshHistoryBtn.addEventListener("click", loadHistory);

document.addEventListener("click", (event) => {
  const addButton = event.target.closest("[data-add-watch]");
  if (addButton) {
    addWatch(addButton.dataset.addWatch);
    return;
  }

  const removeButton = event.target.closest("[data-remove-watch]");
  if (removeButton) {
    removeWatch(removeButton.dataset.removeWatch);
    return;
  }

  const evaluateButton = event.target.closest("[data-evaluate-ticker]");
  if (evaluateButton) {
    selectAndEvaluate(evaluateButton.dataset.evaluateTicker);
  }
});

loadStatus();
loadWatchlist();
loadHistory();
