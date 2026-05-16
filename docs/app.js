const state = {
  rawRows: [],
  summary: [],
  participants: [],
  filtered: [],
  epochs: [],
  showAllRows: false,
  showWeights: false,
  showRewards: true,
  showBug: false,
  showSources: true,
};

const format = new Intl.NumberFormat("en-US", { maximumFractionDigits: 9 });

loadData().then(({ rows, summary }) => {
  state.rawRows = rows;
  state.summary = summary;
  state.epochs = [...new Set(rows.map((row) => row.epoch))].sort((a, b) => a - b);
  state.participants = pivotRows(rows);
  hydrateFilters();
  render();
}).catch((error) => {
  document.getElementById("tableBody").innerHTML = `
    <tr>
      <td colspan="3">
        Failed to load data: ${escapeHtml(error.message)}.
        Run from a local server with <code>python3 -m http.server 8080 --directory docs</code>
        or rebuild <code>docs/data.js</code> with <code>python3 scripts/build_pages_data.py</code>.
      </td>
    </tr>
  `;
});

async function loadData() {
  if (window.__GONKA_COMPENSATION_DATA__) {
    return {
      rows: window.__GONKA_COMPENSATION_DATA__.rows,
      summary: window.__GONKA_COMPENSATION_DATA__.summary,
    };
  }
  const [rows, summary] = await Promise.all([
    fetch("data/compensation_rows.json").then((response) => response.json()),
    fetch("data/summary.json").then((response) => response.json()),
  ]);
  return { rows, summary };
}

document.getElementById("searchInput").addEventListener("input", render);
document.getElementById("epochFilter").addEventListener("change", render);
document.getElementById("reasonFilter").addEventListener("change", render);
document.getElementById("showAllRows").addEventListener("change", (event) => {
  state.showAllRows = event.target.checked;
  render();
});
document.getElementById("showWeights").addEventListener("change", (event) => {
  state.showWeights = event.target.checked;
  render();
});
document.getElementById("showRewards").addEventListener("change", (event) => {
  state.showRewards = event.target.checked;
  render();
});
document.getElementById("showBug").addEventListener("change", (event) => {
  state.showBug = event.target.checked;
  render();
});
document.getElementById("showSources").addEventListener("change", (event) => {
  state.showSources = event.target.checked;
  render();
});

function pivotRows(rows) {
  const byAddress = new Map();
  for (const row of rows) {
    if (!byAddress.has(row.address)) {
      byAddress.set(row.address, {
        address: row.address,
        byEpoch: new Map(),
        hasLoss: false,
        reasons: new Set(),
        baselineCompensationBaseUnits: 0,
        bugCompensationBaseUnits: 0,
        sourceCompensationBaseUnits: 0,
        remainingAfterSourcesBaseUnits: 0,
        sourceExcessBaseUnits: 0,
      });
    }
    const participant = byAddress.get(row.address);
    participant.byEpoch.set(row.epoch, row);
    participant.hasLoss = participant.hasLoss || row.has_loss;
    if (row.reason) participant.reasons.add(row.reason);
    participant.baselineCompensationBaseUnits += Number(row.compensation_base_units || 0);
    participant.bugCompensationBaseUnits += Number(row.bug_compensation_base_units || 0);
    participant.sourceCompensationBaseUnits += Number(row.source_compensation_base_units || 0);
    participant.remainingAfterSourcesBaseUnits += Number(row.remaining_after_sources_base_units || 0);
    participant.sourceExcessBaseUnits += Number(row.source_excess_base_units || 0);
  }
  return [...byAddress.values()].sort((a, b) => {
    const delta = b.baselineCompensationBaseUnits - a.baselineCompensationBaseUnits;
    return delta || a.address.localeCompare(b.address);
  });
}

function hydrateFilters() {
  const epochFilter = document.getElementById("epochFilter");
  const reasonFilter = document.getElementById("reasonFilter");
  for (const epoch of state.epochs) {
    epochFilter.append(new Option(`Epoch ${epoch}`, String(epoch)));
  }
  const reasons = [...new Set(state.rawRows.map((row) => row.reason).filter(Boolean))].sort();
  for (const reason of reasons) {
    reasonFilter.append(new Option(reason, reason));
  }
}

function selectedEpochs() {
  const selected = document.getElementById("epochFilter").value;
  return selected === "all" ? state.epochs : [Number(selected)];
}

function activeMetrics() {
  const metrics = [];
  if (state.showRewards) {
    metrics.push(["reward_delta_after_sources_gnk", "Reward Δ"]);
    metrics.push(["source_weight_delta", "Weight Δ"]);
  }
  if (state.showWeights) {
    metrics.push(["actual_reward_gnk", "Actual"]);
    metrics.push(["compensation_gnk", "Calc reward"]);
    metrics.push(["source_compensation_gnk", "Source reward"]);
    metrics.push(["weight", "Calc weight"]);
    metrics.push(["source_weight", "Source weight"]);
  }
  if (state.showBug) {
    metrics.push(["bug_adjusted_weight", "0.35 W"]);
    metrics.push(["bug_weight_delta", "0.35 W Δ"]);
    metrics.push(["bug_reward_delta_gnk", "0.35 reward"]);
  }
  if (state.showSources) {
    metrics.push(["source_state", "Source"]);
  }
  return metrics.length ? metrics : [["reward_delta_after_sources_gnk", "Reward Δ"]];
}

function render() {
  const search = document.getElementById("searchInput").value.trim().toLowerCase();
  const reason = document.getElementById("reasonFilter").value;
  const epochs = selectedEpochs();

  state.filtered = state.participants.filter((participant) => {
    const rows = epochs.map((epoch) => participant.byEpoch.get(epoch)).filter(Boolean);
    if (!rows.length) return false;
    const hasVisibleLoss = rows.some((row) => row.has_loss);
    if (!state.showAllRows && !hasVisibleLoss) return false;
    if (reason !== "all" && !rows.some((row) => row.reason === reason)) return false;
    if (!search) return true;
    return [
      participant.address,
      [...participant.reasons].join(" "),
      ...rows.map((row) => `${row.reason} ${row.notes} ${row.bug_details}`),
      ...rows.flatMap((row) => (row.sources || []).map((source) => `${source.source} ${source.details} ${source.status}`)),
    ].join(" ").toLowerCase().includes(search);
  });

  renderTotals(epochs);
  renderSummary(epochs);
  renderTable(epochs, activeMetrics());
}

function renderTotals(epochs) {
  const rows = state.filtered.flatMap((participant) => epochs.map((epoch) => participant.byEpoch.get(epoch)).filter(Boolean));
  const baseline = sumRows(rows, "compensation_base_units") / 1e9;
  const source = sumRows(rows, "source_compensation_base_units") / 1e9;
  const remaining = sumRows(rows, "remaining_after_sources_base_units") / 1e9;
  const excess = sumRows(rows, "source_excess_base_units") / 1e9;
  const bug = sumRows(rows, "bug_compensation_base_units") / 1e9;
  document.getElementById("totals").innerHTML = [
    metric("Participants", state.filtered.length),
    metric("Baseline lost GNK", format.format(baseline)),
    metric("Source comp GNK", format.format(source)),
    metric("Remaining GNK", format.format(remaining)),
    metric("Source excess GNK", format.format(excess)),
    metric("Bug lost GNK", format.format(bug)),
  ].join("");
}

function renderSummary(epochs) {
  document.getElementById("summary").innerHTML = epochs.map((epoch) => {
    const rows = state.filtered.map((participant) => participant.byEpoch.get(epoch)).filter(Boolean);
    const total = sumRows(rows, "compensation_base_units") / 1e9;
    const remaining = sumRows(rows, "remaining_after_sources_base_units") / 1e9;
    const count = rows.filter((row) => row.has_loss).length;
    return `<div class="summary-card"><span>Epoch ${epoch}</span><strong>${format.format(total)} GNK</strong><em>${count} rows · remaining ${format.format(remaining)} GNK</em></div>`;
  }).join("");
}

function renderTable(epochs, metrics) {
  document.getElementById("tableHead").innerHTML = `
    <tr>
      <th rowspan="2" class="sticky-col">Address</th>
      <th rowspan="2">Reasons</th>
      ${epochs.map((epoch) => `<th colspan="${metrics.length}">Epoch ${epoch}</th>`).join("")}
    </tr>
    <tr>
      ${epochs.flatMap(() => metrics.map(([, label]) => `<th>${label}</th>`)).join("")}
    </tr>
  `;

  document.getElementById("tableBody").innerHTML = state.filtered.map((participant, index) => {
    const rows = epochs.map((epoch) => participant.byEpoch.get(epoch)).filter(Boolean);
    const hasLoss = rows.some((row) => row.has_loss);
    return `
      <tr class="${hasLoss ? "loss-row" : ""}">
        <td class="sticky-col"><button class="link" data-participant-index="${index}">${escapeHtml(participant.address)}</button></td>
        <td class="reason-cell">${escapeHtml([...participant.reasons].filter(Boolean).join(", "))}</td>
        ${epochs.flatMap((epoch) => metrics.map(([key]) => renderEpochCell(participant.byEpoch.get(epoch), key))).join("")}
      </tr>
    `;
  }).join("");

  document.querySelectorAll("[data-participant-index]").forEach((button) => {
    button.addEventListener("click", () => showParticipantDetails(state.filtered[Number(button.dataset.participantIndex)], epochs));
  });
  document.querySelectorAll("[data-row-key]").forEach((cell) => {
    cell.addEventListener("click", () => {
      const [address, epoch] = cell.dataset.rowKey.split("|");
      const participant = state.participants.find((item) => item.address === address);
      showDetails(participant.byEpoch.get(Number(epoch)));
    });
  });
}

function renderEpochCell(row, key) {
  if (!row) return "<td></td>";
  const value = row[key] ?? "";
  const emptyNeutral = isEmptyNeutralRow(row);
  const displayValue = emptyNeutral ? formatEmptyNeutralCell(key) : formatCellValue(key, value);
  const classes = [];
  if (key === "compensation_gnk" && Number(row.compensation_base_units) > 0) classes.push("loss-strong");
  if (key === "reward_delta_after_sources_gnk" && !emptyNeutral) classes.push(rewardDeltaClass(row));
  if (key === "source_weight_delta" && !emptyNeutral) classes.push(sourceStateClass(row));
  if (key === "source_state" && !emptyNeutral) classes.push(sourceStateClass(row));
  if (key.startsWith("bug_") && row.bug_adjusted_weight !== null) classes.push("bug");
  if (key.startsWith("source_") && Number(row.source_compensation_base_units || 0) > 0) classes.push("source");
  if (key.startsWith("remaining_") && Number(row.remaining_after_sources_base_units || 0) > 0) classes.push("remaining");
  if (key === "source_excess_gnk" && Number(row.source_excess_base_units || 0) > 0) classes.push("diff");
  if (key === "match_status") {
    if (row.match_status.includes("matches")) classes.push("match");
    if (row.match_status === "source_differs") classes.push("diff");
  }
  if (row.has_loss) classes.push("clickable");
  return `<td class="${classes.join(" ")}" data-row-key="${escapeHtml(row.address)}|${row.epoch}" title="${escapeHtml(String(value))}">${escapeHtml(displayValue)}</td>`;
}

function formatEmptyNeutralCell(key) {
  if (["reward_delta_after_sources_gnk", "source_weight_delta", "source_state"].includes(key)) {
    return "";
  }
  return formatCellValue(key, "");
}

function showParticipantDetails(participant, epochs) {
  const rows = epochs.map((epoch) => participant.byEpoch.get(epoch)).filter(Boolean);
  const totalLost = sumRows(rows, "compensation_base_units") / 1e9;
  const remaining = sumRows(rows, "remaining_after_sources_base_units") / 1e9;
  document.getElementById("detailContent").innerHTML = `
    <h2>${escapeHtml(participant.address)}</h2>
    <p>Total visible lost reward: ${formatGnk(totalLost)} GNK. Remaining after sources: ${formatGnk(remaining)} GNK.</p>
    <div class="detail-grid">
      ${rows.map((row) => detail(`Epoch ${row.epoch}`, `actual ${row.actual_reward_gnk} GNK; reward Δ ${row.reward_delta_after_sources_gnk || "0.000000000"} GNK; ${row.reason || "no reason"}`)).join("")}
    </div>
  `;
  document.getElementById("detailDialog").showModal();
}

function showDetails(row) {
  document.getElementById("detailContent").innerHTML = `
    <h2>${escapeHtml(row.address)}</h2>
    ${renderVerdict(row)}
    ${renderWhatHappened(row)}
    ${renderWeightsSummary(row)}
    ${renderRewardsSummary(row)}
    ${renderSourceLayers(row)}
    ${renderTechnicalDetails(row)}
  `;
  document.getElementById("detailDialog").showModal();
}

function renderVerdict(row) {
  return `
    <section class="verdict-card ${verdictClass(row)}">
      <div>
        <span class="section-kicker">Epoch ${row.epoch}</span>
        <strong>${formatGnkValue(row.reward_delta_after_sources_gnk)} GNK</strong>
        <em>Final Reward Δ</em>
      </div>
      <div class="verdict-meta">
        ${pill(statusLabel(row.source_state), sourceStateClass(row))}
        ${pill(matchLabel(row.match_status), "neutral-pill")}
        ${row.reason ? pill(row.reason, "neutral-pill") : ""}
      </div>
    </section>
  `;
}

function renderWhatHappened(row) {
  return section("What happened", `
    <div class="kv-grid">
      ${kv("Actual received", `${formatGnkValue(row.actual_reward_gnk)} GNK`)}
      ${kv("Reason", row.reason || "none")}
      ${kv("Source status", statusLabel(row.source_state))}
      ${kv("Match", matchLabel(row.match_status))}
      ${kv("Final Reward Δ", `${formatGnkValue(row.reward_delta_after_sources_gnk)} GNK`, rewardDeltaClass(row))}
      ${kv("Calculated before sources", `${formatGnkValue(row.calculated_layers_gnk)} GNK`)}
      ${kv("Source total", `${formatGnkValue(row.source_compensation_gnk)} GNK`)}
    </div>
  `);
}

function renderWeightsSummary(row) {
  return section("Weights", `
    <div class="kv-grid">
      ${kv("Chain weight", row.weight)}
      ${kv("Confirmation weight", row.confirmation_weight)}
      ${kv("Effective weight", row.effective_weight)}
      ${kv("0.35 weight delta", row.bug_weight_delta ?? "0")}
      ${kv("Weight with 0.35 fix", row.bug_adjusted_weight ?? row.effective_weight)}
      ${kv("Source weight", row.source_weight ?? "0")}
    </div>
  `);
}

function renderRewardsSummary(row) {
  return section("Rewards", `
    <div class="kv-grid">
      ${kv("Expected by base calc", `${formatGnkValue(row.expected_reward_gnk)} GNK`)}
      ${kv("Actual received", `${formatGnkValue(row.actual_reward_gnk)} GNK`)}
      ${kv("Baseline lost", `${formatGnkValue(row.compensation_gnk)} GNK`)}
      ${kv("Expected with 0.35 fix", `${formatGnkValue(row.bug_expected_reward_gnk || row.expected_reward_gnk)} GNK`)}
      ${kv("0.35 reward delta", `${formatGnkValue(row.bug_reward_delta_gnk || row.bug_compensation_gnk)} GNK`)}
      ${kv("Final Reward Δ", `${formatGnkValue(row.reward_delta_after_sources_gnk)} GNK`, rewardDeltaClass(row))}
    </div>
  `);
}

function renderSourceLayers(row) {
  const sources = row.sources || [];
  if (!sources.length) {
    return "";
  }
  return section("Sources", `
    <table class="source-table">
      <thead>
        <tr>
          <th>Source</th>
          <th>Compensation</th>
          <th>Weight</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        ${sources.map((source) => `
          <tr>
            <td>${sourceLink(source)}</td>
            <td>${formatGnkValue(source.source_compensation_gnk)} GNK</td>
            <td>${escapeHtml(source.source_weight || source.weight || "")}</td>
            <td>${escapeHtml(source.status || "")}</td>
          </tr>
          <tr>
            <td colspan="4" class="source-details">
              ${helpDetails("details", source.details || "")}
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `);
}

function renderTechnicalDetails(row) {
  return section("Technical details", `
    <div class="compact-details">
      ${helpDetails("formula", `
        base_expected = floor(expected_weight * fixed_epoch_reward / total_epoch_weight)
        baseline_lost = max(0, base_expected - actual_received)
        calculated_layers_total = baseline_lost + adjustment_layers
        final_reward_delta = calculated_layers_total - source_total
      `)}
      ${helpDetails("base notes", row.notes || "No base notes.")}
      ${helpDetails("0.35 bug details", row.bug_details || "No 0.35 bug adjustment for this row.")}
      ${helpDetails("epoch constants", `fixed_epoch_reward=${formatBaseUnitsAsGnk(row.fixed_epoch_reward)} GNK; total_epoch_weight=${row.total_epoch_weight}`)}
    </div>
  `);
}

function sumRows(rows, key) {
  return rows.reduce((sum, row) => sum + Number(row[key] || 0), 0);
}

function formatGnk(value) {
  return Number(value || 0).toFixed(9);
}

function formatCellValue(key, value) {
  if (value === null || value === undefined || value === "") return "";
  if (key === "source_state") {
    return {
      no_source: "no source",
      collapsed_to_zero: "zero",
      remaining_after_source: "remaining",
      source_exceeds_calculated: "source > calc",
    }[value] || String(value);
  }
  if (key === "match_status") {
    return {
      no_source: "",
      source_matches_baseline: "base",
      source_matches_bug_adjusted: "bug",
      source_differs: "diff",
    }[value] || String(value);
  }
  if (key.endsWith("_gnk")) {
    return Number(value || 0).toLocaleString("en-US", {
      maximumFractionDigits: 6,
    });
  }
  return String(value);
}

function sourceStateClass(row) {
  return {
    no_source: "no-source",
    collapsed_to_zero: "collapsed",
    remaining_after_source: "remaining",
    source_exceeds_calculated: "source-exceeds",
  }[row.source_state] || "";
}

function rewardDeltaClass(row) {
  const delta = Number(row.reward_delta_after_sources_base_units || 0);
  if (delta > 0) return "problem-delta";
  if (delta < 0) return "source-exceeds";
  return "collapsed";
}

function isEmptyNeutralRow(row) {
  return Number(row.reward_delta_after_sources_base_units || 0) === 0
    && Number(row.source_compensation_base_units || 0) === 0
    && row.source_state === "no_source";
}

function verdictClass(row) {
  const delta = Number(row.reward_delta_after_sources_base_units || 0);
  if (delta > 0) return "verdict-positive";
  if (delta < 0) return "verdict-negative";
  return "verdict-zero";
}

function statusLabel(value) {
  return {
    no_source: "no source",
    collapsed_to_zero: "zero",
    remaining_after_source: "remaining",
    source_exceeds_calculated: "source > calc",
  }[value] || value || "unknown";
}

function matchLabel(value) {
  return {
    no_source: "no source match",
    source_matches_baseline: "matches baseline",
    source_matches_bug_adjusted: "matches bug layer",
    source_matches_calculated_layers: "matches calculated layers",
    source_differs: "differs",
  }[value] || value || "unknown";
}

function section(title, content) {
  return `
    <section class="detail-section">
      <h3 class="detail-section-title">${escapeHtml(title)}</h3>
      ${content}
    </section>
  `;
}

function kv(label, value, className = "") {
  return `
    <div class="kv-item ${escapeAttribute(className)}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(formatOptional(value))}</strong>
    </div>
  `;
}

function pill(label, className = "") {
  return `<span class="pill ${escapeAttribute(className)}">${escapeHtml(label)}</span>`;
}

function textBlock(label, value) {
  if (!value) return "";
  return `
    <div class="text-block">
      <span>${escapeHtml(label)}</span>
      <p>${escapeHtml(value)}</p>
    </div>
  `;
}

function helpDetails(label, value) {
  return `
    <details class="help-details">
      <summary><span>?</span>${escapeHtml(label)}</summary>
      <p>${escapeHtml(value)}</p>
    </details>
  `;
}

function formatOptional(value, fallback = "0") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function formatGnkValue(value) {
  if (value === null || value === undefined || value === "") return "0.000000000";
  return formatGnk(value);
}

function formatBaseUnitsAsGnk(value) {
  return formatGnk(Number(value || 0) / 1e9);
}

function metric(label, value) {
  return `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`;
}

function detail(label, value) {
  return `<div class="detail-item"><span>${label}</span><strong>${escapeHtml(String(value))}</strong></div>`;
}

function sourceLink(source) {
  const label = escapeHtml(source.source || "source");
  if (!source.source_url) return label;
  return `<a href="${escapeAttribute(source.source_url)}" target="_blank" rel="noreferrer">${label}</a>`;
}

function escapeAttribute(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}
