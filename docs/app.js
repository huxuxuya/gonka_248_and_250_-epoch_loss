const state = {
  rawRows: [],
  summary: [],
  participants: [],
  filtered: [],
  epochs: [],
  showAllRows: false,
  showWeights: false,
  showRewards: true,
  showFullLoss: false,
  showBug: false,
  showSources: true,
  sourceNames: [],
  enabledSources: new Set(),
  audit: null,
};

const format = new Intl.NumberFormat("en-US", { maximumFractionDigits: 9 });

loadData().then(({ rows, summary }) => {
  state.rawRows = rows;
  state.summary = summary;
  state.epochs = [...new Set(rows.map((row) => row.epoch))].sort((a, b) => a - b);
  state.sourceNames = [...new Set(rows.flatMap((row) => (row.sources || []).map((source) => source.source).filter(Boolean)))].sort();
  state.enabledSources = new Set(state.sourceNames);
  state.participants = pivotRows(rows);
  state.audit = window.__GONKA_SHARD_AUDIT_DATA__ || null;
  hydrateFilters();
  hydrateAuditFilters();
  render();
  renderAudit();
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
document.getElementById("showFullLoss").addEventListener("change", (event) => {
  state.showFullLoss = event.target.checked;
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
document.getElementById("exportSources").addEventListener("click", showSourceExport);
document.getElementById("auditSearchInput").addEventListener("input", renderAudit);
document.getElementById("auditEpochFilter").addEventListener("change", renderAudit);
document.getElementById("auditNodeFilter").addEventListener("change", renderAudit);
document.getElementById("auditClassFilter").addEventListener("change", renderAudit);
document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
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

function hydrateAuditFilters() {
  if (!state.audit) return;
  const epochFilter = document.getElementById("auditEpochFilter");
  const nodeFilter = document.getElementById("auditNodeFilter");
  const classFilter = document.getElementById("auditClassFilter");
  for (const epoch of state.audit.epochs || []) {
    epochFilter.append(new Option(`Epoch ${epoch}`, String(epoch)));
  }
  for (const node of state.audit.nodes || []) {
    nodeFilter.append(new Option(shortNode(node), node));
  }
  const classes = [...new Set((state.audit.participant_rows || []).map((row) => row.classification).filter(Boolean))].sort();
  for (const classification of classes) {
    classFilter.append(new Option(classificationLabel(classification), classification));
  }
}

function switchView(view) {
  document.getElementById("compensationView").classList.toggle("hidden-view", view !== "compensation");
  document.getElementById("auditView").classList.toggle("hidden-view", view !== "audit");
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
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
  if (state.showFullLoss) {
    metrics.push(["full_lost_delta_after_sources_gnk", "Full loss Δ"]);
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
    const rows = epochs.map((epoch) => sourceAdjustedRow(participant.byEpoch.get(epoch))).filter(Boolean);
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
  renderSourceLegend();
  renderTable(epochs, activeMetrics());
}

function renderAudit() {
  if (!state.audit) {
    document.getElementById("auditMetrics").innerHTML = metric("Audit data", "not loaded");
    return;
  }
  renderAuditMetrics();
  renderAuditEpochSummary();
  renderAuditOutcomes();
  renderAuditDowntime();
  renderAuditExclusions();
  renderAuditAnomalies();
  renderAuditGaps();
  renderAuditRescales();
  renderAuditConsensus();
  renderAuditSignatures();
}

function auditFilteredRows(rows, options = {}) {
  const search = document.getElementById("auditSearchInput").value.trim().toLowerCase();
  const epoch = document.getElementById("auditEpochFilter").value;
  const node = document.getElementById("auditNodeFilter").value;
  const classification = document.getElementById("auditClassFilter").value;
  return rows.filter((row) => {
    if (epoch !== "all" && String(row.epoch) !== epoch) return false;
    if (node !== "all" && row.node !== node) return false;
    if (options.classification !== false && classification !== "all" && row.classification !== classification) return false;
    if (!search) return true;
    return Object.values(row).join(" ").toLowerCase().includes(search);
  });
}

function renderAuditMetrics() {
  const summary = state.audit.summary || {};
  const preserved = state.audit.preserved || {};
  const signatureTotals = summary.signature_totals || {};
  const performanceRows = (state.audit.participant_rows || []).filter((row) => row.has_performance_summary === "True");
  const downtimeRows = performanceRows.filter((row) => row.classification === "explained_by_downtime_test");
  const exclusionRows = performanceRows.filter((row) => String(row.classification || "").startsWith("explained_by_exclusion:"));
  const missingPerformance = (state.audit.participant_rows || []).filter((row) => row.classification === "missing_performance_summary");
  document.getElementById("auditMetrics").innerHTML = [
    metric("Run", state.audit.run_id || ""),
    metric("Preserved", `${preserved.ok || 0}/${preserved.files || 0}`),
    metric("Consensus", `${summary.consensus_ok || 0}/${summary.consensus_total || 0}`),
    metric("Signatures", `${signatureTotals.nonempty || 0}/${signatureTotals.signatures || 0}`),
    metric("Downtime", downtimeRows.length),
    metric("Exclusions", exclusionRows.length),
    metric("Gaps", summary.anomalies || 0),
    metric("Missing perf", missingPerformance.length),
    metric("Latest", Object.entries(state.audit.latest_by_node || {}).map(([node, epoch]) => `${shortNode(node)} ${epoch ?? "n/a"}`).join(" · ")),
  ].join("");
}

function renderAuditEpochSummary() {
  const sourceRows = auditFilteredRows(state.audit.participant_rows || [])
    .filter((row) => row.node && row.has_performance_summary === "True");
  const rowsByEpoch = new Map();
  for (const row of sourceRows) {
    const epoch = String(row.epoch);
    if (!rowsByEpoch.has(epoch)) {
      rowsByEpoch.set(epoch, {
        epoch,
        participants: 0,
        zero_reward: 0,
        downtime: 0,
        exclusions: 0,
        gaps: 0,
        missed: 0,
        total: 0,
        reward_gap_base_units: 0,
      });
    }
    const item = rowsByEpoch.get(epoch);
    item.participants += 1;
    item.zero_reward += Number(row.rewarded_coins || 0) === 0 ? 1 : 0;
    item.downtime += row.classification === "explained_by_downtime_test" ? 1 : 0;
    item.exclusions += String(row.classification || "").startsWith("explained_by_exclusion:") ? 1 : 0;
    item.gaps += row.classification === "settlement_anomaly" ? 1 : 0;
    item.missed += Number(row.missed_requests || 0);
    item.total += Number(row.total_requests || 0);
    item.reward_gap_base_units += Number(row.reward_gap_base_units || 0);
  }
  const rows = [...rowsByEpoch.values()]
    .map((row) => ({ ...row, miss_rate_summary: { missed: row.missed, total: row.total } }))
    .sort((a, b) => Number(b.epoch) - Number(a.epoch));
  document.getElementById("auditEpochSummaryCount").textContent = `${rows.length} epochs`;
  renderSimpleTable("auditEpochSummaryTable", rows, [
    ["epoch", "Epoch"],
    ["participants", "Participants"],
    ["zero_reward", "Zero reward"],
    ["downtime", "Downtime"],
    ["exclusions", "Exclusions"],
    ["gaps", "Gaps"],
    ["miss_rate_summary", "Miss rate"],
    ["reward_gap_base_units", "Total gap"],
  ], (row) => {
    document.getElementById("auditEpochFilter").value = String(row.epoch);
    renderAudit();
  });
}

function renderAuditOutcomes() {
  const rows = auditFilteredRows(state.audit.participant_rows || [])
    .filter((row) => row.has_performance_summary === "True")
    .filter((row) => row.classification && row.classification !== "no_reward_gap")
    .sort((a, b) =>
      Number(b.epoch) - Number(a.epoch)
      || outcomeSeverity(b.classification) - outcomeSeverity(a.classification)
      || Number(b.missed_requests || 0) - Number(a.missed_requests || 0)
      || a.address.localeCompare(b.address)
    );
  document.getElementById("auditOutcomeCount").textContent = `${rows.length} rows`;
  renderSimpleTable("auditOutcomeTable", rows, [
    ["epoch", "Epoch"],
    ["address", "Address"],
    ["node", "Node"],
    ["classification", "Classification"],
    ["signed_models", "Models"],
    ["inference_count", "Inf"],
    ["missed_requests", "Miss"],
    ["miss_rate", "Miss rate"],
    ["p_value", "p-value"],
    ["rewarded_coins", "Rewarded"],
    ["reward_gap_base_units", "Gap"],
  ], showAuditDetails);
}

function renderAuditDowntime() {
  const rows = auditFilteredRows(state.audit.participant_rows || [])
    .filter((row) => row.has_performance_summary === "True")
    .filter((row) => row.classification === "explained_by_downtime_test")
    .map((row) => ({
      ...row,
      success_total: `${row.inference_count}/${row.total_requests}`,
      miss_total: `${row.missed_requests}/${row.total_requests}`,
      downtime_reason: downtimeReason(row),
    }))
    .sort((a, b) =>
      Number(b.epoch) - Number(a.epoch)
      || Number(b.missed_requests || 0) - Number(a.missed_requests || 0)
      || Number(b.miss_rate || 0) - Number(a.miss_rate || 0)
      || a.address.localeCompare(b.address)
    );
  document.getElementById("auditDowntimeCount").textContent = `${rows.length} rows`;
  renderSimpleTable("auditDowntimeTable", rows, [
    ["epoch", "Epoch"],
    ["address", "Address"],
    ["node", "Node"],
    ["signed_models", "Models"],
    ["success_total", "Success/total"],
    ["miss_total", "Miss/total"],
    ["miss_rate", "Miss rate"],
    ["p_value", "p-value"],
    ["passes_downtime_test", "Passed"],
    ["rewarded_coins", "Rewarded"],
    ["downtime_reason", "Why downtime"],
  ], showAuditDetails);
}

function renderAuditExclusions() {
  const rows = auditFilteredRows(state.audit.participant_rows || [])
    .filter((row) => row.has_performance_summary === "True")
    .filter((row) => String(row.classification || "").startsWith("explained_by_exclusion:"))
    .map((row) => ({
      ...row,
      exclusion_label: row.exclusion_reason || row.classification.replace("explained_by_exclusion:", ""),
      work_summary: `${row.inference_count} inf / ${row.missed_requests} miss`,
      exclusion_explanation: exclusionExplanation(row),
    }))
    .sort((a, b) =>
      Number(b.epoch) - Number(a.epoch)
      || String(a.exclusion_label).localeCompare(String(b.exclusion_label))
      || Number(b.reward_gap_base_units || 0) - Number(a.reward_gap_base_units || 0)
      || a.address.localeCompare(b.address)
    );
  document.getElementById("auditExclusionCount").textContent = `${rows.length} rows`;
  renderSimpleTable("auditExclusionTable", rows, [
    ["epoch", "Epoch"],
    ["address", "Address"],
    ["node", "Node"],
    ["exclusion_label", "Reason"],
    ["exclusion_block_height", "Block"],
    ["signed_models", "Models"],
    ["work_summary", "Work"],
    ["miss_rate", "Miss rate"],
    ["rewarded_coins", "Rewarded"],
    ["reward_gap_base_units", "Gap"],
    ["exclusion_explanation", "Why excluded"],
  ], showAuditDetails);
}

function downtimeReason(row) {
  const misses = Number(row.missed_requests || 0);
  const total = Number(row.total_requests || 0);
  const pValue = Number(row.p_value || 0);
  const missRate = total ? misses / total : 0;
  return `miss ${(missRate * 100).toFixed(2)}%; p=${pValue.toExponential(2)} < 0.05`;
}

function exclusionExplanation(row) {
  const reason = row.exclusion_reason || row.classification.replace("explained_by_exclusion:", "");
  if (reason === "failed_confirmation_poc") {
    return `failed confirmation PoC at block ${row.exclusion_block_height || "n/a"}`;
  }
  if (reason === "statistical_invalidations") {
    return `statistical invalidations at block ${row.exclusion_block_height || "n/a"}`;
  }
  return `${reason || "excluded"} at block ${row.exclusion_block_height || "n/a"}`;
}

function classificationLabel(classification) {
  if (classification === "no_reward_gap") return "OK / no gap";
  if (classification === "explained_by_downtime_test") return "Downtime test failed";
  if (classification === "settlement_anomaly") return "Unexplained settlement gap";
  if (classification === "missing_performance_summary") return "Missing performance summary";
  if (String(classification || "").startsWith("explained_by_exclusion:")) {
    return `Excluded: ${classification.replace("explained_by_exclusion:", "")}`;
  }
  return classification || "";
}

function outcomeSeverity(classification) {
  if (classification === "explained_by_downtime_test") return 4;
  if (String(classification || "").startsWith("explained_by_exclusion:")) return 3;
  if (classification === "settlement_anomaly") return 2;
  return 1;
}

function renderAuditAnomalies() {
  const rows = auditFilteredRows(state.audit.anomalies || []);
  const matrix = buildAuditAnomalyMatrix(rows);
  document.getElementById("auditAnomalyCount").textContent = `${rows.length} cells · ${matrix.length} addresses`;
  renderAuditAnomalyMatrix(matrix);
}

function renderAuditGaps() {
  const rows = auditFilteredRows(state.audit.anomalies || [])
    .map((row) => ({
      ...row,
      gap_formula: gapFormula(row),
      gap_reason: gapReason(row),
      proof_summary: proofSummary(row),
    }))
    .sort((a, b) =>
      Number(b.reward_gap_base_units || 0) - Number(a.reward_gap_base_units || 0)
      || Number(b.epoch) - Number(a.epoch)
      || a.address.localeCompare(b.address)
    );
  document.getElementById("auditGapCount").textContent = `${rows.length} rows`;
  renderSimpleTable("auditGapTable", rows, [
    ["epoch", "Epoch"],
    ["address", "Address"],
    ["node", "Node"],
    ["proof_summary", "Proof"],
    ["expected_weight", "Expected weight"],
    ["expected_reward_base_units", "Expected"],
    ["rewarded_coins", "Rewarded"],
    ["reward_gap_base_units", "Gap"],
    ["miss_rate", "Miss rate"],
    ["passes_downtime_test", "Downtime passed"],
    ["exclusion_reason", "Exclusion"],
    ["gap_formula", "Formula"],
    ["gap_reason", "Why gap"],
  ], showAuditDetails);
}

function renderAuditRescales() {
  const rows = auditFilteredRows(state.audit.participant_rows || [], { classification: false })
    .filter((row) => row.expected_weight_reason === "chain_rescaled_confirmation_by_parent_weight")
    .map((row) => ({
      ...row,
      old_expected_weight: row.confirmation_weight,
      rescale: `${row.confirmation_weight} * ${row.weight} / ${row.model_coefficient_weight}`,
      rescaled_delta: Number(row.confirmation_weight || 0) - Number(row.expected_weight || 0),
      reward_match: Number(row.reward_gap_base_units || 0) === 0 ? "matches chain" : "still differs",
    }))
    .sort((a, b) =>
      Number(b.rescaled_delta || 0) - Number(a.rescaled_delta || 0)
      || Number(b.epoch) - Number(a.epoch)
      || a.address.localeCompare(b.address)
    );
  document.getElementById("auditRescaleCount").textContent = `${rows.length} rows`;
  renderSimpleTable("auditRescaleTable", rows, [
    ["epoch", "Epoch"],
    ["address", "Address"],
    ["node", "Node"],
    ["validation_models", "Models"],
    ["weight", "Parent weight"],
    ["confirmation_weight", "Old expected"],
    ["model_raw_weight", "Raw MLNode weight"],
    ["model_coefficient_weight", "Coeff weight"],
    ["expected_weight", "Chain expected"],
    ["rescaled_delta", "Weight delta"],
    ["rewarded_coins", "Rewarded"],
    ["expected_reward_base_units", "Expected"],
    ["reward_match", "Result"],
    ["rescale", "Formula"],
  ], showAuditDetails);
}

function buildAuditAnomalyMatrix(rows) {
  const byAddress = new Map();
  for (const row of rows) {
    if (!byAddress.has(row.address)) {
      byAddress.set(row.address, {
        address: row.address,
        node: row.node,
        totalGap: 0,
        epochs: new Map(),
        models: new Set(),
      });
    }
    const item = byAddress.get(row.address);
    item.totalGap += Number(row.reward_gap_base_units || 0);
    item.epochs.set(String(row.epoch), row);
    for (const model of String(row.signed_models || "").split(";").filter(Boolean)) {
      item.models.add(model);
    }
  }
  return [...byAddress.values()].sort((a, b) => b.totalGap - a.totalGap || a.address.localeCompare(b.address));
}

function gapFormula(row) {
  return `max(0, expected ${formatBaseUnitsAsGnk(row.expected_reward_base_units)} - rewarded ${formatBaseUnitsAsGnk(row.rewarded_coins)})`;
}

function gapReason(row) {
  if (row.classification !== "settlement_anomaly") return classificationLabel(row.classification);
  return "expected reward is higher than rewarded_coins, with proof present and no downtime/exclusion explanation";
}

function proofSummary(row) {
  const proof = [];
  if (row.signed_base === "True" || row.signed_base === true) proof.push("base");
  const models = shortModelList(String(row.signed_models || "").split(";").filter(Boolean));
  if (models) proof.push(models);
  return proof.join(" + ") || "none";
}

function renderAuditAnomalyMatrix(matrix) {
  const epochs = (state.audit.epochs || []).map(String);
  const table = document.getElementById("auditAnomalyTable");
  table.querySelector("thead").innerHTML = `
    <tr>
      <th class="sticky-col">Address</th>
      <th>Node</th>
      <th>Models</th>
      <th>Total gap</th>
      ${epochs.map((epoch) => `<th>Epoch ${escapeHtml(epoch)}</th>`).join("")}
    </tr>
  `;
  table.querySelector("tbody").innerHTML = matrix.map((item, index) => `
    <tr>
      <td class="sticky-col"><button class="link" data-audit-address="${index}">${escapeHtml(item.address)}</button></td>
      <td>${escapeHtml(shortNode(item.node))}</td>
      <td title="${escapeAttribute([...item.models].join("; "))}">${escapeHtml(shortModelList([...item.models]))}</td>
      <td class="problem-delta">${escapeHtml(formatBaseUnitsAsGnk(item.totalGap))} GNK</td>
      ${epochs.map((epoch) => renderAuditEpochCell(item.epochs.get(epoch), index, epoch)).join("")}
    </tr>
  `).join("");
  table.querySelectorAll("[data-audit-cell]").forEach((cell) => {
    cell.addEventListener("click", () => {
      const [rowIndex, epoch] = cell.dataset.auditCell.split("|");
      showAuditDetails(matrix[Number(rowIndex)].epochs.get(epoch));
    });
  });
  table.querySelectorAll("[data-audit-address]").forEach((button) => {
    button.addEventListener("click", () => showAuditAddressDetails(matrix[Number(button.dataset.auditAddress)]));
  });
}

function renderAuditEpochCell(row, index, epoch) {
  if (!row) return "<td></td>";
  const gap = `${formatBaseUnitsAsGnk(row.reward_gap_base_units)} GNK`;
  const missed = `${row.missed_requests}/${row.total_requests}`;
  return `
    <td class="audit-anomaly clickable" data-audit-cell="${index}|${escapeAttribute(epoch)}" title="${escapeAttribute(`${gap}; miss ${missed}; p=${row.p_value}`)}">
      <strong>${escapeHtml(gap)}</strong>
      <em>miss ${escapeHtml(row.miss_rate)}</em>
    </td>
  `;
}

function showAuditAddressDetails(item) {
  const rows = [...item.epochs.values()].sort((a, b) => Number(a.epoch) - Number(b.epoch));
  document.getElementById("detailContent").innerHTML = `
    <h2>${escapeHtml(item.address)}</h2>
    <section class="verdict-card verdict-positive">
      <div>
        <span class="section-kicker">Audit anomalies</span>
        <strong>${formatBaseUnitsAsGnk(item.totalGap)} GNK</strong>
        <em>Total visible reward gap</em>
      </div>
      <div class="verdict-meta">
        ${pill(`${rows.length} epochs`, "remaining")}
        ${pill(shortNode(item.node), "neutral-pill")}
      </div>
    </section>
    ${section("Epochs", `
      <div class="detail-grid">
        ${rows.map((row) => `
          <button class="detail-item audit-detail-button" type="button" data-audit-detail-epoch="${escapeAttribute(row.epoch)}">
            <span>Epoch ${escapeHtml(row.epoch)}</span>
            <strong>${formatBaseUnitsAsGnk(row.reward_gap_base_units)} GNK</strong>
          </button>
        `).join("")}
      </div>
    `)}
  `;
  document.getElementById("detailDialog").showModal();
  document.querySelectorAll("[data-audit-detail-epoch]").forEach((button) => {
    button.addEventListener("click", () => {
      showAuditDetails(item.epochs.get(button.dataset.auditDetailEpoch));
    });
  });
}

function renderAuditConsensus() {
  const rows = auditFilteredRows(state.audit.consensus || [], { classification: false });
  renderSimpleTable("auditConsensusTable", rows, [
    ["epoch", "Epoch"],
    ["label", "Endpoint"],
    ["model_id", "Model"],
    ["ok_count", "OK"],
    ["hash_count", "Hashes"],
    ["consensus", "Consensus"],
  ]);
}

function renderAuditSignatures() {
  const rows = auditFilteredRows(state.audit.signatures || [], { classification: false });
  renderSimpleTable("auditSignatureTable", rows, [
    ["epoch", "Epoch"],
    ["node", "Node"],
    ["model_id", "Model"],
    ["signature_count", "Sigs"],
    ["nonempty_signature_count", "Nonempty"],
    ["validation_weights_count", "Weights"],
    ["number_of_requests", "Requests"],
  ]);
}

function renderSimpleTable(tableId, rows, columns, onClick) {
  const table = document.getElementById(tableId);
  table.querySelector("thead").innerHTML = `
    <tr>${columns.map(([, label]) => `<th>${escapeHtml(label)}</th>`).join("")}</tr>
  `;
  table.querySelector("tbody").innerHTML = rows.map((row, index) => `
    <tr class="${auditRowClass(row)}" ${onClick ? `data-audit-row="${index}"` : ""}>
      ${columns.map(([key]) => `<td title="${escapeAttribute(formatAuditCell(key, row[key]))}">${escapeHtml(formatAuditCell(key, row[key]))}</td>`).join("")}
    </tr>
  `).join("");
  if (onClick) {
    table.querySelectorAll("[data-audit-row]").forEach((rowElement) => {
      rowElement.addEventListener("click", () => onClick(rows[Number(rowElement.dataset.auditRow)]));
    });
  }
}

function showAuditDetails(row) {
  document.getElementById("detailContent").innerHTML = `
    <h2>${escapeHtml(row.address)}</h2>
    <section class="verdict-card verdict-positive">
      <div>
        <span class="section-kicker">Epoch ${escapeHtml(row.epoch)}</span>
        <strong>${formatBaseUnitsAsGnk(row.reward_gap_base_units)} GNK</strong>
        <em>Reward gap with signed proof data</em>
      </div>
      <div class="verdict-meta">
        ${pill(row.classification || "unknown", "remaining")}
        ${pill(shortNode(row.node), "neutral-pill")}
      </div>
    </section>
    ${section("Proof", `
      <div class="kv-grid">
        ${kv("Signed base", row.signed_base)}
        ${kv("Signed models", row.signed_models || "none")}
        ${kv("Validation models", row.validation_models || "none")}
        ${kv("Weight", row.weight)}
        ${kv("Confirmation weight", row.confirmation_weight)}
        ${kv("Subgroup voting power", row.subgroup_voting_power)}
        ${kv("Raw MLNode weight", row.model_raw_weight || "n/a")}
        ${kv("Coeff weight", row.model_coefficient_weight || "n/a")}
        ${kv("Expected weight", row.expected_weight || "n/a")}
        ${kv("Expected rule", row.expected_weight_reason || "n/a")}
      </div>
    `)}
    ${section("Why it is listed", `
      <div class="kv-grid">
        ${kv("Proof exists", row.signed_base === "True" || row.signed_base === true || row.signed_models ? "yes" : "no")}
        ${kv("Excluded", row.exclusion_reason || "no")}
        ${kv("Downtime passed", row.passes_downtime_test)}
        ${kv("Reason", row.expected_weight_reason === "chain_rescaled_confirmation_by_parent_weight" ? "confirmation was rescaled to parent weight scale" : "expected reward is higher than rewarded_coins")}
        ${kv("Interpretation", Number(row.reward_gap_base_units || 0) === 0 ? "matches chain-style expected reward" : "technical mismatch, needs root-cause check")}
        ${kv("Not caused by", "dashboard claim status alone")}
      </div>
    `)}
    ${section("Performance", `
      <div class="kv-grid">
        ${kv("Inferences", row.inference_count)}
        ${kv("Missed", row.missed_requests)}
        ${kv("Miss rate", row.miss_rate)}
        ${kv("p-value", row.p_value)}
        ${kv("Downtime test", row.passes_downtime_test)}
        ${kv("Claimed", row.claimed)}
      </div>
    `)}
    ${section("Reward", `
      <div class="kv-grid">
        ${kv("Expected", `${formatBaseUnitsAsGnk(row.expected_reward_base_units)} GNK`)}
        ${kv("Rewarded", `${formatBaseUnitsAsGnk(row.rewarded_coins)} GNK`)}
        ${kv("Gap", `${formatBaseUnitsAsGnk(row.reward_gap_base_units)} GNK`, "problem-delta")}
        ${kv("Earned", `${formatBaseUnitsAsGnk(row.earned_coins)} GNK`)}
        ${kv("Burned", `${formatBaseUnitsAsGnk(row.burned_coins)} GNK`)}
        ${kv("Exclusion", row.exclusion_reason || "none")}
      </div>
    `)}
  `;
  document.getElementById("detailDialog").showModal();
}

function renderTotals(epochs) {
  const rows = state.filtered.flatMap((participant) => epochs.map((epoch) => sourceAdjustedRow(participant.byEpoch.get(epoch))).filter(Boolean));
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
    const rows = state.filtered.map((participant) => sourceAdjustedRow(participant.byEpoch.get(epoch))).filter(Boolean);
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
    const rows = epochs.map((epoch) => sourceAdjustedRow(participant.byEpoch.get(epoch))).filter(Boolean);
    const hasLoss = rows.some((row) => row.has_loss);
    return `
      <tr class="${hasLoss ? "loss-row" : ""}">
        <td class="sticky-col"><button class="link" data-participant-index="${index}">${escapeHtml(participant.address)}</button></td>
        <td class="reason-cell">${escapeHtml([...participant.reasons].filter(Boolean).join(", "))}</td>
        ${epochs.flatMap((epoch) => metrics.map(([key]) => renderEpochCell(sourceAdjustedRow(participant.byEpoch.get(epoch)), key))).join("")}
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
      showDetails(sourceAdjustedRow(participant.byEpoch.get(Number(epoch))));
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
  if (["reward_delta_after_sources_gnk", "full_lost_delta_after_sources_gnk"].includes(key) && !emptyNeutral) classes.push(rewardDeltaClass(row));
  if (key === "source_weight_delta" && !emptyNeutral) classes.push(sourceStateClass(row));
  if (key === "source_state" && !emptyNeutral) classes.push(sourceStateClass(row));
  const collapsedSourceClass = collapsedSourceColorClass(row);
  if (collapsedSourceClass && ["reward_delta_after_sources_gnk", "full_lost_delta_after_sources_gnk", "source_weight_delta", "source_state"].includes(key)) {
    classes.push(collapsedSourceClass);
  }
  const sourceStripeStyleValue = sourceStripeStyle(row, key);
  if (key.startsWith("bug_") && row.bug_adjusted_weight !== null) classes.push("bug");
  if (key.startsWith("source_") && Number(row.source_compensation_base_units || 0) > 0) classes.push("source");
  if (key.startsWith("remaining_") && Number(row.remaining_after_sources_base_units || 0) > 0) classes.push("remaining");
  if (key === "source_excess_gnk" && Number(row.source_excess_base_units || 0) > 0) classes.push("diff");
  if (key === "match_status") {
    if (row.match_status.includes("matches")) classes.push("match");
    if (row.match_status === "source_differs") classes.push("diff");
  }
  if (row.has_loss) classes.push("clickable");
  const styleAttribute = sourceStripeStyleValue ? ` style="${escapeAttribute(sourceStripeStyleValue)}"` : "";
  return `<td class="${classes.join(" ")}" data-row-key="${escapeHtml(row.address)}|${row.epoch}" title="${escapeHtml(String(value))}"${styleAttribute}>${escapeHtml(displayValue)}</td>`;
}

function renderSourceLegend() {
  const items = [
    ["source-grc-e247-preserver-audit", "GRC-e247-preserver-audit", "source closed calculated loss"],
    ["source-grc-e254-api-issue", "GRC-e254-api-issue", "source closed calculated loss"],
    ["source-consensus-failure-restriction", "consensus_failure_restriction", "source closed calculated loss"],
    ["source-segovchik-grc-case-1", "SegovChik-grc-case-1", "source closed calculated loss"],
    ["source-epoch-248-compensation-package", "epoch-248-compensation-package", "README payout source"],
    ["source-epoch-250-compensation-package", "epoch-250-compensation-package", "README payout source"],
    ["source-grc-e247-preserver-audit-remaining", "grc-e247-preserver-audit-remaining", "remaining GRC-e247 delta payout source"],
    ["source-mixed", "multiple sources", "closed by more than one source"],
  ];
  const visibleItems = items.filter(([, source]) => source === "multiple sources" || state.sourceNames.includes(source));
  document.getElementById("sourceLegend").innerHTML = [
    ...visibleItems.map(([className, label, note]) => {
      const isToggleable = label !== "multiple sources";
      const checked = !isToggleable || state.enabledSources.has(label);
      const disabled = !isToggleable ? "disabled" : "";
      const mutedClass = isToggleable && !checked ? "source-disabled" : "";
      return `
      <div class="legend-item ${className}">
        <span></span>
        <label>
          <input type="checkbox" data-source-toggle="${escapeAttribute(label)}" ${checked ? "checked" : ""} ${disabled}>
          <strong class="${mutedClass}">${escapeHtml(label)}</strong>
        </label>
        <em>${escapeHtml(note)}</em>
      </div>
    `;
    }),
    `<div class="legend-item legend-remaining"><span></span><strong>remaining</strong><em>calculated loss is still not covered by sources</em></div>`,
    `<div class="legend-item legend-problem"><span></span><strong>problem delta</strong><em>calculated loss is non-zero after source layer</em></div>`,
  ].join("");

  document.querySelectorAll("[data-source-toggle]").forEach((input) => {
    input.addEventListener("change", (event) => {
      const source = event.target.dataset.sourceToggle;
      if (event.target.checked) {
        state.enabledSources.add(source);
      } else {
        state.enabledSources.delete(source);
      }
      render();
    });
  });
}

function formatEmptyNeutralCell(key) {
  if (["reward_delta_after_sources_gnk", "full_lost_delta_after_sources_gnk", "source_weight_delta", "source_state"].includes(key)) {
    return "";
  }
  return formatCellValue(key, "");
}

function showParticipantDetails(participant, epochs) {
  const rows = epochs.map((epoch) => sourceAdjustedRow(participant.byEpoch.get(epoch))).filter(Boolean);
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
      ${kv("Full loss Δ", `${formatGnkValue(row.full_lost_delta_after_sources_gnk)} GNK`, rewardDeltaClass(row))}
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
      ${kv("0.35 base weight", row.bug_base_weight ?? "0")}
      ${kv("0.35 chain bug weight", row.bug_chain_weight ?? "0")}
      ${kv("0.35 weight delta", row.bug_weight_delta ?? "0")}
      ${kv("Full loss weight", row.full_loss_weight ?? row.effective_weight)}
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
      ${kv("Full loss reward", `${formatGnkValue(row.full_lost_reward_gnk)} GNK`)}
      ${kv("Final Reward Δ", `${formatGnkValue(row.reward_delta_after_sources_gnk)} GNK`, rewardDeltaClass(row))}
      ${kv("Full loss Δ", `${formatGnkValue(row.full_lost_delta_after_sources_gnk)} GNK`, rewardDeltaClass(row))}
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

function sourceAdjustedRow(row) {
  if (!row) return row;
  const sources = (row.sources || []).filter((source) => state.enabledSources.has(source.source));
  const sourceTotal = sources.reduce((sum, source) => sum + Number(source.source_compensation_base_units || 0), 0);
  const sourceWeight = sources.reduce((sum, source) => sum + Number(source.source_weight || source.weight || 0), 0);
  const comparableCalculated = comparableCalculatedForActiveSources(row, sources, sourceTotal);
  const tolerance = sourceMatchTolerance(sources);
  const rawDelta = Number(row.calculated_layers_base_units || 0) - sourceTotal;
  const rewardDelta = normalizeTinyDelta(rawDelta, tolerance);
  const fullLossRawDelta = Number(row.full_lost_reward_base_units || row.calculated_layers_base_units || 0)
    - Number(row.actual_reward_base_units || 0)
    - sourceTotal;
  const fullLossDelta = normalizeTinyDelta(fullLossRawDelta, tolerance);
  const remaining = Math.max(0, rewardDelta);
  const sourceExcess = Math.max(0, -rewardDelta);

  return {
    ...row,
    sources,
    source_weight: sourceWeight || null,
    source_weight_delta: sourceWeight ? Number(row.weight || 0) - sourceWeight : null,
    source_comparable_calculated_base_units: comparableCalculated,
    source_comparable_calculated_gnk: sources.length ? formatBaseUnitsAsGnk(comparableCalculated) : "",
    source_compensation_base_units: sourceTotal,
    source_compensation_gnk: sourceTotal ? formatBaseUnitsAsGnk(sourceTotal) : "",
    reward_delta_after_sources_base_units: rewardDelta,
    reward_delta_after_sources_gnk: formatBaseUnitsAsGnk(rewardDelta),
    full_lost_delta_after_sources_base_units: fullLossDelta,
    full_lost_delta_after_sources_gnk: formatBaseUnitsAsGnk(fullLossDelta),
    remaining_after_sources_base_units: remaining,
    remaining_after_sources_gnk: remaining ? formatBaseUnitsAsGnk(remaining) : "",
    source_excess_base_units: sourceExcess,
    source_excess_gnk: sourceExcess ? formatBaseUnitsAsGnk(sourceExcess) : "",
    source_state: classifyActiveSourceState(Number(row.calculated_layers_base_units || 0), sourceTotal, sources.length > 0, tolerance),
    match_status: activeMatchStatus(row, sourceTotal, comparableCalculated, tolerance),
  };
}

function comparableCalculatedForActiveSources(row, sources, sourceTotal) {
  if (!sources.length) return Number(row.compensation_base_units || 0);
  if (sources.some((source) => isFullLayerSource(source.source))) {
    return Number(row.calculated_layers_base_units || 0);
  }
  const bugSourceTotal = sources
    .filter((source) => source.source === "GRC-e247-preserver-audit")
    .reduce((sum, source) => sum + Number(source.source_compensation_base_units || 0), 0);
  const hasNonBugSource = sources.some((source) => source.source !== "GRC-e247-preserver-audit");
  let total = 0;
  if (hasNonBugSource) total += Number(row.compensation_base_units || 0);
  if (bugSourceTotal) total += Number(row.bug_compensation_base_units || 0);
  return total || (sourceTotal ? Number(row.compensation_base_units || 0) : 0);
}

function sourceMatchTolerance(sources) {
  return Math.max(2400, ...sources.map((source) => Number(source.source_match_tolerance_base_units || 0)));
}

function normalizeTinyDelta(value, tolerance) {
  return Math.abs(value) <= tolerance ? 0 : value;
}

function classifyActiveSourceState(calculated, sourceTotal, hasSource, tolerance) {
  if (!hasSource) return "no_source";
  if (Math.abs(calculated - sourceTotal) <= tolerance) return "collapsed_to_zero";
  if (calculated > sourceTotal) return "remaining_after_source";
  return "source_exceeds_calculated";
}

function activeMatchStatus(row, sourceTotal, comparableCalculated, tolerance) {
  if (sourceTotal <= 0) return "no_source";
  if (Math.abs(sourceTotal - comparableCalculated) <= tolerance) return "source_matches_calculated_layers";
  if (Math.abs(sourceTotal - Number(row.compensation_base_units || 0)) <= tolerance) return "source_matches_baseline";
  if (row.bug_compensation_base_units !== null && Math.abs(sourceTotal - Number(row.bug_compensation_base_units || 0)) <= tolerance) {
    return "source_matches_bug_adjusted";
  }
  return "source_differs";
}

function showSourceExport() {
  const rows = [];
  for (const row of state.rawRows) {
    for (const source of row.sources || []) {
      if (!state.enabledSources.has(source.source)) continue;
      const baseUnits = Number(source.source_compensation_base_units || 0);
      if (baseUnits <= 0) continue;
      rows.push({
        epoch: row.epoch,
        address: row.address,
        source: source.source,
        amount_ngnk: baseUnits,
        amount_gnk: formatBaseUnitsAsGnk(baseUnits),
      });
    }
  }
  rows.sort((a, b) => a.epoch - b.epoch || a.address.localeCompare(b.address) || a.source.localeCompare(b.source));

  const csvRows = [
    ["epoch", "address", "source", "amount_ngnk", "amount_gnk"],
    ...rows.map((row) => [row.epoch, row.address, row.source, row.amount_ngnk, row.amount_gnk]),
  ];
  document.getElementById("exportCsv").value = csvRows.map((row) => row.map(csvCell).join(",")).join("\n");
  document.getElementById("exportDialog").showModal();
}

function csvCell(value) {
  const text = String(value ?? "");
  if (!/[",\n]/.test(text)) return text;
  return `"${text.replace(/"/g, '""')}"`;
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

function formatAuditCell(key, value) {
  if (value === null || value === undefined || value === "") return "";
  if (key === "node") return shortNode(value);
  if (key === "classification") return classificationLabel(value);
  if (key === "signed_models") return shortModelList(String(value).split(";").filter(Boolean));
  if (key === "miss_rate_summary") {
    const rate = value.total ? value.missed / value.total : 0;
    return `${(rate * 100).toFixed(2)}% (${value.missed}/${value.total})`;
  }
  if (key === "miss_rate") return `${(Number(value || 0) * 100).toFixed(2)}%`;
  if (key === "p_value") return Number(value || 0).toExponential(3);
  if (["rewarded_coins", "expected_reward_base_units", "reward_gap_base_units"].includes(key)) {
    return `${formatBaseUnitsAsGnk(value)} GNK`;
  }
  if (key === "model_id" && !value) return "base";
  if (String(value).length > 64) return `${String(value).slice(0, 61)}...`;
  return String(value);
}

function auditRowClass(row) {
  if (row.classification === "settlement_anomaly") return "audit-anomaly";
  if (row.classification === "explained_by_downtime_test") return "audit-warning";
  if (String(row.classification || "").startsWith("explained_by_exclusion:")) return "audit-warning";
  if (row.classification === "missing_performance_summary") return "audit-warning";
  if (row.consensus === "False") return "audit-warning";
  if (row.consensus === "True") return "audit-ok";
  return "";
}

function shortNode(value) {
  return String(value || "")
    .replace("http://", "")
    .replace("https://", "")
    .replace(":8000", "");
}

function shortModelList(models) {
  if (!models.length) return "";
  return models.map((model) => model.split("/").pop().replace("-Instruct-2507-FP8", "")).join(", ");
}

function sourceStateClass(row) {
  return {
    no_source: "no-source",
    collapsed_to_zero: "collapsed",
    remaining_after_source: "remaining",
    source_exceeds_calculated: "source-exceeds",
  }[row.source_state] || "";
}

function collapsedSourceColorClass(row) {
  if (row.source_state !== "collapsed_to_zero") return "";
  if (Number(row.source_compensation_base_units || 0) <= 0) return "";
  const sourceNames = [...new Set((row.sources || []).map((source) => source.source).filter(Boolean))];
  if (sourceNames.length > 1) return "source-mixed";
  return sourceColorClass(sourceNames[0]);
}

function sourceStripeStyle(row, key) {
  if (!["reward_delta_after_sources_gnk", "full_lost_delta_after_sources_gnk", "source_weight_delta", "source_state"].includes(key)) return "";
  if (row.source_state !== "collapsed_to_zero") return "";
  if (Number(row.source_compensation_base_units || 0) <= 0) return "";
  const colors = [...new Set((row.sources || []).map((source) => sourceColorValue(source.source)).filter(Boolean))];
  if (colors.length < 2) return "";
  const step = 100 / colors.length;
  const stops = colors.flatMap((color, index) => {
    const start = (index * step).toFixed(2);
    const end = ((index + 1) * step).toFixed(2);
    return [`${color} ${start}%`, `${color} ${end}%`];
  });
  return `background: linear-gradient(135deg, ${stops.join(", ")}) !important`;
}

function sourceColorClass(sourceName) {
  return {
    "GRC-e247-preserver-audit": "source-grc-e247-preserver-audit",
    "GRC-e254-api-issue": "source-grc-e254-api-issue",
    "consensus_failure_restriction": "source-consensus-failure-restriction",
    "SegovChik-grc-case-1": "source-segovchik-grc-case-1",
    "epoch-248-compensation-package": "source-epoch-248-compensation-package",
    "epoch-250-compensation-package": "source-epoch-250-compensation-package",
    "grc-e247-preserver-audit-remaining": "source-grc-e247-preserver-audit-remaining",
  }[sourceName] || "";
}

function sourceColorValue(sourceName) {
  return {
    "GRC-e247-preserver-audit": "#d8efe1",
    "GRC-e254-api-issue": "#d9eafb",
    "consensus_failure_restriction": "#efe4ff",
    "SegovChik-grc-case-1": "#ffe8c7",
    "epoch-248-compensation-package": "#cfeeea",
    "epoch-250-compensation-package": "#f4dfc8",
    "grc-e247-preserver-audit-remaining": "#b7e3ef",
  }[sourceName] || "";
}

function isFullLayerSource(sourceName) {
  return sourceName === "epoch-248-compensation-package" || sourceName === "epoch-250-compensation-package" || sourceName === "grc-e247-preserver-audit-remaining";
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
